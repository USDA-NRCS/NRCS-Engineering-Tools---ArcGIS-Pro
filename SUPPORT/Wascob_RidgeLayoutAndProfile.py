## wascobridgeStations.py
##
## Created by Matt Patton, USDA NRCS, 2016
## Revised by Chris Morse, USDA NRCS, 2020
##
## Creates points at user specified interval along digitized or provided lines,
## Derives stationing distances and XYZ values, providing Z values in feet,
## as well as interpolating the line(s) to 3d using the appropriate Zfactor.

# ==========================================================================================
# Updated  7/2/2020 - Adolfo Diaz
#
# - This tool is almost identical to the Tile Layout and Profile tool!
# - Updated and Tested for ArcGIS Pro 2.4.2 and python 3.6
# - Combined all cursors into one.
# - All describe functions use the arcpy.da.Describe functionality.
# - All field calculation expressions are in PYTHON3 format.
# - All cursors were updated to arcpy.da
# - Updated AddMsgAndPrint to remove ArcGIS 10 boolean and gp function
# - Updated print_exception function.  Traceback functions slightly changed for Python 3.6.
# - Added parallel processing factor environment
# - swithced from exit() to exit()
# - wrapped the code that writes to text files in a try-except clause b/c if there is an
#   an error prior to establishing the log file than the error never gets reported.
# - All gp functions were translated to arcpy
# - Every function including main is in a try/except clause
# - Main code is wrapped in if __name__ == '__main__': even though script will never be
#   used as independent library.
# - Normal messages are no longer Warnings unnecessarily.

## ===============================================================================================================
def print_exception():

    try:

        exc_type, exc_value, exc_traceback = sys.exc_info()
        theMsg = "\t" + traceback.format_exception(exc_type, exc_value, exc_traceback)[1] + "\n\t" + traceback.format_exception(exc_type, exc_value, exc_traceback)[-1]

        if theMsg.find("exit") > -1:
            AddMsgAndPrint("\n\n")
            pass
        else:
            AddMsgAndPrint("\n----------------------------------- ERROR Start -----------------------------------",2)
            AddMsgAndPrint(theMsg,2)
            AddMsgAndPrint("------------------------------------- ERROR End -----------------------------------\n",2)

    except:
        AddMsgAndPrint("Unhandled error in print_exception method", 2)
        pass

## ================================================================================================================
def AddMsgAndPrint(msg, severity=0):
    # prints message to screen if run as a python script
    # Adds tool message to the geoprocessor
    # Split the message on  \n first, so that if it's multiple lines, a GPMessage will be added for each line

    print(msg)

    try:
        f = open(textFilePath,'a+')
        f.write(msg + " \n")
        f.close
        del f

    except:
        pass

    if severity == 0:
        arcpy.AddMessage(msg)

    elif severity == 1:
        arcpy.AddWarning(msg)

    elif severity == 2:
        arcpy.AddError(msg)


## ================================================================================================================
def logBasicSettings():
    # record basic user inputs and settings to log file for future purposes

    import getpass, time
    arcInfo = arcpy.GetInstallInfo()  # dict of ArcGIS Pro information

    f = open(textFilePath,'a+')
    f.write("\n################################################################################################################\n")
    f.write("Executing \"8. Wascob Ridge Layout and Profile\" tool")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write(arcInfo['ProductName'] + ": " + arcInfo['Version'] + "\n")
    f.write("User Parameters:\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tInput Dem: " + arcpy.Describe(ProjectDEM).CatalogPath + "\n")
    f.write("\tInterval: " + str(interval) + "\n")

    f.close
    del f

## ================================================================================================================
# Import system modules
import arcpy, sys, os, string, traceback
from arcpy.sa import *

if __name__ == '__main__':

    try:

        # Check out Spatial Analyst License
        if arcpy.CheckExtension("Spatial") == "Available":
            arcpy.CheckOutExtension("Spatial")
        else:
            AddMsgAndPrint("Spatial Analyst Extension not enabled. Please enable Spatial analyst from the Tools/Extensions menu. Exiting!",2)
            exit()

        # Check out 3D Analyst License
        if arcpy.CheckExtension("3D") == "Available":
            arcpy.CheckOutExtension("3D")
        else:
            AddMsgAndPrint("3D Analyst Extension not enabled. Please enable 3D Analyst from the Tools/Extensions menu. Exiting!",2)
            exit()

        #----------------------------------------------------------------------------------------- Input Parameters
        inWatershed = arcpy.GetParameterAsText(0)
        inputLine = arcpy.GetParameterAsText(1)
        interval = arcpy.GetParameterAsText(2)

        # Environment settings
        arcpy.env.parallelProcessingFactor = "75%"
        arcpy.env.overwriteOutput = True
        arcpy.env.geographicTransformations = "WGS_1984_(ITRF00)_To_NAD_1983"
        arcpy.env.resamplingMethod = "BILINEAR"
        arcpy.env.pyramid = "PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP"

        # --------------------------------------------------------------------- Variables
        watershed_path = arcpy.Describe(inWatershed).CatalogPath
        watershedGDB_path = watershed_path[:watershed_path .find(".gdb")+4]
        watershedFD_path = watershedGDB_path + os.sep + "Layers"
        userWorkspace = os.path.dirname(watershedGDB_path)
        outputFolder = userWorkspace + os.sep + "gis_output"
        tables = outputFolder + os.sep + "tables"
        stakeoutPoints = watershedFD_path + os.sep + "stakeoutPoints"

        if not arcpy.Exists(outputFolder):
            arcpy.CreateFolder_management(userWorkspace, "gis_output")
        if not arcpy.Exists(tables):
            arcpy.CreateFolder_management(outputFolder, "tables")

        ProjectDEM = watershedGDB_path + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_Project_DEM"
        zUnits = "Feet"

        # Set path to log file and start logging
        textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.txt"
        logBasicSettings()

        # --------------------------------------------------------------------- Permanent Datasets
        outLine = watershedFD_path + os.sep + "RidgeLines"
        outPoints = watershedFD_path + os.sep + "RidgeStationPoints"
        pointsTable = tables + os.sep + "ridgestations.dbf"
        stakeoutTable = tables + os.sep + "ridgestakeoutPoints.dbf"
        outLineLyr = "RidgeLines"
        outPointsLyr = "RidgeStationPoints"

        # --------------------------------------------------------------------- Temp Datasets
        stationLyr = "stations"
        stationElev = watershedGDB_path + os.sep + "stationElev"

        # --------------------------------------------------------------------- Check some parameters
        AddMsgAndPrint("\nChecking inptus...",0)
        # Exit if interval not set propertly
        try:
            float(interval)
        except:
            AddMsgAndPrint("\tStation Interval was invalid; cannot set interpolation interval. Exiting...",2)
            exit()

        interval = float(interval)

        if not arcpy.Exists(ProjectDEM):
            AddMsgAndPrint("\tMissing Project_DEM from FGDB. Can not perform raster analysis.",2)
            AddMsgAndPrint("\tProject_DEM must be in the same geodatabase as your input watershed.",2)
            AddMsgAndPrint("\tCheck your the source of your provided watershed. Exiting...",2)
            exit()

        # ---------------------------------- Retrieve DEM Properties
        demDesc = arcpy.da.Describe(ProjectDEM)
        demName = demDesc['name']
        demPath = demDesc['catalogPath']
        demCellSize = demDesc['meanCellWidth']
        demFormat = demDesc['format']
        demSR = demDesc['spatialReference']
        demCoordType = demSR.type
        linearUnits = demSR.linearUnitName

        if demCoordType == "Projected":
            if linearUnits in ("Meter","Meters"):
                linearUnits = "Meters"
            elif linearUnits in ("Foot", "Feet", "Foot_US"):
                linearUnits = "Feet"
            else:
                AddMsgAndPrint("\tHorizontal DEM units could not be determined. Please use a projected DEM with meters or feet for horizontal units. Exiting...",2)
                exit()
        else:
            AddMsgAndPrint("\t" + demName + " is NOT in a Projected Coordinate System. Exiting...",2)
            exit()

        # zUnits are feet because we are using WASCOB project DEM
        # This Zfactor is used for expressing elevations from input data as feet, regardless of input z-units. But z-units are feet in this toolbox. Redundant.
        Zfactor = 1

        # ------------------------------------------------------------- Delete [previous toc lyrs if present
        # Copy the input line before deleting the TOC layer reference in case input line IS the previous line selected from the TOC
        lineTemp = arcpy.CreateScratchName("lineTemp",data_type="FeatureClass",workspace="in_memory")
        arcpy.CopyFeatures_management(inputLine, lineTemp)

        if arcpy.Exists(outLineLyr):
            AddMsgAndPrint("\nRemoving previous layers from ArcMap",0)
            arcpy.Delete_management(outLineLyr)

        if arcpy.Exists(outPointsLyr):
            arcpy.Delete_management(outPointsLyr)

        # ------------------------------------------------------------- Copy input and create routes / points
        # Check for fields: if user input is previous line they will already exist
        if len(arcpy.ListFields(lineTemp,"ID")) < 1:
            arcpy.AddField_management(lineTemp, "ID", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED")
        if len(arcpy.ListFields(lineTemp,"NO_STATIONS")) < 1:
            arcpy.AddField_management(lineTemp, "NO_STATIONS", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED")
        if len(arcpy.ListFields(lineTemp,"FROM_PT")) < 1:
            arcpy.AddField_management(lineTemp, "FROM_PT", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED")
        if len(arcpy.ListFields(lineTemp,"LENGTH_FT")) < 1:
            arcpy.AddField_management(lineTemp, "LENGTH_FT", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")

        expression = "!shape.length@feet!"
        arcpy.CalculateField_management(lineTemp, "LENGTH_FT", expression, "PYTHON3")
        del expression

        # Create Table to hold station values
        stationTable = "in_memory\stationTable"
        arcpy.CreateTable_management("in_memory","stationTable")
        arcpy.AddField_management(stationTable, "ID", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        arcpy.AddField_management(stationTable, "STATION", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        arcpy.AddField_management(stationTable, "POINT_X", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        arcpy.AddField_management(stationTable, "POINT_Y", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        arcpy.AddField_management(stationTable, "POINT_Z", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

        # Calculate number of stations / remainder
        AddMsgAndPrint("\nCalculating the number of stations")
        AddMsgAndPrint("\tStation Point interval: " + str(interval) + " Feet")

        with arcpy.da.UpdateCursor(lineTemp,['OID@','ID','NO_STATIONS','FROM_PT','LENGTH_FT']) as cursor:
            for row in cursor:
                row[1] = row[0]

                if row[4] < interval:
                    AddMsgAndPrint("\tThe Length of line " + str(row[1]) + " is less ",2)
                    AddMsgAndPrint("\tthan the specified interval of " + str(interval) + " feet.",2)
                    AddMsgAndPrint("\tChoose a lower interval or supply a longer line. Exiting!",2)
                    exit()

                exp = row[4] / interval - 0.5 + 1
                row[2] = round(exp)
                row[3] = 0
                cursor.updateRow(row)

                AddMsgAndPrint("\tLine " + str(row[1]) + " Total Length: " + str(int(row[4])) + " Feet")
                AddMsgAndPrint("\tEquidistant stations (Including Station 0): " + str(row[2]))
                remainder = (round(exp) * interval) - row[4]

                if remainder > 0:
                    AddMsgAndPrint("\tPlus 1 covering the remaining " + str(int(remainder)) + " feet\n")

                insertCursor = arcpy.da.InsertCursor(stationTable, ['ID','STATION'])
                insertCursor.insertRow((row[0],int(row[4])))

                currentStation = 0
                while currentStation < row[2]:
                    insertCursor.insertRow((row[0],currentStation*interval))
                    #AddMsgAndPrint("Added: ID: " + str(row[1]) + " -- " + str(currentStation*interval))
                    currentStation+=1
                del insertCursor, currentStation

        # Create Route(s) lyr and define events along each route
        AddMsgAndPrint("\nCreating Stations")

        routes = arcpy.CreateScratchName("routes",data_type="FeatureClass",workspace="in_memory")
        arcpy.CreateRoutes_lr(lineTemp, "ID", routes, "TWO_FIELDS", "FROM_PT", "LENGTH_FT", "UPPER_LEFT", "1", "0", "IGNORE", "INDEX")

        stationEvents = arcpy.CreateScratchName("stationEvents",data_type="FeatureClass",workspace="in_memory")
        arcpy.MakeRouteEventLayer_lr(routes, "ID", stationTable, "ID POINT STATION", stationEvents, "", "NO_ERROR_FIELD", "NO_ANGLE_FIELD", "NORMAL", "ANGLE", "LEFT", "POINT")
        arcpy.AddField_management(stationEvents, "STATIONID", "TEXT", "", "", "25", "", "NULLABLE", "NON_REQUIRED")
        arcpy.CalculateField_management(stationEvents, "STATIONID", "str(!STATION!) + '_' + str(!ID!)", "PYTHON3")

        stationTemp = watershedFD_path + os.sep + "stations"
        arcpy.CopyFeatures_management(stationEvents, stationTemp)
        arcpy.AddXY_management(stationTemp)

        arcpy.AddField_management(stationTemp, "POINT_Z", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

        arcpy.MakeFeatureLayer_management(stationTemp, stationLyr)
        AddMsgAndPrint("\tSuccessfuly created a total of " + str(int(arcpy.GetCount_management(stationLyr).getOutput(0))) + " stations",0)
        AddMsgAndPrint("\tfor the " + str(int(arcpy.GetCount_management(lineTemp).getOutput(0))) + " line(s) provided\n")

        # -------------------------------------------------------------------- Retrieve Elevation values
        AddMsgAndPrint("\nRetrieving station elevations")

        # Buffer the stations the width of one raster cell / unit
        if linearUnits == "Meters":
            bufferSize = str(demCellSize) + " Meters"
        elif linearUnits == "Feet":
            bufferSize = str(demCellSize) + " Feet"
        else:
            bufferSize = str(demCellSize) + " Unknown"

        stationBuffer = arcpy.CreateScratchName("stationBuffer",data_type="FeatureClass",workspace="in_memory")
        arcpy.Buffer_analysis(stationTemp, stationBuffer, bufferSize, "FULL", "ROUND", "NONE", "")

        ZonalStatisticsAsTable(stationBuffer, "STATIONID", ProjectDEM, stationElev, "NODATA", "ALL")

        arcpy.AddJoin_management(stationLyr, "StationID", stationElev, "StationID", "KEEP_ALL")

        expression = "round(!stationElev.MEAN! * " + str(Zfactor) + ",1)"
        arcpy.CalculateField_management(stationLyr, "stations.POINT_Z", expression, "PYTHON")

        arcpy.RemoveJoin_management(stationLyr, "stationElev")
        arcpy.DeleteField_management(stationTemp, "STATIONID; POINT_M")

        # ---------------------------------------------------------------------- Create final output
        # Interpolate Line to 3d via Z factor
        arcpy.InterpolateShape_3d (ProjectDEM, lineTemp, outLine, "", Zfactor)

        # Copy Station Points
        arcpy.CopyFeatures_management(stationTemp, outPoints)

        # Copy output to tables folder
        arcpy.CopyRows_management(outPoints, pointsTable)

        arcpy.Delete_management(stationTemp)

        # ------------------------------------------------------------------------------------------------ Compact FGDB
        arcpy.Compact_management(watershedGDB_path)
        AddMsgAndPrint("Successfully Compacted FGDB: " + os.path.basename(watershedGDB_path) + "\n")

        # ---------------------------------------------------------------- Create Layers and apply symbology
        AddMsgAndPrint("\nAdding Layers to ArcGIS Pro")
        arcpy.SetParameterAsText(3, outLine)
        arcpy.SetParameterAsText(4, outPoints)

        AddMsgAndPrint("\nProcessing Complete!")

    except:
        print_exception()

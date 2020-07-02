## profileXYZ.py (Line to XYZ)
##
## Created by Peter Mead, Adolfo Diaz, USDA NRCS, 2013
## Updated by Chris Morse, USDA NRCS, 2018
## Updated by Chris Morse, USDA NRCS, 2019
##
## Creates points at user specified interval along digitized or provided lines,
## Derives stationing distances and XYZ values, providing Z values in feet,
## as well as interpolating the line(s) to 3d using the appropriate Zfactor.
#
## Optionally exports a comma delimited txt file for other applications

# ==========================================================================================
# Updated  7/2/2020 - Adolfo Diaz
#
# - This tool is almost identical to the Tile Layout and Profile tool!
#   and the Ridge Layout and Profile tool
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
    f.write("\n##################################################################\n")
    f.write("Executing \"Line to XYZ\" Tool" + "\n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write(arcInfo['ProductName'] + ": " + arcInfo['Version'] + "\n")
    f.write("User Parameters:\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tInput Dem: " + arcpy.Describe(inputDEM).CatalogPath + "\n")
    f.write("\tInterval: " + str(interval) + "\n")
    f.write("\tElevation Z-units: " + zUnits + "\n")

    f.close
    del f
## ================================================================================================================
# Import system modules
import arcpy, sys, os, traceback
from arcpy.sa import *

if __name__ == '__main__':

    try:
        # Check out 3D and SA licenses
        if arcpy.CheckExtension("3d") == "Available":
            arcpy.CheckOutExtension("3d")
        else:
            arcpy.AddError("\n3D analyst extension is not enabled. Please enable 3D analyst from the Tools/Extensions menu. Exiting...\n")
            exit()
        if arcpy.CheckExtension("spatial") == "Available":
            arcpy.CheckOutExtension("spatial")
        else:
            arcpy.AddError("\nSpatial Analyst Extension not enabled. Please enable Spatial Analyst from the Tools/Extensions menu. Exiting...\n")
            exit()

        arcpy.SetProgressorLabel("Setting Variables")
        #----------------------------------------------------------------------------------------- Input Parameters
        userWorkspace = arcpy.GetParameterAsText(0)
        inputDEM = arcpy.GetParameterAsText(1)
        zUnits = arcpy.GetParameterAsText(2)
        inputLine = arcpy.GetParameterAsText(3)
        interval = arcpy.GetParameterAsText(4)
        text = arcpy.GetParameter(5)

        # Environment settings
        arcpy.env.parallelProcessingFactor = "75%"
        arcpy.env.overwriteOutput = True
        arcpy.env.geographicTransformations = "WGS_1984_(ITRF00)_To_NAD_1983"
        arcpy.env.resamplingMethod = "BILINEAR"
        arcpy.env.pyramid = "PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP"

        # --------------------------------------------------------------------- Directory Paths
        watershedGDB_name = os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.gdb"  # replace spaces for new FGDB name
        watershedGDB_path = userWorkspace + os.sep + watershedGDB_name
        watershedFD = watershedGDB_path + os.sep + "Layers"
        projectName = arcpy.ValidateTableName(os.path.basename(userWorkspace).replace(" ","_"))

        # log inputs and settings to file
        textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.txt"
        logBasicSettings()

        # --------------------------------------------------------------------- Permanent Datasets
        outLine = watershedFD + os.sep + projectName + "_XYZ_line"
        # Must Have a unique name for output -- Append a unique digit to output if required
        x = 1
        y = 0

        while x > 0:
            if arcpy.Exists(outLine):
                outLine = watershedFD + os.sep + projectName + "_XYZ_line" + str(x)
                x += 1
                y += 1
            else:
                x = 0
        if y > 0:
            outPoints = watershedFD + os.sep + projectName + "_XYZ_points" + str(y)
            outTxt = userWorkspace + os.sep + projectName + "_XYZ_line" + str(y) + ".txt"
        else:
            outPoints = watershedFD + os.sep + projectName + "_XYZ_points"
            outTxt = userWorkspace + os.sep + projectName + "_XYZ_line.txt"
        del x
        del y

        outLineLyr = "" + os.path.basename(outLine) + ""
        outPointsLyr = "" + os.path.basename(outPoints) + ""

        # --------------------------------------------------------------------- Temp Datasets
        stationLyr = "stations"
        stationElev = watershedGDB_path + os.sep + "stationElev"

        # --------------------------------------------------------------------- Check station interval
        # Exit if interval not set propertly
        try:
            float(interval)
        except:
            AddMsgAndPrint("\nStation Interval was invalid; Cannot set interpolation interval. Exiting...\n",2)
            exit()

        interval = float(interval)

        # --------------------------------------------------------------------- Check DEM Coordinate System and Linear Units
        demDesc = arcpy.da.Describe(inputDEM)
        demName = demDesc['name']
        demPath = demDesc['catalogPath']
        demCellSize = demDesc['meanCellWidth']
        demFormat = demDesc['format']
        demSR = demDesc['spatialReference']
        demCoordType = demSR.type
        linearUnits = demSR.linearUnitName

        try:
            if interval < float(demCellSize):
                AddMsgAndPrint("\nThe interval specified is less than the DEM cell size. Please re-run with a higher interval value. Exiting...\n",2)
                exit()
        except:
            AddMsgAndPrint("\nThere may be an issue with the DEM cell size. Exiting...\n",2)
            exit()

        if linearUnits in ("Meter","Meters"):
            linearUnits = "Meters"
        elif linearUnits in ("Foot", "Feet", "Foot_US"):
            linearUnits = "Feet"

        AddMsgAndPrint("\nGathering information about DEM: " + demName+ "\n")

        # Coordinate System must be a Projected type in order to continue.
        # zUnits will determine Zfactor for the conversion of elevation values to a profile in feet

        if demCoordType == "Projected":
            if zUnits == "Meters":
                Zfactor = 3.280839896
            elif zUnits == "Centimeters":
                Zfactor = 0.03280839896
            elif zUnits == "Inches":
                Zfactor = 0.0833333
            # zUnits must be feet; no more choices
            else:
                Zfactor = 1

            AddMsgAndPrint("\tProjection Name: " + demSR.name)
            AddMsgAndPrint("\tXY Linear Units: " + linearUnits)
            AddMsgAndPrint("\tElevation Values (Z): " + zUnits)
            AddMsgAndPrint("\tCell Size: " + str(demCellSize) + " x " + str(demCellSize) + " " + linearUnits)

        else:
            AddMsgAndPrint("\n\n\t" + os.path.basename(inputDEM) + " is NOT in a projected Coordinate System. Exiting...\n",2)
            exit()

        # ------------------------------------------------------------------------ Create FGDB, FeatureDataset
        # Boolean - Assume FGDB already exists
        bFGDBexists = True

        # Create Watershed FGDB and feature dataset if it doesn't exist
        if not arcpy.Exists(watershedGDB_path):
            arcpy.CreateFileGDB_management(userWorkspace, watershedGDB_name)
            arcpy.CreateFeatureDataset_management(watershedGDB_path, "Layers", demSR)
            AddMsgAndPrint("\nSuccessfully created File Geodatabase: " + watershedGDB_name)
            bFGDBexists = False

        # if GDB already existed but feature dataset doesn't
        if not arcpy.Exists(watershedFD):
            arcpy.CreateFeatureDataset_management(watershedGDB_path, "Layers", demSR)


        # ------------------------------------------------------------- Delete [previous toc lyrs if present
        # Copy the input line before deleting the TOC layer reference in case input line IS the previous line selected from the TOC
        lineTemp = arcpy.CreateScratchName("lineTemp",data_type="FeatureClass",workspace="in_memory")
        arcpy.CopyFeatures_management(inputLine, lineTemp)

        if arcpy.Exists(outLineLyr):
            AddMsgAndPrint("\nRemoving previous layers from ArcGIS Pro")
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

        # Should this next sort actually be done with STATIONID, instead of STATION?
        stationTemp = watershedFD + os.sep + "stations"
        arcpy.Sort_management(stationEvents, stationTemp, [["STATION", "ASCENDING"]])

        arcpy.AddXY_management(stationTemp)
        arcpy.AddField_management(stationTemp, "POINT_Z", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

        arcpy.MakeFeatureLayer_management(stationTemp, stationLyr)
        AddMsgAndPrint("\tSuccessfuly created a total of " + str(int(arcpy.GetCount_management(stationLyr).getOutput(0))) + " stations",0)
        AddMsgAndPrint("\tfor the " + str(int(arcpy.GetCount_management(lineTemp).getOutput(0))) + " line(s) provided\n")

        # --------------------------------------------------------------------- Retrieve Elevation values
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

        ZonalStatisticsAsTable(stationBuffer, "STATIONID", inputDEM, stationElev, "NODATA", "ALL")

        arcpy.AddJoin_management(stationLyr, "StationID", stationElev, "StationID", "KEEP_ALL")

        expression = "round(!stationElev.MEAN! * " + str(Zfactor) + ",1)"
        arcpy.CalculateField_management(stationLyr, "stations.POINT_Z", expression, "PYTHON")

        arcpy.RemoveJoin_management(stationLyr, "stationElev")
        arcpy.DeleteField_management(stationTemp, "STATIONID; POINT_M")

        # ---------------------------------------------------------------------- Create final output
        # Interpolate Line to 3d via Z factor
        arcpy.InterpolateShape_3d(inputDEM, lineTemp, outLine, "", Zfactor)

        # Copy Station Points
        arcpy.CopyFeatures_management(stationTemp, outPoints)

        arcpy.Delete_management(stationElev)
        arcpy.Delete_management(stationTemp)

        # Create Txt file if selected and write attributes of station points
        if text == True:
            AddMsgAndPrint("Creating Output text file:\n")
            AddMsgAndPrint("\t" + str(outTxt) + "\n")

            t = open(outTxt, 'w')
            t.write("ID, STATION, X, Y, Z")


            with arcpy.da.SearchCursor(outPoints,['ID', 'STATION', 'POINT_X', 'POINT_Y', 'POINT_Z'],sql_clause=(None,'ORDER BY STATION')) as cursor:
                for row in cursor:
                    t.write(str(row[0]) + "," + str(row[1]) + "," + str(row[2]) + "," + str(row[3]) + "," + str(row[4]) + "\n")

            t.close()

        # ---------------------------------------------------------------- Prepare to add to ArcMap
        AddMsgAndPrint("Adding Layers to ArcGIS Pro\n")
        arcpy.SetParameterAsText(6, outLine)
        arcpy.SetParameterAsText(7, outPoints)

        # ---------------------------------------------------------------------------------------------------------------------------- Compact FGDB

        arcpy.Compact_management(watershedGDB_path)
        AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path))

        # ---------------------------------------------------------------------------- FIN!
        AddMsgAndPrint("Processing Complete!\n")

    except:
        print_exception()




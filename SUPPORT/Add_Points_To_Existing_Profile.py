## Wascob_AddPointsToTileProfile.py
##
## Created by Peter Mead, USDA NRCS, 2013
## Updated by Chris Morse, USDA NRCS, 2020
##
## Adds Points to WASCOB Tile Station Points
##

# ==========================================================================================
# Updated  7/7/2020 - Adolfo Diaz
#
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
    f.write("Executing \"Wascob Add Points to Profile\" tool")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write(arcInfo['ProductName'] + ": " + arcInfo['Version'] + "\n")
    f.write("User Parameters:\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tInput Stations: " + str(stationPoints) + "\n")

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
            arcpy.AddError("Spatial Analyst Extension not enabled. Please enable Spatial analyst from the Tools/Extensions menu. Exiting...\n")
            exit()

        #------------------------------------------------------------------ Input Parameters
        stationPoints = arcpy.GetParameterAsText(0)
        inPoints = arcpy.GetParameterAsText(1)

        # Environment settings
        arcpy.env.parallelProcessingFactor = "75%"
        arcpy.env.overwriteOutput = True
        arcpy.env.geographicTransformations = "WGS_1984_(ITRF00)_To_NAD_1983"
        arcpy.env.resamplingMethod = "BILINEAR"
        arcpy.env.pyramid = "PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP"

        # ----------------------------------------------------------------- Variables
        watershed_path = arcpy.Describe(stationPoints).CatalogPath
        watershedGDB_path = watershed_path[:watershed_path .find(".gdb")+4]
        watershedFD_path = watershedGDB_path + os.sep + "Layers"
        userWorkspace = os.path.dirname(watershedGDB_path)
        outputFolder = userWorkspace + os.sep + "gis_output"
        tables = outputFolder + os.sep + "tables"

        ProjectDEM = watershedGDB_path + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_Project_DEM"
        tileLines = watershedFD_path + os.sep + "tileLines"

        # Set path to log file and start logging
        textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.txt"
        logBasicSettings()

        if not arcpy.Exists(outputFolder):
            arcpy.CreateFolder_management(userWorkspace, "gis_output")
        if not arcpy.Exists(tables):
            arcpy.CreateFolder_management(outputFolder, "tables")

        # ---------------------------------------------------------------- Permanent Datasets
        pointsTable = tables + os.sep + "stations.dbf"
        stations = watershedFD_path + os.sep + "stationPoints"

        # ---------------------------------------------------------------- Lyrs to ArcMap
        outPointsLyr = "StationPoints"

        # ---------------------------------------------------------------- Temporary Datasets
        #linesNear = watershedGDB_path + os.sep + "linesNear"
        #pointsNear = watershedGDB_path + os.sep + "pointsNear"
        pointsLyr = "pointsLyr"
        stationTemp = watershedFD_path + os.sep + "stations"
        stationTable = watershedGDB_path + os.sep + "stationTable"
        routes = watershedFD_path + os.sep + "routes"
        stationEvents = watershedGDB_path + os.sep + "stationEvents"
        station_lyr = "stations"
        stationLyr = "stationLyr"
        stationBuffer = watershedFD_path + os.sep + "stationsBuffer"
        stationElev = watershedGDB_path + os.sep + "stationElev"
        outlets = watershedFD_path + os.sep + "tileOutlets"

        # -------------------------------------------------------------- Create Temp Point(s)
        pointsTemp = arcpy.CreateScratchName("pointsTemp",data_type="FeatureClass",workspace="in_memory")
        arcpy.CopyFeatures_management(inPoints, pointsTemp)

        AddMsgAndPrint("\nChecking inputs...")

        # Exit if no TileLines
        if not arcpy.Exists(tileLines):
            if arcpy.Exists("TileLines"):
                tileLines = "TileLines"
            else:
                AddMsgAndPrint("\tTile Lines Feature Class not found in same directory as Station Points ",2)
                AddMsgAndPrint("\tor in Current ArcMap Document. Unable to compute Stationing.",2)
                AddMsgAndPrint("\tCheck the source of your inputs and try again. Exiting...",2)
                exit()

        # Exit if no Project DEM
        if not arcpy.Exists(ProjectDEM):
            AddMsgAndPrint("\tMissing Project_DEM from FGDB. Can not perform raster analysis.",2)
            AddMsgAndPrint("\tProject_DEM must be in the same geodatabase as your input watershed.",2)
            AddMsgAndPrint("\tCheck your the source of your provided watershed. Exiting...",2)
            exit()

        # Exit if no points were digitized
        count = int(arcpy.GetCount_management(pointsTemp).getOutput(0))
        if count < 1:
            AddMsgAndPrint("\tNo points provided. You must use the Add Features tool to create",2)
            AddMsgAndPrint("\tat least one point to add to the stations. Exiting...",2)
            exit()
        else:
            AddMsgAndPrint("\nAdding " + str(count) + " station(s) to existing station points...",0)

        # Add Fields as necessary
        if len(arcpy.ListFields(pointsTemp,"ID")) < 1:
            arcpy.AddField_management(pointsTemp, "ID", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED")
        if len(arcpy.ListFields(pointsTemp,"STATION")) < 1:
            arcpy.AddField_management(pointsTemp, "STATION", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED")
        if len(arcpy.ListFields(pointsTemp,"POINT_X")) < 1:
            arcpy.AddField_management(pointsTemp, "POINT_X", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")
        if len(arcpy.ListFields(pointsTemp,"POINT_Y")) < 1:
            arcpy.AddField_management(pointsTemp, "POINT_Y", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")
        if len(arcpy.ListFields(pointsTemp,"POINT_Z")) < 1:
            arcpy.AddField_management(pointsTemp, "POINT_Z", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")
        if len(arcpy.ListFields(pointsTemp,"STATIONID")) < 1:
            arcpy.AddField_management(pointsTemp, "STATIONID", "TEXT", "", "", "25", "", "NULLABLE", "NON_REQUIRED")

        # ---------------------------------- Retrieve Raster Properties
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

        # --------------------------------------------------------------- Find Nearest Tile Line
        AddMsgAndPrint("\nFinding Nearest Tile Line(s)...")
        linesNear = arcpy.CreateScratchName("linesNear",data_type="ArcInfoTable",workspace="in_memory")
        arcpy.GenerateNearTable_analysis(pointsTemp, tileLines, linesNear, "", "NO_LOCATION", "NO_ANGLE", "ALL", "1")

        with arcpy.da.SearchCursor(linesNear,['OID@', 'NEAR_FID']) as cursor:
            for row in cursor:
                pointID = row[0]
                tileID = row[1]
                whereclause = "OBJECTID = " + str(pointID)

                with arcpy.da.UpdateCursor(pointsTemp,['ID'],where_clause=whereclause) as cursor:
                    for row2 in cursor:
                        row2[0] = tileID
                        cursor.updateRow(row2)

        arcpy.Delete_management(linesNear)

        # -------------------------------------------------------------------- Find Distance from point "0" along each tile line
        # Clear any selected points
        arcpy.SelectLayerByAttribute_management(stationPoints, "CLEAR_SELECTION")
        # Select each point "0"
        arcpy.SelectLayerByAttribute_management(stationPoints, "NEW_SELECTION", "\"STATION\" = 0")
        # Create layer from selection
        arcpy.MakeFeatureLayer_management(stationPoints, station_lyr)

        AddMsgAndPrint("\nCalculating station distance(s)...",0)
        pointsNear = arcpy.CreateScratchName("pointsNear",data_type="ArcInfoTable",workspace="in_memory")
        arcpy.GenerateNearTable_analysis(pointsTemp, station_lyr, pointsNear, "", "NO_LOCATION", "NO_ANGLE", "ALL", "1")
        arcpy.SelectLayerByAttribute_management(stationPoints, "CLEAR_SELECTION")


        # Calculate stations in new Points
        with arcpy.da.SearchCursor(pointsNear,['OID@', 'NEAR_DIST']) as cursor:
            for row in cursor:
                pointID = row[0]
                distance = row[1]

                if linearUnits == "Meters":
                    station = int(distance * 3.280839896)
                else:
                    station = int(distance)

                whereclause = "OBJECTID = " + str(pointID)
                with arcpy.da.UpdateCursor(pointsTemp,['STATION'],where_clause=whereclause) as cursor:
                    for row2 in cursor:
                        row2[0] = station
                        cursor.updateRow(row2)

        arcpy.Delete_management(pointsNear)

        # ------------------- Append to Existing
        arcpy.Append_management(pointsTemp, stationPoints, "NO_TEST", "", "")
        arcpy.CopyRows_management(stationPoints, stationTable)
        arcpy.Delete_management(stationPoints)

        AddMsgAndPrint("\nCreating new stations...",0)
        arcpy.CreateRoutes_lr(tileLines, "ID", routes, "TWO_FIELDS", "FROM_PT", "LENGTH_FT", "UPPER_LEFT", "1", "0", "IGNORE", "INDEX")
        arcpy.MakeRouteEventLayer_lr(routes, "ID", stationTable, "ID POINT STATION", stationEvents, "", "NO_ERROR_FIELD", "NO_ANGLE_FIELD", "NORMAL", "ANGLE", "LEFT", "POINT")

        arcpy.AddField_management(stationEvents, "STATIONID", "TEXT", "", "", "25", "", "NULLABLE", "NON_REQUIRED", "")
        arcpy.CalculateField_management(stationEvents, "STATIONID", "str(!STATION!) + '_' + str(!ID!)", "PYTHON3")

        arcpy.CopyFeatures_management(stationEvents, stationTemp)

        arcpy.Delete_management(stationTable)
        arcpy.Delete_management(routes)

        # ------------------------------ Add X/Y Cordinates
        arcpy.AddXY_management(stationTemp)
        arcpy.AddField_management(stationTemp, "POINT_Z", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        arcpy.MakeFeatureLayer_management(stationTemp, stationLyr, "", "", "")
        AddMsgAndPrint("\n\tSuccessfuly added a total of " + str(count) + " stations",0)

        # --------------------------------------------------------------------- Retrieve Elevation values
        AddMsgAndPrint("\nRetrieving station elevations...",0)

        # Buffer the stations the width of one raster cell / unit
        if linearUnits == "Meters":
            bufferSize = str(demCellSize) + " Meters"
        elif linearUnits == "Feet":
            bufferSize = str(demCellSize) + " Feet"
        else:
            bufferSize = str(demCellSize) + " Unknown"

        arcpy.Buffer_analysis(stationTemp, stationBuffer, bufferSize, "FULL", "ROUND", "NONE", "")
        ZonalStatisticsAsTable(stationBuffer, "STATIONID", ProjectDEM, stationElev, "NODATA", "ALL")
        arcpy.AddJoin_management(stationLyr, "StationID", stationElev, "StationID", "KEEP_ALL")

        expression = "round(!stationElev.MEAN!,1)"
        arcpy.CalculateField_management(stationLyr, "stations.POINT_Z", expression, "PYTHON3")
        arcpy.RemoveJoin_management(stationLyr, "stationElev")
        arcpy.DeleteField_management(stationTemp, "STATIONID; POINT_M")
        del expression

        AddMsgAndPrint("\n\tSuccessfully added elevation values",0)
        arcpy.Delete_management(stationElev)
        arcpy.Delete_management(stationBuffer)

        # --------------------------------------------------------------------------- Copy Station Output to FD
        if arcpy.Exists(stations):
            arcpy.Delete_management(stations)
        AddMsgAndPrint("\nSaving output...")
        arcpy.CopyFeatures_management(stationTemp, stations)

        arcpy.Delete_management(stationTemp)
        arcpy.Delete_management(pointsTemp)

        # ----------------------------------------------------------------------------- Copy output to tables folder
        # Delete existing points Table
        AddMsgAndPrint("\nUpdating Station Table...")
        if arcpy.Exists(pointsTable):
            arcpy.Delete_management(pointsTable)

        # Copy output to dbf for import
        arcpy.CopyRows_management(stations, pointsTable)

        # ------------------------------------------------------------------------------------------------ Compact FGDB
        arcpy.Compact_management(watershedGDB_path)
        AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path) + "\n")

        # ---------------------------------------------------------------- Create Layers and apply symbology
        AddMsgAndPrint("\nAdding Output to ArcGIS Pro")
        arcpy.SetParameterAsText(2, stations)

        AddMsgAndPrint("\nProcessing Complete!\n")

    except:
        print_exception()


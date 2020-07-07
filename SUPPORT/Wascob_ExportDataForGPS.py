## wascob_exportData.py
##
## Created by Peter Mead, USDA NRCS, 2013
## Updated by Chris Morse, USDA NRCS, 2020
##
## Exports WASCOB related data to shapefiles in PCS native to the project.

# ==========================================================================================
# Updated  7/7/2020 - Adolfo Diaz
#
# - The output coordinate system paramater from this tool was removed due to the
#   variability of transformations that can be applied from one coord system to another.
#   Instead, the output data will be exported using the coordinate system of the project.
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
    f.write("Executing \"Wascob: Export Data\" Tool\n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write(arcInfo['ProductName'] + ": " + arcInfo['Version'] + "\n")
    f.write("User Parameters:\n")
    f.write("\tInput Watershed: " + inWatershed + "\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")

##    if len(outCoordsys) > 0:
##        f.write("\tOutput Coord Sys: " + outCoordsys + "\n")
##    else:
##        f.write("\tOutput Coord Sys: BLANK\n")

    f.close
    del f

## ================================================================================================================
# Import system modules
import arcpy, sys, os, traceback, string


if __name__ == '__main__':

    try:

        # ---------------------------------------------- Input Parameters
        inWatershed = arcpy.GetParameterAsText(0)
        #outCoordsys = arcpy.GetParameterAsText(1)

        # Environment settings
        arcpy.env.parallelProcessingFactor = "75%"
        arcpy.env.overwriteOutput = True

        # ---------------------------------------------------------------------------- Define Variables
        watershed_path = arcpy.Describe(inWatershed).CatalogPath
        watershedGDB_path = watershed_path[:watershed_path .find(".gdb")+4]
        watershedFD_path = watershedGDB_path + os.sep + "Layers"
        userWorkspace = os.path.dirname(watershedGDB_path)
        outputFolder = userWorkspace + os.sep + "gis_output"

        # Set path to log file and start logging
        textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.txt"
        logBasicSettings()

        # ----------------------------------- Inputs to be converted to shp
        stationPoints = watershedFD_path + os.sep + "StationPoints"
        rStationPoints = watershedFD_path + os.sep + "RidgeStationPoints"
        tileLines = watershedFD_path + os.sep + "tileLines"
        ridgeLines = watershedFD_path + os.sep + "RidgeLines"
        stakeoutPoints = watershedFD_path + os.sep + "stakeoutPoints"
        referenceLines = watershedFD_path + os.sep + "ReferenceLine"

        # ----------------------------------- Possible Existing Feature Layers
        stations = "StationPoints"
        rstations = "RidgeStationPoints"
        tile = "TileLines"
        ridge = "RidgeLines"
        points = "StakeoutPoints"
        refLine = "Reference Line"

        # ------------------------ If lyrs present, clear any possible selections
        if arcpy.Exists(stations):
            arcpy.SelectLayerByAttribute_management(stations, "CLEAR_SELECTION", "")
        if arcpy.Exists(rstations):
            arcpy.SelectLayerByAttribute_management(rstations, "CLEAR_SELECTION", "")
        if arcpy.Exists(tile):
            arcpy.SelectLayerByAttribute_management(tile, "CLEAR_SELECTION", "")
        if arcpy.Exists(ridge):
            arcpy.SelectLayerByAttribute_management(ridge, "CLEAR_SELECTION", "")
        if arcpy.Exists(refLine):
            arcpy.SelectLayerByAttribute_management(refLine, "CLEAR_SELECTION", "")
        if arcpy.Exists(points):
            arcpy.SelectLayerByAttribute_management(points, "CLEAR_SELECTION", "")

        # ----------------------------------------------------- Shapefile Outputs
        stationsOut = outputFolder + os.sep + "StationPoints.shp"
        rStationsOut = outputFolder + os.sep + "RidgeStationPoints.shp"
        tileOut = outputFolder + os.sep + "TileLines.shp"
        ridgeOut = outputFolder + os.sep + "RidgeLines.shp"
        pointsOut = outputFolder + os.sep + "StakeoutPoints.shp"
        linesOut = outputFolder + os.sep + "ReferenceLines.shp"

        # ------------------------------------------------------------ Copy FC's to Shapefiles
        AddMsgAndPrint("\nCopying GPS layers to output Folder",0)
        if arcpy.Exists(stationPoints):
            arcpy.CopyFeatures_management(stationPoints, stationsOut)
        else:
            AddMsgAndPrint("\nUnable to find Station Points in project workspace. Copy failed. Export them manually.",1)

        if arcpy.Exists(rStationPoints):
            arcpy.CopyFeatures_management(rStationPoints, rStationsOut)
        else:
            AddMsgAndPrint("\nUnable to find Ridge Station Points in project workspace. Copy failed. Export them manually.",1)

        if arcpy.Exists(tileLines):
            arcpy.CopyFeatures_management(tileLines, tileOut)
        else:
            AddMsgAndPrint("\nUnable to find TileLines in project workspace. Copy failed. Export them manually.",1)

        if arcpy.Exists(ridgeLines):
            arcpy.CopyFeatures_management(ridgeLines, ridgeOut)
        else:
            AddMsgAndPrint("\nUnable to find Ridge Lines in project workspace. Copy failed. Export them manually.",1)

        if arcpy.Exists(stakeoutPoints):
            arcpy.CopyFeatures_management(stakeoutPoints, pointsOut)
        else:
            AddMsgAndPrint("\nUnable to find stakeoutPoints in project workspace. Copy failed. Export them manually.",1)

        if arcpy.Exists(referenceLines):
            arcpy.CopyFeatures_management(referenceLines, linesOut)
        else:
            AddMsgAndPrint("\nUnable to find referenceLines in project workspace. Copy failed. Export them manually.",1)

        # --------------------------------------------------- Restore Environments if necessary
        AddMsgAndPrint("\nData was exported using the coordinate system of your project or DEM data!")
        AddMsgAndPrint("\nIf this coordinate system is not suitable for use with your GPS system, please use the ")
        AddMsgAndPrint("\nProject tool found in ArcToolbox under Data Management Tools, Projections and Transformations,")
        AddMsgAndPrint("\nto re-project the exported data into a coordinate system suitable for your GPS system.\n")

        AddMsgAndPrint("\nProcessing Finished!")

    except:
        print_exception()

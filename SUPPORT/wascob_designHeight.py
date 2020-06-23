# ==========================================================================================
# Name: Wascob_DesignHeight.py
#
# Author: Peter Mead
#         Becker Soil Water Conservation District
#         Red River Valley Conservation Service Area
# e-mail: pemead@co.becker.mn.us
#
# Author: Adolfo.Diaz
#         GIS Specialist
#         National Soil Survey Center
#         USDA - NRCS
# e-mail: adolfo.diaz@usda.gov
# phone: 608.662.4422 ext. 216
#
# Author: Chris Morse
#         IN State GIS Coordinator
#         USDA - NRCS
# e-mail: chris.morse@usda.gov
# phone: 317.501.1578

# Created by Peter Mead, 2013
# Updated by Chris Morse, USDA NRCS, 2020

## Creates embankment points for stakeout, Allows user input of intake location.
## Appends results to "StakeoutPoints" Layer in Table of contents.

# ==========================================================================================
# Updated  6/23/2020 - Adolfo Diaz
#
# - Updated and Tested for ArcGIS Pro 2.4.2 and python 3.6
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
    f.write("Executing \"7. Wascob Design Height & Intake Location\" tool\n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write(arcInfo['ProductName'] + ": " + arcInfo['Version'] + "\n")
    f.write("User Parameters:\n")
    f.write("\tInput Watershed: " + inWatershed + "\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tSelected Subbasin: " + Subbasin + "\n")
    f.write("\tDesign Elevation: " + DesignElev + "\n")
    f.write("\tIntake Elevation: " + IntakeElev + "\n")

    f.close
    del f

## ================================================================================================================
# Import system modules
import arcpy, sys, os, traceback, string
from arcpy.sa import *

if __name__ == '__main__':

    try:

        # ---------------------------------------------- Input Parameters
        inWatershed = arcpy.GetParameterAsText(0)
        Subbasin = arcpy.GetParameterAsText(1)
        DesignElev = arcpy.GetParameterAsText(2)
        IntakeElev = arcpy.GetParameterAsText(3)
        IntakeLocation = arcpy.GetParameterAsText(4)

        # Check out Spatial Analyst License
        if arcpy.CheckExtension("Spatial") == "Available":
            arcpy.CheckOutExtension("Spatial")
        else:
            arcpy.AddError("Spatial Analyst Extension not enabled. Please enable Spatial analyst from the Tools/Extensions menu. Exiting...\n")
            exit()

        # Environment settings
        arcpy.env.overwriteOutput = True
        arcpy.env.parallelProcessingFactor = "75%"
        arcpy.env.geographicTransformations = "WGS_1984_(ITRF00)_To_NAD_1983"
        arcpy.env.resamplingMethod = "BILINEAR"
        arcpy.env.pyramid = "PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP"

        # ---------------------------------------------------------------------------- Define Variables
        watershed_path = arcpy.Describe(inWatershed).CatalogPath
        watershedGDB_path = watershed_path[:watershed_path .find(".gdb")+4]
        watershedGDB_name = os.path.basename(watershedGDB_path)
        watershedFD_path = watershedGDB_path + os.sep + "Layers"
        userWorkspace = os.path.dirname(watershedGDB_path)
        wsName = os.path.basename(inWatershed)
        #ReferenceLine = watershedFD_path + "ReferenceLine"

        # ---------------------------------------------------------------------------- Existing Datasets
        stakeoutPoints = watershedFD_path + os.sep + "stakeoutPoints"
        ProjectDEM = watershedGDB_path + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_Project_DEM"

        # ------------- Layers in ArcGIS Pro
        stakeoutPoints = "stakeoutPoints"
        ReferenceLine = "ReferenceLine"

        # --------------------------------------------------------------------------- Temporary Datasets
        RefLineLyr = "ReferenceLineLyr"
        stakeoutPointsLyr ="stakeoutPointsLyr"
        pointsSelection = "pointsSelection"
        refLineSelection = "refLineSelection"

        # Set path to log file and start logging
        textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.txt"
        logBasicSettings()

        # ---------------------------------------------------------------------------- Check inputs
        AddMsgAndPrint("\nChecking inputs and workspace...",0)
        if not arcpy.Exists(ProjectDEM):
            AddMsgAndPrint("\tMissing Project_DEM from FGDB. Can not perform raster analysis.",2)
            AddMsgAndPrint("\tProject_DEM must be in the same geodatabase as your input watershed.",2)
            AddMsgAndPrint("\tCheck your the source of your provided watershed. Exiting...",2)
            exit()

        if not arcpy.Exists(ReferenceLine):
            AddMsgAndPrint("\tReference Line not found in table of contents or in the workspace of your input watershed",2)
            AddMsgAndPrint("\tDouble check your inputs and workspace. Exiting...",2)
            exit()

        if int(arcpy.GetCount_management(IntakeLocation).getOutput(0)) > 1:
            # Exit if user input more than one intake
            AddMsgAndPrint("\tYou provided more than one inlet location",2)
            AddMsgAndPrint("\tEach subbasin must be completed individually,",2)
            AddMsgAndPrint("\twith one intake provided each time you run this tool.",2)
            AddMsgAndPrint("\tTry again with only one intake loacation. Exiting...",2)
            exit()

        if int(arcpy.GetCount_management(IntakeLocation).getOutput(0)) < 1:
            # Exit if no intake point was provided
            AddMsgAndPrint("\tYou did not provide a point for your intake loaction",2)
            AddMsgAndPrint("\tYou must create a point at the proposed inlet location by using",2)
            AddMsgAndPrint("\tthe Add Features tool in the Design Height tool dialog box. Exiting...",2)
            exit()

        if not arcpy.Exists(stakeoutPoints):
            arcpy.CreateFeatureclass_management(watershedFD_path, "stakeoutPoints", "POINT", "", "DISABLED", "DISABLED", "", "", "0", "0", "0")
            arcpy.AddField_management(stakeoutPoints, "ID", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
            arcpy.AddField_management(stakeoutPoints, "Subbasin", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
            arcpy.AddField_management(stakeoutPoints, "Elev", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
            arcpy.AddField_management(stakeoutPoints, "Notes", "TEXT", "", "", "50", "", "NULLABLE", "NON_REQUIRED", "")

        # ----------------------------------------------------- Select reference line for specified Subbasin
##        AddMsgAndPrint("\nSelecting Reference Line for subbasin " + str(Subbasin))
##        expression = arcpy.AddFieldDelimiters(ReferenceLine, "Subbasin") + " = " + str(Subbasin) + ""
##        refLineSelection = [row[0] for row in arcpy.da.SearchCursor(ReferenceLine,"Subbasin",where_clause=expression)]
##
##        if not len(refLineSelection) > 0:
##            # Exit if no corresponding subbasin id found in reference line
##            AddMsgAndPrint("\tNo reference line features were found for subbasin " + str(Subbasin),2)
##            AddMsgAndPrint("\tDouble check your inputs and specify a different subbasin ID. Exiting...",2)
##            exit()

        arcpy.MakeFeatureLayer_management(ReferenceLine, RefLineLyr)
        exp = "\"Subbasin\" = " + str(Subbasin) + ""
        arcpy.SelectLayerByAttribute_management(RefLineLyr, "NEW_SELECTION", exp)
        arcpy.MakeFeatureLayer_management(RefLineLyr, refLineSelection)

        if not int(arcpy.GetCount_management(refLineSelection).getOutput(0)) > 0:
            # Exit if no corresponding subbasin id found in reference line
            AddMsgAndPrint("\tNo reference line features were found for subbasin " + str(Subbasin),2)
            AddMsgAndPrint("\tDouble check your inputs and specify a different subbasin ID. Exiting...",2)
            exit()

        refTemp = arcpy.CreateScratchName("refTemp",data_type="FeatureClass",workspace="in_memory")
        arcpy.CopyFeatures_management(refLineSelection, refTemp)
        arcpy.SelectLayerByAttribute_management(RefLineLyr, "CLEAR_SELECTION", "")

        # Select any existing Reference points for specified basin and delete
        arcpy.MakeFeatureLayer_management(stakeoutPoints, stakeoutPointsLyr)
        arcpy.SelectLayerByAttribute_management(stakeoutPointsLyr, "NEW_SELECTION", exp)
        arcpy.MakeFeatureLayer_management(stakeoutPointsLyr, pointsSelection)
        if int(arcpy.GetCount_management(pointsSelection).getOutput(0)) > 0:
            arcpy.DeleteFeatures_management(pointsSelection)
        arcpy.SelectLayerByAttribute_management(stakeoutPointsLyr, "CLEAR_SELECTION")

        # Create Intake from user input and append to Stakeout Points
        AddMsgAndPrint("\nCreating Intake Reference Point")
        intake = arcpy.CreateScratchName("intake",data_type="FeatureClass",workspace="in_memory")
        arcpy.CopyFeatures_management(IntakeLocation, intake)
        arcpy.AddField_management(intake, "ID", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        arcpy.AddField_management(intake, "Subbasin", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        arcpy.AddField_management(intake, "Elev", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        arcpy.AddField_management(intake, "Notes", "TEXT", "", "", "50", "", "NULLABLE", "NON_REQUIRED", "")

        arcpy.CalculateField_management(intake, "Id", "" + str(Subbasin)+ "", "PYTHON3")
        arcpy.CalculateField_management(intake, "Subbasin", "" + str(Subbasin)+ "", "PYTHON3")
        arcpy.CalculateField_management(intake, "Elev", "" + str(IntakeElev)+ "", "PYTHON3")
        arcpy.CalculateField_management(intake, "Notes", "\"Intake\"", "PYTHON3")
        AddMsgAndPrint("\tSuccessfully created intake for subbasin " + str(Subbasin) + " at " + str(IntakeElev) + " feet",0)

        AddMsgAndPrint("\tAppending results to Stakeout Points...",0)
        arcpy.Append_management(intake, stakeoutPoints, "NO_TEST", "", "")

        # Use DEM to determine intersection of Reference Line and Plane @ Design Elevation
        AddMsgAndPrint("\nCalculating Pool Extent")
        arcpy.SelectLayerByAttribute_management(inWatershed, "NEW_SELECTION", exp)
        WSmask = arcpy.CreateScratchName("WSmask",data_type="FeatureClass",workspace="in_memory")
        arcpy.CopyFeatures_management(inWatershed, WSmask)
        arcpy.SelectLayerByAttribute_management(inWatershed, "CLEAR_SELECTION")

        DA_Dem = ExtractByMask(ProjectDEM, WSmask)
        DA_sn = SetNull(DA_Dem, DA_Dem, "VALUE > " + str(DesignElev))
        DAx0 = arcpy.sa.Times(DA_sn, 0)
        DAint = Int(DAx0)

        DA_snPoly = arcpy.CreateScratchName("DA_snPoly",data_type="FeatureClass",workspace="in_memory")
        arcpy.RasterToPolygon_conversion(DAint, DA_snPoly, "NO_SIMPLIFY", "VALUE")

        AddMsgAndPrint("\nCreating Embankment Reference Points")
        refTempClip = arcpy.CreateScratchName("refTempClip",data_type="FeatureClass",workspace="in_memory")
        arcpy.Clip_analysis(refTemp, DA_snPoly, refTempClip)

        refPoints = arcpy.CreateScratchName("refPoints",data_type="FeatureClass",workspace="in_memory")
        arcpy.FeatureVerticesToPoints_management(refTempClip, refPoints, "BOTH_ENDS")
        AddMsgAndPrint("\tSuccessfully created " +  str(int(arcpy.GetCount_management(refPoints).getOutput(0))) + " reference points at " + str(DesignElev) + " feet",0)

        arcpy.AddField_management(refPoints, "Id", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED")
        arcpy.CalculateField_management(refPoints, "Id", "" + str(Subbasin)+ "", "PYTHON3")

        arcpy.AddField_management(refPoints, "Elev", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")
        arcpy.CalculateField_management(refPoints, "Elev", "" + str(DesignElev)+ "", "PYTHON3")

        arcpy.AddField_management(refPoints, "Notes", "TEXT", "", "", "50", "", "NULLABLE", "NON_REQUIRED")
        arcpy.CalculateField_management(refPoints, "Notes", "\"Embankment\"", "PYTHON3")

        AddMsgAndPrint("\tAppending Results to Stakeout Points...",0)
        arcpy.Append_management(refPoints, stakeoutPoints, "NO_TEST")

        # Add XY Coordinates to Stakeout Points
        AddMsgAndPrint("\nAdding XY Coordinates to Stakeout Points")
        arcpy.AddXY_management(stakeoutPoints)

        # ------------------------------------------------------------------------------------------------ Compact FGDB
        arcpy.Compact_management(watershedGDB_path)
        AddMsgAndPrint(" \nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path),0)

        # ------------------------------------------------------------------------------------------------ add to ArcMap
        AddMsgAndPrint("\nAdding Results to ArcGIS Pro")
        arcpy.SetParameterAsText(5, stakeoutPoints)

        AddMsgAndPrint("\nProcessing Finished!\n")

    except:
        print_exception()

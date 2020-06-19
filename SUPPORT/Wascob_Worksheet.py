# ==========================================================================================
# Name: Wascob_Worksheet.py
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

# Created by Peter Mead, Adolfo Diaz, USDA NRCS, 2013
# Updated by Chris Morse, USDA NRCS, 2019

# ==========================================================================================
# Updated  6/19/2020 - Adolfo Diaz
#
# - Updated and Tested for ArcGIS Pro 2.4.2 and python 3.6
# - All describe functions use the arcpy.da.Describe functionality.
# - All field calculation expressions are in PYTHON3 format.
# - All cursors were updated to arcpy.da
# - Updated AddMsgAndPrint to remove ArcGIS 10 boolean and gp function
# - Updated print_exception function.  Traceback functions slightly changed for Python 3.6.
# - Added parallel processing factor environment
# - swithced from sys.exit() to exit()
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
    f.write("Executing \"6. Wascob Design Worksheet\" tool\n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write(arcInfo['ProductName'] + ": " + arcInfo['Version'] + "\n")
    f.write("User Parameters:\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tInput Watershed: " + inWatershed + "\n")

    f.close
    del f

## ================================================================================================================
# Import system modules
import arcpy, sys, os, traceback, subprocess, time, shutil

if __name__ == '__main__':

    try:

        # ---------------------------------------------- Input Parameters
        inWatershed = arcpy.GetParameterAsText(0)

        # Environment settings
        arcpy.env.overwriteOutput = True
        arcpy.env.parallelProcessingFactor = "75%"
        arcpy.env.geographicTransformations = "WGS_1984_(ITRF00)_To_NAD_1983"
        arcpy.env.resamplingMethod = "BILINEAR"
        arcpy.env.pyramid = "PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP"

        # ---------------------------------------------- Variables
        watershed_path = arcpy.da.Describe(inWatershed)['catalogPath']
        watershedGDB_path = watershed_path[:watershed_path .find(".gdb")+4]
        watershedFD_path = watershedGDB_path + os.sep + "Layers"
        watershedGDB_name = os.path.basename(watershedGDB_path)
        userWorkspace = os.path.dirname(watershedGDB_path)
        wsName = os.path.basename(inWatershed)
        outputFolder = userWorkspace + os.sep + "gis_output"
        tables = outputFolder + os.sep + "tables"
        Documents = userWorkspace + os.sep + "Documents"

        # Set path to log file and start logging
        textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.txt"
        logBasicSettings()

        # ------------------------------------------------ Existing Data
        inWorksheet = os.path.join(os.path.dirname(sys.argv[0]), "LiDAR_WASCOB.xlsm")
        rcn = watershedFD_path + os.sep + wsName + "_RCN"

        # ------------------------------------------------ Permanent Datasets
        stakeoutPoints = watershedFD_path + os.sep + "stakeoutPoints"
        rcnTable = tables + os.sep + "RCNsummary.dbf"
        watershedTable = tables + os.sep + "watershed.dbf"

        # ---------------------------- Layers in ArcMap
        outPoints = "StakeoutPoints"

        # Check inputs and workspace
        AddMsgAndPrint("\nChecking inputs...",0)

        # Make sure RCN layer was created
        if not arcpy.Exists(rcn):
            AddMsgAndPrint("\t" + str(os.path.basename(rcn)) + " not found in " + str(watershedGDB_name),2)
            AddMsgAndPrint("\tYou must run Tool #5: \"Calculate Runoff Curve Number\" before executing this tool. Exiting",2)
            exit()

        # Make Sure RCN Field is in the Watershed
        if not len(arcpy.ListFields(inWatershed,"RCN")) > 0:
            AddMsgAndPrint("\tRCN Field not found in " + str(wsName),2)
            AddMsgAndPrint("\tYou must run Tool #5: \"Calculate Runoff Curve Number\" before executing this tool. Exiting",2)
            exit()

        # Make Sure RCN Field has valid value(s)
        #expression = arcpy.AddFieldDelimiters(inWatershed, 'RCN') + " IS NULL OR " + arcpy.AddFieldDelimiters(inWatershed, 'RCN') + " = \'\'"
        expression = arcpy.AddFieldDelimiters(inWatershed, 'RCN') + " IS NULL"
        nullRCNValues = [row[0] for row in arcpy.da.SearchCursor(inWatershed, ['RCN'],where_clause=expression)]

        if len(nullRCNValues) > 0:
            AddMsgAndPrint("\tRCN Field in " + str(wsName) + " contains invalid or Null values!",2)
            AddMsgAndPrint("\tRe-run Tool #5: \"Calculate Runoff Curve Number\" or manually correct RCN value(s). Exiting...",2)
            exit()

        # Make sure Wacob Worksheet template exists
        if not arcpy.Exists(inWorksheet):
            AddMsgAndPrint("\tLiDAR_WASCOB.xlsm Worksheet template not found in " + str(os.path.dirname(sys.argv[0])),2)
            AddMsgAndPrint("\tPlease Check the Support Folder and replace the file if necessary. Exiting...",2)
            sys.exit()

        # Check Addnt'l directories
        if not arcpy.Exists(outputFolder):
            arcpy.CreateFolder_management(userWorkspace, "gis_output")
        if not arcpy.Exists(tables):
            arcpy.CreateFolder_management(outputFolder, "tables")

        # If Documents folder not present, create and copy required files to it
        if not arcpy.Exists(Documents):
            arcpy.CreateFolder_management(userWorkspace, "Documents")
            DocumentsFolder =  os.path.join(os.path.dirname(sys.argv[0]), "Documents")
            if arcpy.Exists(DocumentsFolder):
                arcpy.Copy_management(DocumentsFolder, Documents, "Folder")
            del DocumentsFolder

        # Copy User Watershed and RCN Layer tables for spreadsheet import
        AddMsgAndPrint("\nCopying results to tables\n")
        arcpy.CopyRows_management(inWatershed, watershedTable)
        arcpy.CopyRows_management(rcn, rcnTable)

        # ------------------------------------------------------------------ Create Wascob Worksheet
        #os.path.basename(userWorkspace).replace(" ","_") + "_Wascob.gdb"
        outWorksheet = Documents + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_WASCOB.xlsm"
        x = 1
        while x > 0:
            if arcpy.Exists(outWorksheet):
                outWorksheet = Documents + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_WASCOB" + str(x) + ".xlsm"
                x += 1
            else:
                x = 0
        del x

        # Copy template and save as defined
        shutil.copyfile(inWorksheet, outWorksheet)

        # --------------------------------------------------------------------------- Create Stakeout Points FC
        if not arcpy.Exists(outPoints):

            arcpy.CreateFeatureclass_management(watershedFD_path, "stakeoutPoints", "POINT", "", "DISABLED", "DISABLED", "", "", "0", "0", "0")
            arcpy.AddField_management(stakeoutPoints, "ID", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
            arcpy.AddField_management(stakeoutPoints, "Subbasin", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
            arcpy.AddField_management(stakeoutPoints, "Elev", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
            arcpy.AddField_management(stakeoutPoints, "Notes", "TEXT", "", "", "50", "", "NULLABLE", "NON_REQUIRED", "")

            # ------------------------------------------------------------------------------------------------ Compact FGDB
            arcpy.Compact_management(watershedGDB_path)

            # ------------------------------------------------------------------------------------------------ add to ArcMap
            AddMsgAndPrint("\nAdding Stakeout Points to ArcGIS Pro Session\n")
            arcpy.SetParameterAsText(1, stakeoutPoints)

        # ----------------------------------------------------------------------- Launch Wascob Spreadsheet
        AddMsgAndPrint("\n===============================================================")
        AddMsgAndPrint("\tThe LiDAR_WASCOB Spreadsheet will open in Microsoft Excel")
        AddMsgAndPrint("\tand has been saved to " + str(userWorkspace)+ " \Documents.")
        AddMsgAndPrint("\tIf the file doesn't open automatically, navigate to the above ")
        AddMsgAndPrint("\tlocation and open it manually.")
        AddMsgAndPrint("\tOnce Excel is open, enable macros (if not already enabled),")
        AddMsgAndPrint("\tand set the path to your project folder to import your gis data.")
        AddMsgAndPrint("\tOnce you have completed the Wascob Design Sheet(s) you can return ")
        AddMsgAndPrint("\tto ArcMap and complete the degign height and tile layout steps.")
        AddMsgAndPrint("\n===============================================================")

        try:
            os.startfile(outWorksheet)
        except:
            AddMsgAndPrint("\tCould not open the Excel Worksheet. Please open it manually.",0)

        AddMsgAndPrint("\nProcessing Finished\n",0)

    except:
        print_exception()


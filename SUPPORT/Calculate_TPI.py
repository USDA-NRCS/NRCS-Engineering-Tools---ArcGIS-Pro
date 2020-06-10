# ==========================================================================================
# Name: Calculate_TPI.py
#
# Author: Peter Mead
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
#
# ==========================================================================================
# Updated  6/10/2020 - Adolfo Diaz
#
# - Updated and Tested for ArcGIS Pro 2.4.2 and python 3.6
# - All temporary raster layers such as Fill and Minus are stored in Memory and no longer
#   written to hard disk.
# - All describe functions use the arcpy.da.Describe functionality.
# - Updated AddMsgAndPrint to remove ArcGIS 10 boolean and gp function
# - Updated print_exception function.  Traceback functions slightly changed for Python 3.6.
# - Added Snap Raster environment
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
    f.write(" \n################################################################################################################ \n")
    f.write("Executing \"Topographic Position Index\" Tool \n")
    f.write("User Name: " + getpass.getuser() + " \n")
    f.write("Date Executed: " + time.ctime() + " \n")
    f.write(arcInfo['ProductName'] + ": " + arcInfo['Version'] + "\n")
    f.write("User Parameters:\n")
    f.write(" \tWorkspace: " + userWorkspace + " \n")
    f.write(" \tInput DEM: " + inputDEM + " \n")
    if len(inWatershed) > 0:
        f.write(" \tClipping set to mask: " + inWatershed + " \n")
    else:
        f.write(" \tClipping: NOT SELECTED\n")

    f.close
    del f

## ================================================================================================================
# Import system modules
import arcpy, sys, os, string, traceback
from arcpy.sa import *

if __name__ == '__main__':

    try:
        # Check out Spatial Analyst License
        if arcpy.CheckExtension("spatial") == "Available":
            arcpy.CheckOutExtension("spatial")
        else:
            arcpy.AddError("Spatial Analyst Extension not enabled. Please enable Spatial analyst from the Tools/Extensions menu\n",2)
            exit()

        # -------------------------------------------------------------------------------------------- Input Parameters
        inputDEM = arcpy.GetParameterAsText(0)
        inWatershed = arcpy.GetParameterAsText(1)

        if len(inWatershed) > 0:
            bClip = True
        else:
            bClip = False

        # --------------------------------------------------------------------- Define Variables
        # Input DEM Spatial Reference Information
        demPath = arcpy.da.Describe(inputDEM)['catalogPath']
        demDesc = arcpy.da.Describe(demPath)
        demName = demDesc['name']
        demCellSize = demDesc['meanCellWidth']
        demSR = demDesc['spatialReference']
        demSRname = demSR.name
        demLinearUnits = demSR.linearUnitName

        # Set environmental variables
        arcpy.env.parallelProcessingFactor = "75%"
        arcpy.env.overwriteOutput = True

        # AOI DEM must be from a engineering tools file geodatabase
        if not demPath.find('_EngTools.gdb') > -1:
            arcpy.AddError("\n\nInput AOI DEM is not in a \"xx_EngTools.gdb\" file geodatabase.")
            arcpy.AddError("\n\nYou must provide a DEM prepared with the Define Area of Interest Tool.... ....EXITING")
            exit()

        watershedGDB_path = demPath[:demPath.find(".gdb")+4]
        userWorkspace = os.path.dirname(watershedGDB_path)
        watershedGDB_name = os.path.basename(watershedGDB_path)
        projectName = arcpy.ValidateTableName(os.path.basename(userWorkspace).replace(" ","_"))

        # Path of Log file
        textFilePath = userWorkspace + os.sep + projectName + "_EngTools.txt"

        # record basic user inputs and settings to log file for future purposes
        logBasicSettings()

        # -------------------------------------------------------------------- Permanent Datasets
        tpiOut = watershedGDB_path + os.sep + projectName + "_TPI"

        #-------------------------------------------------------------------- Get Raster Properties
        AddMsgAndPrint("\nDEM information: " + demName + ":")
        AddMsgAndPrint("\n\tProjection Name: " + demSRname)
        AddMsgAndPrint("\tXY Linear Units: " + demLinearUnits)
        AddMsgAndPrint("\tCell Size: " + str(demCellSize) + " " + demLinearUnits)

        # ----------------------------------- Set Environment Settings
        arcpy.env.extent = "MINOF"
        arcpy.env.cellSize = demCellSize
        arcpy.env.snapRaster = demPath
        arcpy.env.outputCoordinateSystem = demSR

        # ---------------------------------------------------------------------------- If user provided a mask clip inputs first.
        if bClip:

            # Clip inputs to input Mask
            AddMsgAndPrint("\nClipping Input DEM to " + str(os.path.basename(inWatershed)))
            DEMclip = ExtractByMask(inputDEM, inWatershed)

            # Reset path to DEM
            inputDEM = DEMclip

        # --------------------------------------------------------------------------------- Create TPI
        AddMsgAndPrint("\nCalculating Topographic Position Index")

        # Smooth the DEM to generalize cell transitions
        DEMsmooth = FocalStatistics(inputDEM,"RECTANGLE 3 3 CELL","MEAN","DATA")

        # Subtract the original surface to create tpi
        TPI = Minus(DEMsmooth,inputDEM)

        if arcpy.Exists(tpiOut):
            arcpy.Delete_management(tpiOut)

        TPI.save(tpiOut)
        AddMsgAndPrint("\n\tSuccessfully Calculated Topographic Position Index")

        # ----------------------------------------------------------------------- Compact FGDB
        arcpy.Compact_management(watershedGDB_path)
        AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path))

        # ------------------------------------------------------------ Prepare to Add to Arcmap
        arcpy.SetParameterAsText(2, tpiOut)
        AddMsgAndPrint("\n\tOverlay the results with a hillshade to best view cell transitions")
        AddMsgAndPrint("\nProcessing Completed!")

    except:
        print_exception()
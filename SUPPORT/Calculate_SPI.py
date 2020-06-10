# ==========================================================================================
# Name: Calculate_SPI.py
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
# Updated  6/9/2020 - Adolfo Diaz
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
    f.write("Executing \"Stream Power Index\" Tool \n")
    f.write("User Name: " + getpass.getuser() + " \n")
    f.write("Date Executed: " + time.ctime() + " \n")
    f.write(arcInfo['ProductName'] + ": " + arcInfo['Version'] + "\n")
    f.write("User Parameters:\n")
    f.write(" \tWorkspace: " + userWorkspace + " \n")
    f.write(" \tInput DEM: " + inputDEM + " \n")
    f.write(" \tInput Flow Dir Grid: " + FlowDir + " \n")
    f.write(" \tInput Flow Accumulation Grid: " + FlowAccum + " \n")
    f.write(" \tOverland Flow Threshold: " + str(minFlow) + " feet\n")
    f.write(" \tIn Channel Threshold: " + str(maxDA) + " feet\n")

    f.write(" \tInput Z Units: " + str(zUnits) + " \n")

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
from math import cos, sin, asin, sqrt, radians

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
        zUnits = arcpy.GetParameterAsText(1)
        inWatershed = arcpy.GetParameterAsText(2)
        minFlow = arcpy.GetParameterAsText(3)
        maxDA = arcpy.GetParameterAsText(4)

        # Set environmental variables
        arcpy.env.parallelProcessingFactor = "75%"
        arcpy.env.overwriteOutput = True

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

        # AOI DEM must be from a engineering tools file geodatabase
        if not demPath.find('_EngTools.gdb') > -1:
            AddMsgAndPrint("\n\nInput AOI DEM is not in a \"xx_EngTools.gdb\" file geodatabase.",2)
            AddMsgAndPrint("\n\nYou must provide a DEM prepared with the Define Area of Interest Tool.... ....EXITING",2)
            exit()

        watershedGDB_path = demPath[:demPath.find(".gdb")+4]
        userWorkspace = os.path.dirname(watershedGDB_path)
        watershedGDB_name = os.path.basename(watershedGDB_path)
        projectName = arcpy.ValidateTableName(os.path.basename(userWorkspace).replace(" ","_"))

        # -------------------------------------------------------------------- Permanent Datasets
        spiOut = watershedGDB_path + os.sep + projectName + "_SPI"

        # -------------------------------------------------------------------- Required Existing Inputs
        FlowAccum = watershedGDB_path + os.sep + "flowAccumulation"
        FlowDir = watershedGDB_path + os.sep + "flowDirection"

        # Path of Log file
        textFilePath = userWorkspace + os.sep + projectName + "_EngTools.txt"

        # record basic user inputs and settings to log file for future purposes
        logBasicSettings()

        # ------------------------------------------------------------------- Check some parameters
        # Flow Accum and Flow Dir must be in project gdb
        if not arcpy.Exists(FlowDir):
            AddMsgAndPrint("\n\nFlow Direction grid not found in same directory as " + demName + " (" + watershedGDB_path + "/" + watershedGDB_name + ")",2)
            AddMsgAndPrint("\nYou Must run the \"Create Stream\" Network Tool to create Flow Direction/Accumulation Grids....EXITING\n",2)
            exit()

        if not arcpy.Exists(FlowAccum):
            AddMsgAndPrint("\n\nFlow Accumulation grid not found in same directory as " + demName + " (" + watershedGDB_path + "/" + watershedGDB_name + ")",2)
            AddMsgAndPrint("\nYou Must run the \"Create Stream\" Network Tool to create Flow Direction/Accumulation Grids....EXITING\n",2)
            exit()

        # float minFlow and MaxDA as a failsafe...
        try:
            float(minFlow)
        except:
            AddMsgAndPrint("\n\nMinimum flow threshold is invalid... ...provide an integer and try again....EXITING",2)
            exit()
        try:
            float(maxDA)
        except:
            AddMsgAndPrint("\n\nIn channel-threshold is invalid... ...provide an integer and try again....EXITING",2)
            exit()

        ## ---------------------------------------------------------------------------------------------- Z-factor conversion Lookup table
        # lookup dictionary to convert XY units to area.  Key = XY unit of DEM; Value = conversion factor to sq.meters
        acreConversionDict = {'Meters':4046.8564224,'Meter':4046.8564224,'Foot':43560,'Foot_US':43560,'Feet':43560, 'Centimeter':40470000,'Inch':6273000}

        # Assign Z-factor based on XY and Z units of DEM
        # the following represents a matrix of possible z-Factors
        # using different combination of xy and z units
        # ----------------------------------------------------
        #                      Z - Units
        #                       Meter    Foot     Centimeter     Inch
        #          Meter         1	    0.3048	    0.01	    0.0254
        #  XY      Foot        3.28084	  1	      0.0328084	    0.083333
        # Units    Centimeter   100	    30.48	     1	         2.54
        #          Inch        39.3701	  12       0.393701	      1
        # ---------------------------------------------------

        unitLookUpDict = {'Meter':0,'Meters':0,'Foot':1,'Foot_US':1,'Feet':1,'Centimeter':2,'Centimeters':2,'Inch':3,'Inches':3}

        zFactorList = [[1.0,     0.3048, 0.01,      0.0254],
                       [3.28084, 1.0,    0.0328084, 0.083333],
                       [100.0,   30.48,  1.0,       2.54],
                       [39.3701, 12.0,   0.393701,  1.0]]

        AddMsgAndPrint("\nDEM information: " + demName + ":")
        AddMsgAndPrint("\n\tProjection Name: " + demSRname)
        AddMsgAndPrint("\tXY Linear Units: " + demLinearUnits)
        AddMsgAndPrint("\tElevation Values (Z): " + zUnits)
        AddMsgAndPrint("\tCell Size: " + str(demCellSize) + " " + demLinearUnits)

        # ----------------------------------- Set Environment Settings
        arcpy.env.extent = "MINOF"
        arcpy.env.cellSize = demCellSize
        arcpy.env.snapRaster = demPath
        arcpy.env.outputCoordinateSystem = demSR

        # -------------------------------------------------------------------------- Calculate overland and in-channel thresholds

        # Set Minimum flow length / In channel threshold to proper units
        if demLinearUnits in ('Foot','Foot_US','Feet'):
            overlandThresh = minFlow
            channelThresh = float(maxDA) * 43560 / demCellSize**2

        elif demLinearUnits in ('Meter','Meters'):
            overlandThresh = float(minFlow) / 3.280839895013123
            channelThresh = float(maxDA) * 4046 / demCellSize**2

        else:
            AddMsgAndPrint("\nCould not determine linear units",2)
            exit()

        # ---------------------------------------------------------------------------- If user provided a mask clip inputs first.
        if bClip:

            # Clip inputs to input Mask
            AddMsgAndPrint("\nClipping Grids to " + str(os.path.basename(inWatershed)))
            DEMclip = ExtractByMask(inputDEM, inWatershed)

            FDRclip = ExtractByMask(FlowDir, inWatershed)
            AddMsgAndPrint("\tSuccessfully clipped Flow Accumulation")

            FACclip = ExtractByMask(FlowAccum, inWatershed)
            AddMsgAndPrint("\tSuccessfully clipped Flow Accumulation")

            # Reset paths to DEM and Flow Accum
            inputDEM = DEMclip
            FlowDir = FDRclip
            FlowAccum = FACclip

        # ----------------------------------------------------------------------------- Prefilter FlowAccum Based on Flow Length and Drain Area
        arcpy.SetProgressorLabel("Filtering flow accumulation based on flow length and contributing area")

        # Calculate Upstream Flow Length
        AddMsgAndPrint("\nCalculating Upstream Flow Lengths")
        FlowLen = FlowLength(Raster(FlowDir),"UPSTREAM")

        # Filter Out Overland Flow
        expression = "\"VALUE\" < " + str(overlandThresh)
        AddMsgAndPrint("\tFiltering out flow accumulation with overland flow < " + str(minFlow) + " feet")
        facFilt1 = SetNull(Raster(FlowAccum), FlowLen, expression)

        # Filter Out Channelized Flow
        expression = "\"VALUE\" > " + str(channelThresh)
        AddMsgAndPrint("\tFiltering out channelized flow with > " + str(maxDA) + " Acre Drainage Area")
        facFilt2 = SetNull(facFilt1, facFilt1, expression)

        # --------------------------------------------------------------------------------- Calculate Slope Grid
        zFactor = zFactorList[unitLookUpDict.get(zUnits)][unitLookUpDict.get(demLinearUnits)]
        AddMsgAndPrint("\nPreparing Slope Grid using a Z-Factor of " + str(zFactor))

        # Smooth the DEM to remove imperfections in drop
        AddMsgAndPrint("\tSmoothing the Raw DEM")
        smoothDEM = FocalStatistics(inputDEM, "RECTANGLE 3 3 CELL","MEAN","DATA")

        # Calculate percent slope with proper Z Factor
        AddMsgAndPrint("\tCalculating percent slope")
        slope = Slope(smoothDEM, "PERCENT_RISE", zFactor)

        # --------------------------------------------------------------------------------- Create and Filter Stream Power Index
        # Calculate SPI
        AddMsgAndPrint("\nCalculating Stream Power Index")
        spiTemp = Raster(Ln(Times(Plus(facFilt2,0.001),Plus(Divide(slope,100),0.001))))

        AddMsgAndPrint("\nFiltering index values")

        # Set Values < 0 to null
        setNegativeNulls = SetNull(spiTemp, spiTemp, "VALUE<=0.0")

        if arcpy.Exists(spiOut):
            arcpy.Delete_management(spiOut)

        setNegativeNulls.save(spiOut)

        # ----------------------------------------------------------------------- Compact FGDB
        arcpy.Compact_management(watershedGDB_path)
        AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path))

        # ------------------------------------------------------------ Prepare to Add to Arcmap
        arcpy.SetParameterAsText(5, spiOut)
        AddMsgAndPrint("\nProcessing Completed!")

    except:
        print_exception()

# ==========================================================================================
# Name: Calculate_CTI.py
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
# Updated  6/8/2020 - Adolfo Diaz

# - The CTI equation was updated to the follwowing equation: Ln [a/tan ß], where:
#        a represents the catchment area per pixel
#        ß refers to the slope, in degrees
# - CTI information and the equation used can be accessed here:
#   https://wikispaces.psu.edu/display/AnthSpace/Compound+Topographic+Index
# - The arcpy geoprocessing closely follows the following site:
#   https://github.com/jeffreyevans/GradientMetrics/blob/master/scripts/cti.py
# - Updated and Tested for ArcGIS Pro 2.4.2 and python 3.6
# - Added functionality to utilize a DEM image service or a DEM in GCS.  Added 2 new
#   function to handle this capability: extractSubsetFromGCSdem and getPCSresolutionFromGCSraster.
# - If GCS DEM is used then the coordinate system of the FGDB will become the same as the AOI
#   assuming the AOI is in a PCS.  If both AOI and DEM are in a GCS then the tool will exit.
# - All temporary raster layers such as Fill and Minus are stored in Memory and no longer
#   written to hard disk.
# - All describe functions use the arcpy.da.Describe functionality.
# - All intermediate datasets are written to "in_memory" instead of written to a FGDB and
#   and later deleted.  This avoids having to check and delete intermediate data during every
#   execution.
# - All field calculation expressions are in PYTHON3 format.
# - Used acre conversiont dictionary and z-factor lookup table
# - All cursors were updated to arcpy.da
# - Added code to remove layers from an .aprx rather than simply deleting them
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

    try:

        import getpass, time
        arcInfo = arcpy.GetInstallInfo()  # dict of ArcGIS Pro information

        f = open(textFilePath,'a+')
        f.write(" \n################################################################################################################ \n")
        f.write("Executing \"Compound Topographic Index\" Tool \n")
        f.write("User Name: " + getpass.getuser() + " \n")
        f.write("Date Executed: " + time.ctime() + " \n")
        f.write(arcInfo['ProductName'] + ": " + arcInfo['Version'] + "\n")
        f.write("User Parameters:\n")
        f.write(" \tWorkspace: " + userWorkspace + " \n")
        f.write(" \tInput DEM: " + inputDEM + " \n")
        f.write(" \tInput Flow Accumulation Grid: " + FlowAccum + " \n")

        if len(zUnits) < 1:
            f.write(" \tInput Z Units: BLANK \n")
        else:
            f.write(" \tInput Z Units: " + str(zUnits) + " \n")
        if len(inWatershed) > 0:
            f.write(" \tClipping set to mask: " + inWatershed + " \n")
        else:
            f.write(" \tClipping: NOT SELECTED\n")

        f.close
        del f

    except:
        print_exception()
        exit()

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
            arcpy.AddError("\n\nInput AOI DEM is not in a \"xx_EngTools.gdb\" file geodatabase.")
            arcpy.AddError("\n\nYou must provide a DEM prepared with the Define Area of Interest Tool.... ....EXITING")
            exit()

        watershedGDB_path = demPath[:demPath.find(".gdb")+4]
        userWorkspace = os.path.dirname(watershedGDB_path)
        watershedGDB_name = os.path.basename(watershedGDB_path)
        projectName = arcpy.ValidateTableName(os.path.basename(userWorkspace).replace(" ","_"))

        # -------------------------------------------------------------------- Permanent Datasets
        ctiOut = watershedGDB_path + os.sep + projectName + "_CTI"

        # Path of Log file
        textFilePath = userWorkspace + os.sep + projectName + "_EngTools.txt"

        # ------------------------------------------------------------------- Check some parameters
        FlowAccum = watershedGDB_path + os.sep + "flowAccumulation"

        # record basic user inputs and settings to log file for future purposes
        logBasicSettings()

        # Flow Accum and Flow Dir must be in project gdb
        if not arcpy.Exists(FlowAccum):
            AddMsgAndPrint("\n\nFlow Accumulation grid not found in same directory as " + str(os.path.basename(inputDEM)) + " (" + watershedGDB_path + "/" + watershedGDB_name + ")",2)
            AddMsgAndPrint("\nYou Must run the \"Create Stream\" Network Tool to create Flow Direction/Accumulation Grids....EXITING\n",2)
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

        # ---------------------------------------------------------------------------- If user provided a mask clip inputs first.
        if bClip:

            # Clip inputs to input Mask
            AddMsgAndPrint("\nClipping Grids to " + str(os.path.basename(inWatershed)))
            DEMclip = ExtractByMask(inputDEM, inWatershed)

            FACclip = ExtractByMask(FlowAccum, inWatershed)
            AddMsgAndPrint("\tSuccessfully clipped Flow Accumulation")

            # Reset paths to DEM and Flow Accum
            inputDEM = DEMclip
            FlowAccum = FACclip

        # --------------------------------------------------------------------------------- Create and Filter CTI
        # CTI is defined by the following equation: Ln [a/tan ß], where:
        # a represents the catchment area per pixel
        # ß refers to the slope, in degrees
        # Final equation is Ln (As / tan ß)
        arcpy.SetProgressorLabel("Computing Compound Topographic Index")

        # In the above equation, a needs to be converted to As so as to account for DEM resolution
        flowAccumulation = Raster(FlowAccum)
        As = Times(Plus(flowAccumulation,1),demCellSize)

        # Calculate slope (ß) in degrees.
        arcpy.SetProgressorLabel("Calculating Slope in Degrees")
        zFactor = zFactorList[unitLookUpDict.get(zUnits)][unitLookUpDict.get(demLinearUnits)]
        DEMsmooth = FocalStatistics(inputDEM,"RECTANGLE 3 3 CELL","MEAN","DATA")
        slopeDegree = Slope(DEMsmooth, "DEGREE", zFactor)
        AddMsgAndPrint("\nCalculated Slope in Degrees using a Z-Factor of " + str(zFactor))

        # Convert slope (ß) to radians / 90
        # 1.570796 values comes from (pi / 2)
        arcpy.SetProgressorLabel("Converting Slope to Radians")
        slopeToRadians = Divide(Times(slopeDegree,1.570796),90)

        # denomoniator of the above equation
        # If slope value is greater than 0 compute the tangent of the slope value
        # otherwise assign 0.001 - why 0.001???
        arcpy.SetProgressorLabel("Calculating Tangent of Slope values")
        tanSlope = Con(slopeToRadians > 0, Tan(slopeToRadians), 0.001 )

        # Final Equation
        arcpy.SetProgressorLabel("Calculating Compound Topographic Index")
        naturalLog = Ln(Divide(As,tanSlope))
        AddMsgAndPrint("\nCalculated Compound Topographic Index")

        if arcpy.Exists(ctiOut):
            arcpy.Delete_management(ctiOut)

        naturalLog.save(ctiOut)

        # ----------------------------------------------------------------------- Compact FGDB
        arcpy.SetProgressorLabel("Compacting " + os.path.basename(watershedGDB_path))
        arcpy.Compact_management(watershedGDB_path)
        AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path))

        # ------------------------------------------------------------ Add data to ArcGIS Pro
        arcpy.SetParameterAsText(3, ctiOut)
        AddMsgAndPrint("\nProcessing Completed!")

    except:
        print_exception()

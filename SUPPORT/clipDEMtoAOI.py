# ==========================================================================================
# Name: Clip DEM to AOI
#
# Author: Peter Mead
# e-mail: pemead@co.becker.mn.us
#
# Author: Chris Morse
#         IN State GIS Coordinator
#         USDA - NRCS
# e-mail: chris.morse@usda.gov
# phone: 317.501.1578
#
# Author: Adolfo.Diaz
#         GIS Specialist
#         National Soil Survey Center
#         USDA - NRCS
# e-mail: adolfo.diaz@usda.gov
# phone: 608.662.4422 ext. 216

# Created by Peter Mead, Adolfo Diaz, USDA NRCS, 2013
# Updated by Chris Morse, USDA NRCS, 2019

# ==========================================================================================
# Updated  3/6/2020 - Adolfo Diaz
# - Updated and Tested for ArcGIS Pro 2.4.2 and python 3.6
# - Added Snap Raster environment
# - Added parallel processing factor environment

## ================================================================================================================
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

        if severity == 0:
            arcpy.AddMessage(msg)
        elif severity == 1:
            arcpy.AddWarning(msg)
        elif severity == 2:
            arcpy.AddError(msg)

    except:
        pass

## ================================================================================================================
def logBasicSettings():
    # record basic user inputs and settings to log file for future purposes

    import getpass, time

    f = open(textFilePath,'a+')
    f.write("\n##################################################################\n")
    f.write("Executing \"Clip DEM to AOI\" Tool" + "\n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write("ArcGIS Version: " + str(arcpy.GetInstallInfo()['Version']) + "\n")
    f.write("User Parameters:\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tInput DEM: " + inputDEM + "\n")
    f.write("\tOutput DEM: " + outputDEM + "\n")

    f.close
    del f

## ================================================================================================================
# Import system modules
import arcpy, sys, os, traceback

if __name__ == '__main__':

    try:

        # Check out Spatial Analyst License
        if arcpy.CheckExtension("Spatial") == "Available":
            arcpy.CheckOutExtension("Spatial")
        else:
            arcpy.AddError("\nSpatial Analyst Extension not enabled. Please enable Spatial Analyst from the Tools/Extensions menu. Exiting...\n")
            sys.exit()

        arcpy.SetProgressorLabel("Setting Variables")
        # --------------------------------------------------------------------- Input Parameters
        inputDEM = arcpy.GetParameterAsText(0)
        inMask = arcpy.GetParameterAsText(1)
        outputDEM = arcpy.GetParameterAsText(2)

        # --------------------------------------------------------------------- Directory Paths
        userWorkspace = os.path.dirname(os.path.realpath(outputDEM))
        demName = os.path.splitext(os.path.basename(outputDEM))[0]

        # Environment settings
        arcpy.env.overwriteOutput = True
        arcpy.env.geographicTransformations = "WGS_1984_(ITRF00)_To_NAD_1983"
        arcpy.env.resamplingMethod = "BILINEAR"
        arcpy.env.pyramid = "PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP"
        arcpy.env.parallelProcessingFactor = "75%"

        # log inputs and settings to file
        textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.txt"
        logBasicSettings()

        # --------------------------------------------------------------------- Basic Checks before processing
        arcpy.SetProgressorLabel("Validating Inputs")
        AddMsgAndPrint("\nValidating Inputs...",0)

        # Exit if no AOI provided
        if not int(arcpy.GetCount_management(inMask).getOutput(0)) > 0:
            AddMsgAndPrint("\nNo area of interest was provided, you must digitize or select a mask. Exiting...",2)
            sys.exit()

        # Exit if AOI contains more than 1 digitized area.
        if int(arcpy.GetCount_management(inMask).getOutput(0)) > 1:
            AddMsgAndPrint("\nYou can only digitize one Area of Interest or provide a single feature. Please try again. Exiting...",2)
            sys.exit()

        # Exit if mask isn't a polygon
        if arcpy.Describe(inMask).ShapeType != "Polygon":
            AddMsgAndPrint("\nYour Area of Interest must be a polygon layer. Exiting...",2)
            sys.exit()

        # --------------------------------------------------------------------- Gather DEM Info
        arcpy.SetProgressorLabel("Gathering information about input DEM file")
        AddMsgAndPrint("\nInformation about input DEM file " + os.path.basename(inputDEM)+ ":",0)

        desc = arcpy.Describe(inputDEM)
        sr = desc.SpatialReference
        cellSize = desc.MeanCellWidth
        units = sr.LinearUnitName

        # Coordinate System must be a Projected type in order to continue.
        if sr.Type == "Projected":
            AddMsgAndPrint("\n\tInput Projection Name: " + sr.Name,0)
            AddMsgAndPrint("\tXY Linear Units: " + units,0)
            AddMsgAndPrint("\tCell Size: " + str(desc.MeanCellWidth) + " x " + str(desc.MeanCellHeight) + " " + units,0)
        else:
            AddMsgAndPrint("\n\n\t" + os.path.basename(inputDEM) + " is NOT in a Projected Coordinate System. Exiting...",2)
            sys.exit(0)

        # -------------------------------------------------------------------- Clip DEM to AOI
        arcpy.SetProgressorLabel("Clipping DEM to Area of Interest")
        AddMsgAndPrint("\nClipping DEM to Area of Interest...",0)

        arcpy.env.snapRaster = inputDEM
        maskedDEM = arcpy.sa.ExtractByMask(inputDEM, inMask)
        maskedDEM.save(outputDEM)

        AddMsgAndPrint("\n\tSuccessully Clipped " + os.path.basename(inputDEM) + " to Area of Interest!",0)

        # ------------------------------------------------------------------------------------------------ FIN!
        AddMsgAndPrint("\nProcessing Complete!\n",0)

    # -----------------------------------------------------------------------------------------------------------------

    except SystemExit:
        pass

    except KeyboardInterrupt:
        AddMsgAndPrint("Interruption requested. Exiting...")

    except:
        print_exception()

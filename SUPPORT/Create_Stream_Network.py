# ==========================================================================================
# Name: Create_Stream_Network.py
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
#
# Created by Peter Mead, Adolfo Diaz, USDA NRCS, 2013
# Updated by Chris Morse, USDA NRCS, 2019
#
# ==========================================================================================
# Updated  4/20/2020 - Adolfo Diaz
#
# - Updated and Tested for ArcGIS Pro 2.4.2 and python 3.6
# - All temporary raster layers such as Fill and Minus are stored in Memory and no longer
#   written to hard disk.
# - All describe functions use the arcpy.da.Describe functionality.
# - Removed determineOverlap() function since this can now be done using the extent
#   object to determine overalop of culverts within the AOI
# - All field calculation expressions are in PYTHON3 format.
# - Used acre conversiont dictionary and z-factor lookup table
# - All cursors were updated to arcpy.da
# - Updated AddMsgAndPrint to remove ArcGIS 10 boolean and gp function
# - Updated print_exception function.  Traceback functions slightly changed for Python 3.6.
# - Added Snap Raster environment
# - Added parallel processing factor environment
# - swithced from sys.exit() to exit()
# - All gp functions were translated to arcpy
# - Every function including main is in a try/except clause
# - Main code is wrapped in if __name__ == '__main__': even though script will never be
#   used as independent library.
# - Normal messages are no longer Warnings unnecessarily.

# ==========================================================================================
# Updated  4/20/2020 - Adolfo Diaz
#
# - Decided to clip the culverts to the AOI instead of using the extent object b/c
#   county or statewide culvert layers may be used in the future and there is no sense
#   in assessing every culvert within a couty/state wide layer.
# - Added code to remove layers from an .aprx rather than simply deleting them

#
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

    try:
        import getpass, time

        arcInfo = arcpy.GetInstallInfo()  # dict of ArcGIS Pro information

        f = open(textFilePath,'a+')
        f.write("\n################################################################################################################\n")
        f.write("Executing \"2.Create Stream Network\" Tool\n")
        f.write("User Name: " + getpass.getuser() + "\n")
        f.write("Date Executed: " + time.ctime() + "\n")
        f.write(arcInfo['ProductName'] + ": " + arcInfo['Version'] + "\n")
        f.write("User Parameters:\n")
        f.write("\tWorkspace: " + userWorkspace + "\n")
        f.write("\tDem_AOI: " + DEM_aoi + "\n")

        if culvertsExist:

            if int(arcpy.GetCount_management(burnCulverts).getOutput(0)) > 1:
                f.write("\tCulverts Digitized: " + str(numOfCulverts) + "\n")
            else:
                f.write("\tCulverts Digitized: 0\n")

        else:
            f.write("\tCulverts Digitized: 0\n")

        f.write("\tStream Threshold: " + str(streamThreshold) + "\n")

        f.close
        del f

    except:
        print_exception()
        exit()

## ================================================================================================================
# Import system modules
import arcpy, sys, os, traceback
from arcpy.sa import *

if __name__ == '__main__':

    try:

        # Check out Spatial Analyst License
        if arcpy.CheckExtension("spatial") == "Available":
            arcpy.CheckOutExtension("spatial")
        else:
            arcpy.AddError("Spatial Analyst Extension not enabled. Please enable Spatial analyst from the Tools/Extensions menu\n",2)
            exit()

        # --------------------------------------------------------------------------------------------- Input Parameters
        AOI = arcpy.GetParameterAsText(0)
        burnCulverts = arcpy.GetParameterAsText(1)
        streamThreshold = float(arcpy.GetParameterAsText(2))

        # Uncomment the following  3 lines to run from pythonWin
##        AOI = r'E:\NRCS_Engineering_Tools_ArcPro\Testing\Testing_EngTools.gdb\Layers\Testing_AOI'
##        burnCulverts = ""
##        streamThreshold = float(1)

        # Set environmental variables
        arcpy.env.parallelProcessingFactor = "75%"
        arcpy.env.overwriteOutput = True

        # --------------------------------------------------------------------------------------------- Define Variables
        aoiDesc = arcpy.da.Describe(AOI)
        aoiPath = aoiDesc['catalogPath']
        aoiName = aoiDesc['name']
        aoiExtent = aoiDesc['extent']

        # exit if AOI doesn't follow file structure
        if aoiPath.find('.gdb') == -1 or not aoiName.endswith('AOI'):
            AddMsgAndPrint("\n\n" + aoiName + " is an invalid project_AOI Feature",2)
            AddMsgAndPrint("Run Watershed Delineation Tool #1. Define Area of Interest\n\n",2)
            exit()

        watershedGDB_path = aoiPath[:aoiPath.find('.gdb')+4]
        watershedGDB_name = os.path.basename(watershedGDB_path)
        watershedGDB_FDpath = watershedGDB_path + os.sep + 'Layers'
        userWorkspace = os.path.dirname(watershedGDB_path)
        projectName = arcpy.ValidateTableName(os.path.basename(userWorkspace).replace(" ","_"))

        # --------------------------------------------------------------- Datasets
        # ------------------------------ Permanent Datasets
        culverts = watershedGDB_FDpath + os.sep + projectName + "_Culverts"
        streams = watershedGDB_FDpath + os.sep + projectName + "_Streams"
        DEM_aoi = watershedGDB_path + os.sep + projectName + "_DEM"
        hydroDEM = watershedGDB_path + os.sep + "hydroDEM"
        FlowAccum = watershedGDB_path + os.sep + "flowAccumulation"
        FlowDir = watershedGDB_path + os.sep + "flowDirection"

        # check if culverts exist.  This is only needed b/c the script may be executed manually
        numOfCulverts = int(arcpy.GetCount_management(burnCulverts).getOutput(0))
        if len(burnCulverts) < 1 or not numOfCulverts:
            culvertsExist = False
        else:
            culvertsExist = True

        # Path of Log file
        textFilePath = userWorkspace + os.sep + projectName + "_EngTools.txt"

        # record basic user inputs and settings to log file for future purposes
        logBasicSettings()

        # ---------------------------------------------------------------------------------------------------------------------- Check Parameters
        # Make sure the FGDB and DEM_aoi exists from Define Area of Interest tool.
        if not arcpy.Exists(watershedGDB_path) or not arcpy.Exists(DEM_aoi):
            AddMsgAndPrint("\nThe \"" + str(projectName) + "_DEM\" raster file or the File Geodatabase from Step 1 was not found",2)
            AddMsgAndPrint("Run Watershed Delineation Tool #1: Define Area of Interest",2)
            exit()

        # --------------------------------------------------------------------------------------- Remove any project layers from aprx and workspace
        datasetsToRemove = (streams,hydroDEM,FlowAccum,FlowDir)             # Full path of layers
        datasetsBaseName = [os.path.basename(x) for x in datasetsToRemove]  # layer names as they would appear in .aprx

        # Remove culverts from .aprx as well
        if culvertsExist:
            datasetsBaseName.append(os.path.basename(culverts))

        aprx = arcpy.mp.ArcGISProject("CURRENT")

        # Remove layers from ArcGIS Pro Session
        try:
            for maps in aprx.listMaps():
                for lyr in maps.listLayers():
                    if lyr.name in datasetsBaseName:
                       maps.removeLayer(lyr)
        except:
            pass

        x = 0
        for dataset in datasetsToRemove:

            if arcpy.Exists(dataset):

                if x < 1:
                    AddMsgAndPrint("\nRemoving old datasets from FGDB: " + watershedGDB_name,1)
                    x += 1

                try:
                    arcpy.Delete_management(dataset)
                    AddMsgAndPrint("\tDeleting....." + os.path.basename(dataset),1)
                except:
                    pass

        # -------------------------------------------------------------------------------------------------------------------- Retrieve DEM Properties
        demDesc = arcpy.da.Describe(DEM_aoi)
        demName = demDesc['name']
        demPath = demDesc['catalogPath']
        demCellSize = demDesc['meanCellWidth']
        demFormat = demDesc['format']
        demSR = demDesc['spatialReference']
        demCoordType = demSR.type
        linearUnits = demSR.linearUnitName

        arcpy.env.extent = "MINOF"
        arcpy.env.cellSize = demCellSize
        arcpy.env.snapRaster = demPath
        arcpy.env.outputCoordinateSystem = demSR
        arcpy.env.workspace = watershedGDB_path

        ## ------------------------------------------------------------------------- Z-factor conversion Lookup table
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
        zFactorList = [[1,0.3048,0.01,0.0254],
                       [3.28084,1,0.0328084,0.083333],
                       [100,30.48,1.0,2.54],
                       [39.3701,12,0.393701,1.0]]

        # ------------------------------------------------------------------------------------------------------------------------ Incorporate Culverts into DEM
        reuseCulverts = False
        # Culverts will be incorporated into the DEM_aoi if at least 1 culvert is provided.
        if culvertsExist:

            if numOfCulverts > 0:

                # if paths are not the same then assume culverts were manually digitized
                # or input is some from some other feature class/shapefile
                if not arcpy.da.Describe(burnCulverts)['catalogPath'] == culverts:

                    # delete the culverts feature class; new one will be created
                    if arcpy.Exists(culverts):
                        arcpy.Delete_management(culverts)
                        arcpy.Clip_analysis(burnCulverts,aoiPath,culverts)
                        AddMsgAndPrint("\nSuccessfully Recreated \"Culverts\" feature class.")

                    else:
                        arcpy.Clip_analysis(burnCulverts,aoiPath,culverts)
                        AddMsgAndPrint("\nSuccessfully Created \"Culverts\" feature class")

                # paths are the same therefore input was from within FGDB
                else:
                    AddMsgAndPrint("\nUsing Existing \"Culverts\" feature class:",1)
                    reuseCulverts = True

                # Number of culverts within AOI
                numOfCulvertsWithinAOI = int(arcpy.GetCount_management(culverts).getOutput(0))

##                for row in arcpy.da.SearchCursor(culverts,['SHAPE@']):
##                    culvertExtent = row[0].extent
##                    if aoiExtent.contains(culvertExtent):
##                        numOfCulvertsWithinAOI+=1
##                del row

                # ------------------------------------------------------------------- Buffer Culverts
                if numOfCulvertsWithinAOI:

                    # determine linear units to set buffer value to the equivalent of 1 pixel
                    if linearUnits in ('Meter','Meters'):
                        bufferSize = str(demCellSize) + " Meters"
                        AddMsgAndPrint("\nBuffer size applied on Culverts: " + str(demCellSize) + " Meter(s)")

                    elif linearUnits in ('Foot','Foot_US','Feet'):
                        bufferSize = str(demCellSize) + " Feet"
                        AddMsgAndPrint("\nBuffer size applied on Culverts: " + bufferSize)

                    else:
                        bufferSize = str(demCellSize) + " Unknown"
                        AddMsgAndPrint("\nBuffer size applied on Culverts: Equivalent of 1 pixel since linear units are unknown",0)

                    # Buffer the culverts to 1 pixel
                    culvertBuffered = "in_memory" + os.sep + os.path.basename(arcpy.CreateScratchName("culvertBuffered",data_type="FeatureClass",workspace=watershedGDB_path))
                    arcpy.Buffer_analysis(culverts, culvertBuffered, bufferSize, "FULL", "ROUND", "NONE", "")

                    # Dummy field just to execute Zonal stats on each feature
                    expression = "!" + arcpy.da.Describe(culvertBuffered)['OIDFieldName'] + "!"
                    arcpy.AddField_management(culvertBuffered, "ZONE", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED")
                    arcpy.CalculateField_management(culvertBuffered, "ZONE", expression, "PYTHON3")

                    # Get the minimum elevation value for each culvert
                    culvertRaster = watershedGDB_path + os.sep + "culvertRaster"
                    culvertMinValue = ZonalStatistics(culvertBuffered, "ZONE", DEM_aoi, "MINIMUM", "NODATA")
                    culvertMinValue.save(culvertRaster)
                    AddMsgAndPrint("\nApplying the minimum Zonal DEM Value to the Culverts")

                    # Elevation cells that overlap the culverts will get the minimum elevation value
                    mosaicList = DEM_aoi + ";" + culvertRaster
                    arcpy.MosaicToNewRaster_management(mosaicList, watershedGDB_path, "hydroDEM", "#", "32_BIT_FLOAT", demCellSize, "1", "LAST", "#")
                    AddMsgAndPrint("\nFusing Culverts and " + demName + " to create " + os.path.basename(hydroDEM))

                    Fill_hydroDEM = Fill(hydroDEM)

                # No Culverts will be used due to no overlap or determining overlap error.
                else:
                    AddMsgAndPrint("\nThere were no culverts digitized within " + aoiName,1)
                    Fill_hydroDEM = Fill(DEM_aoi)

        else:
            AddMsgAndPrint("\nNo Culverts detected!")
            Fill_hydroDEM = Fill(DEM_aoi)

        AddMsgAndPrint("\nSuccessfully filled sinks in Fill_hydroDEM to remove small imperfections")

        # ---------------------------------------------------------------------------------------------- Create Stream Network
        # Create Flow Direction Grid.
        arcpy.SetProgressorLabel("Creating Flow Direction")
        outFlowDirection = FlowDirection(Fill_hydroDEM, "NORMAL")
        outFlowDirection.save(FlowDir)

        # Create Flow Accumulation Grid...
        arcpy.SetProgressorLabel("Creating Flow Accumulation")
        outFlowAccumulation = FlowAccumulation(FlowDir, "", "INTEGER")
        outFlowAccumulation.save(FlowAccum)

        # Need to compute a histogram for the FlowAccumulation layer so that the full range of values are captured for subsequent stream generation
        # This tries to fix a bug of the primary channel not generating for large watersheds with high values in flow accumulation grid
        arcpy.CalculateStatistics_management(FlowAccum)
        AddMsgAndPrint("\nSuccessfully created Flow Accumulation and Flow Direction")

        # stream link will be created using pixels that have a flow accumulation greater than the
        # user-specified acre threshold
        if streamThreshold > 0:

            acreConvFactor = acreConversionDict.get(linearUnits)
            acreThresholdVal = round((streamThreshold * acreConvFactor)/(demCellSize**2))
            conExpression = "Value >= " + str(acreThresholdVal)

            # Select all cells that are greater than or equal to the acre stream threshold value
            conFlowAccum = Con(FlowAccum, FlowAccum, "", conExpression)

            # Create Stream Link Works
            arcpy.SetProgressorLabel("Creating Stream Link")
            outStreamLink = StreamLink(conFlowAccum,FlowDir)

        # All values in flowAccum will be used to create stream link
        else:
            arcpy.SetProgressorLabel("Creating Stream Link")
            acreThresholdVal = 0
            outStreamLink = StreamLink(FlowAccum,FlowDir)

        # Converts a raster representing a linear network to features representing the linear network.
        # creates field grid_code
        StreamToFeature(outStreamLink, FlowDir, streams, "SIMPLIFY")
        AddMsgAndPrint("\nSuccessfully created stream linear network using a flow accumulation value >= " + str(acreThresholdVal))

        # ------------------------------------------------------------------------------------------------ Delete unwanted datasets
        arcpy.Delete_management(Fill_hydroDEM)
        arcpy.Delete_management(outStreamLink)

        # ------------------------------------------------------------------------------------------------ Compact FGDB
        try:
            arcpy.Compact_management(watershedGDB_path)
            AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path))
        except:
            pass

        # ------------------------------------------------------------------------------------------------ Prepare to Add to Arcmap

        arcpy.SetParameterAsText(3, streams)

        if not reuseCulverts:
            arcpy.SetParameterAsText(4, culverts)

        AddMsgAndPrint("\nAdding Layers to ArcGIS Pro Session")
        AddMsgAndPrint("")

    except:
        print_exception()










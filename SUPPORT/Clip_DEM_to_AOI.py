# ==========================================================================================
# Name: Clip_DEM_to_AOI.py
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
# Updated  5/23/2020 - Adolfo Diaz
#
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
    f.write("Executing \"Clip DEM to AOI\" Tool" + "\n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write(arcInfo['ProductName'] + ": " + arcInfo['Version'] + "\n")
    f.write("User Parameters:\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")

    if arcpy.da.Describe(inputDEM)['format'] == 'Image Service':
        f.write("\tInput DEM: " + inputDEM + " Image Service\n")
    else:
        f.write("\tInput DEM: " + inputDEM + "\n")

    f.write("\tOutput DEM: " + outputDEM + "\n")

    f.close
    del f

## ================================================================================================================
def extractSubsetFromGCSdem(demSource,zUnits):
    # This function will extract a subset from a DEM that is in a GCS Coordinate System.
    # This includes a local DEM or Web Image Service.  The DEM will be clipped to the
    # bounding extent of the project AOI in Lat/Long.  The resolution of the GCS DEM will
    # attempt to be determined using the 'getImageServiceResolution' function.  Once
    # the original linear resolution has been determined the clipped DEM can be projected
    # to the same PCS as the project AOI.  The projection tool does not honor a mask env
    # therefore extract by mask is then executed on the newly projected DEM.
    # -- Clip is the fastest however it doesn't honor cellsize so a project is required.
    # -- Original Z-factor on WGS84 service cannot be calculated b/c linear units are
    #    unknown.  Assume linear units and z-units are the same.
    # Returns a clipped DEM and new Z-Factor

    try:
        # Set the output CS to the input DEM i.e WGS84
        arcpy.env.outputCoordinateSystem = demSR
        arcpy.env.resamplingMethod = "BILINEAR"

        # Make a copy of projectAOI so that it converts into output GCS
        projectedAOIcopy = arcpy.CreateScratchName("projectAOIcopy",data_type="FeatureClass",workspace="in_memory")
        arcpy.CopyFeatures_management(AOI,projectedAOIcopy)

        # Extent coordinates should be GCS
        projectAOIext = arcpy.Describe(projectedAOIcopy).extent
        clipExtent = str(projectAOIext.XMin) + " " + str(projectAOIext.YMin) + " " + str(projectAOIext.XMax) + " " + str(projectAOIext.YMax)

        if bImageService: arcpy.SetProgressorLabel("Downloading DEM from " + demName + " Image Service")

        demClip = arcpy.CreateScratchName("demClipIS",data_type="RasterDataset",workspace="in_memory")
        arcpy.Clip_management(demSource, clipExtent, demClip, "", "", "", "NO_MAINTAIN_EXTENT")

        if bImageService:
            AddMsgAndPrint("\nSuccessfully downloaded DEM from " + demName + " Image Service")
        else:
            AddMsgAndPrint("\nSuccessully Clipped " + demName + " DEM using " + aoiName,1)

        # convert DD resolution to meters or feet
        outputCellsize = getPCSresolutionFromGCSraster(demClip,aoiLinearUnits)

        # return false if outputCellSize could not be determined
        if outputCellsize == 0:
            return False,False

        # Project DEM subset to projectAOI PCS
        arcpy.env.outputCoordinateSystem = aoiSR
        outputCS = arcpy.env.outputCoordinateSystem

        demProject = arcpy.CreateScratchName("demProjectIS",data_type="RasterDataset",workspace="in_memory")
        arcpy.SetProgressorLabel("Projecting DEM to " + aoiSRname)
        arcpy.ProjectRaster_management(demClip, demProject, aoiSR, "BILINEAR", outputCellsize)
        arcpy.SetProgressorLabel("")

        outExtract = ExtractByMask(demProject, AOI)

        arcpy.Delete_management(demClip)
        arcpy.Delete_management(demProject)

        # ------------------------------------------------------------------------------------ Report new DEM properties
        maskDesc = arcpy.da.Describe(outExtract)
        newSR = maskDesc['spatialReference']
        newLinearUnits = newSR.linearUnitName
        newCellSize = maskDesc['meanCellWidth']

        newZfactor = zFactorList[unitLookUpDict.get(newLinearUnits)][unitLookUpDict.get(zUnits)]

        # Adjust Z-units by new factor if needed
        if newZfactor != 1.0:
            AddMsgAndPrint("Converting Z-units from " + zUnits + " to " + newLinearUnits + " using multiplicative factor of: " + str(newZfactor))
            outTimes = Times(outExtract,newZfactor)
            outTimes.save(outputDEM)
        else:
            outExtract.save(outputDEM)

        AddMsgAndPrint("\tNew Projection Name: " + newSR.name)
        AddMsgAndPrint("\tXY Linear Units: " + newLinearUnits)
        AddMsgAndPrint("\tElevation Units (Z): " + newLinearUnits)
        AddMsgAndPrint("\tCell Size: " + str(newCellSize) + " " + newLinearUnits,1)
        AddMsgAndPrint("\tZ-Factor: " + str(newZfactor))

        return outputDEM,newZfactor

    except:
        print_exception()

## ================================================================================================================
def getPCSresolutionFromGCSraster(raster,units):
    # This function will calculate the great circle distance between two points
    # on the earth (specified in decimal degrees).  The two points are
    # collected from the Lower Left XY and Upper Left XY of the input raster.
    # These points are fed into the haversine formula and result gets divided
    # by the number of raster rows.  Output number is truncated to a whole
    # number and returned.  Return 0 otherwise.

    try:
        # Get the lower left XY and Upper Left XY coords
        # from input raster.  This should in theory be a line
        rasterDesc = arcpy.da.Describe(raster)
        LLX = rasterDesc['extent'].lowerLeft.X
        LLY = rasterDesc['extent'].lowerLeft.Y
        ULX = rasterDesc['extent'].upperLeft.X
        ULY = rasterDesc['extent'].upperLeft.Y

        # Get the # of rows present in the raster. Do not
        # need columns we are after the distance in latitude (y)
        rows = rasterDesc['height']

        # convert decimal degrees to radians
        lon1, lat1, lon2, lat2 = map(radians, [LLX, LLY, ULX, ULY])

        # difference in lat/long from 2 points in radians
        dlon = lon2 - lon1     # In theory, difference in long (x) should always return 0
        dlat = lat2 - lat1     # difference will be in radians

        # haversine formula
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))
        distMeters = (6371 * c) * 1000

        if units in ('Meter','Meters'):
            resolution = distMeters / rows

            if resolution > 0.0 and resolution < 1.0:
                return round(resolution)
            else:
                return int(resolution)

        elif units in ('Foot','Foot_US','Feet'):
            return int((distMeters * 3.28084) / rows)

        else:

            return 0

    except:
        print_exception()

## ================================================================================================================
# Import system modules
import arcpy, sys, os, traceback
from arcpy.sa import *
from math import cos, sin, asin, sqrt, radians

if __name__ == '__main__':

    try:

        # Check out Spatial Analyst License
        if arcpy.CheckExtension("Spatial") == "Available":
            arcpy.CheckOutExtension("Spatial")
        else:
            AddMsgAndPrint("\nSpatial Analyst Extension not enabled. Please enable Spatial Analyst from the Tools/Extensions menu. Exiting...\n",2)
            exit()

        # --------------------------------------------------------------------- Input Parameters
        inputDEM = arcpy.GetParameterAsText(0)
        zUnits = arcpy.GetParameterAsText(1)           # elevation z units of input DEM
        AOI = arcpy.GetParameterAsText(2)
        outputDEM = arcpy.GetParameterAsText(3)

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
        AddMsgAndPrint("\nValidating Inputs...")

        # Exit if no AOI provided
        if not int(arcpy.GetCount_management(AOI).getOutput(0)) > 0:
            AddMsgAndPrint("\nNo area of interest was provided, you must digitize or select a mask. Exiting...",2)
            exit()

        # Exit if AOI contains more than 1 digitized area.
        if int(arcpy.GetCount_management(AOI).getOutput(0)) > 1:
            AddMsgAndPrint("\nYou can only digitize one Area of Interest or provide a single feature. Please try again. Exiting...",2)
            exit()

        # Exit if mask isn't a polygon
        if arcpy.da.Describe(AOI)['shapeType'] != "Polygon":
            AddMsgAndPrint("\nYour Area of Interest must be a polygon layer. Exiting...",2)
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

        # ---------------------------------------------------------------------------------------- Gather DEM Info
        arcpy.SetProgressorLabel("Gathering information about input DEM file")
        AddMsgAndPrint("\nInformation about input DEM file " + os.path.basename(inputDEM)+ ":",0)

        # Input DEM Spatial Reference Information
        demDesc = arcpy.da.Describe(inputDEM)
        demName = demDesc['name']
        demPath = demDesc['catalogPath']
        demCellSize = demDesc['meanCellWidth']
        demSR = demDesc['spatialReference']
        demFormat = demDesc['format']
        demCoordType = demSR.type

        if demCoordType == 'Projected':
            bProjectedCS = True
            linearUnits = demSR.linearUnitName
        else:
            bProjectedCS = False
            linearUnits = demSR.angularUnitName

        # Indicates a WFS is being used
        bImageService = False
        if demFormat == 'Image Service':
            bImageService = True

        AddMsgAndPrint("\nDEM Information: " + demName + " Image Service" if bImageService else "")
        AddMsgAndPrint("\tProjection Name: " + demSR.name)
        AddMsgAndPrint("\tXY Linear Units: " + linearUnits)
        AddMsgAndPrint("\tCell Size: " + str(demCellSize) + " " + linearUnits)
        AddMsgAndPrint("\tZ-units: " + zUnits)

        # ---------------------------------------------------------------------------------------------- Set Coord System of Project
        # AOI spatial reference info
        aoiDesc = arcpy.da.Describe(AOI)
        aoiSR = aoiDesc['spatialReference']
        aoiSRname = aoiSR.name
        aoiLinearUnits = aoiSR.linearUnitName
        aoiName = aoiDesc['name']
        aoiDemCoordType = aoiSR.type

        # if input DEM and AOI Coordinate System is Geographic then exit
        if not bProjectedCS and aoiDemCoordType != 'Projected':
            AddMsgAndPrint("\n\t" + demName + " DEM and " + aoiName + " AOI are in a Geographic Coordinate System",2)
            AddMsgAndPrint("\tOne of these layers must be in a Projected Coordinate System",2)
            AddMsgAndPrint("\tContact your State GIS Coordinator to resolve this issue. Exiting!",2)
            exit()

        # Set output Coord Sys to AOI if it is projected
        if aoiDemCoordType == 'Projected':
            arcpy.env.outputCoordinateSystem = aoiSR

        else:
            arcpy.env.outputCoordinateSystem = demSR

        # ------------------------------------------------------------------------------------------------- Clip inputDEM
        # DEM is in PCS (Local DEM or WMS)
        if bProjectedCS:
            arcpy.env.snapRaster = inputDEM
            outExtract = ExtractByMask(inputDEM, AOI)

            maskDesc = arcpy.da.Describe(outExtract)
            newSR = maskDesc['spatialReference']
            newLinearUnits = newSR.linearUnitName
            newCellSize = maskDesc['meanCellWidth']

            newZfactor = zFactorList[unitLookUpDict.get(newLinearUnits)][unitLookUpDict.get(zUnits)]

            # Adjust Z-units by new factor if needed
            if newZfactor != 1.0:
                AddMsgAndPrint("Converting Z-units from " + zUnits + " to " + newLinearUnits + " using multiplicative factor of: " + str(newZfactor))
                outTimes = Times(outExtract,newZfactor)
                outTimes.save(outputDEM)
            else:
                outExtract.save(outputDEM)

            AddMsgAndPrint("\nNew Projection Name: " + newSR.name)
            AddMsgAndPrint("\tXY Linear Units: " + newLinearUnits)
            AddMsgAndPrint("\tElevation Units (Z): " + newLinearUnits)
            AddMsgAndPrint("\tCell Size: " + str(newCellSize) + " " + newLinearUnits)
            AddMsgAndPrint("\tZ-Factor: " + str(newZfactor))

            AddMsgAndPrint("\nSuccessully Clipped " + os.path.basename(inputDEM) + " DEM using " + os.path.basename(AOI))

        # DEM is in GCS (Local DEM or WMS)
        else:
            DEM_aoi,zFactor = extractSubsetFromGCSdem(inputDEM,zUnits)

            if DEM_aoi == False:
                AddMsgAndPrint("\nCould not determine resolution of GCS DEM. EXITING",2)
                exit()

        # ------------------------------------------------------------------------------------------------ FIN!
        AddMsgAndPrint("\nProcessing Complete!\n")

    except:
        print_exception()

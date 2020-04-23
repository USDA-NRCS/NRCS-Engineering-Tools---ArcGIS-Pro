# ==========================================================================================
# Name: Define_AOI.py
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

# ==========================================================================================
# Updated  4/15/2020 - Adolfo Diaz
#
# - Updated and Tested for ArcGIS Pro 2.4.2 and python 3.6
# - Added functionality to utilize a DEM image service or a DEM in GCS.  Added 2 new
#   function to handle this capability: extractSubsetFromGCSdem and getPCSresolutionFromGCSraster.
# - If GCS DEM is used then the coordinate system of the FGDB will become the same as the AOI
#   assuming the AOI is in a PCS.  If both AOI and DEM are in a GCS then the tool will exit.
# - All temporary raster layers such as Fill and Minus are stored in Memory and no longer
#   written to hard disk.
# - All describe functions use the arcpy.da.Describe functionality.
# - All field calculation expressions are in PYTHON3 format.
# - Used acre conversiont dictionary and z-factor lookup table
# - All cursors were updated to arcpy.da
# - Added code to remove layers from an .aprx rather than simply deleting them
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

    try:
        # record basic user inputs and settings to log file for future purposes

        import getpass, time
        arcInfo = arcpy.GetInstallInfo()  # dict of ArcGIS Pro information

        f = open(textFilePath,'a+')
        f.write("\n################################################################################################################\n")
        f.write("Executing \"1.Define Area of Interest\" tool\n")
        f.write("User Name: " + getpass.getuser() + "\n")
        f.write("Date Executed: " + time.ctime() + "\n")
        f.write(arcInfo['ProductName'] + ": " + arcInfo['Version'] + "\n")
        f.write("\nUser Parameters:\n")
        f.write("\tWorkspace: " + userWorkspace + "\n")
        f.write("\tInput Dem: " + demPath + "\n")

        if interval > 0:
            f.write("\tContour Interval: " + str(interval) + "\n")
        else:
            f.write("\tContour Interval: NOT SPECIFIED\n")

        if len(zUnits) > 0:
            f.write("\tElevation Z-units: " + zUnits + "\n")

        else:
            f.write("\tElevation Z-units: Not Available" + "\n")

        f.close

    except:
        print_exception()
        exit()

## ================================================================================================================
def splitThousands(someNumber):
# will determine where to put a thousands seperator if one is needed.
# Input is an integer.  Integer with or without thousands seperator is returned.

    try:
        return re.sub(r'(\d{3})(?=\d)', r'\1,', str(someNumber)[::-1])[::-1]

## --------------Use this code in case you want to preserve numbers after the decimal.  I decided to just round up
##        # Number is a floating number
##        if str(someNumber).find("."):
##
##            dropDecimals = int(someNumber)
##            numberStr = str(someNumber)
##
##            afterDecimal = str(numberStr[numberStr.find("."):numberStr.find(".")+2])
##            beforeDecimalCommas = re.sub(r'(\d{3})(?=\d)', r'\1,', str(dropDecimals)[::-1])[::-1]
##
##            return beforeDecimalCommas + afterDecimal
##
##        # Number is a whole number
##        else:
##            return int(re.sub(r'(\d{3})(?=\d)', r'\1,', str(someNumber)[::-1])[::-1])

    except:
        print_exception()
        return someNumber

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
        projectedAOIcopy = "in_memory" + os.sep + os.path.basename(arcpy.CreateScratchName("projectAOIcopy",data_type="FeatureClass",workspace=watershedGDB_path))
        arcpy.CopyFeatures_management(projectAOI,projectedAOIcopy)

        # Extent coordinates should be GCS
        projectAOIext = arcpy.Describe(projectedAOIcopy).extent
        clipExtent = str(projectAOIext.XMin) + " " + str(projectAOIext.YMin) + " " + str(projectAOIext.XMax) + " " + str(projectAOIext.YMax)

        arcpy.SetProgressorLabel("Downloading DEM from " + demName + " Image Service")

        demClip = "in_memory" + os.sep + os.path.basename(arcpy.CreateScratchName("demClipIS",data_type="RasterDataset",workspace=watershedGDB_path))
        arcpy.Clip_management(demSource, clipExtent, demClip, "", "", "", "NO_MAINTAIN_EXTENT")

        if bImageService:
            AddMsgAndPrint("\nSuccessfully downloaded DEM from " + demName + " Image Service")
        else:
            AddMsgAndPrint("\nSuccessully Clipped " + demName + " DEM using " + aoiName,1)

        # convert DD resolution to meters or feet
        outputCellsize = getPCSresolutionFromGCSraster(demClip,aoiLinearUnits)

        # Set the default cell size to 3 if getImageServiceResolution returned 0
        if outputCellsize == 0:
            outputCellsize == 3

        # Project DEM subset to projectAOI PCS
        arcpy.env.outputCoordinateSystem = aoiSR
        outputCS = arcpy.env.outputCoordinateSystem

        demProject = "in_memory" + os.sep + os.path.basename(arcpy.CreateScratchName("demProjectIS",data_type="RasterDataset",workspace=watershedGDB_path))
        arcpy.ProjectRaster_management(demClip, demProject, outputCS, "BILINEAR", outputCellsize)

        outExtract = ExtractByMask(demProject, projectAOI)
        outExtract.save(DEM_aoi)

        arcpy.Delete_management(demClip)
        arcpy.Delete_management(demProject)

        # ------------------------------------------------------------------------------------ Report new DEM properties
        maskDesc = arcpy.da.Describe(DEM_aoi)
        newSR = maskDesc['spatialReference']
        newLinearUnits = newSR.linearUnitName
        newCellSize = maskDesc['meanCellWidth']

        newZfactor = zFactorList[unitLookUpDict.get(zUnits)][unitLookUpDict.get(newLinearUnits)]

        AddMsgAndPrint("\tNew Projection Name: " + newSR.name,0)
        AddMsgAndPrint("\tXY Linear Units: " + newLinearUnits)
        AddMsgAndPrint("\tElevation Units (Z): " + zUnits)
        AddMsgAndPrint("\tCell Size: " + str(newCellSize) + " " + newLinearUnits )
        AddMsgAndPrint("\tZ-Factor: " + str(newZfactor))

        #AddMsgAndPrint(toc(startTime))
        return DEM_aoi,newZfactor

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
            return int(distMeters / rows)

        elif units in ('Foot','Foot_US','Feet'):
            return int((distMeters * 3.28084) / rows)

        else:
            AddMsgAndPrint("\nCould not determine resolution of GCS DEM ",2)
            return 0

    except:
        print_exception()


## ================================================================================================================
# Import system modules
import arcpy, sys, os, traceback, re
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

        # --------------------------------------------------------------------------------------------- Input Parameters
        userWorkspace = arcpy.GetParameterAsText(0)    # User-input directory where FGDB will be created
        inputDEM = arcpy.GetParameterAsText(1)         # DEM
        zUnits = arcpy.GetParameterAsText(2)           # elevation z units of input DEM
        AOI = arcpy.GetParameterAsText(3)              # user-input AOI
        interval = float(arcpy.GetParameterAsText(4))  # user defined contour interval

        # Uncomment the following 5 lines to run from pythonWin
##        userWorkspace = r'E:\NRCS_Engineering_Tools_ArcPro\Testing'
##        inputDEM = r'E:\NRCS_Engineering_Tools_ArcPro\NRCS_Engineering_Tools_ArcPro_Update.gdb\SW_WI'
##        zUnits = "Meters"
##        AOI = r'E:\NRCS_Engineering_Tools_ArcPro\NRCS_Engineering_Tools_ArcPro_Update.gdb\Testing_AOI_UTM'
##        interval = float(10)

        # Set environmental variables
        arcpy.env.parallelProcessingFactor = "75%"
        arcpy.env.overwriteOutput = True
        arcpy.env.geographicTransformations = "WGS_1984_(ITRF00)_To_NAD_1983"

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

        bImageService = False
        if demFormat == 'Image Service':
            bImageService = True

        # --------------------------------------------------------------------------------------------- Set Variables
        projectName = arcpy.ValidateTableName(os.path.basename(userWorkspace).replace(" ","_"))
        textFilePath = userWorkspace + os.sep + projectName + "_EngTools.txt"

        watershedGDB_name = os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.gdb"  # replace spaces for new FGDB name
        watershedGDB_path = userWorkspace + os.sep + watershedGDB_name
        watershedFD = watershedGDB_path + os.sep + "Layers"

        # Permanent Datasets
        projectAOI = watershedFD + os.sep + projectName + "_AOI"
        Contours = watershedFD + os.sep + projectName + "_Contours_" + str(int(interval)).replace(".","_") + "ft"
        DEM_aoi = watershedGDB_path + os.sep + projectName + "_DEM"
        Hillshade_aoi = watershedGDB_path + os.sep + projectName + "_Hillshade"
        depthGrid = watershedGDB_path + os.sep + projectName + "_DepthGrid"

        # ArcGIS Pro Layers
        aoiOut = "" + projectName + "_AOI"
        contoursOut = "" + projectName + "_Contours_" + str(int(interval)).replace(".","_") + "ft"
        demOut = "" + projectName + "_DEM"
        hillshadeOut = "" + projectName + "_Hillshade"
        depthOut = "" + projectName + "_DepthGrid"

        # record basic user inputs and settings to log file for future purposes
        logBasicSettings()

        # ---------------------------------------------------------------------------------------------- Count the number of features in AOI
        # Exit if AOI contains more than 1 digitized area.
        if int(arcpy.GetCount_management(AOI).getOutput(0)) > 1:
            AddMsgAndPrint("\n\nYou can only digitize 1 Area of interest! Please Try Again.",2)
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
        zFactorList = [[1,0.3048,0.01,0.0254],
                       [3.28084,1,0.0328084,0.083333],
                       [100,30.48,1.0,2.54],
                       [39.3701,12,0.393701,1.0]]

        # ---------------------------------------------------------------------------------------------- Set Coord System of Project
        # input DEM Coordinate System is Geographic
        if not bProjectedCS:

            # AOI spatial reference info
            aoiDesc = arcpy.da.Describe(AOI)
            aoiSR = aoiDesc['spatialReference']
            aoiLinearUnits = aoiSR.linearUnitName
            aoiName = aoiDesc['name']
            aoiDemCoordType = aoiSR.type

            # Set output coord system to AOI if AOI is a projected coord System
            if aoiDemCoordType == 'Projected':
                arcpy.env.outputCoordinateSystem = aoiSR
            else:
                AddMsgAndPrint("\n\t" + demName + " DEM and " + aoiName + " AOI are in a Geographic Coordinate System",2)
                AddMsgAndPrint("\tOne of these layers must be in a Projected Coordinate System",2)
                AddMsgAndPrint("\tContact your State GIS Coordinator to resolve this issue. Exiting!",2)
                exit()

            # assume there will be no z-factor adjustment
            # Maybe the zUnits should be compared against aoiLinearUnits
            zFactor = 1

        # Coordinate System is Projected (Could be local DEM or WMS in PCS)
        else:
            # Set output coord system to input DEM
            arcpy.env.outputCoordinateSystem = demSR

            if not len(zUnits) > 0:
                zUnits = linearUnits

            zFactor = zFactorList[unitLookUpDict.get(zUnits)][unitLookUpDict.get(linearUnits)]

        if not linearUnits:
            AddMsgAndPrint("\tCould not determine units of DEM....Exiting!",2)
            exit()

        AddMsgAndPrint("\nDEM Information: " + demName + " Image Service" if bImageService else "")
        AddMsgAndPrint("\tProjection Name: " + demSR.name,0)
        AddMsgAndPrint("\tXY Units: " + linearUnits,0)
        if bProjectedCS:
            AddMsgAndPrint("\tElevation Values (Z): " + zUnits,0)
        AddMsgAndPrint("\tCell Size: " + str(demCellSize) + " " + linearUnits,0)
        AddMsgAndPrint("\tZ-Factor used: " + str(zFactor))

        # --------------------------------------------------------------------------------------- Remove any project layers from aprx and workspace
        datasetsToRemove = (demOut,hillshadeOut,depthOut,contoursOut)       # Full path of layers
        datasetsBaseName = [os.path.basename(x) for x in datasetsToRemove]  # layer names as they would appear in .aprx

        aprx = arcpy.mp.ArcGISProject("CURRENT")

        # Remove layers from ArcGIS Pro Session if executed from an .aprx
        try:
            for maps in aprx.listMaps():
                for lyr in maps.listLayers():
                    if lyr.name in datasetsBaseName:
                        maps.removeLayer(lyr)
        except:
            pass

        if arcpy.Exists(watershedGDB_path):

            x = 0
            for dataset in datasetsToRemove:

                if arcpy.Exists(dataset):

                    # Strictly Formatting
                    if x < 1:
                        AddMsgAndPrint("\nRemoving old datasets from FGDB: " + watershedGDB_name ,1)
                        x += 1

                    try:
                        arcpy.Delete_management(dataset)
                        AddMsgAndPrint("\tDeleting....." + os.path.basename(dataset),1)
                    except:
                        pass

            # FGDB feature dataset exists; make sure coordinate system
            # is the same as arcpy.env.outputCoordinateSystem
            if arcpy.Exists(watershedFD):
                fdDesc = arcpy.da.Describe(watershedFD)
                fdSR = fdDesc['spatialReference']

                # recreate FD to the correct output coord system
                if fdSR != arcpy.env.outputCoordinateSystem:
                    arcpy.Delete_management(watershedFD)
                    arcpy.CreateFeatureDataset_management(watershedGDB_path, "Layers", arcpy.env.outputCoordinateSystem)

                    # Strictly formatting
                    if x > 0:
                        format = "\t"
                    else:
                        format = "\n"
                    AddMsgAndPrint(format + "Recreated '" + os.path.basename(watershedFD) + "' Feature Dataset b/c of Coordinate System conflict",1)

            else:
                arcpy.CreateFeatureDataset_management(watershedGDB_path, "Layers", arcpy.env.outputCoordinateSystem)

        # ------------------------------------------------------------ If project geodatabase and feature dataset do not exist, create them.
        else:
            # Create NEW project file geodatabase
            arcpy.CreateFileGDB_management(userWorkspace, watershedGDB_name)

            # Create Feature Dataset using spatial reference of input AOI
            arcpy.CreateFeatureDataset_management(watershedGDB_path, "Layers", arcpy.env.outputCoordinateSystem)

            AddMsgAndPrint("\nSuccessfully created File Geodatabase: " + watershedGDB_name)
            AddMsgAndPrint("\tOutput Coordinate System: " + str(arcpy.env.outputCoordinateSystem.name))

        # ----------------------------------------------------------------------------------------------- Create New AOI
        # if AOI path and  projectAOI path are not the same then assume AOI was manually digitized
        # or input is some from some other feature class/shapefile

        # AOI and projectAOI paths are not the same
        if arcpy.da.Describe(AOI)['catalogPath'] != projectAOI:

            # delete the existing projectAOI feature class and recreate it.
            if arcpy.Exists(projectAOI):

                arcpy.Delete_management(projectAOI)
                arcpy.CopyFeatures_management(AOI, projectAOI)
                AddMsgAndPrint("\nSuccessfully Recreated \"" + str(projectName) + "_AOI\" feature class")

            else:
                arcpy.CopyFeatures_management(AOI, projectAOI)
                AddMsgAndPrint("\nSuccessfully Created \"" + str(projectName) + "_AOI\" feature class")

        # paths are the same therefore AOI is projectAOI
        else:
            AddMsgAndPrint("\nUsing Existing \"" + str(projectName) + "_AOI\" feature class:")

            # Use temp lyr, delete from TOC and copy back to avoid refresh issues in arcmap
            arcpy.CopyFeatures_management(AOI, "aoiTemp")

            if arcpy.Exists(aoiOut):
                arcpy.Delete_management(aoiOut)

            arcpy.CopyFeatures_management("aoiTemp", projectAOI)
            arcpy.Delete_management("aoiTemp")

        # -------------------------------------------------------------------------------------------- Exit if AOI was not a polygon
        if arcpy.da.Describe(projectAOI)['shapeType'] != "Polygon":
            AddMsgAndPrint("\n\nYour Area of Interest must be a polygon layer!.....Exiting!",2)
            exit()

        # --------------------------------------------------------------------------------------------  Populate AOI with DEM Properties
        # Write input DEM name to AOI
        if len(arcpy.ListFields(projectAOI,"INPUT_DEM")) < 1:
            arcpy.AddField_management(projectAOI, "INPUT_DEM", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

        arcpy.CalculateField_management(projectAOI, "INPUT_DEM", "\"" + demName + "\"", "PYTHON3", "")

        # Write XY Units to AOI
        if len(arcpy.ListFields(projectAOI,"XY_UNITS")) < 1:
            arcpy.AddField_management(projectAOI, "XY_UNITS", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

        arcpy.CalculateField_management(projectAOI, "XY_UNITS", "\"" + linearUnits + "\"", "PYTHON3", "")

        # Write Z Units to AOI
        if len(arcpy.ListFields(projectAOI,"Z_UNITS")) < 1:
            arcpy.AddField_management(projectAOI, "Z_UNITS", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

        arcpy.CalculateField_management(projectAOI, "Z_UNITS", "\"" + str(zUnits) + "\"", "PYTHON3", "")

        # Delete unwanted "Id" remanant field
        if len(arcpy.ListFields(projectAOI,"Id")) > 0:

            try:
                arcpy.DeleteField_management(projectAOI,"Id")
            except:
                pass

        # -------------------------------------------------------------------------------------------- notify user of Area and Acres of AOI
        aoiDesc = arcpy.da.Describe(projectAOI)
        aoiSR = aoiDesc['spatialReference']
        aoiLinearUnits = aoiSR.linearUnitName
        aoiName = aoiDesc['name']

        area =  sum([row[0] for row in arcpy.da.SearchCursor(projectAOI, ("SHAPE@AREA"))])
        acres = area / acreConversionDict.get(aoiLinearUnits)

        if aoiLinearUnits in ('Meter','Meters'):
            AddMsgAndPrint("\t" + aoiName + " Area:  " + str(splitThousands(round(area,2))) + " Sq. Meters",0)

        elif aoiLinearUnits in ('Feet','Foot','Foot_US'):
            AddMsgAndPrint("\t" + aoiName + " Area:  " + str(splitThousands(round(area,2))) + " Sq. Ft.",0)

        else:
            AddMsgAndPrint("\t" + aoiName + " Area:  " + str(splitThousands(round(area,2))),0)

        AddMsgAndPrint("\t" + aoiName + " Acres: " + str(splitThousands(round(acres,2))) + " Acres",0)

        # ------------------------------------------------------------------------------------------------- Clip inputDEM
        # DEM is in PCS (Local DEM or WMS)
        if bProjectedCS:
            outExtract = ExtractByMask(inputDEM, projectAOI)
            outExtract.save(DEM_aoi)
            AddMsgAndPrint("\nSuccessully Clipped " + os.path.basename(inputDEM) + " DEM using " + os.path.basename(projectAOI))

        # DEM is in GCS (Local DEM or WMS)
        else:
            DEM_aoi,zFactor = extractSubsetFromGCSdem(inputDEM,zUnits)

        # ------------------------------------------------------------------------------------------------ Create Smoothed Contours
        # Smooth DEM and Create Contours if user-defined interval is greater than 0 and valid
        createContours = False

        if interval > 0:
            createContours = True

        else:
            createContours = False
            AddMsgAndPrint("\nContours will not be created since interval was not specified or set to 0",0)

        if createContours:

            # Run Focal Statistics on the DEM_aoi for the purpose of generating smooth contours
            DEMsmooth = FocalStatistics(DEM_aoi,"RECTANGLE 3 3 CELL","MEAN","DATA")

            Contour(DEMsmooth, Contours, interval, "0", zFactor)
            arcpy.AddField_management(Contours, "Index", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
            arcpy.Delete_management(DEMsmooth)

            AddMsgAndPrint("\nSuccessfully Created " + str(interval) + " foot Contours from " + os.path.basename(DEM_aoi) + " using a Z-factor of " + str(zFactor))

            # Update Contour index value; strictly for symbolizing
            with arcpy.da.UpdateCursor(Contours,['Contour','Index']) as cursor:
                 for row in cursor:

                    if (row[0]%interval * 5) == 0:
                        row[1] = 1
                    else:
                        row[1] = 0
                    cursor.updateRow(row)

            # Delete unwanted "Id" remanant field
            if len(arcpy.ListFields(Contours,"Id")) > 0:

                try:
                    arcpy.DeleteField_management(Contours,"Id")
                except:
                    pass

        # ---------------------------------------------------------------------------------------------- Create Hillshade and Depth Grid
        # Process: Creating Hillshade from DEM_aoi
        outHillshade = Hillshade(DEM_aoi, "315", "45", "NO_SHADOWS", zFactor)
        outHillshade.save(Hillshade_aoi)
        AddMsgAndPrint("\nSuccessfully Created Hillshade from " + os.path.basename(DEM_aoi))
        fill = False

        try:
            # Fills sinks in DEM_aoi to remove small imperfections in the data.
            outFill = Fill(DEM_aoi)
            AddMsgAndPrint("\nSuccessfully filled sinks in " + os.path.basename(DEM_aoi) + " to create Depth Grid")
            fill = True

        except:
            AddMsgAndPrint("\n\nError encountered while filling sinks on " + os.path.basename(DEM_aoi) + "\n")
            AddMsgAndPrint("Depth Grid will not be created\n",1)
            print_exception()

        if fill:
            # DEM_aoi - Fill_DEMaoi = FilMinus
            outMinus = Minus(outFill,DEM_aoi)

            # Create a Depth Grid; Any pixel where there is a difference write it out
            outCon = Con(outMinus,outMinus,"", "VALUE > 0")
            outCon.save(depthGrid)

            # Delete unwanted rasters
            arcpy.Delete_management(outFill)
            arcpy.Delete_management(outMinus)

            AddMsgAndPrint("\nSuccessfully Created Depth Grid",0)

        # ------------------------------------------------------------------------------------------------ Compact FGDB
        try:
            arcpy.Compact_management(watershedGDB_path)
            AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path))
        except:
            pass

        # ------------------------------------------------------------------------------------------------ Prepare to Add to Arcmap
        if createContours:
            arcpy.SetParameterAsText(5, Contours)

        arcpy.SetParameterAsText(6, projectAOI)
        arcpy.SetParameterAsText(7, DEM_aoi)
        arcpy.SetParameterAsText(8, Hillshade_aoi)
        arcpy.SetParameterAsText(9, depthGrid)

        AddMsgAndPrint("\nAdding Layers to ArcGIS Pro\n")

    except:
        print_exception()

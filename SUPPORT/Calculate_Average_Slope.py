# ==========================================================================================
# Name: Calculate_Average_Slope.py
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
# Updated  7/29/2020 - Adolfo Diaz
#
# - Updated and Tested for ArcGIS Pro 2.4.2 and python 3.6
# - All temporary raster layers such as Fill and Minus are stored in Memory and no longer
#   written to hard disk.
# - MEAN values will always be determed by zonal statistics.  The original script mined the
#   properties of the slope if there was only 1 AOI and use zonal statistics for multiple AOIs.
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
    f.write("\n##################################################################\n")
    f.write("Executing \"Calculate Average Slope\" Tool \n")
    f.write("User Name: " + getpass.getuser()+ "\n")
    f.write("Date Executed: " + time.ctime()+ "\n")
    f.write("ArcGIS Version: " + str(arcpy.GetInstallInfo()['Version']) + "\n")
    f.write("User Parameters:\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tDem: " + inputDEM + "\n")
    f.write("\tElevation Z-units: " + zUnits + "\n")
    f.write("\tSlope Type: " + slopeType + "\n")

    f.close
    del f

## ================================================================================================================
def splitThousands(someNumber):
# will determine where to put a thousands seperator if one is needed.
# Input is an integer.  Integer with or without thousands seperator is returned.

    try:
        return re.sub(r'(\d{3})(?=\d)', r'\1,', str(someNumber)[::-1])[::-1]
    except:
        print_exception()
        return someNumber

## ================================================================================================================
# Import system modules
import arcpy, sys, os, traceback, re
from arcpy.sa import *

if __name__ == '__main__':

    try:

        # Check out Spatial Analyst License
        if arcpy.CheckExtension("spatial") == "Available":
            arcpy.CheckOutExtension("spatial")
        else:
            arcpy.AddError("Spatial Analyst Extension not enabled. Please enable Spatial analyst from the Tools/Extensions menu\n",2)
            exit()

        #--------------------------------------------------------------------- Input Parameters
        userWorkspace = arcpy.GetParameterAsText(0)
        inputDEM = arcpy.GetParameterAsText(1)
        zUnits = arcpy.GetParameterAsText(2)
        AOI = arcpy.GetParameterAsText(3)
        slopeType = arcpy.GetParameterAsText(4)

        # Set environmental variables
        arcpy.env.parallelProcessingFactor = "75%"
        arcpy.env.overwriteOutput = True
        arcpy.env.geographicTransformations = "WGS_1984_(ITRF00)_To_NAD_1983"
        arcpy.env.resamplingMethod = "BILINEAR"
        arcpy.env.pyramid = "PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP"

        # --------------------------------------------------------------------------------------------- Define Variables
        projectName = arcpy.ValidateTableName(os.path.basename(userWorkspace).replace(" ","_"))
        textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.txt"

        watershedGDB_name = os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.gdb"  # replace spaces for new FGDB name
        watershedGDB_path = userWorkspace + os.sep + watershedGDB_name
        watershedFD = watershedGDB_path + os.sep + "Layers"
        AOIpath = arcpy.da.Describe(AOI)['catalogPath']

        # Permanent Datasets
        projectAOI = watershedFD + os.sep + projectName + "_AOI"
        AOIname = projectName + "_AOI"

        # ----------------------------- Temporary Datasets
        slopeStats = watershedGDB_path + os.sep + "slopeStats"

        # ArcGIS Pro Layers
        aoiOut = "" + projectName + "_AOI"

        # record basic user inputs and settings to log file for future purposes
        logBasicSettings()

        # --------------------------------------------------------------------- Gather DEM Info
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

        zFactorList = [[1.0,         0.3048, 0.01,      0.0254],
                       [3.280839896, 1.0,    0.0328084, 0.083333],
                       [100.0,       30.48,  1.0,       2.54],
                       [39.3701,     12.0,   0.393701,  1.0]]

        # Input DEM Spatial Reference Information
        demPath = arcpy.da.Describe(inputDEM)['catalogPath']
        demDesc = arcpy.da.Describe(demPath)
        demName = demDesc['name']
        demCellSize = demDesc['meanCellWidth']
        demSR = demDesc['spatialReference']
        demSRname = demSR.name
        demLinearUnits = demSR.linearUnitName
        demFormat = demDesc['format']
        demCoordType = demSR.type

        if demLinearUnits in ('Meter','Meters'):
            demLinearUnits = "Meters"
        elif demLinearUnits in ('Foot','Feet','Foot_US'):
            demLinearUnits = "Feet"

        # Coordinate System must be a Projected Type in order to continue.
        # zfactor will be applied to slope calculation if zUnits are different than XY units

        if demCoordType == "Projected":

            zFactor = zFactorList[unitLookUpDict.get(zUnits)][unitLookUpDict.get(demLinearUnits)]

            AddMsgAndPrint("\nDEM Information: " + demName)
            AddMsgAndPrint("\tProjection Name: " + demSRname)
            AddMsgAndPrint("\tXY Linear Units: " + demLinearUnits)
            AddMsgAndPrint("\tElevation Values (Z): " + zUnits)
            AddMsgAndPrint("\tCell Size: " + str(demCellSize) + " " + demLinearUnits)
            AddMsgAndPrint("\tZ-Factor: " + str(zFactor))

        else:
            AddMsgAndPrint("\n\n\t" + os.path.basename(inputDEM) + " is NOT in a projected Coordinate System. Exiting...",2)
            exit()

        # Create Watershed FGDB and feature dataset if it doesn't exist
        if not arcpy.Exists(watershedGDB_path):
            arcpy.CreateFileGDB_management(userWorkspace, watershedGDB_name)
            arcpy.CreateFeatureDataset_management(watershedGDB_path, "Layers", sr)
            AddMsgAndPrint("\nSuccessfully created File Geodatabase: " + watershedGDB_name,0)

        # if GDB already existed but feature dataset doesn't
        if not arcpy.Exists(watershedFD):
            arcpy.CreateFeatureDataset_management(watershedGDB_path, "Layers", sr)

        # ----------------------------------------------------------------------------------------------- Create New AOI
        # if AOI path and  projectAOI path are not the same then assume AOI was manually digitized
        # or input is some from some other feature class/shapefile

        # AOI and projectAOI paths are not the same
        if AOIpath != projectAOI:

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

        # -------------------------------------------------------------------------------------------- Exit if AOI was not a polygon
        if arcpy.da.Describe(projectAOI)['shapeType'] != "Polygon":
            AddMsgAndPrint("\n\nYour Area of Interest must be a polygon layer!.....Exiting!",2)
            exit()

        # --------------------------------------------------------------------------------------------  Populate AOI with DEM Properties
        # Write input DEM name to AOI
        if len(arcpy.ListFields(projectAOI,"INPUT_DEM")) < 1:
            arcpy.AddField_management(projectAOI, "INPUT_DEM", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED")

        arcpy.CalculateField_management(projectAOI, "INPUT_DEM", "\"" + demName + "\"", "PYTHON3")

        # Write XY Units to AOI
        if len(arcpy.ListFields(projectAOI,"XY_UNITS")) < 1:
            arcpy.AddField_management(projectAOI, "XY_UNITS", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED")

        arcpy.CalculateField_management(projectAOI, "XY_UNITS", "\"" + demLinearUnits + "\"", "PYTHON3")

        # Write Z Units to AOI
        if len(arcpy.ListFields(projectAOI,"Z_UNITS")) < 1:
            arcpy.AddField_management(projectAOI, "Z_UNITS", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED")

        arcpy.CalculateField_management(projectAOI, "Z_UNITS", "\"" + str(zUnits) + "\"", "PYTHON3")

       #--------------------------------------------------------------------- Add uniqueID, Acre Field, and Avg_Slope field
        if not len(arcpy.ListFields(projectAOI,"Acres")) > 0:
            arcpy.AddField_management(projectAOI, "Acres", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")
        arcpy.CalculateField_management(projectAOI, "Acres", "!shape.area@acres!", "PYTHON_9.3")

        if not len(arcpy.ListFields(projectAOI,"Avg_Slope")) > 0:
            arcpy.AddField_management(projectAOI, "Avg_Slope", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")

        # This value is needed to standardize all possible inputs for objectID headings getting appended for cases where objectID already exists in inputs
        if not len(arcpy.ListFields(projectAOI,"UID")) > 0:
            arcpy.AddField_management(projectAOI, "UID", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED")

        objectIDfld = "!" + arcpy.da.Describe(projectAOI)['OIDFieldName'] + "!"
        arcpy.CalculateField_management(projectAOI, "UID", objectIDfld, "PYTHON3")

        # ----------------------------------------------------------------------------------------------- Calculate slope and return Avg.Slope
        # extract AOI area
        DEM_aoi = ExtractByMask(inputDEM, AOI)
        AddMsgAndPrint("\nSuccessully Clipped " + os.path.basename(inputDEM) + " using " + os.path.basename(projectAOI))

        # Smooth the DEM to remove noise
        DEMsmooth = FocalStatistics(DEM_aoi, "RECTANGLE 3 3 CELL","MEAN","DATA")
        AddMsgAndPrint("\nSuccessully Smoothed the Clipped DEM")

        # Calculate Slope using user specified slopeType and appropriate Z factor
        if slopeType == "Degrees":
            slopeType = "DEGREE"
        else:
            slopeType = "PERCENT_RISE"

        # create slopeGrid
        slopeGrid = Slope(DEMsmooth, slopeType, zFactor)
        AddMsgAndPrint("\nSuccessully Created Slope Grid using a Z-factor of " + str(zFactor))

        # retreive slope average from zonal statistics if there is more than 1 AOI delineation
        ZonalStatisticsAsTable(projectAOI, "UID", slopeGrid, slopeStats, "DATA")
        AddMsgAndPrint("\nSuccessfully Calculated Average Slope for " + str(arcpy.GetCount_management(projectAOI).getOutput(0)) + " AOIs:",0)

        # create an update cursor for each row of the AOI table and pull in the corresponding record from the slopestats table
        with arcpy.da.UpdateCursor(projectAOI,['UID','Avg_Slope','Acres','SHAPE@AREA']) as cursor:
            for row in cursor:
                aoiID = row[0]
                expression = (u'{} = ' + str(aoiID)).format(arcpy.AddFieldDelimiters(slopeStats, "UID"))
                avgSlope = [row[0] for row in arcpy.da.SearchCursor(slopeStats,["MEAN"],where_clause=expression)][0]
                row[1] = avgSlope
                cursor.updateRow(row)

                # Inform the user of Watershed Acres, area and avg. slope
                AddMsgAndPrint("\n\tAOI ID: " + str(aoiID))
                AddMsgAndPrint("\t\tAcres: " + str(splitThousands(round(row[2],2))))
                AddMsgAndPrint("\t\tArea: " + str(splitThousands(round(row[3],2))) + " Sq. " + demLinearUnits)
                AddMsgAndPrint("\t\tAvg. Slope: " + str(round(avgSlope,2)))

        arcpy.Delete_management(slopeStats)

        # ------------------------------------------------------------------------------------------------ Compact FGDB
        arcpy.Compact_management(watershedGDB_path)
        AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path))

        # ------------------------------------------------------------------------------------------------ Prepare to Add to Arcmap
        # Remove the AOI from the map if it is present in the map
        aprx = arcpy.mp.ArcGISProject("CURRENT")

        for maps in aprx.listMaps():
            for lyr in maps.listLayers():
                if lyr.name in (AOIname):
                    maps.removeLayer(lyr)

        # Prep for proper layer file labels importing as determined by slope type selected to be run
        if slopeType == "PERCENT_RISE":
            arcpy.SetParameterAsText(5, projectAOI)
        else:
            arcpy.SetParameterAsText(6, projectAOI)

        AddMsgAndPrint("\nAdding " + str(aoiOut) + " to ArcGIS Pro")

    except:
        print_exception()

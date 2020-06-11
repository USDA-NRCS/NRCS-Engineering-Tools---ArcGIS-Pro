# ==========================================================================================
# Name: Wascob_AOI.py
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

# Created by Peter Mead, 2013
# Updated by Chris Morse, USDA NRCS, 2019
##
# ===============================================================================================================
# ===============================================================================================================
#
#                 WASCOB_AOI.py for LiDAR Based Design of Water and Sediment Control Basins
#
#                 Author:   Originally Scripted by Peter Mead, MN USDA-NRCS with assistance
#                           from Adolfo Diaz, WI NRCS.
#
#                           Graciously updated and maintained by Peter Mead, under GeoGurus Group.
#
#                 Contact: peter.mead@geogurus.com
#
#                 Notes:
#                           Rescripted in arcpy 12/2013.
#
#                           3/2014 - removed of "Relative Survey" as default.
#                           Added option of creating "Relative Survey" or using MSL (Mean Sea Level) elevations.
#
# ===============================================================================================================
# ===============================================================================================================
#
# Checks a user supplied workspace's file structure and creates
# directories as necessary for 638 Tool Workflow.
#
# Determines input DEM's Native Resolution, Spatial Reference, and Elevation format to
# apply proper conversion factors and projection where necessary throughout the workflow.
#
# Clips a user supplied DEM to a User defined area of interest, Saving a clipped
# "AOI DEM", Polygon Mask, and Hillshade of the Area of interest.
#
# Converts (if necessary) Clipped Input to Feet, and creates "Project DEM" --  with
# elevations rounded to nearest 1/10th ft for the area of interest. Option to use MSL elevations
# or create " Relative Survey". Relative survey is useful when projects will be staked in
# field using a laser vs. msl when using a vrs system.
#
# The Project DEM is "smoothed" using focal mean within a 3 cell x 3 cell window,
# and indexed contour lines are generated at the user defined interval.
#
# A "Depth Grid" is also created to show area of the DEM where water would theoretically
# pool due to either legitimate sinks or "digital dams" existing in the raster data.
#
# All Derived Layers are added to the Current MXD's table of contents upon successful execution

# ==========================================================================================
# Updated  6/11/2020 - Adolfo Diaz
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
#
# ===============================================================================================================

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
    f.write("Executing \"WASCOB: Define Area of Interest\" tool\n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write(arcInfo['ProductName'] + ": " + arcInfo['Version'] + "\n")
    f.write("User Parameters:\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tInput Dem: " + demPath)
    f.write("\tElevation Z-units: " + zUnits + "\n")
    f.write("\tContour Interval: " + str(interval) + "\n")

    f.close
    del f

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
# Import system modules
import sys, os, arcpy, string, traceback, re
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
        # Comment following six lines to run from pythonWin
        userWorkspace = arcpy.GetParameterAsText(0)     # User Defined Workspace Folder
        inputDEM = arcpy.GetParameterAsText(1)          # Input DEM Raster
        zUnits = arcpy.GetParameterAsText(2)            # Elevation z units of input DEM
        AOI = arcpy.GetParameterAsText(3)               # AOI that was drawn
        interval = float(arcpy.GetParameterAsText(4))   # user defined contour interval
        relSurvey = arcpy.GetParameterAsText(5)         # Optional - Create Relative Survey

        # Set environmental variables
        arcpy.env.parallelProcessingFactor = "75%"
        arcpy.env.overwriteOutput = True
        arcpy.env.geographicTransformations = "WGS_1984_(ITRF00)_To_NAD_1983"

        # Input DEM Spatial Reference Information
        demPath = arcpy.da.Describe(inputDEM)['catalogPath']
        demDesc = arcpy.da.Describe(demPath)
        demName = demDesc['name']
        demCellSize = demDesc['meanCellWidth']
        demSR = demDesc['spatialReference']
        demSRname = demSR.name
        demFormat = demDesc['format']
        demLinearUnits = demSR.linearUnitName
        demCoordType = demSR.type

        # If user selected relative survey, set boolean to create relative dem surface.
        if str.upper(relSurvey) == "TRUE":
            relativeSurvey = True
        else:
            relativeSurvey = False

        # --------------------------------------------------------------------------------------------- Define Variables
        projectName = arcpy.ValidateTableName(os.path.basename(userWorkspace).replace(" ","_"))
        watershedGDB_name = os.path.basename(userWorkspace).replace(" ","_") + "_Wascob.gdb"  # replace spaces for new FGDB name
        watershedGDB_path = userWorkspace + os.sep + watershedGDB_name
        watershedFD = watershedGDB_path + os.sep + "Layers"
        AOIpath = arcpy.da.Describe(AOI)['catalogPath']

        # WASCOB Project Folders:
        DocumentsFolder =  os.path.join(os.path.dirname(sys.argv[0]), "Documents")
        Documents = userWorkspace + os.sep + "Documents"
        gis_output = userWorkspace + os.sep + "gis_output"

        # ------------------------------ Permanent Datasets
        projectAOI = watershedFD + os.sep + projectName + "_AOI"
        Contours = watershedFD + os.sep + projectName + "_Contours_" + str(int(interval)).replace(".","_") + "ft"
        DEM_aoi = watershedGDB_path + os.sep + projectName + "_Raw_DEM"
        Hillshade_aoi = watershedGDB_path + os.sep + projectName + "_Hillshade"
        depthGrid = watershedGDB_path + os.sep + projectName + "_DepthGrid"
        projectDEM = watershedGDB_path + os.sep + projectName + "_Project_DEM"
        DEMsmooth = watershedGDB_path + os.sep + projectName + "_DEMsmooth"

        # ----------------------------- Temporary Datasets
        FilMinus = watershedGDB_path + os.sep + "FilMinus"

        # record basic user inputs and settings to log file for future purposes
        textFilePath = userWorkspace + os.sep + projectName + "_EngTools.txt"
        logBasicSettings()

        ## ---------------------------------------------------------------------------------------------- Z-factor conversion Lookup table
        # lookup dictionary to convert XY units to area.  Key = XY unit of DEM; Value = conversion factor to sq.meters
        acreConversionDict = {'Meters':4046.8564224,'Meter':4046.8564224,'Foot':43560,'Foot_US':43560,'Feet':43560, 'Centimeter':40470000,'Inch':6273000}

        # ---------------------------------------------------------------------------------------------- Check DEM Coordinate System and Linear Units
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

        # AOI spatial reference info
        aoiDesc = arcpy.da.Describe(AOIpath)
        aoiSR = aoiDesc['spatialReference']
        aoiSRname = aoiSR.name
        aoiLinearUnits = aoiSR.linearUnitName
        aoiName = aoiDesc['name']
        aoiDemCoordType = aoiSR.type

        if demCoordType != 'Projected':
            AddMsgAndPrint("\n" + os.path.basename(inputDEM) + " is not in a Projected Coordinate System. Exiting...",2)
            exit()

        arcpy.env.outputCoordinateSystem = demSR

        AddMsgAndPrint(" \nGathering information about DEM: " + demName)
        AddMsgAndPrint("\tProjection Name: " + demSR.name)
        AddMsgAndPrint("\tXY Units: " + demLinearUnits)
        AddMsgAndPrint("\tElevation Values (Z): " + zUnits)
        AddMsgAndPrint("\tCell Size: " + str(demCellSize) + " " + demLinearUnits)

        # ---------------------------------------------------------------------------------------------- Delete old datasets
        datasetsToRemove = (Contours,Hillshade_aoi,depthGrid,projectDEM,DEMsmooth)       # Full path of layers
        datasetsBaseName = [os.path.basename(x) for x in datasetsToRemove]  # layer names as they would appear in .aprx

        # Remove layers from ArcGIS Pro Session if executed from an .aprx
        try:
            aprx = arcpy.mp.ArcGISProject("CURRENT")

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
                        AddMsgAndPrint("\nRemoving old datasets from FGDB: " + watershedGDB_name )
                        x += 1

                    try:
                        arcpy.Delete_management(dataset)
                        AddMsgAndPrint("\tDeleting....." + os.path.basename(dataset))
                    except:
                        pass

            # If FGDB Exists but FD not present, create it.
            if not arcpy.Exists(watershedFD):
                arcpy.CreateFeatureDataset_management(watershedGDB_path, "Layers", demSR)

        # Otherwise FGDB does not exist, create it.
        else:
            arcpy.CreateFileGDB_management(userWorkspace, watershedGDB_name)
            arcpy.CreateFeatureDataset_management(watershedGDB_path, "Layers", sr)
            AddMsgAndPrint("\nSuccessfully created File Geodatabase: " + watershedGDB_name,0)

        # If Documents folder not present, create and copy required files to it
        if not arcpy.Exists(Documents):
            arcpy.CreateFolder_management(userWorkspace, "Documents")
            if arcpy.Exists(DocumentsFolder):
                arcpy.Copy_management(DocumentsFolder, Documents, "Folder")

        # Create gis_output folder if not present
        if not arcpy.Exists(gis_output):
            arcpy.CreateFolder_management(userWorkspace, "gis_output")

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

        # ---------------------------------------------------------------------------------------------- Count the number of features in AOI
        # Exit if AOI contains more than 1 digitized area.
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

        arcpy.CalculateField_management(projectAOI, "XY_UNITS", "\"" + demLinearUnits + "\"", "PYTHON3", "")

        # Write Z Units to AOI
        if len(arcpy.ListFields(projectAOI,"Z_UNITS")) < 1:
            arcpy.AddField_management(projectAOI, "Z_UNITS", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED")

        arcpy.CalculateField_management(projectAOI, "Z_UNITS", "\"" + str(zUnits) + "\"", "PYTHON3")

        # Delete unwanted "Id" remanant field
        if len(arcpy.ListFields(projectAOI,"Id")) > 0:

            try:
                arcpy.DeleteField_management(projectAOI,"Id")
            except:
                pass

        # -------------------------------------------------------------------------------------------- notify user of Area and Acres of AOI
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
        outExtract = ExtractByMask(inputDEM, projectAOI)
        outExtract.save(DEM_aoi)
        AddMsgAndPrint("\nSuccessully Clipped " + os.path.basename(inputDEM) + " DEM using " + os.path.basename(projectAOI))

        # --------------------------------------------------------------- Round Elevation Values to nearest 10th
        zFactortoFeet = zFactorList[unitLookUpDict.get('Feet')][unitLookUpDict.get(zUnits)]
        if not relativeSurvey:
            AddMsgAndPrint("\nCreating Project DEM using Mean Sea Level Elevations")
        else:
            AddMsgAndPrint("\nCreating Project DEM using Relative Elevations (0 ft. to Maximum rise)")

        # Convert to feet if necessary
        if zUnits != "Feet":
            AddMsgAndPrint("\tConverting Elevation values to Feet using z-factor of " + str(zFactortoFeet),1)
            DEMft = Times(DEM_aoi, zFactortoFeet)
            DEM_aoi = DEMft

        if relativeSurvey:
            AddMsgAndPrint("\tDetermining relative elevations")

            AddMsgAndPrint("\tRetrieving minimum elevation")
            MinDEM = ZonalStatistics(projectAOI,"OBJECTID", DEM_aoi, "MINIMUM", "DATA")

            # Subtract Minimum Elevation from all cells in AOI
            AddMsgAndPrint("\tDetermining maximum rise")
            MinusDEM = Minus(DEM_aoi, MinDEM)
            DEM_aoi = MinusDEM

        AddMsgAndPrint("\tRounding to nearest 1/10th ft")
        # Multiply DEM by 10 for rounding...
        intDEM = Int(Plus(Times(DEM_aoi, 10),0.5))

        # Restore the decimal point for 1/10th foot.
        # This becomes "Project DEM", a raster surface in 1/10th foot values
        outTimes = Times(intDEM, 0.1)
        outTimes.save(projectDEM)

        AddMsgAndPrint("\tSuccessfully created Project DEM in 1/10th foot values")

        # ------------------------------------------------------------------------------------------------ Create Contours
        AddMsgAndPrint("\nCreating " + str(interval) + "-foot contours...",0)

        # Run Focal Statistics on the Project DEM to generate smooth contours
        outFocal = FocalStatistics(projectDEM,"RECTANGLE 3 3 CELL","MEAN","DATA")
        outFocal.save(DEMsmooth)

        # Create Contours from DEMsmooth
        # Z factor to use here is 1 because vertical values of the input DEM have been forced to be feet.
        Contour(DEMsmooth, Contours, interval, "0", 1)
        AddMsgAndPrint("\nSuccessfully Created " + str(interval) + " foot Contours from " + os.path.basename(projectDEM))
        arcpy.AddField_management(Contours, "Index", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

        # Update Contour index value; strictly for symbolizing
        with arcpy.da.UpdateCursor(Contours,['Contour','Index']) as cursor:
             for row in cursor:
                if (row[0]%(interval * 5)) == 0:
                    row[1] = 1
                else:
                    row[1] = 0
                cursor.updateRow(row)

        AddMsgAndPrint("\tSuccessfully indexed Contour lines")

        # Delete unwanted "Id" remanant field
        if len(arcpy.ListFields(Contours,"Id")) > 0:

            try:
                arcpy.DeleteField_management(Contours,"Id")
            except:
                pass

        # ---------------------------------------------------------------------------------------------- Create Hillshade and Depth Grid
        # Process: Creating Hillshade from DEM_aoi
        # This section needs a different Zfactor than just the feet conversion multiplier used earlier!
        # Update Zfactor for use with hillshade. This is because the hillshade is created with the original DEM, prior to conversion to vertical feet.

        zFactor = zFactorList[unitLookUpDict.get(zUnits)][unitLookUpDict.get(demLinearUnits)]

        AddMsgAndPrint("\nCreating Hillshade for AOI...",0)
        DEM_aoi = watershedGDB_path + os.sep + projectName + "_Raw_DEM"

        outHillshade = Hillshade(DEM_aoi, "315", "45", "NO_SHADOWS", zFactor)
        outHillshade.save(Hillshade_aoi)
        AddMsgAndPrint("\nSuccessfully Created Hillshade from " + os.path.basename(DEM_aoi) + " using a Z-factor of " + str(zFactortoFeet))

        outFill = Fill(DEM_aoi)
        AddMsgAndPrint("\nSuccessfully filled sinks in " + os.path.basename(DEM_aoi) + " to create Depth Grid")

        # DEM_aoi - Fill_DEMaoi = FilMinus
        outMinus = Minus(outFill,DEM_aoi)

        # Create a Depth Grid; Any pixel where there is a difference write it out
        outCon = Con(outMinus,outMinus,"", "VALUE > 0")
        outCon.save(depthGrid)
        AddMsgAndPrint("\nSuccessfully Created Depth Grid")

        # ------------------------------------------------------------------------------------------------ Prepare to Add to Arcmap
        AddMsgAndPrint("\nAdding Layers to ArcGIS Pro")
        arcpy.SetParameterAsText(6, Contours)
        arcpy.SetParameterAsText(7, projectAOI)
        arcpy.SetParameterAsText(8, projectDEM)
        arcpy.SetParameterAsText(9, Hillshade_aoi)
        arcpy.SetParameterAsText(10, depthGrid)

        # ------------------------------------------------------------------------------------------------ Compact FGDB
        AddMsgAndPrint("\n\nCompacting FGDB: " + os.path.basename(watershedGDB_path))
        arcpy.Compact_management(watershedGDB_path)

    except:
        print_exception()

# ==========================================================================================
# Name: CreatePoolAtDesiredElevation.py
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
# Updated  4/24/2020 - Adolfo Diaz
#
# - This is the same script as 'CalculateStageStorageVolume.py' with the following Modfications:
#       1) Removed the bCreatePools boolean
#       2) Pools at increment levels will not be created
#       3) Pools layers and merge layers were deleted
#       4) Removed capability to produce storage table
# - Updated and Tested for ArcGIS Pro 2.4.2 and python 3.6
# - All temporary raster layers such as Times and SetNull are stored in Memory and no longer
#   written to hard disk.
# - Created new symbologoy layer CreatePoolAtDesiredElevation.lyrx b/c the old oned didn't
#   label the output polygon.
# - All describe functions use the arcpy.da.Describe functionality.
# - All field calculation expressions are in PYTHON3 format.
# - Created dictionaries for all conversion units and factors and renamed them to more
# - logical names.
# - Used acre conversiont dictionary and z-factor lookup table
# - Created lookup dictionaries for acreConversions, ftConversions, convToAcreFootFactors
# - All cursors were updated to arcpy.da
# - Added code to remove layers from an .aprx rather than simply deleting them
# - Added code to add tables to an .aprx
# - Updated AddMsgAndPrint to remove ArcGIS 10 boolean and gp function
# - Updated print_exception function.  Traceback functions slightly changed for Python 3.6.
# - Added Snap Raster environment
# - Added parallel processing factor environment
# - swithced from exit() to exit()
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
        f.write("Executing \"Calculate Stage Storage Volume\" Tool\n")
        f.write("User Name: " + getpass.getuser() + "\n")
        f.write("Date Executed: " + time.ctime() + "\n")
        f.write(arcInfo['ProductName'] + ": " + arcInfo['Version'] + "\n")
        f.write("User Parameters:\n")
        f.write("\tWorkspace: " + userWorkspace + "\n")
        f.write("\tInput Dem: " + arcpy.Describe(inputDEM).CatalogPath + "\n")
        f.write("\tInput Watershed Boundary: " + str(inPool) + "\n")
        f.write("\tPool Elevation: " + str(maxElev) + " Feet\n")
        f.write("\tOutput Pool Polygon: " + str(poolExit) + "\n")

        if len(zUnits) > 0:
            f.write("\tElevation Z-units: " + zUnits + "\n")
        else:
            f.write("\tElevation Z-units: BLANK" + "\n")

        f.write("\tInput Watershed or Pool Mask: " + str(inPool) + "\n")

        f.close
        del f

    except:
        print_exception()
        exit()

## ================================================================================================================
def createPool(elevationValue,storageTxtFile):

    try:

        global convToFeetFactor,acreConversion,ftConversion,convToAcreFootFactor

        poolPolygonTemp = "in_memory" + os.sep + os.path.basename(arcpy.CreateScratchName("poolPolygonTemp",data_type="FeatureClass",workspace=watershedGDB_path))

        # Create new raster of only values below an elevation value by nullifying
        # cells above the desired elevation value.
        conStatement = "Value > " + str(elevationValue)
        valuesAboveElev = SetNull(tempDEM, tempDEM, conStatement)

        # Multiply every pixel by 0 and convert to integer for vectorizing
        zeroValues = Times(valuesAboveElev, 0)
        zeroInt = Int(zeroValues)

        # Convert to polygon and dissolve
        arcpy.RasterToPolygon_conversion(zeroInt, poolPolygonTemp, "NO_SIMPLIFY", "VALUE")
        arcpy.Dissolve_management(poolPolygonTemp, poolExit, "", "", "MULTI_PART", "DISSOLVE_LINES")

        arcpy.AddField_management(poolExit, "ELEV_FEET", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")
        arcpy.AddField_management(poolExit, "DEM_ELEV", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")
        arcpy.AddField_management(poolExit, "POOL_ACRES", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")
        arcpy.AddField_management(poolExit, "POOL_SQFT", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")
        arcpy.AddField_management(poolExit, "ACRE_FOOT", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")
        arcpy.AddField_management(poolExit, "CUBIC_FEET", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")
        arcpy.AddField_management(poolExit, "CUBIC_METERS", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")

        # open storageCSV file and read the last line which should represent the last pool
        file = open(storageTxtFile)
        lines = file.readlines()
        file.close()

        area2D = float(lines[len(lines)-1].split(',')[4])
        volume = float(lines[len(lines)-1].split(',')[6])

        elevFeetCalc = round(elevationValue * convToFeetFactor,1)
        poolAcresCalc = round(area2D / acreConversion,1)
        poolSqftCalc = round(area2D / ftConversion,1)
        acreFootCalc = round(volume / convToAcreFootFactor,1)
        cubicMeterCalc = round(volume * convToCubicMeterFactor,1)
        cubicFeetCalc = round(volume * convToCubicFeetFactor,1)

        arcpy.CalculateField_management(poolExit, "ELEV_FEET", elevFeetCalc,  "PYTHON3")
        arcpy.CalculateField_management(poolExit, "DEM_ELEV", elevationValue,  "PYTHON3")
        arcpy.CalculateField_management(poolExit, "POOL_ACRES", poolAcresCalc,  "PYTHON3")
        arcpy.CalculateField_management(poolExit, "POOL_SQFT", poolSqftCalc,  "PYTHON3")
        arcpy.CalculateField_management(poolExit, "ACRE_FOOT", acreFootCalc,  "PYTHON3")
        arcpy.CalculateField_management(poolExit, "CUBIC_METERS", cubicMeterCalc,  "PYTHON3")
        arcpy.CalculateField_management(poolExit, "CUBIC_FEET", cubicFeetCalc,  "PYTHON3")

        AddMsgAndPrint("\n\tCreated " + poolName + ":")
        AddMsgAndPrint("\t\tElevation " + str(elevFeetCalc) + " Ft")
        AddMsgAndPrint("\t\tArea:   " + str(splitThousands(poolSqftCalc)) + " Sq.Feet")
        AddMsgAndPrint("\t\tArea:   " + str(splitThousands(poolAcresCalc)) + " Acres")
        AddMsgAndPrint("\t\tVolume: " + str(splitThousands(acreFootCalc)) + " Ac. Foot")
        AddMsgAndPrint("\t\tVolume: " + str(splitThousands(cubicMeterCalc)) + " Cubic Meters")
        AddMsgAndPrint("\t\tVolume: " + str(splitThousands(cubicFeetCalc)) + " Cubic Feet")

        #------------------------------------------------------------------------------------ Delete Temp Layers
        arcpy.Delete_management(poolPolygonTemp)
        del valuesAboveElev,zeroValues,zeroInt

        return True

    except:
        AddMsgAndPrint("\nFailed to Create Pool Polygon for elevation value: " + str(elevationValue),1)
        print_exception()
        return False

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
import sys, os, string, traceback, re
from arcpy.sa import *

if __name__ == '__main__':

    try:

        # Check out 3D and SA licenses
        if arcpy.CheckExtension("3d") == "Available":
            arcpy.CheckOutExtension("3d")
        else:
            arcpy.AddError("\n3D analyst extension is not enabled. Please enable 3D analyst from the Tools/Extensions menu\n")
            exit()

        if arcpy.CheckExtension("spatial") == "Available":
            arcpy.CheckOutExtension("spatial")
        else:
            arcpy.AddError("\nSpatial Analyst Extension not enabled. Please enable Spatial analyst from the Tools/Extensions menu\n")
            exit()

        #----------------------------------------------------------------------------------------- Input Parameters
        inputDEM = arcpy.GetParameterAsText(0)
        zUnits = arcpy.GetParameterAsText(1)
        inPool = arcpy.GetParameterAsText(2)
        maxElev = float(arcpy.GetParameterAsText(3))

        # Uncomment the following 6 lines to run from pythonWin
##        inputDEM = r'E:\NRCS_Engineering_Tools_ArcPro\Testing\Testing_EngTools.gdb\Testing_DEM'
##        inPool = r'E:\NRCS_Engineering_Tools_ArcPro\Testing\Testing_EngTools.gdb\Layers\StageStorage_Input'
##        maxElev = 1150
##        zUnits = "Meters"

        # Set environmental variables
        arcpy.env.parallelProcessingFactor = "75%"
        arcpy.env.overwriteOutput = True

        # ---------------------------------------------------------------------------------------- Define Variables
        inPool = arcpy.da.Describe(inPool)['catalogPath']

        if inPool.find('.gdb') > -1 or inPool.find('.mdb') > -1:
            watershedGDB_path = inPool[:inPool.find('.')+4]

        elif inPool.find('.shp')> -1:
            watershedGDB_path = os.path.dirname(inPool) + os.sep + os.path.basename(os.path.dirname(inPool)).replace(" ","_") + "_EngTools.gdb"

        else:
            AddMsgAndPrint("\n\nPool Polygon must either be a feature class or shapefile!.....Exiting",2)
            exit()

        watershedGDB_name = os.path.basename(watershedGDB_path)
        watershedFD = watershedGDB_path + os.sep + "Layers"
        poolName = os.path.basename(inPool) + "_Pool_" + str(maxElev).replace(".","_")
        poolExit = watershedFD + os.sep + poolName

        userWorkspace = os.path.dirname(watershedGDB_path)

        # Path of Log file; Log file will record everything done in a workspace
        textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.txt"

        # record basic user inputs and settings to log file for future purposes
        logBasicSettings()

        # ---------------------------------------------------------------------------------------------- Check Parameters
        # Exit if inPool has more than 1 polygon
        if int(arcpy.GetCount_management(inPool).getOutput(0)) > 1:
            AddMsgAndPrint("\n\nOnly ONE Watershed or Pool Polygon can be submitted!.....Exiting!",2)
            AddMsgAndPrint("Either export an individual polygon from your " + os.path.basename(inPool) + " Layer",2)
            AddMsgAndPrint("make a single selection, or provide a different input...EXITING\n",2)
            exit()

        # Exit if inPool is not a Polygon geometry
        if arcpy.da.Describe(inPool)['shapeType'] != "Polygon":
            AddMsgAndPrint("\n\nYour Watershed or Pool Area must be a polygon layer!.....Exiting!\n",2)
            exit()

        # Exit if Elevation value is less than 1
        if maxElev < 1:
            AddMsgAndPrint("\n\nMaximum Elevation Value must be greater than 0.....Exiting\n",2)
            exit()

        ## ---------------------------------------------------------------------------------------------- Z-factor conversion Lookup table
        arcpy.AddMessage("D")
        # lookup dictionary to convert XY units to area.  Key = XY unit of DEM; Value = conversion factor to sq.meters
        acreConversionDict = {'Meters':4046.8564224,'Meter':4046.8564224,'Foot':43560,'Foot_US':43560,'Feet':43560, 'Centimeter':40470000,'Inch':6273000}
        ftConversionDict = {'Meters':0.092903,'Meter':0.092903,'Foot':1,'Foot_US':1,'Feet':1}
        conversionToAcreFootDict = {'Meters':1233.48184,'Meter':1233.48184,'Foot':43560,'Foot_US':43560,'Feet':43560}  # to acre Foot
        conversionToFtFactorDict = {'Meters':3.280839896,'Meter':3.280839896,'Foot':1,'Foot_US':1,'Feet':1, 'Centimeter':0.0328084, 'Centimeters':0.0328084, 'Inches':0.0833333, 'Inch':0.0833333}
        conversionToCubicMetersDict = {'Meters':1,'Meter':1,'Foot':0.0283168,'Foot_US':0.0283168,'Feet':0.0283168}
        conversionToCubicFeetDict = {'Meters':35.3147,'Meter':35.3147,'Foot':1,'Foot_US':1,'Feet':1}

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
        zFactorList = [[1,0.304800609601219,0.01,0.0254],
                       [3.28084,1,0.0328084,0.083333],
                       [100,30.4800609601219,1.0,2.54],
                       [39.3701,12,0.393701,1.0]]

        # ---------------------------------------------------------------------------------------------- Check DEM Coordinate System and Linear Units
        # Input DEM Spatial Reference Information
        demDesc = arcpy.da.Describe(inputDEM)
        demName = demDesc['name']
        demPath = demDesc['catalogPath']
        demCellSize = demDesc['meanCellWidth']
        demSR = demDesc['spatialReference']
        linearUnits = demSR.linearUnitName
        demCoordType = demSR.type

        acreConversion = acreConversionDict.get(linearUnits)
        ftConversion = ftConversionDict.get(linearUnits)
        convToAcreFootFactor = conversionToAcreFootDict.get(linearUnits)
        convToCubicMeterFactor = conversionToCubicMetersDict.get(linearUnits)
        convToCubicFeetFactor = conversionToCubicFeetDict.get(linearUnits)

        # if zUnits were left blank than assume Z-values are the same as XY units.
        if not len(zUnits) > 0:
            zUnits = linearUnits

        # ----------------------------------------- Retrieve DEM Properties and set Z-unit conversion Factors
        AddMsgAndPrint("\nGathering information about DEM: " + os.path.basename(inputDEM))

        # Coordinate System must be a Projected type in order to continue.
        if demCoordType == "Projected":

            # This will be used to convert elevation values to Feet.
            zFactor = zFactorList[unitLookUpDict.get(zUnits)][unitLookUpDict.get('Feet')]
            convToFeetFactor = conversionToFtFactorDict.get(zUnits)

            AddMsgAndPrint("\tProjection Name: " + demSR.name)
            AddMsgAndPrint("\tXY Linear Units: " + linearUnits)
            AddMsgAndPrint("\tElevation Values (Z): " + zUnits)
            AddMsgAndPrint("\tCell Size: " + str(demCellSize) + " x " + str(demCellSize) + " " + linearUnits)

        else:
            AddMsgAndPrint("\n\n\t" + os.path.basename(inputDEM) + " is NOT in a projected Coordinate System....EXITING",2)
            exit()

        # ----------------------------------- Set Environment Settings
        arcpy.env.extent = "MINOF"
        arcpy.env.cellSize = demCellSize
        arcpy.env.snapRaster = demPath
        arcpy.env.outputCoordinateSystem = demSR
        arcpy.env.workspace = watershedFD

        # --------------------------------------------------------------------------- Create FGDB, FeatureDataset
        # Boolean - Assume FGDB already exists
        bFGDBexists = True

        # Create Watershed FGDB and feature dataset if it doesn't exist
        if not arcpy.Exists(watershedGDB_path):
            arcpy.CreateFileGDB_management(userWorkspace, watershedGDB_name)
            arcpy.CreateFeatureDataset_management(watershedGDB_path, "Layers", demSR)
            AddMsgAndPrint("\nSuccessfully created File Geodatabase: " + watershedGDB_name,1)
            bFGDBexists = False

        # if GDB already existed but feature dataset doesn't
        if not arcpy.Exists(watershedFD):
            arcpy.CreateFeatureDataset_management(watershedGDB_path, "Layers", demSR)

        # --------------------------------------------------------------------- Clean old files if FGDB already existed.
        if bFGDBexists:

            layersToRemove = (poolExit)

            x = 0
            for layer in layersToRemove:
                if arcpy.Exists(layer):

                    # strictly for formatting
                    if x == 0:
                        AddMsgAndPrint("\nRemoving old files from FGDB: " + watershedGDB_name )
                        x += 1

                    try:
                        arcpy.Delete_management(layer)
                        AddMsgAndPrint("\tDeleting....." + os.path.basename(layer))
                    except:
                        pass

        # --------------------------------------------------------------------------------- ClipDEM to User's Pool or Watershed
        tempDEM = ExtractByMask(inputDEM, inPool)

        # User specified max elevation value must be within min-max elevation range of clipped dem
        demTempMaxElev = round(float(arcpy.GetRasterProperties_management(tempDEM, "MAXIMUM").getOutput(0)))
        demTempMinElev = round(float(arcpy.GetRasterProperties_management(tempDEM, "MINIMUM").getOutput(0)))

        # convert max elev value and increment(FT) to match the native Z-units of input DEM
        maxElevConverted = maxElev * zFactor

        # if maxElevConverted is not within elevation range exit.
        if not demTempMinElev < maxElevConverted <= demTempMaxElev:

            AddMsgAndPrint("\nThe Max Elevation value specified is not within the elevation range of your watershed-pool area",2)
            AddMsgAndPrint("Elevation Range of your watershed-pool polygon is:",2)
            AddMsgAndPrint("\tMaximum Elevation: " + str(demTempMaxElev) + " " + zUnits + " ---- " + str(round(float(demTempMaxElev*convToFeetFactor),1)) + " Feet")
            AddMsgAndPrint("\tMinimum Elevation: " + str(demTempMinElev) + " " + zUnits + " ---- " + str(round(float(demTempMinElev*convToFeetFactor),1)) + " Feet")
            AddMsgAndPrint("Please enter an elevation value within this range.....Exiting!\n\n",2)
            exit()

        else:
            AddMsgAndPrint("\nSuccessfully clipped DEM to " + os.path.basename(inPool))

        # --------------------------------------------------------------------------------- Set Elevations to calculate volume and surface area

        AddMsgAndPrint("\nCreating Pool at " + str(maxElev) + " FT")

        storageCSV = userWorkspace + os.sep + poolName + "_storageCSV.txt"
        arcpy.SurfaceVolume_3d(tempDEM, storageCSV, "BELOW", maxElevConverted, "1")

        if not createPool(maxElevConverted,storageCSV):
            AddMsgAndPrint("\nFailed To Create Pool at elevation: " + str(maxElevConverted),2)
            exit()

        arcpy.Delete_management(tempDEM)

        if arcpy.Exists(storageCSV):
            arcpy.Delete_management(storageCSV)

        # ------------------------------------------------------------------------------------------------ Compact FGDB
        arcpy.Compact_management(watershedGDB_path)
        AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path))

        # ------------------------------------------------------------------------------------------------ Prepare to Add to ArcGIS Pro

        arcpy.SetParameterAsText(4, poolExit)

    except:
        print_exception()

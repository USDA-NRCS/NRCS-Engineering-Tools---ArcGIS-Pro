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
# - Updated and Tested for ArcGIS Pro 2.4.2 and python 3.6
# - All temporary raster layers such as Times and SetNull are stored in Memory and no longer
#   written to hard disk.
# - All describe functions use the arcpy.da.Describe functionality.
# - All field calculation expressions are in PYTHON3 format.
# - Used acre conversiont dictionary and z-factor lookup table
# - Created lookup dictionaries for acreConversions, ftConversions, volConversions
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

    import getpass, time
    arcInfo = arcpy.GetInstallInfo()

    f = open(textFilePath,'a+')
    f.write("\n################################################################################################################\n")
    f.write("Executing \"Create Pool at Desired Elevation\" Tool\n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write(arcInfo['ProductName'] + ": " + arcInfo['Version'] + "\n")
    f.write("User Parameters:\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tInput Dem: " + arcpy.da.Describe(inputDEM)['catalogPath'] + "\n")
    f.write("\tInput Watershed Mask: " + str(inPool) + "\n")
    f.write("\tPool Elevation: " + str(poolElev) + "\n")
    f.write("\tOutput Pool Polygon: " + str(outPool) + "\n")

    if len(zUnits) > 0:
        f.write("\tElevation Z-units: " + zUnits + "\n")
    else:
        f.write("\tElevation Z-units: BLANK" + "\n")
    f.close
    del f

## ================================================================================================================
# Import system modules
import sys, os, string, traceback
from arcpy.sa import *

if __name__ == '__main__':


    try:
        # Check out SA license
        if arcpy.CheckExtension("spatial") == "Available":
            arcpy.CheckOutExtension("spatial")
        else:
            arcpy.AddError("\nSpatial Analyst Extension not enabled. Please enable Spatial analyst from the Tools/Extensions menu\n")
            exit()

        #----------------------------------------------------------------------------------------- Input Parameters
        inputDEM = arcpy.GetParameterAsText(0)
        zUnits = arcpy.GetParameterAsText(1)
        inMask = arcpy.GetParameterAsText(2)
        poolElev = float(arcpy.GetParameterAsText(3))

##        inputDEM = "C:\demo\Data\Elevation\dem"
##        inPool = "C:\_LatestTools\Test3\Test3_EngTools.gdb\Layers\Watershed"
##        poolElev = "1140"
##        zUnits = ""

        # Set environmental variables
        arcpy.env.parallelProcessingFactor = "75%"
        arcpy.env.overwriteOutput = True

        # ---------------------------------------------------------------------------------------- Define Variables
        inPool = arcpy.da.Describe(inMask)['catalogPath']

        if inPool.find('.gdb') > -1 or inPool.find('.mdb') > -1:
            watershedGDB_path = inPool[:inPool.find('.')+4]
        elif inPool.find('.shp')> -1:
            watershedGDB_path = os.path.dirname(inPool) + os.sep + os.path.basename(os.path.dirname(inPool)).replace(" ","_") + "_EngTools.gdb"
        else:
            AddMsgAndPrint("\n\nPool Polygon must either be a feature class or shapefile!.....Exiting",2)
            exit()

        watershedGDB_name = os.path.basename(watershedGDB_path)
        watershedFD = watershedGDB_path + os.sep + "Layers"
        poolName = os.path.basename(inPool) + "_Pool_" + str(poolElev).replace(".","_")
        userWorkspace = os.path.dirname(watershedGDB_path)

        # Path of Log file; Log file will record everything done in a workspace
        textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.txt"

        # --------------------------------------------- Permanent Datasets
        outPool = watershedFD +os.sep + poolName

        # Must Have a unique name for pool -- Append a unique digit to watershed if required
        x = 1
        while x > 0:
            if arcpy.Exists(outPool):
                outPool = watershedFD + os.sep + os.path.basename(inMask) + "_Pool" + str(x) + "_" + str(poolElev).replace(".","_")
                x += 1
            else:
                x = 0
        del x

        # record basic user inputs and settings to log file for future purposes
        logBasicSettings()

        # --------------------------------------------- Temporary Datasets
        DEMminus = watershedGDB_path + os.sep + "DEMminus"
        volGrid = watershedGDB_path + os.sep + "volGrid"
        volume = watershedGDB_path + os.sep + "volume"
        ExtentRaster = watershedGDB_path + os.sep + "ExtRast"

        # --------------------------------------------- Layers in ArcMap
        outPoolLyr = "" + os.path.basename(outPool) + ""

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
        if poolElev < 1:
            AddMsgAndPrint("\n\nPool Elevation Value must be greater than 0.....Exiting\n",2)
            exit()

        ## ---------------------------------------------------------------------------------------------- Z-factor conversion Lookup table
        # lookup dictionary to convert XY units to area.  Key = XY unit of DEM; Value = conversion factor to sq.meters
        acreConversionDict = {'Meters':4046.8564224,'Meter':4046.8564224,'Foot':43560,'Foot_US':43560,'Feet':43560, 'Centimeter':40470000,'Inch':6273000}
        ftConversionDict = {'Meters':0.092903,'Meter':0.092903,'Foot':1,'Foot_US':1,'Feet':1}
        volConversionDict = {'Meters':1233.48184,'Meter':1233.48184,'Foot':43560,'Foot_US':43560,'Feet':43560}
        acreFootConvFactorDict = {'Meters':0.000810713,'Meter':0.000810713,'Foot':0.000022957,'Foot_US':0.000022957,'Feet':0.000022957}
        conversionToFtFactorDict = {'Meters':3.280839896,'Meter':3.280839896,'Foot':1,'Foot_US':1,'Feet':1, 'Centimeter':0.0328084, 'Centimeters':0.0328084, 'Inches':0.0833333, 'Inch':0.0833333}

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
        cellArea = demCellSize**2
        demSR = demDesc['spatialReference']
        linearUnits = demSR.linearUnitName
        demCoordType = demSR.type

        # if zUnits were left blank than assume Z-values are the same as XY units.
        if not len(zUnits) > 0:
            zUnits = linearUnits

        # ----------------------------------------- Retrieve DEM Properties and set Z-unit conversion Factors
        AddMsgAndPrint("\nGathering information about DEM: " + os.path.basename(inputDEM))

        # Coordinate System must be a Projected type in order to continue.
        # XY & Z Units will determine Zfactor for Elevation and Volume Conversions.
        if demCoordType == "Projected":

            # This will be used to convert elevation values to Feet.
            zFactor = zFactorList[unitLookUpDict.get(zUnits)][unitLookUpDict.get('Feet')]
            acreConversion = acreConversionDict.get(linearUnits)
            convToFeetFactor = conversionToFtFactorDict.get(zUnits)
            acreFtConv= acreFootConvFactorDict.get(linearUnits)

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

        # ---------------------------------------------------------------------------------------------- Create FGDB, FeatureDataset
        # Boolean - Assume FGDB already exists
        bFGDBexists = True

        # Create Watershed FGDB and feature dataset if it doesn't exist
        if not arcpy.Exists(watershedGDB_path):
            arcpy.CreateFileGDB_management(userWorkspace, watershedGDB_name)
            arcpy.CreateFeatureDataset_management(watershedGDB_path, "Layers", demSR)
            AddMsgAndPrint("\nSuccessfully created File Geodatabase: " + watershedGDB_name)
            bFGDBexists = False

        # if GDB already existed but feature dataset doesn't
        if not arcpy.Exists(watershedFD):
            arcpy.CreateFeatureDataset_management(watershedGDB_path, "Layers", demSR)

        # -------------------------------------------------------- Remove existing From ArcGIS Pro Session
        aprx = arcpy.mp.ArcGISProject("CURRENT")

        try:
            for maps in aprx.listMaps():
                for lyr in maps.listLayers():
                    if lyr.name == outPoolLyr:
                        maps.removeLayer(lyr)
        except:
            pass

        # ------------------------------------------------------------------------------------------------ Delete old data from gdb
        datasetsToRemove = (ExtentRaster,tempDEM,DEMminus,DEMsn,volGrid,volume,PoolRast1,PoolRast2,poolTemp)

        x = 0
        for dataset in datasetsToRemove:

            if arcpy.Exists(dataset):

                if x < 1:
                    AddMsgAndPrint("\nRemoving old datasets from FGDB: " + watershedGDB_name)
                    x += 1

                try:
                    arcpy.Delete_management(dataset)
                    AddMsgAndPrint("\tDeleting....." + os.path.basename(dataset))
                except:
                    pass

        # Convert Pool Elevation entered by user in feet to match the zUnits of the DEM specified by the user, using Zfactor
        demElev = poolElev * zFactor

        # ---------------------------------------------------- Clip DEM to Watershed & Setnull above Pool Elevation
        tempDEM = ExtractByMask(inputDEM, inPool)

        # User specified max elevation value must be within min-max range of elevation values in clipped dem
        demTempMaxElev = round((float(arcpy.GetRasterProperties_management(tempDEM, "MAXIMUM").getOutput(0)) * convToFeetFactor),1)
        demTempMinElev = round((float(arcpy.GetRasterProperties_management(tempDEM, "MINIMUM").getOutput(0)) * convToFeetFactor),1)

        # Check to make sure specifies max elevation is within the range of elevation in clipped dem
        if not demTempMinElev < poolElev <= demTempMaxElev:

            AddMsgAndPrint("\nThe Max Elevation value specified is not within the elevation range of your watershed-pool area",2)
            AddMsgAndPrint("Elevation Range of your watershed-pool is:",2)
            AddMsgAndPrint("\tMaximum Elevation: " + str(demTempMaxElev) + " " + zUnits + " ---- " + str(round(float(demTempMaxElev*convToFeetFactor),1)) + " Feet")
            AddMsgAndPrint("\tMinimum Elevation: " + str(demTempMinElev) + " " + zUnits + " ---- " + str(round(float(demTempMinElev*convToFeetFactor),1)) + " Feet")
            AddMsgAndPrint("Please enter an elevation value within this range.....Exiting!\n\n",2)
            exit()

        AddMsgAndPrint("\nCreating Pool at " + str(poolElev) + " feet")

        conStatement = "Value > " + str(demElev)
        valuesAboveElev = SetNull(tempDEM, tempDEM, conStatement)

        # Multiply every pixel by 0 and convert to integer for vectorizing
        zeroValues = Times(valuesAboveElev, 0)
        zeroInt = Int(zeroValues)

        # Convert to polygon and dissolve
        arcpy.RasterToPolygon_conversion(zeroInt, poolTemp, "NO_SIMPLIFY", "VALUE")
        arcpy.Dissolve_management(poolTemp, outPool, "", "", "MULTI_PART", "DISSOLVE_LINES")

        arcpy.AddField_management(outPool, "IDENT", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED")
        arcpy.AddField_management(outPool, "DEM_Elevation", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")
        arcpy.AddField_management(outPool, "POOL_Elevation", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")
        arcpy.AddField_management(outPool, "POOL_ACRES", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")
        arcpy.AddField_management(outPool, "RasterVol", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")
        arcpy.AddField_management(outPool, "ACRE_FOOT", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")

        objectIDfld = "!" + arcpy.da.Describe(outPool)['OIDFieldName'] + "!"
        arcpy.CalculateField_management(outletFC, "IDENT", objectIDfld, "PYTHON3")       # Unique Identifier for pool
        arcpy.CalculateField_management(outPool, "DEM_Elevation", demElev,  "PYTHON3")   # Pool elevation value in DEM's z-units
        arcpy.CalculateField_management(outPool, "POOL_Elevation", poolElev,  "PYTHON3") # Pool elevation value in feet
        arcpy.CalculateField_management(outPool, "POOL_ACRES", poolElev,  "PYTHON3")

        AddMsgAndPrint("\tCreated pool polygon")

        arcpy.CalculateField_management(poolExit, "ELEV_FEET", elevFeetCalc,  "PYTHON3")

        # ------------------------------------------------------- Insert Cursor to populate attributes, Create and Sum Volume Grid.
        rows = arcpy.UpdateCursor(outPool)
        row = rows.next()

        while row:

            row.ID = row.OBJECTID
            row.DemElev = str(demElev)
            row.PoolElev = str(poolElev)

            if units == "Meters":
                row.PoolAcres = str(round(row.Shape_Area / 4046.86,1))
            else:
                row.PoolAcres = str(round(row.Shape_Area / 43560,1))

            rows.UpdateRow(row)

            AddMsgAndPrint("\tCalculated pool area",1)

            arcpy.FeatureToRaster_conversion(poolTemp, "DemElev", ExtentRaster, cellSize)
            arcpy.Minus_sa(ExtentRaster, tempDEM, DEMminus)
            arcpy.SetNull_sa(DEMminus,DEMminus, DEMsn, "Value <= 0")
            arcpy.Times_sa(DEMsn, cellArea, volGrid)
            arcpy.ZonalStatistics_sa(outPool, "ID", volGrid, volume, "SUM")

            row.RasterVol = str(round((float(arcpy.GetRasterProperties_management(volume, "MAXIMUM").getOutput(0))),1))
            row.AcreFt = str(round(float(row.RasterVol * convFactor),1))
            rows.UpdateRow(row)

            AddMsgAndPrint("\tCalculated Pool volume..",1)
            AddMsgAndPrint("\n\t==================================================",0)
            AddMsgAndPrint("\tOutput Pool Polygon: " + os.path.basename(outPool) + "",0)
            AddMsgAndPrint("\tPool Elevation: " + str(row.PoolElev) + " Feet",0)
            AddMsgAndPrint("\tArea: " + str(row.poolAcres) + " Acres",0)
            AddMsgAndPrint("\tVolume: " + str(row.RasterVol) + " Cubic " + str(units),0)
            AddMsgAndPrint("\tVolume: " + str(row.AcreFt) + " Acre Feet",0)
            AddMsgAndPrint("\t====================================================",0)

            break

            row = rows.next()

        del row
        del rows

        # ------------------------------------------------------------------------------------------------ Delete Intermediate Data
        datasetsToRemove = (ExtentRaster,tempDEM,DEMminus,DEMsn,volGrid,volume,DEMsn,poolTemp,PoolRast1,PoolRast2)

        x = 0
        for dataset in datasetsToRemove:

            if arcpy.Exists(dataset):

                if x < 1:
                    AddMsgAndPrint("\nDeleting intermediate data...",1)
                    x += 1

                try:
                    arcpy.Delete_management(dataset)
                except:
                    pass

        del dataset
        del datasetsToRemove
        del x

        # ------------------------------------------------------------------------------------------------ Compact FGDB
        try:
            arcpy.compact_management(watershedGDB_path)
            AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path),1)
        except:
            pass

        # ------------------------------------------------------------------------------------------------ Prepare to Add to Arcmap
        arcpy.SetParameterAsText(4, outPool)
        AddMsgAndPrint("\nAdding output to ArcMap",1)

        AddMsgAndPrint("\nProcessing Complete!\n",1)

    except:
        print_exception()

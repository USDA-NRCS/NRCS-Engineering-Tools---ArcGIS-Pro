# ==========================================================================================
# Name: StageStorage.py
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
    f.write("\tMaximum Elevation: " + str(maxElev) + " Feet\n")
    f.write("\tAnalysis Increment: " + str(userIncrement) + " Feet\n")

    if len(zUnits) > 0:
        f.write("\tElevation Z-units: " + zUnits + "\n")
    else:
        f.write("\tElevation Z-units: BLANK" + "\n")

    f.write("\tInput Watershed or Pool Mask: " + str(inPool) + "\n")

    if bCreatePools:
        f.write("\tCreate Pool Polygons: YES\n")
    else:
        f.write("\tCreate Pool Polygons: NO\n")

    f.close
    del f

## ================================================================================================================
def createPool(elevationValue,storageTxtFile):

    try:

        global conversionFactor,acreConversion,ftConversion,volConversion

        tempDEM2 = watershedGDB_path + os.sep + "tempDEM2"
        tempDEM3 = watershedGDB_path + os.sep + "tempDEM3"
        tempDEM4 = watershedGDB_path + os.sep + "tempDEM4"
        poolTemp = watershedFD + os.sep + "poolTemp"
        poolTempLayer = os.path.dirname(watershedGDB_path) + os.sep + "poolTemp.shp"

        # Just in case they exist Remove them
        layersToRemove = (tempDEM2,tempDEM3,tempDEM4,poolTemp,poolTempLayer)

        for layer in layersToRemove:
            if arcpy.exists(layer):
                try:
                    arcpy.delete_management(layer)
                except:
                    pass

        fcName =  ("Pool_" + str(round((elevationValue * conversionFactor),1))).replace(".","_")

        poolExit = watershedFD + os.sep + fcName

        # Create new raster of only values below an elevation value
        conStatement = "Value > " + str(elevationValue)
        arcpy.SetNull_sa(tempDEM, tempDEM, tempDEM2, conStatement)

        # Multiply every pixel by 0 and convert to integer for vectorizing
        # with geoprocessor 9.3 you need to have 0 w/out quotes.
        arcpy.Times_sa(tempDEM2, 0, tempDEM3)
        arcpy.Int_sa(tempDEM3, tempDEM4)

        # Convert to polygon and dissolve
        # This continuously fails despite changing env settings.  Works fine from python win
        # but always fails from arcgis 10 not 9.3.  Some reason ArcGIS 10 thinks that the
        # output of RasterToPolygon is empty....WTF!!!!
        try:
            arcpy.RasterToPolygon_conversion(tempDEM4, poolTemp, "NO_SIMPLIFY", "VALUE")

        except:
            if arcpy.exists(poolTemp):
                pass
                 #AddMsgAndPrint(" ",0)

            else:
                AddMsgAndPrint("\n" + arcpy.GetMessages(2) + "\n",2)
                exit()

        if ArcGIS10:
            arcpy.CopyFeatures_management(poolTemp,poolTempLayer)
            arcpy.Dissolve_management(poolTempLayer, poolExit, "", "", "MULTI_PART", "DISSOLVE_LINES")

        else:
            arcpy.Dissolve_management(poolTemp, poolExit, "", "", "MULTI_PART", "DISSOLVE_LINES")

        arcpy.AddField_management(poolExit, "ELEV_FEET", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        arcpy.AddField_management(poolExit, "POOL_ACRES", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        arcpy.AddField_management(poolExit, "POOL_SQFT", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        arcpy.AddField_management(poolExit, "ACRE_FOOT", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

        # open storageCSV file and read the last line which should represent the last pool
        file = open(storageTxtFile)
        lines = file.readlines()
        file.close()

        area2D = float(lines[len(lines)-1].split(',')[4])
        volume = float(lines[len(lines)-1].split(',')[6])

        elevFeetCalc = round(elevationValue * conversionFactor,1)
        poolAcresCalc = round(area2D / acreConversion,1)
        poolSqftCalc = round(area2D / ftConversion)
        acreFootCalc = round(volume / volConversion,1)

        arcpy.CalculateField_management(poolExit, "ELEV_FEET", elevFeetCalc, "VB")
        arcpy.CalculateField_management(poolExit, "POOL_ACRES", poolAcresCalc, "VB")
        arcpy.CalculateField_management(poolExit, "POOL_SQFT", poolSqftCalc, "VB")
        arcpy.CalculateField_management(poolExit, "ACRE_FOOT", acreFootCalc, "VB")

        AddMsgAndPrint("\n\tCreated " + fcName + ":",1)
        AddMsgAndPrint("\t\tArea:   " + str(splitThousands(round(poolSqftCalc,1))) + " Sq.Feet",0)
        AddMsgAndPrint("\t\tAcres:  " + str(splitThousands(round(poolAcresCalc,1))),0)
        AddMsgAndPrint("\t\tVolume: " + str(splitThousands(round(acreFootCalc,1))) + " Ac. Foot",0)

        #------------------------------------------------------------------------------------ Delete Temp Layers
        layersToRemove = (tempDEM2,tempDEM3,tempDEM4,poolTemp,poolTempLayer)

        for layer in layersToRemove:
            if arcpy.exists(layer):
                try:
                    arcpy.delete_management(layer)
                except:
                    pass

        del tempDEM2,tempDEM3,tempDEM4,poolTemp,poolTempLayer,poolExit,conStatement,file,lines,storageTxtFile
        del area2D,volume,elevFeetCalc,poolAcresCalc,poolSqftCalc,acreFootCalc,layersToRemove

    except:
        AddMsgAndPrint("\nFailed to Create Pool Polygon for elevation value: " + str(elevationValue),1)
        print_exception()
        exit()
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
        userIncrement = float(arcpy.GetParameterAsText(4))
        bCreatePools = arcpy.GetParameterAsText(5)

        # Uncomment the following 6 lines to run from pythonWin
    ##    inputDEM = r'C:\flex\final\final_EngTools.gdb\DEM_aoi'
    ##    inPool = r'C:\flex\final\final_EngTools.gdb\Layers\stageStoragePoly'
    ##    maxElev = 1000
    ##    userIncrement = 20     #feet
    ##    zUnits = "Meters"
    ##    bCreatePools = True

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
        poolName = os.path.splitext(os.path.basename(inPool))[0]
        userWorkspace = os.path.dirname(watershedGDB_path)

        # ------------------------------------------- Layers in Arcmap
        poolMergeOut = "" + arcpy.ValidateTableName(poolName) + "_All_Pools"
        storageTableView = "Stage_Storage_Table"

        # Path of Log file; Log file will record everything done in a workspace
        textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.txt"

        # Storage CSV file
        storageCSV = userWorkspace + os.sep + poolName + "_storageCSV.txt"

        # ---------------------------------------------------------------------- Datasets
        tempDEM = watershedGDB_path + os.sep + "tempDEM"

        storageTable = watershedGDB_path + os.sep + arcpy.ValidateTablename(poolName) + "_storageTable"
        PoolMerge = watershedFD + os.sep + arcpy.ValidateTablename(poolName) + "_All_Pools"


        if str(bCreatePools).upper() == "TRUE":
            bCreatePools = True
        else:
            bCreatePools = False

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

        # Exit if elevation increment is not greater than 0
        if userIncrement < 0.5:
            AddMsgAndPrint("\n\nAnalysis Increment Value must be greater than or equal to 0.5.....Exiting\n",2)
            exit()

        ## ---------------------------------------------------------------------------------------------- Z-factor conversion Lookup table
        # lookup dictionary to convert XY units to area.  Key = XY unit of DEM; Value = conversion factor to sq.meters
        acreConversionDict = {'Meters':4046.8564224,'Meter':4046.8564224,'Foot':43560,'Foot_US':43560,'Feet':43560, 'Centimeter':40470000,'Inch':6273000}
        ftConversionDict = {'Meters':0.092903,'Meter':0.092903,'Foot':1,'Foot_US':1,'Feet':1}
        volConversionDict = {'Meters':1233.48184,'Meter':1233.48184,'Foot':43560,'Foot_US':43560,'Feet':43560}
        conversionFactorDict = {'Meters':3.280839896,'Meter':3.280839896,'Foot':1,'Foot_US':1,'Feet':1, 'Centimeter':30.4800609601219, 'Centimeter':30.4800609601219, 'Inches':0.0833333, 'Inch':0.0833333}

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
        volConversion = volConversionDict.get(linearUnits)

        # if zUnits were left blank than assume Z-values are the same as XY units.
        if not len(zUnits) > 0:
            zUnits = linearUnits

        # ----------------------------------------- Retrieve DEM Properties and set Z-unit conversion Factors
        AddMsgAndPrint("\nGathering information about DEM: " + os.path.basename(inputDEM),1)

        # Coordinate System must be a Projected type in order to continue.
        if demCoordType == "Projected":

            zFactor = zFactorList[unitLookUpDict.get(zUnits)][unitLookUpDict.get(linearUnits)]
            conversionFactor = conversionFactorDict.get(zUnits)

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
        arcpy.env.workspace = watershedGDB_path

        # --------------------------------------------------------------------------- Create FGDB, FeatureDataset
        # Boolean - Assume FGDB already exists
        bFGDBexists = True

        # Create Watershed FGDB and feature dataset if it doesn't exist
        if not arcpy.exists(watershedGDB_path):
            arcpy.CreateFileGDB_management(userWorkspace, watershedGDB_name)
            arcpy.CreateFeatureDataset_management(watershedGDB_path, "Layers", demSR)
            AddMsgAndPrint("\nSuccessfully created File Geodatabase: " + watershedGDB_name,1)
            bFGDBexists = False

        # if GDB already existed but feature dataset doesn't
        if not arcpy.exists(watershedFD):
            arcpy.CreateFeatureDataset_management(watershedGDB_path, "Layers", demSR)

        # --------------------------------------------------------------------- Clean old files if FGDB already existed.
        if bFGDBexists:

            layersToRemove = (PoolMerge,storageTable,tempDEM,storageCSV)

            x = 0
            for layer in layersToRemove:

                if arcpy.exists(layer):

                    # strictly for formatting
                    if x == 0:
                        AddMsgAndPrint("\nRemoving old files from FGDB: " + watershedGDB_name ,1)
                        x += 1

                    try:
                        arcpy.delete_management(layer)
                        AddMsgAndPrint("\tDeleting....." + os.path.basename(layer),0)
                    except:
                        pass

            arcpy.workspace = watershedFD

            poolFCs = arcpy.ListFeatureClasses("Pool_*")

            for poolFC in poolFCs:

                if arcpy.exists(poolFC):
                    arcpy.delete_management(poolFC)
                    AddMsgAndPrint("\tDeleting....." + poolFC,0)

            if os.path.exists(storageCSV):
                os.remove(storageCSV)

            del x,layer,layersToRemove,poolFCs

        if os.path.exists(storageCSV):
            os.remove(storageCSV)
            AddMsgAndPrint("\tDeleting....." + storageCSV,0)

        # ------------------------------------- Remove layers from ArcMap if they exist
        layersToRemove = (poolMergeOut,storageTableView)

        x = 0
        for layer in layersToRemove:

            if arcpy.exists(layer):

                if x == 0:
                    AddMsgAndPrint("",1)
                    x+=1

                try:
                    arcpy.delete_management(layer)
                    AddMsgAndPrint("Removing previous " + layer + " from your ArcMap Session",1)
                except:
                    pass

        del x
        del layer
        del layersToRemove
        # --------------------------------------------------------------------------------- ClipDEM to User's Pool or Watershed
        arcpy.ExtractByMask_sa(inputDEM, inPool, tempDEM)

        # User specified max elevation value must be within min-max elevation range of clipped dem
        demTempMaxElev = round(float(arcpy.GetRasterProperties_management(tempDEM, "MAXIMUM").getOutput(0)),1)
        demTempMinElev = round(float(arcpy.GetRasterProperties_management(tempDEM, "MINIMUM").getOutput(0)),1)

        # convert max elev value and increment(FT) to match the native Z-units of input DEM
        maxElevConverted = maxElev * Zfactor
        increment = userIncrement * Zfactor

        # if maxElevConverted is not within elevation range exit.
        if not demTempMinElev < maxElevConverted <= demTempMaxElev:

            AddMsgAndPrint("\nThe Max Elevation value specified is not within the elevation range of your watershed-pool area",2)
            AddMsgAndPrint("Elevation Range of your watershed-pool polygon is:",2)
            AddMsgAndPrint("\tMaximum Elevation: " + str(demTempMaxElev) + " " + zUnits + " ---- " + str(round(float(demTempMaxElev*conversionFactor),1)) + " Feet",0)
            AddMsgAndPrint("\tMinimum Elevation: " + str(demTempMinElev) + " " + zUnits + " ---- " + str(round(float(demTempMinElev*conversionFactor),1)) + " Feet",0)
            AddMsgAndPrint("Please enter an elevation value within this range.....Exiting!\n\n",2)
            exit()

        else:
            AddMsgAndPrint("\nSuccessfully clipped DEM to " + os.path.basename(inPool),1)

        # --------------------------------------------------------------------------------- Set Elevations to calculate volume and surface area
        try:

            i = 1
            while maxElevConverted > demTempMinElev:

                if i == 1:
                    AddMsgAndPrint("\nDeriving Surface Volume for elevation values between " + str(round(demTempMinElev * conversionFactor,1)) + " and " + str(maxElev) + " FT every " + str(userIncrement) + " FT" ,1)
                    numOfPoolsToCreate = str(int(round((maxElevConverted - demTempMinElev)/increment)))
                    AddMsgAndPrint(numOfPoolsToCreate + " Pool Feature Classes will be created",1)
                    i+=1

                arcpy.SurfaceVolume_3d(tempDEM, storageCSV, "BELOW", maxElevConverted, "1")

                if bCreatePools:

                    if not createPool(maxElevConverted,storageCSV):
                        pass

                maxElevConverted = maxElevConverted - increment

            del i

        except:
            print_exception()
            exit()

        if arcpy.exists(tempDEM):
            arcpy.delete_management(tempDEM)

        #------------------------------------------------------------------------ Convert StorageCSV to FGDB Table and populate fields.
        arcpy.CopyRows_management(storageCSV, storageTable, "")
        arcpy.AddField_management(storageTable, "ELEV_FEET", "DOUBLE", "5", "1", "", "", "NULLABLE", "NON_REQUIRED", "")
        arcpy.AddField_management(storageTable, "POOL_ACRES", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        arcpy.AddField_management(storageTable, "POOL_SQFT", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        arcpy.AddField_management(storageTable, "ACRE_FOOT", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

        elevFeetCalc = "round([Plane_Height] *" + str(conversionFactor) + ",1)"
        poolAcresCalc = "round([Area_2D] /" + str(acreConversion) + ",1)"
        poolSqftCalc = "round([Area_2D] /" + str(ftConversion) + ",1)"
        acreFootCalc = "round([Volume] /" + str(volConversion) + ",1)"

        arcpy.CalculateField_management(storageTable, "ELEV_FEET", elevFeetCalc, "VB")
        arcpy.CalculateField_management(storageTable, "POOL_ACRES", poolAcresCalc, "VB")
        arcpy.CalculateField_management(storageTable, "POOL_SQFT", poolSqftCalc, "VB")
        arcpy.CalculateField_management(storageTable, "ACRE_FOOT", acreFootCalc, "VB")

        del elevFeetCalc,poolAcresCalc,poolSqftCalc,acreFootCalc

        AddMsgAndPrint("\nSuccessfully Created " + os.path.basename(storageTable),1)

        #------------------------------------------------------------------------ Append all Pool Polygons together
        if bCreatePools:

            mergeList = ""

            i = 1
            arcpy.workspace = watershedFD
            poolFCs = arcpy.ListFeatureClasses("Pool_*")

            for poolFC in poolFCs:

                if i == 1:
                    mergeList = arcpy.Describe(poolFC).CatalogPath + ";"

                else:
                    mergeList = mergeList + ";" + arcpy.Describe(poolFC).CatalogPath

                i+=1

            arcpy.Merge_management(mergeList,PoolMerge)

            AddMsgAndPrint("\nSuccessfully Merged Pools into " + os.path.basename(PoolMerge),1)

            del mergeList,poolFCs,i

        # ------------------------------------------------------------------------------------------------ Compact FGDB
        try:
            arcpy.compact_management(watershedGDB_path)
            AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path),1)
        except:
            pass

        # ------------------------------------------------------------------------------------------------ Prepare to Add to Arcmap

        if bCreatePools:
            arcpy.SetParameterAsText(7, PoolMerge)

        # Create a table view from the storage table to add to Arcmap
        arcpy.maketableview_management(storageTable,storageTableView)


        if os.path.exists(storageCSV):
            try:
                os.path.remove(storageCSV)
            except:
                pass

        del storageCSV

    except:
        print_exception()

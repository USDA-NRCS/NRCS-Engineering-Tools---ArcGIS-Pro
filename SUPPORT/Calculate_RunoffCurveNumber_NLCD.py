# ==========================================================================================
# Name: Calculate_RunoffCurveNumber_NLCD.py
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
# Updated  5/18/2020 - Adolfo Diaz
#
# - Why is landuseOut = "" + wsName + "_Landuse" being removed if the tool doesn't create
#   this layer?
# - This tool incorrectly assumes MUNAME field is present in the soils layer.
# - Need to add functionality to get NLCD data from WMS instead of locally
# - Need to add functionality to get Soils data directly from SDA instead of locally.
# - 3 raster datasets could not be used as in_memory raster datasets b/c of Joins.  The
#   soilsGrid, landuse and LU_PLUS_SOILS are still being written out.
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
    f.write("\n################################################################################################################\n")
    f.write("Executing \"Calculate Runoff Curve Number from NLCD\" Tool\n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write(arcInfo['ProductName'] + ": " + arcInfo['Version'] + "\n")
    f.write("User Parameters:\n")
    f.write("\tInput Watershed: " + inWatershed + "\n")
    f.write("\tInput NLCD Raster: " + inNLCD + "\n")
    f.write("\tInput Soils: " + inSoils + "\n")

    if bCreateRCNgrid:
        f.write("\tCreate RCN Grid: SELECTED\n")
        if len(snapRaster) > 0:
            f.write("\tRCN Grid Snap Raster: " + snapRaster + "\n")
            f.write("\tRCN Grid Cellsize: " + str(float(outCellSize)) + "\n")
            f.write("\tRCN Grid Coord Sys: " + str(outCoordSys) + "\n")
        else:
            f.write("\tRCN Grid Snap Raster: NOT SPECIFIED\n")
    else:
        f.write("\tCreate RCN Grid: NOT SELECTED\n")

    f.close
    del f

## ================================================================================================================
# Import system modules
import arcpy, sys, os, string, traceback
from arcpy.sa import *

if __name__ == '__main__':

    try:
        # Check out Spatial Analyst License
        if arcpy.CheckExtension("spatial") == "Available":
            arcpy.CheckOutExtension("spatial")
        else:
            arcpy.AddError("Spatial Analyst Extension not enabled. Please enable Spatial analyst from the Tools/Extensions menu\n",2)
            exit()

        # ---------------------------------------------------------------------- Input Parameters
        inWatershed = arcpy.GetParameterAsText(0)
        inNLCD = arcpy.GetParameterAsText(1)
        inSoils = arcpy.GetParameterAsText(2)
        inputField = arcpy.GetParameterAsText(3)
        curveNoGrid = arcpy.GetParameterAsText(4)
        snapRaster = arcpy.GetParameterAsText(5)

##        inWatershed = r'E:\NRCS_Engineering_Tools_ArcPro\Testing\Testing_EngTools.gdb\Layers\NLCD_Wtshd'
##        inNLCD = r'E:\NRCS_Engineering_Tools_ArcPro\Testing\NLCD_2016_Land_Cover_L48_20190424_9B7ItnooQo9kN1CQCBzH.tiff'
##        inSoils =  r'E:\NRCS_Engineering_Tools_ArcPro\Testing\Testing_EngTools.gdb\Layers\ProWatershed_Soils'
##        inputField = 'HYDGROUP'
##        curveNoGrid = True
##        snapRaster = r'E:\NRCS_Engineering_Tools_ArcPro\Testing\Testing_EngTools.gdb\Testing_DEM'

        # Set environmental variables
        arcpy.env.parallelProcessingFactor = "75%"
        arcpy.env.overwriteOutput = True

        # Check for RCN Grid choice...
        if curveNoGrid == "#" or curveNoGrid == "" or curveNoGrid == False or curveNoGrid == "false":
            bCreateRCNgrid = False

        else:
            bCreateRCNgrid = True

        # If snap raster provided assign output cell size from snapRaster
        if len(snapRaster) > 0:
            if arcpy.Exists(snapRaster):
                snapRasterDesc = arcpy.da.Describe(snapRaster)
                outCoordSys = snapRasterDesc['spatialReference']
                outCellSize = snapRasterDesc['meanCellWidth']

            else:
                AddMsgAndPrint("\n\nSpecified Snap Raster Does not exist, please make another selection or verify the path...EXITING",2)
                exit()

        # --------------------------------------------------------------------------- Define Variables
        inWatershed = arcpy.da.Describe(inWatershed)['catalogPath']
        inSoils = arcpy.da.Describe(inSoils)['catalogPath']

        if inWatershed.find('.gdb') > -1 or inWatershed.find('.mdb') > -1:

            # inWatershed was created using 'Create Watershed Tool'
            if inWatershed.find('_EngTools'):
                watershedGDB_path = inWatershed[:inWatershed.find('.') + 4]

            # inWatershed is a fc from a DB not created using 'Create Watershed Tool'
            else:
                watershedGDB_path = os.path.dirname(inWatershed[:inWatershed.find('.')+4]) + os.sep + os.path.basename(inWatershed).replace(" ","_") + "_EngTools.gdb"

        elif inWatershed.find('.shp')> -1:
            watershedGDB_path = os.path.dirname(inWatershed[:inWatershed.find('.')+4]) + os.sep + os.path.basename(inWatershed).replace(".shp","").replace(" ","_") + "_EngTools.gdb"

        else:
            AddMsgAndPrint("\n\nWatershed Polygon must either be a feature class or shapefile!.....Exiting",2)
            exit()

        watershedFD = watershedGDB_path + os.sep + "Layers"
        watershedGDB_name = os.path.basename(watershedGDB_path)
        userWorkspace = os.path.dirname(watershedGDB_path)
        wsName = arcpy.ValidateTableName(os.path.splitext(os.path.basename(inWatershed))[0])

        # log File Path
        textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.txt"

        # record basic user inputs and settings to log file for future purposes
        logBasicSettings()

        # --------------------------------------------------- Temporary Datasets
        # These layers wouldn't work using in_memory rasters, specifically the combine
        landuse = watershedGDB_path + os.sep + "NLCD"
        soilsGrid = watershedGDB_path + os.sep + "SOILS"
        LU_PLUS_SOILS = watershedGDB_path + os.sep + "LU_PLUS_SOILS"

        # --------------------------------------------------- Permanent Datasets
        wsSoils = watershedFD + os.sep + wsName + "_Soils"
        watershed = watershedFD + os.sep + wsName
        RCN_GRID = watershedGDB_path + os.sep + wsName + "_RCN_Grid"
        RCN_TABLE = watershedGDB_path + os.sep + wsName + "_RCN_Summary_Table"

##         # ----------------------------------------------------------- Lookup Tables
        NLCD_RCN_TABLE = os.path.join(os.path.dirname(sys.argv[0]), "Support.gdb" + os.sep + "NLCD_RCN_TABLE")

        # ----------------------------------------------------------------------------- Check Some Parameters
        # Exit if any are true
        if not int(arcpy.GetCount_management(inWatershed).getOutput(0)) > 0:
            AddMsgAndPrint("\n\nWatershed Layer is empty.....Exiting!",2)
            exit()

        if int(arcpy.GetCount_management(inWatershed).getOutput(0)) > 1:
            AddMsgAndPrint("\n\nOnly ONE Watershed or Subbasin can be submitted!...",2)
            AddMsgAndPrint("Either dissolve " + os.path.basename(inWatershed) + " Layer, export an individual polygon, ",2)
            AddMsgAndPrint("make a single selection, or provide a different input...EXITING",2)
            exit()

        if arcpy.Describe(inWatershed).ShapeType != "Polygon":
            AddMsgAndPrint("\n\nYour Watershed Layer must be a polygon layer!.....Exiting!",2)
            exit()

        if arcpy.Describe(inSoils).ShapeType != "Polygon":
            AddMsgAndPrint("\n\nYour Soils Layer must be a polygon layer!.....Exiting!",2)
            exit()

        if not len(arcpy.ListFields(inSoils,inputField)) > 0:
            AddMsgAndPrint("\nThe field specified for Hydro Groups does not exist in your soils data.. please specify another name and try again..EXITING",2)
            exit()

        if not len(arcpy.ListFields(inSoils,"MUNAME")) > 0:
            AddMsgAndPrint("\nMUNAME field does not exist in your soils data.. please correct and try again..EXITING",2)
            exit()

        if not arcpy.Exists(NLCD_RCN_TABLE):
            AddMsgAndPrint("\n\n\"NLCD_RCN_TABLE\" was not found! Make sure \"Support.gdb\" is located within the same location as this script",2)
            exit()

        # --------------------------------------------------------------------------- Create FGDB, FeatureDataset
        # Boolean - Assume FGDB already exists
        bFGDBexists = True

        # Create Watershed FGDB and feature dataset if it doesn't exist
        if not arcpy.Exists(watershedGDB_path):
            inWatershedSR = arcpy.da.Describe(inWatershed)['spatialReference']

            arcpy.CreateFileGDB_management(userWorkspace, watershedGDB_name)
            arcpy.CreateFeatureDataset_management(watershedGDB_path, "Layers", inWatershedSR)
            AddMsgAndPrint("\nSuccessfully created File Geodatabase: " + watershedGDB_name)
            bFGDBexists = False

        # if GDB already existed but feature dataset doesn't
        if not arcpy.Exists(watershedFD):
            inWatershedSR = arcpy.da.Describe(inWatershed)['spatialReference']
            arcpy.CreateFeatureDataset_management(watershedGDB_path, "Layers", inWatershedSR)

        # --------------------------------------------------------------------- Delete previous layers from ArcMap if they exist
        datasetsToRemove = [wsSoils,RCN_GRID,RCN_TABLE]           # Full path of layers
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

        if bFGDBexists:
            x = 0

            # These had to be added b/c in_memory layers didn't work
            datasetsToRemove.append(soilsGrid)
            datasetsToRemove.append(landuse)
            datasetsToRemove.append(LU_PLUS_SOILS)

            for layer in datasetsToRemove:
                if arcpy.Exists(layer):

                    # strictly for formatting
                    if x == 0:
                        AddMsgAndPrint("\nRemoving old files from FGDB: " + watershedGDB_name ,1)
                        x += 1
                    try:
                        arcpy.Delete_management(layer)
                        AddMsgAndPrint("\tDeleting....." + os.path.basename(layer),0)
                    except:
                        pass

        # ----------------------------------------------------------------------------------------------- Create Watershed
        # if paths are not the same then assume AOI was manually digitized
        # or input is some from some other feature class/shapefile

        # True if watershed was not created from this Eng tools
        bExternalWatershed = False

        if not inWatershed == watershed:

            bExternalWatershed = True

            # delete the AOI feature class; new one will be created
            if arcpy.Exists(watershed):
                arcpy.Delete_management(watershed)
                arcpy.CopyFeatures_management(inWatershed, watershed)
                AddMsgAndPrint("\nSuccessfully Overwrote existing Watershed",1)

            else:
                arcpy.CopyFeatures_management(inWatershed, watershed)
                AddMsgAndPrint("\nSuccessfully Created Watershed " + os.path.basename(watershed))

        # paths are the same therefore input IS projectAOI
        else:
            AddMsgAndPrint("\nUsing existing " + os.path.basename(watershed) + " feature class")

        if bExternalWatershed:

            # Delete all fields in watershed layer except for obvious ones
            for field in [f.name for f in arcpy.ListFields(watershed)]:

                # Delete all fields that are not the following
                if not field in (watershedDesc['shapeFieldName'],watershedDesc['OIDFieldName'],"Subbasin"):
                    arcpy.DeleteField_management(watershed,field)

            if not len(arcpy.ListFields(watershed,"Subbasin")) > 0:
                arcpy.AddField_management(watershed, "Subbasin", "SHORT", "", "", "", "", "NULLABLE", "NON_REQUIRED")
                arcpy.CalculateField_management(watershed, "Subbasin",watershedDesc['OIDFieldName'],"PYTHON3")

            if not len(arcpy.ListFields(watershed,"Acres")) > 0:
                arcpy.AddField_management(watershed, "Acres", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")
                arcpy.CalculateField_management(watershed, "Acres", "!shape.area@ACRES!", "PYTHON3")

        # ------------------------------------------------------------------------------------------------ Prepare Landuse Raster(s)
        # lookup dictionary to convert XY units to area.  Key = XY unit of DEM; Value = conversion factor to sq.meters
        acreConversionDict = {'Meters':4046.8564224,'Meter':4046.8564224,'Foot':43560,'Foot_US':43560,'Feet':43560, 'Centimeter':40470000,'Inch':6273000}

        # ----------------------------------- Describe input NLCD Properties
        nlcdDesc = arcpy.da.Describe(inNLCD)
        nlcdDescSR = nlcdDesc['spatialReference']
        nlcdUnits = nlcdDescSR.linearUnitName
        nlcdCellSize = nlcdDesc['meanCellWidth']
        cellArea = nlcdCellSize ** 2

        arcpy.env.extent = "MINOF"
        arcpy.env.cellSize = nlcdCellSize

        if nlcdUnits in ("Meter","Meters"):
            nlcdUnits = "Meters"
        elif nlcdUnits in ("Feet","Foot","Foot_US"):
            nlcdUnits = "Feet"
        else:
            AddMsgAndPrint("\nCould not determine resolution of NLCD layer....EXiting",2)
            exit()

        # ---------------------------------------------------------------------- Clip NLCD to watershed boundary
        AddMsgAndPrint("\nClipping " + str(os.path.basename(inNLCD)) + " to " + str(wsName) + " boundary..")

        #landuse = arcpy.CreateScratchName("NLCD",data_type="RasterDataset",workspace="in_memory")
        outMask = ExtractByMask(inNLCD, inWatershed)
        outMask.save(landuse)

        AddMsgAndPrint("\nSuccessully Clipped NLCD...")

        # Isolate Cultivated Cropland and export to poly for soils processing
        cultivatedGrid = Con(landuse,landuse,"","\"VALUE\" = 81 OR \"VALUE\" = 82 OR \"VALUE\" = 83 OR \"VALUE\" = 84 OR \"VALUE\" = 85")

        cultivatedPoly = arcpy.CreateScratchName("cultivated_poly",data_type="FeatureClass",workspace="in_memory")
        arcpy.RasterToPolygon_conversion(cultivatedGrid,cultivatedPoly,"SIMPLIFY","VALUE")

        # -------------------------------------------------------------------------------------- Clip and Process Soils Data
        # Clip the soils to the watershed
        #wsSoils = arcpy.CreateScratchName("SoilsClip",data_type="ArcInfoTable",workspace="in_memory")
        arcpy.Clip_analysis(inSoils,watershed,wsSoils)
        AddMsgAndPrint("\nSuccessfully clipped " + str(os.path.basename(inSoils)) + " soils layer")
        AddMsgAndPrint(str(wsSoils))

        # If Input field name other than ssurgo default, add and calc proper field
        if inputField.upper() != "HYDGROUP":
            arcpy.AddField_management(wsSoils, "HYDGROUP", "TEXT", "", "", "20", "", "NULLABLE", "NON_REQUIRED")
        arcpy.CalculateField_management(wsSoils, "HYDGROUP", "!" + str(inputField) + "!", "PYTHON3")

        # ADD HYD_CODE Field for lookup
        if len(arcpy.ListFields(wsSoils,"HYD_CODE")) < 1:
            arcpy.AddField_management(wsSoils, "HYD_CODE", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")

        # ---------------------------------------------------------------------------------- update muname and hydrgoup values
        AddMsgAndPrint("\n\tProcessing soils data...")

        nullValues = 0

        if len(arcpy.ListFields(wsSoils,"MUNAME")) > 0:

            with arcpy.da.UpdateCursor(wsSoils,['MUNAME','HYDGROUP']) as cursor:
                for row in cursor:
                    updateRecord = False

                    # Update HYDGROUP if conditions are met
                    if any(row[0] in s for s in ['Water', 'Pit', 'Urban']):

                        # assign "W" value to any water type map units
                        if row[0].find('Water') > -1:
                            row[1] = "W"
                            updateRecord = True

                        # assign "P" value to any pit-like map units
                        elif row[0].find('Pit') > -1:
                            row[1] = "P"
                            updateRecord = True

                        # "D" value to any unpopulated Urban mapunits
                        elif row[0].find('Urban') > -1:
                            row[1] = "D"
                            updateRecord = True

                    # assign null HYDRGROUP values to "W" (RCN value of 99)
                    if row[1] is None or len(row[1]) == 0 or row[1] == '':
                        row[1] = "W"
                        nullValues += 1
                        updateRecord = True

                    if updateRecord:
                        cursor.updateRow(row)
                    else:
                        continue
            del cursor

        if nullValues:
            AddMsgAndPrint("\n\tThere are " + str(nullValues) + " null hydro group(s) remaining",1)
            AddMsgAndPrint("\t\tA RCN value of 99 will be applied to these areas",1)

        # ---------------------------------------------------------------------------------- update combined hydrgoup values
        AddMsgAndPrint("\n\tChecking for combined hydrologic groups...")

        soilsLyr = "soilsLyr"
        arcpy.MakeFeatureLayer_management(wsSoils, soilsLyr)

        query = "\"HYDGROUP\" LIKE '%/%'"
        arcpy.SelectLayerByAttribute_management(soilsLyr, "NEW_SELECTION", query)
        combClasses = int(arcpy.GetCount_management(soilsLyr).getOutput(0))

        if combClasses > 0:
            AddMsgAndPrint("\n\tThere are " + str(combClasses) + " soil map unit(s) with combined hydro groups",0)

            # Select Combined Classes that intersect cultivated cropland
            arcpy.SelectLayerByLocation(soilsLyr, "INTERSECT", cultivatedPoly, 0, "NEW_SELECTION")
            combClassesIntCultPoly = int(arcpy.GetCount_management(soilsLyr).getOutput(0))

            if combClassesIntCultPoly > 0:
                AddMsgAndPrint("\n\t\tSetting " + str(combClassesIntCultPoly) + " combined group(s) on cultivated land to drained state",0)
                # Set selected polygons to drained state
                arcpy.CalculateField_management(soilsLyr, "HYDGROUP", "!HYDGROUP![0]", "PYTHON3")

            # Set remaining combined groups to natural state
            arcpy.SelectLayerByAttribute_management(soilsLyr, "SWITCH_SELECTION")
            remainingPolys = int(arcpy.GetCount_management(soilsLyr).getOutput(0))

            if remainingPolys > 0:
                AddMsgAndPrint("\tSetting "  + str(remainingPolys) + " non-cultivated combined group(s) to natural state",0)
                arcpy.CalculateField_management(soilsLyr,"HYDGROUP", "\"D\"", "PYTHON3")

        # Clear any remaining selections
        arcpy.SelectLayerByAttribute_management(soilsLyr, "CLEAR_SELECTION")

        # Join NLCD Lookup table to populate HYD_CODE field
        arcpy.AddJoin_management(soilsLyr, "HYDGROUP", NLCD_RCN_TABLE, "Soil", "KEEP_ALL")
        calcFld = ''.join((os.path.basename(wsSoils),'.HYD_CODE'))
        arcpy.CalculateField_management(soilsLyr, calcFld, "!NLCD_RCN_TABLE.ID!", "PYTHON3")
        arcpy.RemoveJoin_management(soilsLyr, "NLCD_RCN_TABLE")

        # ----------------------------------------------------------------------------------------------  Create Soils Raster
        # Set snap raster to clipped NLCD
        arcpy.env.snapRaster = landuse

        # Convert soils to raster using preset cellsize
        AddMsgAndPrint("\nCreating Hydro Groups Raster")
        arcpy.PolygonToRaster_conversion(soilsLyr,"HYD_CODE",soilsGrid,"MAXIMUM_AREA","NONE",arcpy.env.cellSize)

        # ----------------------------------------------------------------------------------------------- Create Curve Number Grid
        # Combine Landuse and Soils
        outCombine = Combine([landuse,soilsGrid])
        outCombine.save(LU_PLUS_SOILS)

        arcpy.BuildRasterAttributeTable_management(LU_PLUS_SOILS)

        # Add RCN field to raster attributes
        arcpy.AddField_management(LU_PLUS_SOILS, "HYD_CODE", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")
        arcpy.AddField_management(LU_PLUS_SOILS, "LANDUSE", "TEXT", "", "", "255", "", "NULLABLE", "NON_REQUIRED", "")
        arcpy.AddField_management(LU_PLUS_SOILS, "HYD_GROUP", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        arcpy.AddField_management(LU_PLUS_SOILS, "RCN", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        arcpy.AddField_management(LU_PLUS_SOILS, "ACRES", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        arcpy.AddField_management(LU_PLUS_SOILS, "WGT_RCN", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

        arcpy.CalculateField_management(LU_PLUS_SOILS, "HYD_CODE", "(!NLCD! * 100) + !SOILS!", "PYTHON3")
        arcpy.CalculateField_management(LU_PLUS_SOILS, "ACRES", "!COUNT! * (" + str(cellArea) + " / " + str(acreConversionDict.get(nlcdUnits)) + ")", "PYTHON3")

        # Sum the count (equivalent to area) for each CN in watershed
        rcn_stats = arcpy.CreateScratchName("rcn_stats",data_type="ArcInfoTable",workspace="in_memory")
        arcpy.Statistics_analysis(LU_PLUS_SOILS, rcn_stats,[["COUNT", "SUM"]])

        # Join NLCD Lookup table to retrieve RCN and desc values
        arcpy.MakeRasterLayer_management(LU_PLUS_SOILS, "LU_PLUS_SOILS_LYR")
        arcpy.AddJoin_management("LU_PLUS_SOILS_LYR", "HYD_CODE", NLCD_RCN_TABLE, "Join_", "KEEP_ALL")
        arcpy.CalculateField_management("LU_PLUS_SOILS_LYR", "VAT_LU_PLUS_SOILS.RCN", "!NLCD_RCN_TABLE.CN!", "PYTHON3")
        arcpy.CalculateField_management("LU_PLUS_SOILS_LYR", "VAT_LU_PLUS_SOILS.LANDUSE", "!NLCD_RCN_TABLE.NRCS_LANDUSE!","PYTHON3")
        arcpy.CalculateField_management("LU_PLUS_SOILS_LYR", "VAT_LU_PLUS_SOILS.HYD_GROUP", "!NLCD_RCN_TABLE.Soil!", "PYTHON3")

        # -------------------------------------------------------------------------------- Weight Curve Number
        # Retrieve the total area (Watershed Area)
        wsArea = [row[0] for row in arcpy.da.SearchCursor(rcn_stats,["SUM_COUNT"])][0]

        # Multiply CN by percent of area to weight
        arcpy.CalculateField_management(LU_PLUS_SOILS, "WGT_RCN", "!RCN! * (!COUNT! / " + str(float(wsArea)) + ")", "PYTHON")

        # Sum the weights to create weighted RCN
        rcn_stats2 = arcpy.CreateScratchName("rcn_stats2",data_type="ArcInfoTable",workspace="in_memory")
        arcpy.Statistics_analysis(LU_PLUS_SOILS, rcn_stats2, [["WGT_RCN","SUM"]])
        wgtRCN = [row[0] for row in arcpy.da.SearchCursor(rcn_stats2,["SUM_WGT_RCN"])][0]

        AddMsgAndPrint("\n\tWeighted Average Runoff Curve No. for " + str(wsName) + " is " + str(int(wgtRCN)),0)

        # Export RCN Summary Table
        arcpy.CopyRows_management(LU_PLUS_SOILS, RCN_TABLE)

        # Delete un-necessary fields from summary table
        arcpy.DeleteField_management(RCN_TABLE, ["VALUE","COUNT","SOILS","HYD_CODE","HYD_CODE","WGT_RCN"])

        # ------------------------------------------------------------------ Pass results to user watershed
        AddMsgAndPrint("\nAdding RCN results to " + str(wsName) + "'s attributes")

        if not len(arcpy.ListFields(watershed,"RCN")) > 0:
            arcpy.AddField_management(watershed, "RCN", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED")
        arcpy.CalculateField_management(watershed, "RCN", wgtRCN, "PYTHON3")

        # ------------------------------------------------------------------ Optional: Create Runoff Curve Number Grid
        if bCreateRCNgrid:
            AddMsgAndPrint("\nCreating Curve Number Raster...",1)

            # If user provided a snap raster, assign from input
            if len(snapRaster) > 0:
                arcpy.env.snapRaster = snapRaster
                arcpy.env.outputCoordinateSystem = outCoordSys
                arcpy.env.cellSize = outCellSize

            # Convert Combined Raster to Curve Number grid
            outLookup = Lookup(LU_PLUS_SOILS, "RCN")
            outLookup.save(RCN_GRID)

            AddMsgAndPrint("\nSuccessfully Created Runoff Curve Number Grid")

        # ----------------------------------------------------- Delete Intermediate data
        AddMsgAndPrint("\nDeleting intermediate data")
        for layer in [LU_PLUS_SOILS,cultivatedGrid,cultivatedPoly,soilsGrid,rcn_stats,rcn_stats2,landuse]:

            if arcpy.Exists(layer):
                arcpy.Delete_management(layer)

        # ----------------------------------------------------------------------- Compact FGDB
        arcpy.Compact_management(watershedGDB_path)
        AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path))

        # ------------------------------------------------------------ Prepare to Add to Arcmap
        if bExternalWatershed:
            arcpy.SetParameterAsText(6, watershed)
        if bCreateRCNgrid:
            arcpy.SetParameterAsText(7, RCN_GRID)

        arcpy.SetParameterAsText(8, RCN_TABLE)
        AddMsgAndPrint("\nAdding Output to ArcGIS Pro")

    except:
        print_exception()
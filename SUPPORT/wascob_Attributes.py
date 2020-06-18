# ==========================================================================================
# Name: wascob_Attributes.py
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

# This script is a combination of the PrepareSoils_Landuse and Calculate_Stage_Storage_Volume

# ==========================================================================================
# Updated  6/18/2020 - Adolfo Diaz
#
# - Removed entire section of 'Remove domains from fields if they exist'  This section
#   makes no sense b/c landuse and wssoils do NOT exist yet so there is nothing to remove
#   from.
# - No longer check to see if soils, clu or watershed are polygons.  The tool properties
#   will check for this.
# - No longer check for presence of hydrologic field since it is a dependency of the soils
#   layer.
# - Removed calcAvgSlope boolean since this is triggered if the ZonalStatistics works.  If this
#   fails then calcAvgSlope is pointless
# - The original script does not update the 'Subbasin' Field in the ReferenceLine again but it does
#   update the rest of the Reference Line fields: MinElev, MaxElev, MeanElev.  Added code to do this again.

# ==========================================================================================
# Updated  6/17/2020 - Adolfo Diaz
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

    try:

        import getpass, time
        arcInfo = arcpy.GetInstallInfo()  # dict of ArcGIS Pro information

        f = open(textFilePath,'a+')
        f.write("\n################################################################################################################\n")
        f.write("Executing \"1.Prepare Soils and Landuse\" Tool for ArcGIS 9.3 and 10\n")
        f.write("User Name: " + getpass.getuser() + "\n")
        f.write("Date Executed: " + time.ctime() + "\n")
        f.write(arcInfo['ProductName'] + ": " + arcInfo['Version'] + "\n")
        f.write("User Parameters:\n")
        f.write("\tWorkspace: " + userWorkspace + "\n")
        f.write("\tInput Soils Data: " + inSoils + "\n")
        f.write("\tInput Hydro Groups Field: " + hydroField + "\n")

        if bSplitLU:
            f.write("\tInput CLU Layer: " + inCLU + " \n")
        else:
            f.write("\tInput CLU Layer: N/A " + " \n")

        f.close
        del f

    except:
        print_exception()
        exit()

## ================================================================================================================
def splitThousands(someNumber):
# will determine where to put a thousands seperator if one is needed.
# Input is an integer.  Integer with or without thousands seperator is returned.

    try:
        return re.sub(r'(\d{3})(?=\d)', r'\1,', str(int(round(someNumber)))[::-1])[::-1]
    except:
        print_exception()
        return someNumber

## ================================================================================================================
# Import system modules
import arcpy, sys, os, string, traceback, re
from arcpy.sa import *

if __name__ == '__main__':

    try:
        # Script Parameters
        inWatershed = arcpy.GetParameterAsText(0)
        inSoils = arcpy.GetParameterAsText(1)
        hydroField = arcpy.GetParameterAsText(2)
        inCLU = arcpy.GetParameterAsText(3)

        # Check out Spatial Analyst License
        if arcpy.CheckExtension("spatial") == "Available":
            arcpy.CheckOutExtension("spatial")
        else:
            arcpy.AddError("Spatial Analyst Extension not enabled. Please enable Spatial analyst from the Tools/Extensions menu\n",2)
            exit()

        # Check out 3D Analyst License
        if arcpy.CheckExtension("3D") == "Available":
            arcpy.CheckOutExtension("3D")
        else:
            arcpy.AddError("3D Analyst Extension not enabled. Please enable 3D Analyst from the Tools/Extensions menu. Exiting...\n")
            exit()

        # Environment settings
        arcpy.env.parallelProcessingFactor = "75%"
        arcpy.env.overwriteOutput = True
        arcpy.env.geographicTransformations = "WGS_1984_(ITRF00)_To_NAD_1983"
        arcpy.env.resamplingMethod = "BILINEAR"
        arcpy.env.pyramid = "PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP"

        # Determine if CLU is present
        if len(str(inCLU)) > 0:
            inCLU = arcpy.da.Describe(inCLU)['catalogPath']
            bSplitLU = True

        else:
            bSplitLU = False

        # ---------------------------------------------------------------------------- Define Variables
        watershed_path = arcpy.Describe(inWatershed).CatalogPath
        watershedGDB_path = watershed_path[:watershed_path .find(".gdb")+4]
        watershedGDB_name = os.path.basename(watershedGDB_path)
        userWorkspace = os.path.dirname(watershedGDB_path)
        watershedFD = watershedGDB_path + os.sep + "Layers"
        projectName = arcpy.ValidateTableName(os.path.basename(userWorkspace).replace(" ","_"))
        projectAOI = watershedFD + os.sep + projectName + "_AOI"
        projectAOI_path = arcpy.Describe(projectAOI).CatalogPath
        wsName = os.path.splitext(os.path.basename(inWatershed))[0]
        outputFolder = userWorkspace + os.sep + "gis_output"
        tables = outputFolder + os.sep + "tables"

        if not arcpy.Exists(outputFolder):
            arcpy.CreateFolder_management(userWorkspace, "gis_output")
        if not arcpy.Exists(tables):
            arcpy.CreateFolder_management(outputFolder, "tables")

        #ReferenceLine = "ReferenceLine"
        ReferenceLine = watershedFD + os.sep + "ReferenceLine"

        DEM_aoi = watershedGDB_path + os.sep + projectName + "_Raw_DEM"
        ProjectDEM = watershedGDB_path + os.sep + projectName + "_Project_DEM"
        DEMsmooth = watershedGDB_path + os.sep + projectName + "_DEMsmooth"

        # -------------------------------------------------------------------------- Permanent Datasets
        wsSoils = watershedFD + os.sep + wsName + "_Soils"
        landuse = watershedFD + os.sep + wsName + "_Landuse"
        storageTable = tables + os.sep + "storage.dbf"
        embankmentTable = tables + os.sep + "embankments.dbf"

        # -------------------------------------------------------------------------- Temporary Datasets
        #slopeStats = watershedGDB_path + os.sep + "slopeStats"
        #outletStats = watershedGDB_path + os.sep + "outletStats"
        storageTemp = watershedGDB_path + os.sep + "storageTemp"

        # -------------------------------------------------------------------------- Tables
        TR_55_LU_Lookup = os.path.join(os.path.dirname(sys.argv[0]), "Support.gdb" + os.sep + "TR_55_LU_Lookup")
        Hydro_Groups_Lookup = os.path.join(os.path.dirname(sys.argv[0]), "Support.gdb" + os.sep + "HydroGroups")
        Condition_Lookup = os.path.join(os.path.dirname(sys.argv[0]), "Support.gdb" + os.sep + "ConditionTable")
        storageTemplate = os.path.join(os.path.dirname(sys.argv[0]), "storage.dbf")

        # ---------------------------------------------------- Feature Layers in Arcmap
        landuseOut = "Watershed_Landuse"
        soilsOut = "Watershed_Soils"

        # Set path of log file and start logging
        textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.txt"
        logBasicSettings()

        # ----------------------------------------------------------------------------- Check Some Parameters
        # Exit if any are true
        AddMsgAndPrint("\nChecking input data and project data...",0)

        if not int(arcpy.GetCount_management(inWatershed).getOutput(0)) > 0:
            AddMsgAndPrint("\tWatershed Layer is empty!",2)
            AddMsgAndPrint("\tExiting...",2)
            exit()

        if arcpy.Describe(inWatershed).ShapeType != "Polygon":
            AddMsgAndPrint("\tWatershed Layer must be a polygon layer!",2)
            AddMsgAndPrint("\tExiting...",2)
            exit()

        if arcpy.Describe(inSoils).ShapeType != "Polygon":
            AddMsgAndPrint("\tSoils Layer must be a polygon layer!",2)
            AddMsgAndPrint("\tExiting...",2)
            exit()

        if bSplitLU:
            if arcpy.Describe(inCLU).ShapeType != "Polygon":
                AddMsgAndPrint("\tCLU Layer must be a polygon layer!",2)
                AddMsgAndPrint("\tExiting...",2)
                exit()

        if not arcpy.Exists(ProjectDEM):
            AddMsgAndPrint("\tProject DEM was not found in " + watershedGDB_path,2)
            AddMsgAndPrint("\tPlease run the Define AOI and the Create Stream Network tools from the WASCOB toolset.",2)
            AddMsgAndPrint("\tExiting...",2)
            exit()

        if not len(arcpy.ListFields(inSoils,hydroField)) > 0:
            AddMsgAndPrint("\tThe field specified for Hydro Groups does not exist in your soils data.",2)
            AddMsgAndPrint("\tPlease specify another name and try again.",2)
            AddMsgAndPrint("\tExiting...",2)
            exit()

        if not arcpy.Exists(TR_55_LU_Lookup):
            AddMsgAndPrint("\t\"TR_55_LU_Lookup\" was not found!",2)
            AddMsgAndPrint("\tMake sure \"Support.gdb\" is located within the same location as this script.",2)
            AddMsgAndPrint("\tExiting...",2)
            exit()

        if not arcpy.Exists(Hydro_Groups_Lookup):
            AddMsgAndPrint("\t\"Hydro_Groups_Lookup\" was not found!",2)
            AddMsgAndPrint("\tMake sure \"Support.gdb\" is located within the same location as this script.",2)
            AddMsgAndPrint("\tExiting...",2)
            exit()

        if not arcpy.Exists(Condition_Lookup):
            AddMsgAndPrint("\t\"Condition_Lookup\" was not found!",2)
            AddMsgAndPrint("\tMake sure \"Support.gdb\" is located within the same location as this script.",2)
            AddMsgAndPrint("\tExiting...",2)
            exit()

        # ------------------------------------------------------------------------------- Remove existing layers from ArcMap
        layersToRemove = (landuseOut,soilsOut)

        x = 0
        for layer in layersToRemove:
            if arcpy.Exists(layer):
                if x == 0:
                    AddMsgAndPrint("Removing layers from ArcGIS Pro")
                    x+=1
                try:
                    arcpy.delete_management(layer)
                    AddMsgAndPrint("Removing " + layer)
                except:
                    pass
        del x, layersToRemove

        # -------------------------------------------------------------------------- Delete Previous Data if present
        datasetsToRemove = (wsSoils,landuse,storageTable,embankmentTable)

        x = 0
        for dataset in datasetsToRemove:
            if arcpy.Exists(dataset):
                if x < 1:
                    AddMsgAndPrint("\nRemoving old datasets from FGDB: " + watershedGDB_name ,0)
                    x += 1
                try:
                    arcpy.Delete_management(dataset)
                    AddMsgAndPrint("\tDeleting..." + os.path.basename(dataset),0)
                except:
                    pass

        del datasetsToRemove, x

        # ------------------------------------------------------------------ Update inWatershed Area in case of user edits
        AddMsgAndPrint("\nUpdating drainage area(s)",0)

        wsUnits = arcpy.Describe(inWatershed).SpatialReference.LinearUnitName
        if wsUnits == "Meter" or wsUnits == "Foot" or wsUnits == "Foot_US" or wsUnits == "Feet":
            AddMsgAndPrint("\tLinear Units: " + wsUnits,0)
        else:
            AddMsgAndPrint("\tWatershed layer's linear units are UNKNOWN. Computed drainage area and other values may not be correct!",1)

        if len(arcpy.ListFields(inWatershed, "Acres")) < 1:
            # Acres field does not exist, so create it.
            arcpy.AddField_management(inWatershed, "Acres", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

        arcpy.CalculateField_management(inWatershed, "Acres", "!shape.area@acres!", "PYTHON3")
        AddMsgAndPrint("\nSuccessfully updated drainage area(s) acres.",0)

        # -------------------------- Get DEM Properties using ProjectDEM for WASCOB workflow
        demDesc = arcpy.da.Describe(ProjectDEM)
        demName = demDesc['name']
        demPath = demDesc['catalogPath']
        demCellSize = demDesc['meanCellWidth']
        demFormat = demDesc['format']
        demSR = demDesc['spatialReference']
        demCoordType = demSR.type
        linearUnits = demSR.linearUnitName

        if linearUnits in ('Meter','Meters'):
            linearUnits = "Meters"
        elif linearUnits in ('Foot','Feet','Foot_US'):
            linearUnits = "Feet"
        else:
            AddMsgAndPrint("\nLinear XY units of ProjectDEM could not be determined. Confirm input DEM in Define AOI step uses a projected coordinate system based on meters or feet. Exiting...",2)
            exit()

        #In this case we are using the ProjectDEM which has been converted to z units of feet, so we know the zUnits are feet.
        zUnits = "Feet"

        if linearUnits == "Meters":

            # Area units in the Area_2D column output of the SurfaceVolume tool are always based on the XY of the input DEM, regardless of Z.
            ftConversion = 0.092903     # 0.092903 sq meters in 1 sq foot
            acreConversion = 4046.86    # 4046.86 sq meters in 1 acre

            if zUnits == "Feet":
                Zfactor = 0.3048                    # For Slope tool
                conversionFactor = 1                # For computing Plane Height in Feet for output table. 1 foot in 1 foot
                volConversion = 4046.86             # For computing Volume in Acre Feet from square meters by feet for output table.

        # Linear units are Feet
        else:

            # Area units in the Area_2D column output of the SurfaceVolume tool are always based on the XY of the input DEM, regardless of Z.
            ftConversion = 1            # 1 sq feet in 1 sq feet
            acreConversion = 43560      # 43560 sq feet in 1 acre

            if zUnits == "Feet":
                Zfactor = 1                         # For Slope tool
                conversionFactor = 1                # For computing Plane Height in Feet for output table. 1 foot in 1 foot
                volConversion = 43560               # For computing Volume in Acre Feet from square meters by feet for output table.

        # ----------------------------------------------------------------------- Calculate Average Slope
        calcAvgSlope = False
        AddMsgAndPrint("\nUpdating average slope",0)

        # Always re-create DEMsmooth in case people jumped from Watershed workflow to WASCOB workflow somehow and base on ProjectDEM in this WASCOB toolset
        if arcpy.Exists(DEMsmooth):
            arcpy.Delete_management(DEMsmooth)

        # Run Focal Statistics on the ProjectDEM for the purpose of generating smoothed results.
        DEMsmooth = FocalStatistics(ProjectDEM, "RECTANGLE 3 3 CELL","MEAN","DATA")

        # Extract area for slope from DEMSmooth and compute statistics for it
        wtshdDEMsmooth = ExtractByMask(DEMsmooth, inWatershed)
        slopeGrid = Slope(wtshdDEMsmooth, "PERCENT_RISE", Zfactor)

        slopeStats = arcpy.CreateTable_management("in_memory", "slopeStats")
        arcpy.sa.ZonalStatisticsAsTable(inWatershed, "Subbasin", slopeGrid, slopeStats, "DATA")

        # Delete unwanted rasters
        arcpy.Delete_management(DEMsmooth)
        arcpy.Delete_management(wtshdDEMsmooth)
        arcpy.Delete_management(slopeGrid)

        # -------------------------------------------------------------------------------------- Update inWatershed FC with Average Slope
        AddMsgAndPrint("\n\tSuccessfully Calculated Average Slope")

        AddMsgAndPrint("\nCreate Watershed Results:")
        AddMsgAndPrint("\n===================================================")
        AddMsgAndPrint("\tUser Watershed: " + str(wsName))

        arcpy.SetProgressorLabel("Updating watershed fields")
        with arcpy.da.UpdateCursor(inWatershed,['Subbasin','Avg_Slope','Acres','SHAPE@AREA']) as cursor:
            for row in cursor:
                subBasinNumber = row[0]
                expression = (u'{} = ' + str(subBasinNumber)).format(arcpy.AddFieldDelimiters(slopeStats, "Subbasin"))
                avgSlope = [row[0] for row in arcpy.da.SearchCursor(slopeStats,["MEAN"],where_clause=expression)][0]
                row[1] = avgSlope
                cursor.updateRow(row)

                # Inform the user of Watershed Acres, area and avg. slope
                AddMsgAndPrint("\n\tSubbasin: " + str(subBasinNumber))
                AddMsgAndPrint("\t\tAcres: " + str(splitThousands(round(row[2],2))))
                AddMsgAndPrint("\t\tArea: " + str(splitThousands(round(row[3],2))) + " Sq. " + linearUnits)
                AddMsgAndPrint("\t\tAvg. Slope: " + str(round(avgSlope,2)))
                if row[2] > 40:
                    AddMsgAndPrint("\t\tSubbasin " + str(row[0]) + " is greater than the 40 acre 638 standard.",1)
                    AddMsgAndPrint("\t\tConsider re-delineating to split basins or move upstream.",1)

        AddMsgAndPrint("\n===================================================")
        arcpy.Delete_management(slopeStats)

        # ------------------------------------------------------------------------ Update reference line / Perform storage calculations
        if arcpy.Exists(ReferenceLine):
            bCalcSurfaceVol = True

        else:
            AddMsgAndPrint("\nReference Line not found in table of contents or in the workspace of your input watershed,",1)
            AddMsgAndPrint("\nUnable to update attributes to perform surface volume calculations.",1)
            AddMsgAndPrint("\nYou will have to either correct the workspace issue or manually derive surface / volume calculations for " + str(wsName),1)
            bCalcSurfaceVol = False

        # -------------------------------------------------------------------------- Update Reference Line Attributes
        if bCalcSurfaceVol:
            # --------------------------------------------------------------------- Add Attribute Embankement(s) and calc
            if len(arcpy.ListFields(ReferenceLine,"Subbasin")) < 1:
                arcpy.SetProgressorLabel("Adding Subbasin Field to ReferenceLine")
                arcpy.AddField_management(ReferenceLine, "Subbasin", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
            if len(arcpy.ListFields(ReferenceLine,"MaxElev")) < 1:
                arcpy.SetProgressorLabel("Adding MaxElev Field to ReferenceLine")
                arcpy.AddField_management(ReferenceLine, "MaxElev", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
            if len(arcpy.ListFields(ReferenceLine,"MinElev")) < 1:
                arcpy.SetProgressorLabel("Adding MinElev Field to ReferenceLine")
                arcpy.AddField_management(ReferenceLine, "MinElev", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
            if len(arcpy.ListFields(ReferenceLine,"MeanElev")) < 1:
                arcpy.SetProgressorLabel("Adding MeanElev Field to ReferenceLine")
                arcpy.AddField_management(ReferenceLine, "MeanElev", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
            if len(arcpy.ListFields(ReferenceLine,"LengthFt")) < 1:
                arcpy.SetProgressorLabel("Adding LengthFt Field to ReferenceLine")
                arcpy.AddField_management(ReferenceLine, "LengthFt", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

            # The original code does not update the Subbasin Field againg but it does
            # the rest of the Reference Line fields: MinElev, MaxElev, MeanElev
            # Populate Subbasin Field and Calculate embankment length
            arcpy.SetProgressorLabel("Updating Subbasin Field")
            objectIDfld = "!" + arcpy.da.Describe(ReferenceLine)['OIDFieldName'] + "!"
            arcpy.CalculateField_management(ReferenceLine,"Subbasin",objectIDfld, "PYTHON3")

            arcpy.SetProgressorLabel("Updating LengthFt Field")
            arcpy.CalculateField_management(ReferenceLine, "LengthFt","!shape.length@feet!", "PYTHON3")

            # Buffer outlet features by  raster cell size
            bufferDist = "" + str(demCellSize * 2) + " " + str(linearUnits) + ""
            arcpy.SetProgressorLabel("Buffering ReferenceLine by " + str(bufferDist) + " " + linearUnits)
            outletBuffer = arcpy.CreateScratchName("outletBuffer",data_type="FeatureClass",workspace="in_memory")
            arcpy.Buffer_analysis(ReferenceLine, outletBuffer, bufferDist, "FULL", "ROUND", "LIST", "Subbasin")

            # Get Reference Line Elevation Properties (Uses ProjectDEM, which is vertical feet by 1/10ths)
            arcpy.SetProgressorLabel("Calculating Reference Line Attributes")
            AddMsgAndPrint("\nCalculating Reference Line Attributes",0)

            outletStats = arcpy.CreateTable_management("in_memory", "outletStats")
            ZonalStatisticsAsTable(outletBuffer, "Subbasin", ProjectDEM, outletStats, "DATA")

            arcpy.CopyRows_management(storageTemplate, storageTable)

            # Update the Reference FC with the zonal stats
            with arcpy.da.UpdateCursor(ReferenceLine,['Subbasin','MinElev','MaxElev','MeanElev']) as cursor:
                for row in cursor:
                    subBasinNumber = row[0]
                    expression = (u'{} = ' + str(subBasinNumber)).format(arcpy.AddFieldDelimiters(outletStats, "Subbasin"))
                    stats = [(row[0],row[1],row[2]) for row in arcpy.da.SearchCursor(outletStats,["MIN","MAX","MEAN"],where_clause=expression)][0]

                    row[1] = stats[0] # Min Elev
                    row[2] = stats[1] # Max Elev
                    row[3] = round(stats[2],1) # Mean Elev

                    query = "Subbasin" + " = " +str(subBasinNumber)
                    arcpy.SelectLayerByAttribute_management(inWatershed, "NEW_SELECTION", query)

                    subMask = arcpy.CreateScratchName("subMask",data_type="FeatureClass",workspace="in_memory")
                    arcpy.CopyFeatures_management(inWatershed, subMask)
                    subGrid = ExtractByMask(ProjectDEM, subMask)

                    AddMsgAndPrint("\n\tRetrieving Minumum Elevation for subbasin "+ str(subBasinNumber) + "\n")
                    maxValue = stats[1]
                    MinElev = round(float(arcpy.GetRasterProperties_management(subGrid, "MINIMUM").getOutput(0)),1)
                    totalElev = round(float(maxValue - MinElev),1)
                    roundElev = math.floor(totalElev)
                    remainder = totalElev - roundElev

                    Reference_Plane = "BELOW"
                    plnHgt = MinElev + remainder
                    outputText = tables + os.sep + "subbasin" + str(subBasinNumber) +".txt"

                    f = open(outputText, "w")
                    f.write("Dataset, Plane_heig, Reference, Z_Factor, Area_2D, Area_3D, Volume, Subbasin\n")
                    f.close()

                    while plnHgt <= maxValue:
                        Plane_Height = plnHgt
                        AddMsgAndPrint("\tCalculating storage at elevation " + str(round(plnHgt,1)))
                        arcpy.SurfaceVolume_3d(subGrid, outputText, Reference_Plane, Plane_Height, 1)
                        plnHgt = 1 + plnHgt

                    AddMsgAndPrint("\n\t\t\t\tConverting results")
                    arcpy.CopyRows_management(outputText, storageTemp)
                    arcpy.CalculateField_management(storageTemp, "Subbasin", subBasinNumber, "PYTHON")
                    arcpy.Append_management(storageTemp, storageTable, "NO_TEST", "", "")

                    arcpy.Delete_management(subMask)
                    arcpy.Delete_management(subGrid)
                    arcpy.Delete_management(storageTemp)

                    # Only MinElev, MaxElev and MeanElev are being updated.
                    cursor.updateRow(row)

            AddMsgAndPrint("\n\tSuccessfully updated Reference Line attributes")
            arcpy.Delete_management(outletStats)
            arcpy.Delete_management(outletBuffer)

            arcpy.SelectLayerByAttribute_management(inWatershed, "CLEAR_SELECTION")

            arcpy.AddField_management(storageTable, "ELEV_FEET", "DOUBLE", "5", "1", "", "", "NULLABLE", "NON_REQUIRED", "")
            arcpy.AddField_management(storageTable, "POOL_SQFT", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
            arcpy.AddField_management(storageTable, "POOL_ACRES", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
            arcpy.AddField_management(storageTable, "ACRE_FOOT", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

            # Convert area sq feet and volume to cu ft (as necessary)
            elevFeetCalc = "round(!Plane_heig! *" + str(conversionFactor) + ",1)"
            pool2dSqftCalc = "round(!Area_2D! /" + str(ftConversion) + ",1)"
            pool2dAcCalc = "round(!Area_2D! /" + str(acreConversion) + ",1)"
            #pool3dSqftCalc = "round([Area_3D] /" + str(ftConversion) + ",1)"
            cuFootCalc = "round(!Volume! /" + str(volConversion) + ",1)"

            arcpy.CalculateField_management(storageTable, "Subbasin", "'Subbasin' + !Subbasin!", "PYTHON3")
            arcpy.CalculateField_management(storageTable, "ELEV_FEET", elevFeetCalc, "PYTHON3")
            arcpy.CalculateField_management(storageTable, "POOL_SQFT", pool2dSqftCalc, "PYTHON3")
            arcpy.CalculateField_management(storageTable, "POOL_ACRES", pool2dAcCalc, "PYTHON3")
            arcpy.CalculateField_management(storageTable, "ACRE_FOOT", cuFootCalc, "PYTHON3")

            AddMsgAndPrint("\n\tSurface volume and area calculations completed")

        # -------------------------------------------------------------------------- Process Soils and Landuse Data

        AddMsgAndPrint("\nProcessing Soils and Landuse for " + str(wsName) + "...",0)

        if bSplitLU:

            # Dissolve in case the watershed has multiple polygons
            watershedDissolve = arcpy.CreateScratchName("watershedDissolve",data_type="FeatureClass",workspace="in_memory")
            arcpy.Dissolve_management(inWatershed, watershedDissolve, "", "", "MULTI_PART", "DISSOLVE_LINES")

            # Clip the CLU layer to the dissolved watershed layer
            cluClip = arcpy.CreateScratchName("cluClip",data_type="FeatureClass",workspace="in_memory")
            arcpy.Clip_analysis(inCLU, watershedDissolve, cluClip)
            AddMsgAndPrint("\nSuccessfully clipped the CLU to your Watershed Layer")

            # Union the CLU and dissolve watershed layer simply to fill in gaps
            arcpy.Union_analysis(cluClip +";" + watershedDissolve, landuse, "ONLY_FID", "", "GAPS")
            AddMsgAndPrint("\nSuccessfully filled in any CLU gaps and created Landuse Layer: " + os.path.basename(landuse))

            # Delete FID field
            fields = [f.name for f in arcpy.ListFields(landuse,"FID*")]

            if len(fields):
                for field in fields:
                    arcpy.DeleteField_management(landuse,field)

            arcpy.Delete_management(watershedDissolve)
            arcpy.Delete_management(cluClip)

        else:
            AddMsgAndPrint("\nNo CLU Layer Detected",1)

            arcpy.Dissolve_management(inWatershed, landuse, "", "", "MULTI_PART", "DISSOLVE_LINES")
            AddMsgAndPrint("\n\tSuccessfully created Watershed Landuse layer: " + os.path.basename(landuse),0)

        arcpy.AddField_management(landuse, "LANDUSE", "TEXT", "", "", "254", "", "NULLABLE", "NON_REQUIRED")
        arcpy.CalculateField_management(landuse, "LANDUSE", "\"- Select Land Use -\"", "PYTHON3")

        arcpy.AddField_management(landuse, "CONDITION", "TEXT", "", "", "25", "", "NULLABLE", "NON_REQUIRED")
        arcpy.CalculateField_management(landuse, "CONDITION", "\"- Select Condition -\"", "PYTHON3")

        # ---------------------------------------------------------------------------------------------- Set up Domains
        watershedGDBdesc = arcpy.da.Describe(watershedGDB_path)
        domains = watershedGDBdesc['domains']

        if not "LandUse_Domain" in domains:
            arcpy.TableToDomain_management(TR_55_LU_Lookup, "LandUseDesc", "LandUseDesc", watershedGDB_path, "LandUse_Domain", "LandUse_Domain", "REPLACE")

        if not "Hydro_Domain" in domains:
            arcpy.TableToDomain_management(Hydro_Groups_Lookup, "HydrolGRP", "HydrolGRP", watershedGDB_path, "Hydro_Domain", "Hydro_Domain", "REPLACE")

        if not "Condition_Domain" in domains:
            arcpy.TableToDomain_management(Condition_Lookup, "CONDITION", "CONDITION", watershedGDB_path, "Condition_Domain", "Condition_Domain", "REPLACE")

        # Assign Domain To Landuse Fields for User Edits...
        arcpy.AssignDomainToField_management(landuse, "LANDUSE", "LandUse_Domain", "")
        arcpy.AssignDomainToField_management(landuse, "CONDITION", "Condition_Domain", "")

        AddMsgAndPrint("\nSuccessufully added \"LANDUSE\" and \"CONDITION\" fields to Landuse Layer and associated Domains")

        # ---------------------------------------------------------------------------------------------------------------------------------- Work with soils
        # --------------------------------------------------------------------------------------- Clip Soils
        # Clip the soils to the dissolved (and possibly unioned) watershed
        arcpy.Clip_analysis(inSoils,landuse,wsSoils)

        AddMsgAndPrint("\nSuccessfully clipped soils layer to Landuse layer and removed unnecessary fields")

        # --------------------------------------------------------------------------------------- Check Hydrologic Values
        AddMsgAndPrint("\nChecking Hydrologic Group Attributes in Soil Layer.....")

        validHydroValues = ['A','B','C','D','A/D','B/D','C/D','W']
        valuesToConvert = ['A/D','B/D','C/D','W']

        # List of input soil Hydrologic group values
        soilHydValues = list(set([row[0] for row in arcpy.da.SearchCursor(wsSoils,hydroField)]))

        # List of NULL hydrologic values in input soils
        expression = arcpy.AddFieldDelimiters(wsSoils, hydroField) + " IS NULL OR " + arcpy.AddFieldDelimiters(wsSoils, hydroField) + " = \'\'"
        nullSoilHydValues = [row[0] for row in arcpy.da.SearchCursor(wsSoils,hydroField,where_clause=expression)]

        # List of invalid hydrologic values relative to validHydroValues list
        invalidHydValues = [val for val in soilHydValues if not val in validHydroValues]
        hydValuesToConvert = [val for val in soilHydValues if val in valuesToConvert]

        if len(invalidHydValues):
            AddMsgAndPrint("\t\tThe following Hydrologic Values are not valid: " + str(invalidHydValues),1)

        if len(hydValuesToConvert):
            AddMsgAndPrint("\t\tThe following Hydrologic Values need to be converted: " + str(hydValuesToConvert) + " to a single class i.e. \"B/D\" to \"B\"",1)

        if nullSoilHydValues:
            AddMsgAndPrint("\tThere are " + str(len(nullSoilHydValues)) + " NULL polygon(s) that need to be attributed with a Hydrologic Group Value",1)

        # ------------------------------------------------------------------------------------------- Compare Input Field to SSURGO HydroGroup field name
        if hydroField.upper() != "HYDGROUP":
            arcpy.AddField_management(wsSoils, "HYDGROUP", "TEXT", "", "", "20", "", "NULLABLE", "NON_REQUIRED")
            arcpy.CalculateField_management(wsSoils, "HYDGROUP", "!" + str(hydroField) + "!", "PYTHON3")
            AddMsgAndPrint("\n\tAdded " + "\"HYDGROUP\" to soils layer.  Please Populate the Hydrologic Group Values manually for this field")

        # Delete any soil field not in the following list
        fieldsToKeep = ["MUNAME","MUKEY","HYDGROUP","MUSYM","OBJECTID"]

        for field in [f.name for f in arcpy.ListFields(wsSoils)]:
            if not field.upper() in fieldsToKeep and field.find("Shape") < 0:
                arcpy.DeleteField_management(wsSoils,field)

        arcpy.AssignDomainToField_management(wsSoils, "HYDGROUP", "Hydro_Domain", "")

        # ---------------------------------------------------------------------------------------------------------------------------- Compact FGDB
        arcpy.Compact_management(watershedGDB_path)
        AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path),0)

        # --------------------------------------------------------------------------------------------------------------------------- Prepare to Add to Arcmap

        arcpy.SetParameterAsText(4, wsSoils)
        arcpy.SetParameterAsText(5, landuse)

        # Copy refernce line to embankment table
        arcpy.CopyRows_management(ReferenceLine, embankmentTable)

        AddMsgAndPrint("\nAdding Layers to ArcGIS Pro")
        AddMsgAndPrint("\n\t=========================================================================")
        AddMsgAndPrint("\tBEFORE CALCULATING THE RUNOFF CURVE NUMBER FOR YOUR WATERSHED MAKE SURE TO",1)
        AddMsgAndPrint("\tATTRIBUTE THE \"LANDUSE\" AND \"CONDITION\" FIELDS IN " + os.path.basename(landuse) + " LAYER",1)

        if len(hydValuesToConvert) > 0:
            AddMsgAndPrint("\tAND CONVERT THE " + str(len(hydValuesToConvert)) + " COMBINED HYDROLOGIC GROUPS IN " + os.path.basename(wsSoils) + " LAYER",1)

        if len(nullSoilHydValues) > 0:
            AddMsgAndPrint("\tAS WELL AS POPULATE VALUES FOR THE " + str(len(nullSoilHydValues)) + " NULL POLYGONS IN " + os.path.basename(wsSoils) + " LAYER",1)

        AddMsgAndPrint("\t=========================================================================\n")

    except:
        print_exception()

from getpass import getuser
from os import path
from sys import argv, exit
from time import ctime

from arcpy import Describe, env, Exists, GetInstallInfo, GetParameterAsText, ListFields, SetParameterAsText, SetProgressorLabel
from arcpy.analysis import Clip, Union
from arcpy.da import SearchCursor
from arcpy.management import AddField, AssignDomainToField, CalculateField, Compact, Delete, DeleteField, Dissolve, GetCount, MultipartToSinglepart, TableToDomain
from arcpy.mp import ArcGISProject

from utils import AddMsgAndPrint, emptyScratchGDB, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, input_basins, input_soils, soils_hydro_field, input_boundaries):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Prepare Soil and Land Use Layers (WASCOB)\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tWASCOB Basins Layer: {input_basins}\n")
        f.write(f"\tSoils Layer: {input_soils}\n")
        f.write(f"\tSoils Hydrologic Field Name: {soils_hydro_field}\n")
        f.write(f"\tInput Polygon Boundaries Layer: {input_boundaries if input_boundaries else 'None'}\n")


### Initial Tool Validation ###
try:
    aprx = ArcGISProject('CURRENT')
    map = aprx.listMaps('Engineering')[0]
except:
    AddMsgAndPrint('\nThis tool must be run from an ArcGIS Pro project template distributed with the Engineering Tools. Exiting!', 2)
    exit()
# Check out Spatial Analyst License
if CheckExtension("spatial") == "Available":
    CheckOutExtension("spatial")
else:
    AddError("Spatial Analyst Extension not enabled. Please enable Spatial analyst from the Tools/Extensions menu\n",2)
    exit()

### Input Parameters ###
input_basins = GetParameterAsText(0)
input_soils = GetParameterAsText(1)
soils_hydro_field = GetParameterAsText(2)
input_boundaries = GetParameterAsText(3)

### Locate WASCOB GDB ###
basins_path = Describe(input_basins).catalogPath
if '_WASCOB.gdb' in basins_path:
    wascob_gdb = basins_path[:basins_path.find('.gdb')+4]
else:
    #TODO: Call it Wastershed or Basins?
    AddMsgAndPrint('\nThe selected Watershed layer is not from an Engineering Tools project or is not compatible with this version of the toolbox. Exiting...', 2)
    exit()

### Set Paths and Variables ###
support_dir = path.dirname(argv[0])
support_gdb = path.join(support_dir, 'Support.gdb')
scratch_gdb = path.join(support_dir, 'Scratch.gdb')
project_workspace = path.dirname(wascob_gdb)
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")
wascob_fd = path.join(wascob_gdb, 'Layers')
wascob_dem_path = path.join(wascob_gdb, f"{project_name}_DEM_WASCOB")
input_soils_path = Describe(input_soils).catalogPath
basins_name = path.basename(basins_path)
output_soils_name = f"{basins_name}_Soils"
output_soils_path = path.join(wascob_fd, output_soils_name)
output_landuse_name = f"{basins_name}_Land_Use"
output_landuse_path = path.join(wascob_fd, output_landuse_name)
tr_55_land_use_table = path.join(support_gdb, 'TR_55_Land_Use_Domain')
hydro_groups_table = path.join(support_gdb, 'Hydro_Groups_Domain')

### ESRI Environment Settings ###
dem_desc = Describe(wascob_dem_path)
dem_sr = dem_desc.spatialReference
dem_cell_size = dem_desc.meanCellWidth
dem_linear_units = dem_sr.linearUnitName
env.overwriteOutput = True
env.resamplingMethod = 'BILINEAR'
env.pyramid = 'PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP'
env.parallelProcessingFactor = '75%'
env.cellSize = dem_cell_size
env.snapRaster = wascob_dem_path
env.outputCoordinateSystem = dem_sr

### Validate DEM XY Units ###
if dem_linear_units in ['Meter', 'Meters']:
    linear_units = 'Meters'
    z_factor = 0.3048
elif dem_linear_units in ['Foot', 'Foot_US']:
    linear_units = 'Feet'
    z_factor = 1
else:
    AddMsgAndPrint(f"\nUnsupported DEM linear units {dem_linear_units}. Exiting...", 2)
    exit()

#NOTE: This requires knowledge of the input DEM elelvation units, which have been assumed thus far as feet
if linear_units == "Meters":
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

try:
    removeMapLayers(map, [output_soils_name, output_landuse_name])
    logBasicSettings(log_file_path, input_basins, input_soils, soils_hydro_field, input_boundaries)

    # Determine if CLU is present
    if len(str(input_boundaries)) > 0:
        input_boundaries = Describe(input_boundaries).catalogPath
        bSplitLU = True
    else:
        bSplitLU = False


    watershedGDB_path = watershed_path[:watershed_path .find(".gdb")+4]
    watershedGDB_name = path.basename(watershedGDB_path)
    userWorkspace = path.dirname(watershedGDB_path)
    watershedFD = watershedGDB_path + sep + "Layers"

    projectAOI = watershedFD + sep + project_name + "_AOI"
    projectAOI_path = Describe(projectAOI).CatalogPath
    wsName = path.splitext(path.basename(input_watershed))[0]
    outputFolder = userWorkspace + sep + "gis_output"
    tables = outputFolder + sep + "tables"

    ReferenceLine = watershedFD + sep + "ReferenceLine"

    DEM_aoi = watershedGDB_path + sep + project_name + "_Raw_DEM"
    ProjectDEM = watershedGDB_path + sep + project_name + "_Project_DEM"

    wsSoils = watershedFD + sep + wsName + "_Soils"
    landuse = watershedFD + sep + wsName + "_Landuse"
    storageTable = tables + sep + "storage.dbf"
    embankmentTable = tables + sep + "embankments.dbf"

    storageTemp = watershedGDB_path + sep + "storageTemp"

    TR_55_LU_Lookup = path.join(path.dirname(argv[0]), "Support.gdb" + sep + "TR_55_LU_Lookup")
    Hydro_Groups_Lookup = path.join(path.dirname(argv[0]), "Support.gdb" + sep + "HydroGroups")
    Condition_Lookup = path.join(path.dirname(argv[0]), "Support.gdb" + sep + "ConditionTable")
    storageTemplate = path.join(path.dirname(argv[0]), "storage.dbf")

    landuseOut = "Watershed_Landuse"
    soilsOut = "Watershed_Soils"

    if not int(GetCount(input_watershed).getOutput(0)) > 0:
        AddMsgAndPrint("\tWatershed Layer is empty!",2)
        AddMsgAndPrint("\tExiting...",2)
        exit()

    if Describe(input_watershed).ShapeType != "Polygon":
        AddMsgAndPrint("\tWatershed Layer must be a polygon layer!",2)
        AddMsgAndPrint("\tExiting...",2)
        exit()

    if Describe(input_soils).ShapeType != "Polygon":
        AddMsgAndPrint("\tSoils Layer must be a polygon layer!",2)
        AddMsgAndPrint("\tExiting...",2)
        exit()

    if bSplitLU:
        if Describe(input_boundaries).ShapeType != "Polygon":
            AddMsgAndPrint("\tCLU Layer must be a polygon layer!",2)
            AddMsgAndPrint("\tExiting...",2)
            exit()

    if not Exists(ProjectDEM):
        AddMsgAndPrint("\tProject DEM was not found in " + watershedGDB_path,2)
        AddMsgAndPrint("\tPlease run the Define AOI and the Create Stream Network tools from the WASCOB toolset.",2)
        AddMsgAndPrint("\tExiting...",2)
        exit()

    if not len(ListFields(input_soils,soils_hydro_field)) > 0:
        AddMsgAndPrint("\tThe field specified for Hydro Groups does not exist in your soils data.",2)
        AddMsgAndPrint("\tPlease specify another name and try again.",2)
        AddMsgAndPrint("\tExiting...",2)
        exit()

    if not Exists(TR_55_LU_Lookup):
        AddMsgAndPrint("\t\"TR_55_LU_Lookup\" was not found!",2)
        AddMsgAndPrint("\tMake sure \"Support.gdb\" is located within the same location as this script.",2)
        AddMsgAndPrint("\tExiting...",2)
        exit()

    if not Exists(Hydro_Groups_Lookup):
        AddMsgAndPrint("\t\"Hydro_Groups_Lookup\" was not found!",2)
        AddMsgAndPrint("\tMake sure \"Support.gdb\" is located within the same location as this script.",2)
        AddMsgAndPrint("\tExiting...",2)
        exit()

    if not Exists(Condition_Lookup):
        AddMsgAndPrint("\t\"Condition_Lookup\" was not found!",2)
        AddMsgAndPrint("\tMake sure \"Support.gdb\" is located within the same location as this script.",2)
        AddMsgAndPrint("\tExiting...",2)
        exit()

    # Update input_watershed Area in case of user edits
    AddMsgAndPrint("\nUpdating drainage area(s)",0)

    wsUnits = Describe(input_watershed).SpatialReference.LinearUnitName
    if wsUnits == "Meter" or wsUnits == "Foot" or wsUnits == "Foot_US" or wsUnits == "Feet":
        AddMsgAndPrint("\tLinear Units: " + wsUnits,0)
    else:
        AddMsgAndPrint("\tWatershed layer's linear units are UNKNOWN. Computed drainage area and other values may not be correct!",1)

    if len(ListFields(input_watershed, "Acres")) < 1:
        # Acres field does not exist, so create it.
        AddField(input_watershed, "Acres", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

    CalculateField(input_watershed, "Acres", "!shape.area@acres!", "PYTHON3")
    AddMsgAndPrint("\nSuccessfully updated drainage area(s) acres.",0)

    #TODO: Why calculate average slope for watershed(basins) again? Duplicated from Create WASCOB Basins
    # Calculate Average Slope
    calcAvgSlope = False
    AddMsgAndPrint("\nUpdating average slope",0)

    #NOTE: Should not need to do this, project_dem is already smoothed in first step, and we will use wascob_dem (derived from project_dem)
    # # Always re-create DEMsmooth in case people jumped from Watershed workflow to WASCOB workflow somehow and base on ProjectDEM in this WASCOB toolset
    # if Exists(DEMsmooth):
    #     Delete(DEMsmooth)

    # # Run Focal Statistics on the ProjectDEM for the purpose of generating smoothed results.
    # DEMsmooth = FocalStatistics(ProjectDEM, "RECTANGLE 3 3 CELL","MEAN","DATA")

    # # Extract area for slope from DEMSmooth and compute statistics for it
    # wtshdDEMsmooth = ExtractByMask(DEMsmooth, input_watershed)
    # slopeGrid = Slope(wtshdDEMsmooth, "PERCENT_RISE", Zfactor)

    # slopeStats = CreateTable("in_memory", "slopeStats")
    # ZonalStatisticsAsTable(input_watershed, "Subbasin", slopeGrid, slopeStats, "DATA")

    # # Delete unwanted rasters
    # Delete(DEMsmooth)
    # Delete(wtshdDEMsmooth)
    # Delete(slopeGrid)

    # # Update input_watershed FC with Average Slope
    # AddMsgAndPrint("\n\tSuccessfully Calculated Average Slope")

    # AddMsgAndPrint("\nCreate Watershed Results:")
    # AddMsgAndPrint("\tUser Watershed: " + str(wsName))

    # SetProgressorLabel("Updating watershed fields")
    # with UpdateCursor(input_watershed,['Subbasin','Avg_Slope','Acres','SHAPE@AREA']) as cursor:
    #     for row in cursor:
    #         subBasinNumber = row[0]
    #         expression = (u'{} = ' + str(subBasinNumber)).format(AddFieldDelimiters(slopeStats, "Subbasin"))
    #         avgSlope = [row[0] for row in SearchCursor(slopeStats,["MEAN"],where_clause=expression)][0]
    #         row[1] = avgSlope
    #         cursor.updateRow(row)

    #         # Inform the user of Watershed Acres, area and avg. slope
    #         AddMsgAndPrint("\n\tSubbasin: " + str(subBasinNumber))
    #         AddMsgAndPrint("\t\tAcres: " + str(round(row[2],2)))
    #         AddMsgAndPrint("\t\tArea: " + str(round(row[3],2))) + " Sq. " + linear_units
    #         AddMsgAndPrint("\t\tAvg. Slope: " + str(round(avgSlope,2)))
    #         if row[2] > 40:
    #             AddMsgAndPrint("\t\tSubbasin " + str(row[0]) + " is greater than the 40 acre 638 standard.",1)
    #             AddMsgAndPrint("\t\tConsider re-delineating to split basins or move upstream.",1)

    # Delete(slopeStats)

    # Update reference line / Perform storage calculations
    if Exists(ReferenceLine):
        bCalcSurfaceVol = True

    else:
        AddMsgAndPrint("\nReference Line not found in table of contents or in the workspace of your input watershed,",1)
        AddMsgAndPrint("\nUnable to update attributes to perform surface volume calculations.",1)
        AddMsgAndPrint("\nYou will have to either correct the workspace issue or manually derive surface / volume calculations for " + str(wsName),1)
        bCalcSurfaceVol = False

    #TODO: Why do this again, duplicated from Create WASCOB Basins?
    # Update Reference Line Attributes
    if bCalcSurfaceVol:
        # Add Attribute Embankement(s) and calc
        if len(ListFields(ReferenceLine,"Subbasin")) < 1:
            SetProgressorLabel("Adding Subbasin Field to ReferenceLine")
            AddField(ReferenceLine, "Subbasin", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        if len(ListFields(ReferenceLine,"MaxElev")) < 1:
            SetProgressorLabel("Adding MaxElev Field to ReferenceLine")
            AddField(ReferenceLine, "MaxElev", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        if len(ListFields(ReferenceLine,"MinElev")) < 1:
            SetProgressorLabel("Adding MinElev Field to ReferenceLine")
            AddField(ReferenceLine, "MinElev", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        if len(ListFields(ReferenceLine,"MeanElev")) < 1:
            SetProgressorLabel("Adding MeanElev Field to ReferenceLine")
            AddField(ReferenceLine, "MeanElev", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        if len(ListFields(ReferenceLine,"LengthFt")) < 1:
            SetProgressorLabel("Adding LengthFt Field to ReferenceLine")
            AddField(ReferenceLine, "LengthFt", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

        # The original code does not update the Subbasin Field againg but it does
        # the rest of the Reference Line fields: MinElev, MaxElev, MeanElev
        # Populate Subbasin Field and Calculate embankment length
        SetProgressorLabel("Updating Subbasin Field")
        objectIDfld = "!" + da.Describe(ReferenceLine)['OIDFieldName'] + "!"
        CalculateField(ReferenceLine,"Subbasin",objectIDfld, "PYTHON3")

        SetProgressorLabel("Updating LengthFt Field")
        CalculateField(ReferenceLine, "LengthFt","!shape.length@feet!", "PYTHON3")

        # Buffer outlet features by  raster cell size
        bufferDist = "" + str(dem_cell_size * 2) + " " + str(linearUnits) + ""
        SetProgressorLabel("Buffering ReferenceLine by " + str(bufferDist) + " " + linearUnits)
        outletBuffer = CreateScratchName("outletBuffer",data_type="FeatureClass",workspace="in_memory")
        Buffer_analysis(ReferenceLine, outletBuffer, bufferDist, "FULL", "ROUND", "LIST", "Subbasin")

        # Get Reference Line Elevation Properties (Uses ProjectDEM, which is vertical feet by 1/10ths)
        SetProgressorLabel("Calculating Reference Line Attributes")
        AddMsgAndPrint("\nCalculating Reference Line Attributes",0)

        outletStats = CreateTable("in_memory", "outletStats")
        ZonalStatisticsAsTable(outletBuffer, "Subbasin", ProjectDEM, outletStats, "DATA")

        CopyRows(storageTemplate, storageTable)

        # Update the Reference FC with the zonal stats
        with da.UpdateCursor(ReferenceLine,['Subbasin','MinElev','MaxElev','MeanElev']) as cursor:
            for row in cursor:
                subBasinNumber = row[0]
                expression = (u'{} = ' + str(subBasinNumber)).format(AddFieldDelimiters(outletStats, "Subbasin"))
                stats = [(row[0],row[1],row[2]) for row in da.SearchCursor(outletStats,["MIN","MAX","MEAN"],where_clause=expression)][0]

                row[1] = stats[0] # Min Elev
                row[2] = stats[1] # Max Elev
                row[3] = round(stats[2],1) # Mean Elev

                query = "Subbasin" + " = " +str(subBasinNumber)
                SelectLayerByAttribute(input_watershed, "NEW_SELECTION", query)

                subMask = CreateScratchName("subMask",data_type="FeatureClass",workspace="in_memory")
                CopyFeatures(input_watershed, subMask)
                subGrid = ExtractByMask(ProjectDEM, subMask)

                AddMsgAndPrint("\n\tRetrieving Minumum Elevation for subbasin "+ str(subBasinNumber) + "\n")
                maxValue = stats[1]
                MinElev = round(float(GetRasterProperties(subGrid, "MINIMUM").getOutput(0)),1)
                totalElev = round(float(maxValue - MinElev),1)
                roundElev = math.floor(totalElev)
                remainder = totalElev - roundElev

                Reference_Plane = "BELOW"
                plnHgt = MinElev + remainder
                outputText = tables + sep + "subbasin" + str(subBasinNumber) +".txt"

                f = open(outputText, "w")
                f.write("Dataset, Plane_heig, Reference, Z_Factor, Area_2D, Area_3D, Volume, Subbasin\n")
                f.close()

                while plnHgt <= maxValue:
                    Plane_Height = plnHgt
                    AddMsgAndPrint("\tCalculating storage at elevation " + str(round(plnHgt,1)))
                    SurfaceVolume_3d(subGrid, outputText, Reference_Plane, Plane_Height, 1)
                    plnHgt = 1 + plnHgt

                AddMsgAndPrint("\n\t\t\t\tConverting results")
                CopyRows(outputText, storageTemp)
                CalculateField(storageTemp, "Subbasin", subBasinNumber, "PYTHON")
                Append(storageTemp, storageTable, "NO_TEST", "", "")

                Delete(subMask)
                Delete(subGrid)
                Delete(storageTemp)

                # Only MinElev, MaxElev and MeanElev are being updated.
                cursor.updateRow(row)

        AddMsgAndPrint("\n\tSuccessfully updated Reference Line attributes")
        Delete(outletStats)
        Delete(outletBuffer)

        SelectLayerByAttribute(input_watershed, "CLEAR_SELECTION")

        AddField(storageTable, "ELEV_FEET", "DOUBLE", "5", "1", "", "", "NULLABLE", "NON_REQUIRED", "")
        AddField(storageTable, "POOL_SQFT", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        AddField(storageTable, "POOL_ACRES", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        AddField(storageTable, "ACRE_FOOT", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

        # Convert area sq feet and volume to cu ft (as necessary)
        elevFeetCalc = "round(!Plane_heig! *" + str(conversionFactor) + ",1)"
        pool2dSqftCalc = "round(!Area_2D! /" + str(ftConversion) + ",1)"
        pool2dAcCalc = "round(!Area_2D! /" + str(acreConversion) + ",1)"
        cuFootCalc = "round(!Volume! /" + str(volConversion) + ",1)"

        CalculateField(storageTable, "Subbasin", "'Subbasin' + !Subbasin!", "PYTHON3")
        CalculateField(storageTable, "ELEV_FEET", elevFeetCalc, "PYTHON3")
        CalculateField(storageTable, "POOL_SQFT", pool2dSqftCalc, "PYTHON3")
        CalculateField(storageTable, "POOL_ACRES", pool2dAcCalc, "PYTHON3")
        CalculateField(storageTable, "ACRE_FOOT", cuFootCalc, "PYTHON3")

        AddMsgAndPrint("\n\tSurface volume and area calculations completed")

    AddMsgAndPrint("\nProcessing Soils and Landuse for " + str(wsName) + "...")

    if bSplitLU:

        # Dissolve in case the watershed has multiple polygons
        watershedDissolve = CreateScratchName("watershedDissolve",data_type="FeatureClass",workspace="in_memory")
        Dissolve(input_watershed, watershedDissolve, "", "", "MULTI_PART", "DISSOLVE_LINES")

        # Clip the CLU layer to the dissolved watershed layer
        cluClip = CreateScratchName("cluClip",data_type="FeatureClass",workspace="in_memory")
        Clip_analysis(input_boundaries, watershedDissolve, cluClip)
        AddMsgAndPrint("\nSuccessfully clipped the CLU to your Watershed Layer")

        # Union the CLU and dissolve watershed layer simply to fill in gaps
        Union_analysis(cluClip +";" + watershedDissolve, landuse, "ONLY_FID", "", "GAPS")
        AddMsgAndPrint("\nSuccessfully filled in any CLU gaps and created Landuse Layer: " + path.basename(landuse))

        # Delete FID field
        fields = [f.name for f in ListFields(landuse,"FID*")]

        if len(fields):
            for field in fields:
                DeleteField(landuse,field)

        Delete(watershedDissolve)
        Delete(cluClip)

    else:
        AddMsgAndPrint("\nNo CLU Layer Detected",1)

        Dissolve(input_watershed, landuse, "", "", "MULTI_PART", "DISSOLVE_LINES")
        AddMsgAndPrint("\n\tSuccessfully created Watershed Landuse layer: " + path.basename(landuse),0)

    AddField(landuse, "LANDUSE", "TEXT", "", "", "254", "", "NULLABLE", "NON_REQUIRED")
    CalculateField(landuse, "LANDUSE", "\"- Select Land Use -\"", "PYTHON3")

    AddField(landuse, "CONDITION", "TEXT", "", "", "25", "", "NULLABLE", "NON_REQUIRED")
    CalculateField(landuse, "CONDITION", "\"- Select Condition -\"", "PYTHON3")

    # Set up Domains
    watershedGDBdesc = Describe(watershedGDB_path)
    domains = watershedGDBdesc.domains

    if not "LandUse_Domain" in domains:
        TableToDomain(TR_55_LU_Lookup, "LandUseDesc", "LandUseDesc", watershedGDB_path, "LandUse_Domain", "LandUse_Domain", "REPLACE")

    if not "Hydro_Domain" in domains:
        TableToDomain(Hydro_Groups_Lookup, "HydrolGRP", "HydrolGRP", watershedGDB_path, "Hydro_Domain", "Hydro_Domain", "REPLACE")

    if not "Condition_Domain" in domains:
        TableToDomain(Condition_Lookup, "CONDITION", "CONDITION", watershedGDB_path, "Condition_Domain", "Condition_Domain", "REPLACE")

    # Assign Domain To Landuse Fields for User Edits...
    AssignDomainToField(landuse, "LANDUSE", "LandUse_Domain", "")
    AssignDomainToField(landuse, "CONDITION", "Condition_Domain", "")

    AddMsgAndPrint("\nSuccessufully added \"LANDUSE\" and \"CONDITION\" fields to Landuse Layer and associated Domains")

    # Clip the soils to the dissolved (and possibly unioned) watershed
    Clip(input_soils,landuse,wsSoils)

    AddMsgAndPrint("\nSuccessfully clipped soils layer to Landuse layer and removed unnecessary fields")

    # Check Hydrologic Values
    AddMsgAndPrint("\nChecking Hydrologic Group Attributes in Soil Layer.....")

    validHydroValues = ['A','B','C','D','A/D','B/D','C/D','W']
    valuesToConvert = ['A/D','B/D','C/D','W']

    # List of input soil Hydrologic group values
    soilHydValues = list(set([row[0] for row in SearchCursor(wsSoils,soils_hydro_field)]))

    # List of NULL hydrologic values in input soils
    expression = AddFieldDelimiters(wsSoils, soils_hydro_field) + " IS NULL OR " + AddFieldDelimiters(wsSoils, soils_hydro_field) + " = \'\'"
    nullSoilHydValues = [row[0] for row in SearchCursor(wsSoils,soils_hydro_field,where_clause=expression)]

    # List of invalid hydrologic values relative to validHydroValues list
    invalidHydValues = [val for val in soilHydValues if not val in validHydroValues]
    hydValuesToConvert = [val for val in soilHydValues if val in valuesToConvert]

    if len(invalidHydValues):
        AddMsgAndPrint("\t\tThe following Hydrologic Values are not valid: " + str(invalidHydValues),1)

    if len(hydValuesToConvert):
        AddMsgAndPrint("\t\tThe following Hydrologic Values need to be converted: " + str(hydValuesToConvert) + " to a single class i.e. \"B/D\" to \"B\"",1)

    if nullSoilHydValues:
        AddMsgAndPrint("\tThere are " + str(len(nullSoilHydValues)) + " NULL polygon(s) that need to be attributed with a Hydrologic Group Value",1)

    # Compare Input Field to SSURGO HydroGroup field name
    if soils_hydro_field.upper() != "HYDGROUP":
        AddField(wsSoils, "HYDGROUP", "TEXT", "", "", "20", "", "NULLABLE", "NON_REQUIRED")
        CalculateField(wsSoils, "HYDGROUP", "!" + str(soils_hydro_field) + "!", "PYTHON3")
        AddMsgAndPrint("\n\tAdded " + "\"HYDGROUP\" to soils layer.  Please Populate the Hydrologic Group Values manually for this field")

    # Delete any soil field not in the following list
    fieldsToKeep = ["MUNAME","MUKEY","HYDGROUP","MUSYM","OBJECTID"]

    for field in [f.name for f in ListFields(wsSoils)]:
        if not field.upper() in fieldsToKeep and field.find("Shape") < 0:
            DeleteField(wsSoils,field)

    AssignDomainToField(wsSoils, "HYDGROUP", "Hydro_Domain", "")

    # Copy refernce line to embankment table
    CopyRows(ReferenceLine, embankmentTable)

    AddMsgAndPrint("\nAdding Layers to ArcGIS Pro")
    AddMsgAndPrint("\tBEFORE CALCULATING THE RUNOFF CURVE NUMBER FOR YOUR WATERSHED MAKE SURE TO",1)
    AddMsgAndPrint("\tATTRIBUTE THE \"LANDUSE\" AND \"CONDITION\" FIELDS IN " + path.basename(landuse) + " LAYER",1)

    if len(hydValuesToConvert) > 0:
        AddMsgAndPrint("\tAND CONVERT THE " + str(len(hydValuesToConvert)) + " COMBINED HYDROLOGIC GROUPS IN " + path.basename(wsSoils) + " LAYER",1)

    if len(nullSoilHydValues) > 0:
        AddMsgAndPrint("\tAS WELL AS POPULATE VALUES FOR THE " + str(len(nullSoilHydValues)) + " NULL POLYGONS IN " + path.basename(wsSoils) + " LAYER",1)

    ### Add Outputs to Map ###
    SetParameterAsText(4, output_landuse_path)
    SetParameterAsText(5, output_soils_path)

    ### Compact Project GDB ###
    try:
        SetProgressorLabel('Compacting project geodatabase...')
        AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
        Compact(wascob_gdb)
    except:
        pass

    AddMsgAndPrint('\nPrepare Soil and Land Use Layers (WASCOB) completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Prepare Soil and Land Use Layers (WASCOB)'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Prepare Soil and Land Use Layers (WASCOB)'), 2)

finally:
    emptyScratchGDB(scratch_gdb)

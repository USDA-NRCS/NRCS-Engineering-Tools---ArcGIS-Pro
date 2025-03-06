from getpass import getuser
from os import path
from sys import argv, exit
from time import ctime

from arcpy import AddFieldDelimiters, CheckExtension, CheckOutExtension, Describe, env, Exists, GetInstallInfo, \
    GetParameterAsText, ListFields, SetParameterAsText, SetProgressorLabel
from arcpy.analysis import Clip, Union
from arcpy.da import SearchCursor
from arcpy.management import AddField, AssignDomainToField, CalculateField, Compact, CopyFeatures, Delete, DeleteField, \
    Dissolve, GetCount, TableToDomain
from arcpy.mp import ArcGISProject

from utils import AddMsgAndPrint, emptyScratchGDB, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, watershed):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Prepare Soil and Land Use Layers\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tWatershed Layer: {watershed}\n")


### Initial Tool Validation ###
try:
    aprx = ArcGISProject('CURRENT')
    map = aprx.listMaps('Engineering')[0]
except:
    AddMsgAndPrint('\nThis tool must be run from an ArcGIS Pro project template distributed with the Engineering Tools. Exiting!', 2)
    exit()

if CheckExtension('Spatial') == 'Available':
    CheckOutExtension('Spatial')
else:
    AddMsgAndPrint('\nSpatial Analyst Extension not enabled. Please enable Spatial Analyst from Project, Licensing, Configure licensing options. Exiting...', 2)
    exit()

### Input Parameters ###
watershed = GetParameterAsText(0)
soils = GetParameterAsText(1)
hydro_field = GetParameterAsText(2)
clu = GetParameterAsText(3)

### Locate Project GDB ###
watershed_path = Describe(watershed).catalogPath
if 'EngPro.gdb' in watershed_path:
    project_gdb = watershed_path[:watershed_path.find('.gdb')+4]
else:
    AddMsgAndPrint('\nThe selected Watershed layer is not from an Engineering Tools project or is not compatible with this version of the toolbox. Exiting...', 2)
    exit()

### Set Paths and Variables ###
support_dir = path.dirname(argv[0])
support_gdb = path.join(support_dir, 'Support.gdb')
scratch_gdb = path.join(support_dir, 'Scratch.gdb')
project_workspace = path.dirname(project_gdb)
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")
project_fd = path.join(project_gdb, 'Layers')
input_soils_path = Describe(soils).catalogPath
watershed_name = path.basename(watershed_path)
output_soils_name = f"{watershed_name}_Soils"
output_soils_path = path.join(project_fd, output_soils_name)
output_landuse_name = f"{watershed_name}_Landuse"
output_landuse_path = path.join(project_fd, output_landuse_name)
tr_55_table = path.join(support_gdb, 'TR_55_LU_Lookup')
hydro_groups_table = path.join(support_gdb, 'HydroGroups')
condition_table = path.join(support_gdb, 'ConditionTable')
watershed_dissolve_temp = path.join(scratch_gdb, 'Watershed_Dissolve')
clu_clip_temp = path.join(scratch_gdb, 'CLU_Clip')

### Validate Required Datasets Exist ###
if not int(GetCount(watershed_path).getOutput(0)) > 0:
    AddMsgAndPrint('\nThe selected Watershed layer is empty. At least one feature is required. Exiting...', 2)
    exit()
if not Exists(tr_55_table):
    AddMsgAndPrint('\nTR_55_LU_Lookup table was not found in Support.gdb. Exiting...', 2)
    exit()
if not Exists(hydro_groups_table):
    AddMsgAndPrint('\nHydro_Groups_Lookup table was not found in Support.gdb. Exiting...', 2)
    exit()
if not Exists(condition_table):
    AddMsgAndPrint('\nCondition_Lookup table was not found in Support.gdb. Exiting...', 2)
    exit()

### ESRI Environment Settings ###
env.overwriteOutput = True
env.parallelProcessingFactor = '75%'

try:
    removeMapLayers(map, [output_soils_name, output_landuse_name])
    logBasicSettings()

    # Determine if CLU is present
    if len(str(clu)) > 0:
        inCLU = Describe(clu).catalogPath
        bSplitLU = True

    else:
        bSplitLU = False

    # Create Watershed
    # if paths are not the same then assume AOI was manually digitized
    # or input is some from some other feature class/shapefile

    # True if watershed was not created from this Eng tools
    bExternalWatershed = False

    if not watershed_path == watershed:

        # delete the AOI feature class; new one will be created
        if Exists(watershed):

            Delete(watershed)
            CopyFeatures(watershed_path, watershed)
            AddMsgAndPrint('\nSuccessfully Overwrote existing Watershed')

        else:
            CopyFeatures(watershed_path, watershed)
            AddMsgAndPrint("\nSuccessfully Created Watershed " + path.basename(watershed))

        bExternalWatershed = True

    # paths are the same therefore input IS projectAOI
    else:
        AddMsgAndPrint("\nUsing existing " + path.basename(watershed) + " feature class")

    if bExternalWatershed:
        watershedDesc = Describe(watershed)

        # Delete all fields in watershed layer except for obvious ones
        for field in [f.name for f in ListFields(watershed)]:

            # Delete all fields that are not the following
            if not field in (watershedDesc['shapeFieldName'], watershedDesc['OIDFieldName'], 'Subbasin'):
                DeleteField(watershed,field)

        if not len(ListFields(watershed, 'Subbasin')) > 0:
            AddField(watershed, 'Subbasin', 'SHORT')
            CalculateField(watershed, 'Subbasin', watershedDesc['OIDFieldName'], 'PYTHON3')

        if not len(ListFields(watershed,'Acres')) > 0:
            AddField(watershed, 'Acres', 'DOUBLE')
            CalculateField(watershed, 'Acres', '!shape.area@ACRES!', 'PYTHON3')

    # Create Landuse Layer
    if bSplitLU:

        # Dissolve in case the watershed has multiple polygons
        Dissolve(watershed_path, watershed_dissolve_temp, '', '', 'MULTI_PART', 'DISSOLVE_LINES')

        # Clip the CLU layer to the dissolved watershed layer
        Clip(inCLU, watershed_dissolve_temp, clu_clip_temp)
        AddMsgAndPrint('\nSuccessfully clipped the CLU to your Watershed Layer')

        # Union the CLU and dissolve watershed layer simply to fill in gaps
        Union(f"{clu_clip_temp};{watershed_dissolve_temp}", output_landuse_path, 'ONLY_FID', '', 'GAPS')
        AddMsgAndPrint(f"\nSuccessfully filled in any CLU gaps and created Landuse Layer: {output_landuse_name}")

        # Delete FID field
        fields = [f.name for f in ListFields(output_landuse_path, 'FID*')]

        if len(fields):
            for field in fields:
                DeleteField(output_landuse_path, field)

    else:
        AddMsgAndPrint('\nNo CLU Layer Detected',1)

        Dissolve(watershed_path, output_landuse_path, '', '', 'MULTI_PART', 'DISSOLVE_LINES')
        AddMsgAndPrint('\nSuccessfully created Watershed Landuse layer: ' + path.basename(output_landuse_path),1)

    AddField(output_landuse_path, 'LANDUSE', 'TEXT', field_length='254')
    CalculateField(output_landuse_path, 'LANDUSE', "'- Select Land Use -'", 'PYTHON3')

    AddField(output_landuse_path, 'CONDITION', 'TEXT', field_length='25')
    CalculateField(output_landuse_path, 'CONDITION', "'- Select Condition -'", 'PYTHON3')

    # Set up Domains
    domains = Describe(project_gdb).domains
    if not 'LandUse_Domain' in domains:
        TableToDomain(tr_55_table, 'LandUseDesc', 'LandUseDesc', project_gdb, 'LandUse_Domain', 'LandUse_Domain', 'REPLACE')
    if not 'Hydro_Domain' in domains:
        TableToDomain(hydro_groups_table, 'HydrolGRP', 'HydrolGRP', project_gdb, 'Hydro_Domain', 'Hydro_Domain', 'REPLACE')
    if not 'Condition_Domain' in domains:
        TableToDomain(condition_table, 'CONDITION', 'CONDITION', project_gdb, 'Condition_Domain', 'Condition_Domain', 'REPLACE')

    AssignDomainToField(output_landuse_path, 'LANDUSE', 'LandUse_Domain')
    AssignDomainToField(output_landuse_path, 'CONDITION', 'Condition_Domain')

    AddMsgAndPrint("\nSuccessufully added \"LANDUSE\" and \"CONDITION\" fields to Landuse Layer and associated Domains")

    # Clip the soils to the dissolved (and possibly unioned) watershed
    Clip(input_soils_path, output_landuse_path, output_soils_path)

    AddMsgAndPrint('\nSuccessfully clipped soils layer to Landuse layer and removed unnecessary fields')

    # Check Hydrologic Values
    AddMsgAndPrint('\nChecking Hydrologic Group Attributes in Soil Layer.....')

    validHydroValues = ['A','B','C','D','A/D','B/D','C/D','W']
    valuesToConvert = ['A/D','B/D','C/D','W']

    # List of input soil Hydrologic group values
    soilHydValues = list(set([row[0] for row in SearchCursor(output_soils_path, hydro_field)]))

    # List of NULL hydrologic values in input soils
    expression = AddFieldDelimiters(output_soils_path, hydro_field) + " IS NULL OR " + AddFieldDelimiters(output_soils_path, hydro_field) + " = \'\'"
    nullSoilHydValues = [row[0] for row in SearchCursor(output_soils_path, hydro_field, where_clause=expression)]

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
    if hydro_field.upper() != 'HYDGROUP':
        AddField(output_soils_path, 'HYDGROUP', 'TEXT', field_length='20')
        CalculateField(output_soils_path, 'HYDGROUP', f"!{hydro_field}!", 'PYTHON3')
        AddMsgAndPrint("\n\tAdded " + "\"HYDGROUP\" to soils layer.  Please Populate the Hydrologic Group Values manually for this field")

    # Delete any soil field not in the following list
    fieldsToKeep = ['MUNAME','MUKEY','HYDGROUP','MUSYM','OBJECTID']

    for field in [f.name for f in ListFields(output_soils_path)]:
        if not field.upper() in fieldsToKeep and field.find('Shape') < 0: #BUG: See GH issue
            DeleteField(output_soils_path,field)

    AssignDomainToField(output_soils_path, 'HYDGROUP', 'Hydro_Domain')

    SetParameterAsText(4, output_landuse_path)
    SetParameterAsText(5, output_soils_path)

    if bExternalWatershed:
        SetParameterAsText(6, watershed)

    AddMsgAndPrint("\tBEFORE CALCULATING THE RUNOFF CURVE NUMBER FOR YOUR WATERSHED MAKE SURE TO",1)
    AddMsgAndPrint("\tATTRIBUTE THE \"LANDUSE\" AND \"CONDITION\" FIELDS IN " + output_landuse_name + " LAYER",1)

    if len(hydValuesToConvert) > 0:
        AddMsgAndPrint("\tAND CONVERT THE " + str(len(hydValuesToConvert)) + " COMBINED HYDROLOGIC GROUPS IN " + output_soils_name + " LAYER",1)

    if len(nullSoilHydValues) > 0:
        AddMsgAndPrint("\tAS WELL AS POPULATE VALUES FOR THE " + str(len(nullSoilHydValues)) + " NULL POLYGONS IN " + output_soils_name + " LAYER",1)

    ### Compact Project GDB ###
    try:
        SetProgressorLabel('Compacting project geodatabase...')
        AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
        Compact(project_gdb)
    except:
        pass

    AddMsgAndPrint('\nPrepare Soil and Land Use Layers completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Prepare Soil and Land Use Layers'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Prepare Soil and Land Use Layers'), 2)

finally:
    emptyScratchGDB(scratch_gdb)
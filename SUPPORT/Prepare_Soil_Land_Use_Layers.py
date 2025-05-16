from getpass import getuser
from os import path
from sys import argv, exit
from time import ctime

from arcpy import Describe, env, Exists, GetInstallInfo, GetParameterAsText, ListFields, SetParameterAsText, SetProgressorLabel
from arcpy.analysis import Clip, Union
from arcpy.da import SearchCursor
from arcpy.management import AddField, AssignDomainToField, CalculateField, Compact, DeleteField, Dissolve, GetCount, MultipartToSinglepart, TableToDomain
from arcpy.mp import ArcGISProject

from utils import AddMsgAndPrint, emptyScratchGDB, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, input_watershed, input_soils, soils_hydro_field, input_boundaries):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Prepare Soil and Land Use Layers\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tWatershed Layer: {input_watershed}\n")
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

### Input Parameters ###
input_watershed = GetParameterAsText(0)
input_soils = GetParameterAsText(1)
soils_hydro_field = GetParameterAsText(2)
input_boundaries = GetParameterAsText(3)

### Locate Project GDB ###
watershed_path = Describe(input_watershed).catalogPath
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
input_soils_path = Describe(input_soils).catalogPath
watershed_name = path.basename(watershed_path)
output_soils_name = f"{watershed_name}_Soils"
output_soils_path = path.join(project_fd, output_soils_name)
output_landuse_name = f"{watershed_name}_Land_Use"
output_landuse_path = path.join(project_fd, output_landuse_name)
tr_55_land_use_table = path.join(support_gdb, 'TR_55_Land_Use_Domain')
hydro_groups_table = path.join(support_gdb, 'Hydro_Groups_Domain')
boundaries_clip_temp = path.join(scratch_gdb, 'Boundaries_Clip_Temp')
land_use_temp = path.join(scratch_gdb, 'Land_Use_Temp')
watershed_dissolve_temp = path.join(scratch_gdb, 'Watershed_Dissolve')

### Validate Required Datasets Exist ###
if '_Land_Use' in input_watershed or '_Soils' in input_watershed:
    AddMsgAndPrint('\nInput layer appears to be either a Land Use or Soils layer, not the Watershed layer. Exiting...', 2)
    exit()
if not len(ListFields(input_watershed, 'Subbasin')) > 0:
    AddMsgAndPrint('\nSubbasin field was not found in input Watershed layer. Exiting...', 2)
    exit()
if not Exists(tr_55_land_use_table):
    AddMsgAndPrint('\nTR_55_Land_Use_Domain table was not found in Support.gdb. Exiting...', 2)
    exit()
if not Exists(hydro_groups_table):
    AddMsgAndPrint('\nHydro_Groups_Domain table was not found in Support.gdb. Exiting...', 2)
    exit()

### ESRI Environment Settings ###
env.overwriteOutput = True
env.parallelProcessingFactor = '75%'

try:
    removeMapLayers(map, [output_soils_name, output_landuse_name])
    logBasicSettings(log_file_path, input_watershed, input_soils, soils_hydro_field, input_boundaries)

    ### Create Land Use Layer ###
    SetProgressorLabel('Creating Land Use layer...')
    if input_boundaries:
        Dissolve(watershed_path, watershed_dissolve_temp, '', '', 'MULTI_PART', 'DISSOLVE_LINES')
        Clip(input_boundaries, watershed_path, boundaries_clip_temp)
        Union([boundaries_clip_temp, watershed_dissolve_temp], land_use_temp, 'NO_FID')
        MultipartToSinglepart(land_use_temp, output_landuse_path)
        AddMsgAndPrint('\nCreated Land Use layer from dissolved watershed and input boundaries intersection...', log_file_path=log_file_path)
    else:
        Dissolve(watershed_path, output_landuse_path, '', '', 'MULTI_PART', 'DISSOLVE_LINES')
        AddMsgAndPrint('\nCreated Land Use layer from dissolved watershed...', log_file_path=log_file_path)

    ### Set Land Use Domain and Delete Extra Fields ###
    SetProgressorLabel('Setting up LANDUSE domain...')
    AddMsgAndPrint('\nSetting up LANDUSE domain...', log_file_path=log_file_path)

    domains = Describe(project_gdb).domains
    if not 'LandUse_Domain' in domains:
        TableToDomain(tr_55_land_use_table, 'LANDUSE', 'LANDUSE', project_gdb, 'LandUse_Domain', 'LandUse_Domain', 'REPLACE')

    AddField(output_landuse_path, 'LANDUSE', 'TEXT', field_length='254', field_domain='LandUse_Domain')
    CalculateField(output_landuse_path, 'LANDUSE', "'Landuse not assigned'", 'PYTHON3')

    delete_fields = []
    for field in ListFields(output_landuse_path):
        if field.name != 'LANDUSE' and not field.required:
            delete_fields.append(field.name)
    DeleteField(output_landuse_path, delete_fields)

    ### Clip Soil Data with Land Use ###
    SetProgressorLabel('Clipping soils data...')
    AddMsgAndPrint('\nClipping soils data...', log_file_path=log_file_path)
    Clip(input_soils_path, output_landuse_path, output_soils_path)

    ### Update Fields and Hydrologic Group Domain ###
    SetProgressorLabel('Updating soils fields...')
    AddMsgAndPrint('\nUpdating soils fields...', log_file_path=log_file_path)

    if soils_hydro_field.upper() != 'HYDGROUP':
        AddField(output_soils_path, 'HYDGROUP', 'TEXT', field_length='20')
        CalculateField(output_soils_path, 'HYDGROUP', f"!{soils_hydro_field}!", 'PYTHON3')
        AddMsgAndPrint(f"\nAdded 'HYDGROUP' field to soils table and copied values from '{soils_hydro_field}'...", log_file_path=log_file_path)

    if not 'Hydro_Domain' in domains:
        TableToDomain(hydro_groups_table, 'HydrolGRP', 'HydrolGRP', project_gdb, 'Hydro_Domain', 'Hydro_Domain', 'REPLACE')

    AssignDomainToField(output_soils_path, 'HYDGROUP', 'Hydro_Domain')
    soils_hydro_field = 'HYDGROUP'

    delete_fields = []
    for field in ListFields(output_soils_path):
        if not field.name.upper() in ['MUNAME','MUKEY','HYDGROUP','MUSYM'] and not field.required:
            delete_fields.append(field.name)
    DeleteField(output_soils_path, delete_fields)

    ### Validate Hydrologic Group Values ###
    soils_hyrdo_values = set([row[0] for row in SearchCursor(output_soils_path, soils_hydro_field)])
    where_clause = f"{soils_hydro_field} IS NULL OR {soils_hydro_field} = ''"
    empty_hydro_values = [row[0] for row in SearchCursor(output_soils_path, soils_hydro_field, where_clause=where_clause)]
    if len(empty_hydro_values) == 1:
        AddMsgAndPrint('\tThere is 1 NULL polygon that needs to be attributed with a Hydrologic Group Value.', 1, log_file_path)
    elif len(empty_hydro_values) > 1:
        AddMsgAndPrint(f"\tThere are {len(empty_hydro_values)} NULL polygons that need to be attributed with a Hydrologic Group Value.", 1, log_file_path)

    valid_hydro_values = ['A','B','C','D','A/D','B/D','C/D','W']
    invalid_hydro_values = [val for val in soils_hyrdo_values if not val in valid_hydro_values]
    if len(invalid_hydro_values):
        AddMsgAndPrint(f"\tThe following Hydrologic Values are not valid: {str(invalid_hydro_values)}.", 1, log_file_path)

    convert_hydro_values = ['A/D','B/D','C/D','W']
    hydro_values_to_convert = [val for val in soils_hyrdo_values if val in convert_hydro_values]
    if len(hydro_values_to_convert):
        AddMsgAndPrint(f"\tThe following Hydrologic Values need to be converted: {str(hydro_values_to_convert)} to a single class (e.g. 'B/D' to 'B').", 1, log_file_path)

    AddMsgAndPrint(f"\tNOTICE: Before calculating the Runoff Curve Number for the watershed, {output_landuse_name} layer requires attribution for LANDUSE fields, and any combined, invalid, or NULL Hydrologic Group values in {output_soils_name} must be addressed.", 1, log_file_path)

    ### Add Outputs to Map ###
    SetParameterAsText(4, output_landuse_path)
    SetParameterAsText(5, output_soils_path)

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

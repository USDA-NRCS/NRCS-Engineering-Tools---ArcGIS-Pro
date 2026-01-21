from getpass import getuser
from os import path
from sys import argv, exit
from time import ctime

from arcpy import Describe, env, Exists, GetInstallInfo, GetParameterAsText, ListFields, SetParameterAsText, SetProgressorLabel
from arcpy.analysis import Intersect, Statistics
from arcpy.da import SearchCursor, UpdateCursor
from arcpy.management import AddField, AlterField, CalculateField, Compact, DeleteField, Dissolve
from arcpy.mp import ArcGISProject

from utils import AddMsgAndPrint, emptyScratchGDB, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, input_basins):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Calculate Runoff Curve Number (WASCOB)\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tWASCOB Basins Layer: {input_basins}\n")


### Initial Tool Validation ###
try:
    aprx = ArcGISProject('CURRENT')
    map = aprx.listMaps('Engineering')[0]
except:
    AddMsgAndPrint('\nThis tool must be run from an ArcGIS Pro project template distributed with the Engineering Tools. Exiting!', 2)
    exit()

### Input Parameters ###
input_basins = GetParameterAsText(0)

### Locate Project GDB ###
basins_path = Describe(input_basins).catalogPath
basins_name = path.basename(basins_path)
if '_WASCOB.gdb' in basins_path:
    wascob_gdb = basins_path[:basins_path.find('.gdb')+4]
else:
    AddMsgAndPrint('\nThe selected WASCOB Basins layer is not from an Engineering Tools project or is not compatible with this version of the toolbox. Exiting...', 2)
    exit()

### Set Paths and Variables ###
support_dir = path.dirname(argv[0])
support_gdb = path.join(support_dir, 'Support.gdb')
scratch_gdb = path.join(support_dir, 'Scratch.gdb')
project_workspace = path.dirname(wascob_gdb)
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")
project_fd = path.join(wascob_gdb, 'Layers')
land_use_path = path.join(project_fd, f"{basins_name}_Land_Use_WASCOB")
soils_path = path.join(project_fd, f"{basins_name}_Soils_WASCOB")
output_rcn_name = f"{basins_name}_RCN_WASCOB"
output_rcn_path = path.join(project_fd, output_rcn_name)
tr_55_rcn_lookup_table = path.join(support_gdb, 'TR_55_RCN_Lookup')
basins_landuse_soils_temp = path.join(scratch_gdb, 'basins_landuse_soils')
rcn_stats_temp = path.join(scratch_gdb, 'rcn_stats')

### Validate Required Datasets Exist ###
if '_Land_Use' in input_basins or '_Soils' in input_basins:
    AddMsgAndPrint('\nInput layer appears to be either a Land Use or Soils layer, not the WASCOB Basins layer. Exiting...', 2)
    exit()
if not len(ListFields(input_basins, 'Subbasin')) > 0:
    AddMsgAndPrint('\nSubbasin field was not found in input Basins layer. Please run Prepare Soil and Land Use Layers (WASCOB) tool before running this tool. Exiting...', 2)
    exit()
if not Exists(land_use_path):
    AddMsgAndPrint('\nLand Use layer not found for input Basins layer. Please run Prepare Soil and Land Use Layers (WASCOB) tool and attribute the resulting Land Use layer before running this tool. Exiting...', 2)
    exit()
if not Exists(soils_path):
    AddMsgAndPrint('\nSoils layer not found for input Basins layer. Please run Prepare Soil and Land Use Layers (WASCOB) tool before running this tool. Exiting...', 2)
    exit()
if not Exists(tr_55_rcn_lookup_table):
    AddMsgAndPrint('\nTR_55_RCN_Lookup table was not found in Support.gdb. Exiting...', 2)
    exit()

### ESRI Environment Settings ###
env.overwriteOutput = True
env.parallelProcessingFactor = '75%'

try:
    removeMapLayers(map, [output_rcn_name])
    logBasicSettings(log_file_path, input_basins)

    ### Validate LANDUSE Field Values ###
    SetProgressorLabel('Validating LANDUSE field values...')
    AddMsgAndPrint('\nValidating LANDUSE field values...', log_file_path=log_file_path)

    expression = "LANDUSE LIKE '%not assigned%' OR LANDUSE IS NULL"
    null_landuse_values = [row[0] for row in SearchCursor(land_use_path, ['LANDUSE'], where_clause=expression)]
    if len(null_landuse_values) > 0:
        AddMsgAndPrint(f"There are {len(null_landuse_values)} NULL or un-populated values in the LANDUSE field of your Land Use layer.", 2, log_file_path)
        AddMsgAndPrint('All records must have a LANDUSE value to continue. Exiting...', 2, log_file_path)
        exit()

    ### Validate HYDGROUP Field Values ###
    SetProgressorLabel('Validating HYDGROUP field values...')
    AddMsgAndPrint('\nValidating HYDGROUP field values...')

    expression = "HYDGROUP LIKE '%/%' OR HYDGROUP IS NULL"
    null_combined_hydgroup_values = [row[0] for row in SearchCursor(soils_path, ['HYDGROUP'], where_clause=expression)]
    if len(null_combined_hydgroup_values) > 0:
        AddMsgAndPrint(f"There are {len(null_combined_hydgroup_values)} combined or un-populated classes in the HYDGROUP field of your Soils layer.", 2, log_file_path)
        AddMsgAndPrint('All records must have a single HYDGROUP class to continue. Exiting...', 2, log_file_path)
        exit()

    ### Update Fields in Basins ###
    if not len(ListFields(input_basins, 'RCN')) > 0:
        AddField(input_basins, 'RCN', 'LONG')
    if not len(ListFields(input_basins, 'Acres')) > 0:
        AddField(input_basins, 'Acres', 'DOUBLE')
    CalculateField(input_basins, 'Acres', "!shape!.getArea('PLANAR', 'ACRES')", 'PYTHON3')

    ### Intersect Basins, Land Use, Soils and Add Fields ###
    SetProgressorLabel('Intersecting Basins, Land Use, Soils layers...')
    AddMsgAndPrint('\nIntersecting Basins, Land Use, Soils layers...', log_file_path=log_file_path)

    Intersect([input_basins, land_use_path, soils_path], basins_landuse_soils_temp, 'NO_FID')

    AddField(basins_landuse_soils_temp, 'RCN_ACRES', 'DOUBLE')
    AddField(basins_landuse_soils_temp, 'WGTRCN', 'DOUBLE')

    ### RCN Lookup ###
    rcn_lookup = {}
    rcn_fields = ['LANDUSE', 'HYDGROUP', 'RCN']
    with SearchCursor(tr_55_rcn_lookup_table, rcn_fields) as cursor:
        for row in cursor:
            rcn_lookup[(row[0], row[1])] = row[2]

    with UpdateCursor(basins_landuse_soils_temp, rcn_fields) as cursor:
        for row in cursor:
            row[2] = rcn_lookup[row[0], row[1]]
            cursor.updateRow(row)

    ### RCN_ACRES and WGTRCN ###
    CalculateField(basins_landuse_soils_temp, 'RCN_ACRES', "!shape!.getArea('PLANAR', 'ACRES')", 'PYTHON3')
    CalculateField(basins_landuse_soils_temp, 'WGTRCN', '(!RCN_ACRES! / !ACRES!) * !RCN!', 'PYTHON3')
    Statistics(basins_landuse_soils_temp, rcn_stats_temp, 'WGTRCN SUM', 'Subbasin')

    ### Transfer RCN to Basins ###
    SetProgressorLabel('Updating Basins with RCN values...')
    AddMsgAndPrint('\nUpdating Basins with RCN values...', log_file_path=log_file_path)
    with UpdateCursor(input_basins, ['Subbasin','RCN']) as cursor:
        for row in cursor:
            subbasin_number = row[0]
            if subbasin_number is None or len(str(subbasin_number)) < 1:
                AddMsgAndPrint('\nOne or more Subbasins in the Basins layer are missing an ID number. Exiting...', 2, log_file_path)
                exit()
            expression = f"Subbasin = {subbasin_number}"
            rcn_value = [row[0] for row in SearchCursor(rcn_stats_temp, ['SUM_WGTRCN'], where_clause=expression)][0]
            row[1] = rcn_value
            cursor.updateRow(row)
            AddMsgAndPrint(f"\n\tSubbasin ID: {subbasin_number}", 0, log_file_path)
            AddMsgAndPrint(f"\t\tWeighted Average RCN Value: {round(rcn_value,0)}", 0, log_file_path)

    ### Finalize RCN Layer ###
    SetProgressorLabel('Creating RCN Layer...')
    AddMsgAndPrint('\nCreating RCN Layer...', log_file_path=log_file_path)

    # Dissolve by Subbasin, LANDUSE, HYDGROUP to produce RCN layer
    stats_fields = [['LANDUSE','FIRST'], ['HYDGROUP','FIRST'], ['RCN','FIRST'], ['Acres','FIRST']]
    Dissolve(basins_landuse_soils_temp, output_rcn_path, ['Subbasin', 'LANDUSE', 'HYDGROUP'], stats_fields, 'MULTI_PART', 'DISSOLVE_LINES')

    # Remove 'FIRST' from field names and aliases
    DeleteField(output_rcn_path, ['FIRST_LANDUSE','FIRST_HYDGROUP'])
    for field in ListFields(output_rcn_path):
        if field.name.startswith('FIRST'):
            AlterField(output_rcn_path, field.name, field.name[6:], field.name[6:])

    # Update Acres
    CalculateField(output_rcn_path, 'Acres', "!shape!.getArea('PLANAR', 'ACRES')", 'PYTHON3')

    ### Add Output to Map ###
    SetParameterAsText(1, output_rcn_path)

    ### Compact Project GDB ###
    try:
        SetProgressorLabel('Compacting project geodatabase...')
        AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
        Compact(wascob_gdb)
    except:
        pass

    AddMsgAndPrint('\nCalculate Runoff Curve Number (WASCOB) completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Calculate Runoff Curve Number (WASCOB)'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Calculate Runoff Curve Number (WASCOB)'), 2)

finally:
    emptyScratchGDB(scratch_gdb)

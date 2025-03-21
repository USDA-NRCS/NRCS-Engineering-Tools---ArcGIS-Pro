from getpass import getuser
from os import path
from sys import argv, exit
from time import ctime

from arcpy import Describe, env, Exists, GetInstallInfo, GetParameterAsText, ListFields, SetParameterAsText, SetProgressorLabel
from arcpy.analysis import Intersect, Statistics
from arcpy.da import SearchCursor, UpdateCursor
from arcpy.management import AddField, AddJoin, AlterField, CalculateField, Compact, DeleteField, Dissolve, GetCount, \
    MakeFeatureLayer, RemoveJoin, SelectLayerByAttribute
from arcpy.mp import ArcGISProject

from utils import AddMsgAndPrint, emptyScratchGDB, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, input_watershed):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Calculate Runoff Curve Number\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tWatershed Layer: {input_watershed}\n")


### Initial Tool Validation ###
try:
    aprx = ArcGISProject('CURRENT')
    map = aprx.listMaps('Engineering')[0]
except:
    AddMsgAndPrint('\nThis tool must be run from an ArcGIS Pro project template distributed with the Engineering Tools. Exiting!', 2)
    exit()

### Input Parameters ###
input_watershed = GetParameterAsText(0)

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
watershed_name = path.basename(watershed_path)
land_use_path = path.join(project_fd, f"{watershed_name}_Land_Use")
soils_path = path.join(project_fd, f"{watershed_name}_Soils")
output_rcn_name = f"{watershed_name}_RCN"
output_rcn_path = path.join(project_fd, output_rcn_name)
hydro_groups_lookup_table = path.join(support_gdb, 'HYD_GRP_Lookup')
tr_55_rcn_lookup_table = path.join(support_gdb, 'TR_55_RCN_Lookup')
watershed_landuse_soils_temp = path.join(scratch_gdb, 'watershed_landuse_soils')
rcn_stats_temp = path.join(scratch_gdb, 'rcn_stats')

### Validate Required Datasets Exist ###
if '_Land_Use' in input_watershed or '_Soils' in input_watershed:
    AddMsgAndPrint('\nInput layer appears to be either a Land Use or Soils layer, not the Watershed layer. Exiting...', 2)
    exit()
if not len(ListFields(input_watershed, 'Subbasin')) > 0:
    AddMsgAndPrint('\nSubbasin field was not found in input Watershed layer. Please run Prepare Soil and Land Use Layers tool before running this tool. Exiting...', 2)
    exit()
if not Exists(land_use_path):
    AddMsgAndPrint('\nLand Use layer not found for input Watershed layer. Please run Prepare Soil and Land Use Layers tool and attribute the resulting Land Use layer before running this tool. Exiting...', 2)
    exit()
if not Exists(soils_path):
    AddMsgAndPrint('\nSoils layer not found for input Watershed layer. Please run Prepare Soil and Land Use Layers tool before running this tool. Exiting...', 2)
    exit()
if not Exists(hydro_groups_lookup_table):
    AddMsgAndPrint('\nHYD_GRP_Lookup table was not found in Support.gdb. Exiting...', 2)
    exit()
if not Exists(tr_55_rcn_lookup_table):
    AddMsgAndPrint('\nTR_55_RCN_Lookup table was not found in Support.gdb. Exiting...', 2)
    exit()

### ESRI Environment Settings ###
env.overwriteOutput = True
env.parallelProcessingFactor = '75%'

try:
    removeMapLayers(map, [output_rcn_name])
    logBasicSettings(log_file_path, input_watershed)

    ### Validate LANDUSE Field Values ###
    SetProgressorLabel('Validating LANDUSE field values...')
    AddMsgAndPrint('\nValidating LANDUSE field values...', log_file_path=log_file_path)

    expression = "LANDUSE LIKE '%Select%' OR LANDUSE IS NULL"
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

    ### Update Fields in Watershed ###
    if not len(ListFields(input_watershed, 'RCN')) > 0:
        AddField(input_watershed, 'RCN', 'LONG')
    if not len(ListFields(input_watershed, 'Acres')) > 0:
        AddField(input_watershed, 'Acres', 'DOUBLE')
    CalculateField(input_watershed, 'Acres', "!shape!.getArea('PLANAR', 'ACRES')", 'PYTHON3')

    ### Intersect Watershed, Land Use, Soils and Add Fields ###
    SetProgressorLabel('Intersecting Watershed, Land Use, Soils layers...')
    AddMsgAndPrint('\nIntersecting Watershed, Land Use, Soils layers...', log_file_path=log_file_path)

    Intersect([input_watershed, land_use_path, soils_path], watershed_landuse_soils_temp, 'NO_FID')

    AddField(watershed_landuse_soils_temp, 'LUDESC', 'TEXT')
    AddField(watershed_landuse_soils_temp, 'LU_CODE', 'DOUBLE')
    AddField(watershed_landuse_soils_temp, 'HYDROL_ID', 'DOUBLE')
    AddField(watershed_landuse_soils_temp, 'HYD_CODE', 'DOUBLE')
    AddField(watershed_landuse_soils_temp, 'RCN_ACRES', 'DOUBLE')
    AddField(watershed_landuse_soils_temp, 'WGTRCN', 'DOUBLE')
    AddField(watershed_landuse_soils_temp, 'IDENT', 'TEXT')

    watershed_landuse_soils_temp_lyr = 'watershed_landuse_soils_temp_lyr'
    MakeFeatureLayer(watershed_landuse_soils_temp, watershed_landuse_soils_temp_lyr)

    ### Checks on LANDUSE and CONDITION Values ###
    SetProgressorLabel('Checking LANDUSE and CONDITION values...')
    AddMsgAndPrint('\nChecking LANDUSE and CONDITION values...', log_file_path=log_file_path)
    assumptions = 0

    # Check 1: Set CONDITION to NULL for the following LANDUSE types
    expression = "LANDUSE IN ('Fallow Bare Soil', 'Farmstead') OR LANDUSE LIKE 'Roads%' OR LANDUSE LIKE 'Paved%' OR LANDUSE LIKE '%Districts%' OR LANDUSE LIKE 'Newly Graded%' OR LANDUSE LIKE 'Surface Water%' OR LANDUSE LIKE 'Wetland%'"
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, 'NEW_SELECTION', expression)
    if int(GetCount(watershed_landuse_soils_temp_lyr).getOutput(0)) > 0:
        CalculateField(watershed_landuse_soils_temp_lyr, 'CONDITION', "''", 'PYTHON3')
        #TODO: assumptions not updated for this check?
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, 'CLEAR_SELECTION')

    # Check 2: Set CONDITION to 'Good' for all 'N/A' values
    # TODO: remove this value from CONDITION domain? Then this check is not required
    expression = "CONDITION = 'N/A'"
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, 'NEW_SELECTION', expression)
    count = int(GetCount(watershed_landuse_soils_temp_lyr).getOutput(0))
    if count > 0:
        AddMsgAndPrint(f"There were {str(count)} Land Use polygons with a CONDITION of 'N/A' that require a value of 'Poor', 'Fair', or 'Good'.", 1, log_file_path)
        AddMsgAndPrint("\tThese areas will be assigned a 'Good' CONDITION value.", 1, log_file_path)
        CalculateField(watershed_landuse_soils_temp_lyr, 'CONDITION', "'Good'", 'PYTHON3')
        assumptions += 1
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, 'CLEAR_SELECTION')

    # Check 3: Set CONDITION to 'Poor' for the following LANDUSE type: 'Open Space Grass Cover Less Than 50 Percent'
    expression = "LANDUSE = 'Open Space Grass Cover Less Than 50 Percent' AND CONDITION <> 'Poor'"
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, 'NEW_SELECTION', expression)
    count = int(GetCount(watershed_landuse_soils_temp_lyr).getOutput(0))
    if count > 0:
        AddMsgAndPrint(f"There were {str(count)} 'Open Space Grass Cover Less Than 50 Percent' polygons with a CONDITION value other than 'Poor'.", 1, log_file_path)
        AddMsgAndPrint("\tThese areas will be assigned a 'Poor' CONDITION value.", 1, log_file_path)
        CalculateField(watershed_landuse_soils_temp_lyr, "CONDITION", '"Poor"', 'PYTHON3')
        assumptions += 1
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, 'CLEAR_SELECTION')

    # Check 4: Set CONDITION to 'Fair' for the following LANDUSE type: 'Open Space Grass Cover 50 to 75 Percent'
    expression = "LANDUSE = 'Open Space Grass Cover 50 to 75 Percent' AND CONDITION <> 'Fair'"
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, 'NEW_SELECTION', expression)
    count = int(GetCount(watershed_landuse_soils_temp_lyr).getOutput(0))
    if count > 0:
        AddMsgAndPrint(f"There were {str(count)} 'Open Space Grass Cover 50 to 75 Percent' polygons with a CONDITION value other than 'Fair'.", 1, log_file_path)
        AddMsgAndPrint("\tThese areas will be assigned a 'Fair' CONDITION value.", 1, log_file_path)
        CalculateField(watershed_landuse_soils_temp_lyr, 'CONDITION', "'Fair'", 'PYTHON3')
        assumptions += 1
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, 'CLEAR_SELECTION')

    # Check 5: Set CONDITION to 'Good' for the following LANDUSE type: 'Open Space Grass Cover Greater Than 75 Percent'
    expression = "LANDUSE = 'Open Space Grass Cover Greater Than 75 Percent' AND CONDITION <> 'Good'"
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, 'NEW_SELECTION', expression)
    count = int(GetCount(watershed_landuse_soils_temp_lyr).getOutput(0))
    if count > 0:
        AddMsgAndPrint(f"There were {str(count)} 'Open Space Grass Cover Greater Than 75 Percent' polygons with a CONDITION value other than 'Good'.", 1, log_file_path)
        AddMsgAndPrint("\tThese areas will be assigned a 'Good' CONDITION value.", 1, log_file_path)
        CalculateField(watershed_landuse_soils_temp_lyr, 'CONDITION', '"Good"', 'PYTHON3')
        assumptions += 1
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, 'CLEAR_SELECTION')

    # Check 6: Set CONDITION to 'Good' for the following LANDUSE type: 'Meadow or Continuous Grass Not Grazed Generally Hayed'
    expression = "LANDUSE = 'Meadow or Continuous Grass Not Grazed Generally Hayed' AND CONDITION <> 'Good'"
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, 'NEW_SELECTION', expression)
    count = int(GetCount(watershed_landuse_soils_temp_lyr).getOutput(0))
    if count > 0:
        AddMsgAndPrint(f"There were {str(count)} 'Meadow or Continuous Grass Not Grazed Generally Hayed' polygons with a CONDITION value other than 'Good'.", 1, log_file_path)
        AddMsgAndPrint("\tThese areas will be assigned a 'Good' CONDITION value.", 1, log_file_path)
        CalculateField(watershed_landuse_soils_temp_lyr, 'CONDITION', "'Good'", 'PYTHON3')
        assumptions += 1
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, 'CLEAR_SELECTION')

    # Check 7: Set CONDITION to 'Fair' for the following LANDUSE type: 'Woods Grazed Not Burned Some Forest Litter'
    expression = "LANDUSE = 'Woods Grazed Not Burned Some Forest Litter' AND CONDITION <> 'Fair'"
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, 'NEW_SELECTION', expression)
    count = int(GetCount(watershed_landuse_soils_temp_lyr).getOutput(0))
    if count > 0:
        AddMsgAndPrint(f"There were {str(count)} 'Woods Grazed Not Burned Some Forest Litter' polygons with a CONDITION value other than 'Fair'.", 1, log_file_path)
        AddMsgAndPrint("\tThese areas will be assigned a 'Fair' CONDITION value.", 1, log_file_path)
        CalculateField(watershed_landuse_soils_temp_lyr, 'CONDITION', "'Fair'", 'PYTHON3')
        assumptions += 1
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, 'CLEAR_SELECTION')

    # Check 8: Set CONDITION to 'Good' for the following LANDUSE type: 'Woods Not Grazed Adequate Litter and Brush'
    expression = "LANDUSE = 'Woods Not Grazed Adequate Litter and Brush' AND CONDITION <> 'Good'"
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, 'NEW_SELECTION', expression)
    count = int(GetCount(watershed_landuse_soils_temp_lyr).getOutput(0))
    if count > 0:
        AddMsgAndPrint(f"There were {str(count)} 'Woods Not Grazed Adequate Litter and Brush' polygons with a CONDITION value other than 'Good'.", 1, log_file_path)
        AddMsgAndPrint("\tThese areas will be assigned a 'Good' CONDITION value.", 1, log_file_path)
        CalculateField(watershed_landuse_soils_temp_lyr, 'CONDITION', "'Good'", 'PYTHON3')
        assumptions += 1
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, 'CLEAR_SELECTION')

    # Check 9: Set CONDITION to 'Poor' for the following LANDUSE type: "Woods Heavily Grazed or Burned"
    expression = "LANDUSE = 'Woods Heavily Grazed or Burned' AND CONDITION <> 'Poor'"
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, 'NEW_SELECTION', expression)
    count = int(GetCount(watershed_landuse_soils_temp_lyr).getOutput(0))
    if count > 0:
        AddMsgAndPrint(f"There were {str(count)} 'Woods Heavily Grazed or Burned' polygons with a CONDITION value other than 'Poor'.", 1, log_file_path)
        AddMsgAndPrint("\tThese areas will be assigned a 'Poor' CONDITION value.", 1, log_file_path)
        CalculateField(watershed_landuse_soils_temp_lyr, 'CONDITION', "'Poor'", 'PYTHON3')
        assumptions += 1
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, 'CLEAR_SELECTION')

    # Check 10: Set CONDITION for the following LANDUSE types: Cropland requires 'Poor' or 'Good' condition - default to 'Good'
    expression = "LANDUSE LIKE 'Fallow Crop%' AND CONDITION = 'Fair' OR LANDUSE LIKE 'Row Crops%' AND CONDITION = 'Fair' OR LANDUSE LIKE 'Small Grain%' AND CONDITION = 'Fair' OR LANDUSE LIKE 'Close Seeded%' AND CONDITION = 'Fair'"
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, 'NEW_SELECTION', expression)
    count = int(GetCount(watershed_landuse_soils_temp_lyr).getOutput(0))
    if count > 0:
        AddMsgAndPrint(f"There were {str(count)} Cropland related polygons with a 'Fair' CONDITION value. This Land Use assumes 'Good' or 'Poor'.", 1, log_file_path)
        AddMsgAndPrint("\tThese areas will be assigned a 'Good' CONDITION value.", 1, log_file_path)
        CalculateField(watershed_landuse_soils_temp_lyr, 'CONDITION', "'Good'", 'PYTHON3')
        assumptions += 1
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, 'CLEAR_SELECTION')

    if assumptions == 0:
        AddMsgAndPrint('\nAll LANDUSE and CONDITION values populated correctly...', log_file_path=log_file_path)

    ### LUDESC - Concatenate LANDUSE and CONDITION ###
    SetProgressorLabel('Populating LUDESC field...')
    AddMsgAndPrint('\nPopulating LUDESC field...', log_file_path=log_file_path)

    expression = "CONDITION = ''"
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, 'NEW_SELECTION', expression)
    if int(GetCount(watershed_landuse_soils_temp_lyr).getOutput(0)) > 0:
        CalculateField(watershed_landuse_soils_temp_lyr, 'LUDESC', '!LANDUSE!', 'PYTHON3')

    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, 'SWITCH_SELECTION')
    CalculateField(watershed_landuse_soils_temp_lyr, 'LUDESC', '!LANDUSE!' + '" "' + '!CONDITION!', 'PYTHON3')
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, 'CLEAR_SELECTION')

    ### LU_CODE - Join to TR_55_RCN_Lookup Table ### 
    AddJoin(watershed_landuse_soils_temp_lyr, 'LUDESC', tr_55_rcn_lookup_table, 'LandUseDes', 'KEEP_ALL')
    CalculateField(watershed_landuse_soils_temp_lyr, 'watershed_landuse_soils.LU_CODE', '!TR_55_RCN_Lookup.LU_CODE!', 'PYTHON3')
    RemoveJoin(watershed_landuse_soils_temp_lyr)

    ### HYDROL_ID - Join to HYD_GRP_Lookup Table ###
    AddJoin(watershed_landuse_soils_temp_lyr, 'HYDGROUP', hydro_groups_lookup_table, 'HYDGRP', 'KEEP_ALL')
    CalculateField(watershed_landuse_soils_temp_lyr, 'watershed_landuse_soils.HYDROL_ID', '!HYD_GRP_Lookup.HYDCODE!', 'PYTHON3')
    RemoveJoin(watershed_landuse_soils_temp_lyr)

    ### HYD_CODE - Concatenate LU_CODE and HYDROL_ID ###
    CalculateField(watershed_landuse_soils_temp_lyr, 'HYD_CODE', "''.join([str(int(!LU_CODE!)),str(int(!HYDROL_ID!))])", 'PYTHON3')

    ### RCN - Join to TR_55_RCN_Lookup Table ###
    AddJoin(watershed_landuse_soils_temp_lyr, 'HYD_CODE', tr_55_rcn_lookup_table, 'HYD_CODE', 'KEEP_ALL')
    CalculateField(watershed_landuse_soils_temp_lyr, 'watershed_landuse_soils.RCN', "!TR_55_RCN_Lookup.RCN!", 'PYTHON3')
    RemoveJoin(watershed_landuse_soils_temp_lyr)

    ### RNC_ACRES and WGTRCN ###
    CalculateField(watershed_landuse_soils_temp_lyr, 'RCN_ACRES', "!shape!.getArea('PLANAR', 'ACRES')", 'PYTHON3')
    CalculateField(watershed_landuse_soils_temp_lyr, 'WGTRCN', '(!RCN_ACRES! / !ACRES!) * !RCN!', 'PYTHON3')
    Statistics(watershed_landuse_soils_temp_lyr, rcn_stats_temp, 'WGTRCN SUM', 'Subbasin')

    ### Transfer RCN to Watershed ###
    SetProgressorLabel('Updating Watershed with RCN values...')
    AddMsgAndPrint('\nUpdating Watershed with RCN values...', log_file_path=log_file_path)
    with UpdateCursor(input_watershed, ['Subbasin','RCN']) as cursor:
        for row in cursor:
            subbasin_number = row[0]
            if subbasin_number is None or len(str(subbasin_number)) < 1:
                AddMsgAndPrint('\nOne or more Subbasins in the Watershed are missing an ID number. Exiting...', 2, log_file_path)
                exit()
            expression = f"Subbasin = {subbasin_number}"
            rcn_value = [row[0] for row in SearchCursor(rcn_stats_temp, ['SUM_WGTRCN'], where_clause=expression)][0]
            row[1] = rcn_value
            cursor.updateRow(row)
            AddMsgAndPrint(f"\n\tSubbasin ID: {subbasin_number}")
            AddMsgAndPrint(f"\t\tWeighted Average RCN Value: {round(rcn_value,0)}")

    ### Finalize RCN Layer ###
    SetProgressorLabel('Creating RCN Layer...')
    AddMsgAndPrint('\nCreating RCN Layer...', log_file_path=log_file_path)

    # Create new unique ID for each Subbasin
    # exp = "''.join([str(int(!HYD_CODE!)),str(int(!Subbasin!))])"
    CalculateField(watershed_landuse_soils_temp_lyr, 'IDENT', '!HYD_CODE!!Subbasin!', 'PYTHON3')

    # Dissolve by Subbasin and HYD_CODE to produce RCN layer
    stats_fields = [['IDENT','FIRST'], ['LANDUSE','FIRST'], ['CONDITION','FIRST'], ['HYDGROUP','FIRST'], ['RCN','FIRST'], ['Acres','FIRST']]
    Dissolve(watershed_landuse_soils_temp_lyr, output_rcn_path, ['Subbasin','HYD_CODE'], stats_fields, 'MULTI_PART', 'DISSOLVE_LINES')

    # Remove 'FIRST' from field names and aliases
    for field in ListFields(output_rcn_path):
        if field.name.startswith('FIRST'):
            AlterField(output_rcn_path, field.name, field.name[6:], field.name[6:])

    # Update Acres
    CalculateField(output_rcn_path, 'Acres', "!shape!.getArea('PLANAR', 'ACRES')", 'PYTHON3')

    # Remove Unnecessary fields
    DeleteField(output_rcn_path, ['IDENT','HYD_CODE'])

    ### Add Output to Map ###
    # TODO: Check symbology and labeling, update lyrx file
    SetParameterAsText(1, output_rcn_path)

    ### Compact Project GDB ###
    try:
        SetProgressorLabel('Compacting project geodatabase...')
        AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
        Compact(project_gdb)
    except:
        pass

    AddMsgAndPrint('\nCalculate Runoff Curve Number completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Calculate Runoff Curve Number'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Calculate Runoff Curve Number'), 2)

# finally:
#     emptyScratchGDB(scratch_gdb)

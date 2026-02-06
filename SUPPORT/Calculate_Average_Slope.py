from getpass import getuser
from os import path
from sys import argv, exit
from time import ctime

from arcpy import CheckExtension, CheckOutExtension, Describe, env, Exists, GetInstallInfo, GetParameterAsText, ListFields, \
    SetParameterAsText, SetProgressorLabel
from arcpy.da import SearchCursor, UpdateCursor
from arcpy.management import AddField, CalculateField, Compact, CopyFeatures, GetCount
from arcpy.mp import ArcGISProject
from arcpy.sa import Slope, ZonalStatisticsAsTable

from utils import AddMsgAndPrint, emptyScratchGDB, errorMsg


def logBasicSettings(log_file_path, project_dem, input_polygons):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Calculate Average Slope\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tProject DEM: {project_dem}\n")
        f.write(f"\tInput Polygons: {input_polygons}\n")


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
project_dem = GetParameterAsText(0)
input_polygons = GetParameterAsText(1)
output_name = GetParameterAsText(2).replace(' ','_')

### Locate Project GDB ###
project_dem_path = Describe(project_dem).CatalogPath
if 'EngPro.gdb' in project_dem_path and 'DEM' in project_dem_path:
    project_gdb = project_dem_path[:project_dem_path.find('.gdb')+4]
else:
    AddMsgAndPrint('\nThe selected DEM is not from an Engineering Tools project or is not compatible with this version of the toolbox. Exiting...', 2)
    exit()

### Validate Input Polygons ###
if not int(GetCount(input_polygons).getOutput(0)) > 0:
    AddMsgAndPrint('\nAt least one input polygon is required. Exiting...', 2)
    exit()

### Set Paths and Variables ###
support_dir = path.dirname(argv[0])
scratch_gdb = path.join(support_dir, 'Scratch.gdb')
project_workspace = path.dirname(project_gdb)
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")
project_slope_name = f"{project_name}_Slope"
project_slope_path = path.join(project_gdb, project_slope_name)
slope_stats_temp = path.join(scratch_gdb, 'Slope_Stats')
output_slope_path = path.join(project_gdb, 'Layers', output_name)

### ESRI Environment Settings ###
env.overwriteOutput = True
env.resamplingMethod = 'BILINEAR'
env.pyramid = 'PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP'

try:
    logBasicSettings(log_file_path, project_dem, input_polygons)

    ### Create Slope Raster from DEM if Needed ###
    if not Exists(project_slope_path):
        SetProgressorLabel('Creating slope raster from project DEM...')
        AddMsgAndPrint('\nCreating slope raster from project DEM...')
        slope = Slope(project_dem, 'PERCENT_RISE', 0.3048)
        slope.save(project_slope_path)

    ### Copy Input Polygon Features and Add Fields ###
    CopyFeatures(input_polygons, output_slope_path)
    field_list = ListFields(output_slope_path)

    if 'Acres' not in field_list:
        AddField(output_slope_path, 'Acres', 'DOUBLE')
    CalculateField(output_slope_path, 'Acres', "!shape!.getArea('PLANAR', 'ACRES')", 'PYTHON3')

    if 'Avg_Slope' not in field_list:
        AddField(output_slope_path, 'Avg_Slope', 'DOUBLE')

    # Standardize possible inputs for objectID headings getting appended for cases where objectID already exists in inputs
    if 'UID' not in field_list:
        AddField(output_slope_path, 'UID', 'LONG')
    CalculateField(output_slope_path, 'UID', f"!{Describe(output_slope_path).OIDFieldName}!", 'PYTHON3')

    ### Find Average Slope in Input Polygons ###
    SetProgressorLabel('Running Zonal Statistics to find average slope...')
    AddMsgAndPrint('\nRunning Zonal Statistics to find average slope...')
    ZonalStatisticsAsTable(output_slope_path, 'UID', project_slope_path, slope_stats_temp, 'DATA')

    ### Transfer Slope Values ###
    with UpdateCursor(output_slope_path, ['UID','Avg_Slope']) as u_cursor:
        for u_row in u_cursor:
            with SearchCursor(slope_stats_temp, ['MEAN'], where_clause=f"UID={u_row[0]}") as s_cursor:
                s_row = s_cursor.next()
                avg_slope = s_row[0]
            u_row[1] = avg_slope
            u_cursor.updateRow(u_row)

    ### Add Output to Map ###
    SetParameterAsText(3, output_slope_path)

    ### Remove Digitized Layer (if present) ###
    for lyr in map.listLayers():
        if lyr.supports("NAME"):
            if 'Calculate Average Slope Select' in lyr.name:
                map.removeLayer(lyr)

    ### Compact Project GDB ###
    try:
        SetProgressorLabel('Compacting project geodatabase...')
        AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
        Compact(project_gdb)
    except:
        pass

    AddMsgAndPrint('\nCalculate Average Slope completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Calculate Average Slope'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Calculate Average Slope'), 2)

finally:
    emptyScratchGDB(scratch_gdb)

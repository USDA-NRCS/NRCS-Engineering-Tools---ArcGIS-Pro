from getpass import getuser
from os import path
from sys import argv, exit
from time import ctime

from arcpy import AddFieldDelimiters, CheckExtension, CheckOutExtension, Describe, env, Exists, GetInstallInfo, \
    GetParameterAsText, ListFields, SetProgressorLabel
from arcpy.da import SearchCursor, UpdateCursor
from arcpy.management import AddField, CalculateField, Compact
from arcpy.mp import ArcGISProject
from arcpy.sa import FocalStatistics, Slope, ZonalStatisticsAsTable

from utils import AddMsgAndPrint, emptyScratchGDB, errorMsg


def logBasicSettings(log_file_path, watershed):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Update Watershed Attributes\n')
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

### Locate Project GDB ###
watershed_path = Describe(watershed).catalogPath
if 'EngPro.gdb' in watershed_path:
    project_gdb = watershed_path[:watershed_path.find('.gdb')+4]
else:
    AddMsgAndPrint('\nThe selected Watershed layer is not from an Engineering Tools project or is not compatible with this version of the toolbox. Exiting...', 2)
    exit()

### Set Paths and Variables ###
support_dir = path.dirname(argv[0])
scratch_gdb = path.join(support_dir, 'Scratch.gdb')
project_workspace = path.dirname(project_gdb)
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")
project_fd = path.join(project_gdb, 'Layers')
project_aoi_path = path.join(project_fd, f"{project_name}_AOI")
project_dem_path = path.join(project_gdb, f"{project_name}_DEM")
smoothed_dem_path = path.join(project_gdb, f"{project_name}_Smooth_3_3")
watershed_name = path.basename(watershed_path)
flow_length_path = path.join(project_fd, f"{watershed_name}_FlowPaths")
slope_grid_temp = path.join(scratch_gdb, 'Slope_Grid')
slope_stats_temp = path.join(scratch_gdb, 'Slope_Stats')
update_flow_length = False

### Validate Required Datasets Exist ###
if not Exists(project_dem_path):
    AddMsgAndPrint('\nThe project DEM was not found. Exiting...', 2)
    exit()
if not Exists(flow_length_path):
    update_flow_length = True

### ESRI Environment Settings ###
dem_desc = Describe(project_dem_path)
env.overwriteOutput = True
env.parallelProcessingFactor = '75%'
env.extent = 'MAXOF'
env.cellSize = dem_desc.meanCellWidth
env.snapRaster = project_dem_path
env.outputCoordinateSystem = dem_desc.spatialReference
env.workspace = project_gdb
env.mask = watershed

try:
    logBasicSettings(log_file_path, watershed)

    ### Create Smoothed DEM if Needed ###
    if not Exists(smoothed_dem_path):
        SetProgressorLabel('Smoothing DEM with Focal Statistics...')
        AddMsgAndPrint('\nSmoothing DEM with Focal Statistics...')
        output_focal_stats = FocalStatistics(project_dem_path, 'RECTANGLE 3 3 CELL', 'MEAN', 'DATA')
        output_focal_stats.save(smoothed_dem_path)

    ### Update Drainage Area(s) ###
    SetProgressorLabel('Updating drainage area(s)...')
    AddMsgAndPrint('\nUpdating drainage area(s)...', log_file_path=log_file_path)
    if len(ListFields(watershed, 'Acres')) < 1:
        AddField(watershed, 'Acres', 'DOUBLE')
    CalculateField(watershed, 'Acres', "!shape!.getArea('PLANAR', 'ACRES')", 'PYTHON3')

    ### Update Flow Path Length (if present) ###
    if update_flow_length:
        SetProgressorLabel('Updating flow path length...')
        AddMsgAndPrint('\nUpdating flow path length...', log_file_path=log_file_path)
        if len(ListFields(flow_length_path,'Length_ft')) < 1:
            AddField(flow_length_path, 'Length_ft', 'DOUBLE')
        CalculateField(flow_length_path, 'Length_ft', "!shape!.getLength('PLANAR', 'FEET')", 'PYTHON3')

    ### Update Average Slope ###
    SetProgressorLabel('Updating average slope...')
    AddMsgAndPrint('\nUpdating average slope...')
    slope_grid = Slope(smoothed_dem_path, 'PERCENT_RISE', 0.3048) # Z-factor Intl Feet to Meters
    ZonalStatisticsAsTable(watershed_path, 'Subbasin', slope_grid, slope_stats_temp, 'DATA')

    # Update Watershed FC with Average Slope
    AddMsgAndPrint('\nWatershed Results:', log_file_path=log_file_path)
    AddMsgAndPrint(f"\tUser Watershed: {str(watershed_name)}", log_file_path=log_file_path)

    if len(ListFields(watershed, 'Avg_Slope')) < 1:
        AddField(watershed, 'Avg_Slope', 'DOUBLE')

    with UpdateCursor(watershed_path, ['Subbasin','Avg_Slope','Acres','SHAPE@AREA']) as cursor:
        for row in cursor:
            subbasin_number = row[0]
            where_clause = (u'{} = ' + str(subbasin_number)).format(AddFieldDelimiters(slope_stats_temp, 'Subbasin'))
            avg_slope = [row[0] for row in SearchCursor(slope_stats_temp, ['MEAN'], where_clause=where_clause)][0]
            row[1] = avg_slope
            cursor.updateRow(row)

            # Inform the user of Watershed Acres, area and avg. slope
            AddMsgAndPrint(f"\n\tSubbasin: {str(subbasin_number)}", log_file_path=log_file_path)
            AddMsgAndPrint(f"\t\tAcres: {str(round(row[2], 2))}", log_file_path=log_file_path)
            AddMsgAndPrint(f"\t\tArea: {str(round(row[3], 2))} Sq. Meters", log_file_path=log_file_path)
            AddMsgAndPrint(f"\t\tAvg. Slope: {str(round(avg_slope, 2))}", log_file_path=log_file_path)

    ### Compact Project GDB ###
    try:
        SetProgressorLabel('Compacting project geodatabase...')
        AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
        Compact(project_gdb)
    except:
        pass

    AddMsgAndPrint('\nUpdate Watershed Attributes completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Update Watershed Attributes'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Update Watershed Attributes'), 2)

finally:
    emptyScratchGDB(scratch_gdb)

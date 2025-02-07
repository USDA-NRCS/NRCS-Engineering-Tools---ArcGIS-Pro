from getpass import getuser
from os import path
from sys import argv, exit
from time import ctime

from arcpy import CheckExtension, CheckOutExtension, Describe, env, GetInstallInfo, GetParameterAsText, \
    GetParameter, SetParameterAsText, SetProgressorLabel
from arcpy.management import Compact
from arcpy.mp import ArcGISProject
from arcpy.sa import Con, Fill, FocalStatistics, Hillshade, Minus, Slope

from utils import AddMsgAndPrint, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, project_dem, create_hillshade, create_slope, create_depth_grid):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Create Hillshade, Slope, Depth Grid\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tProject DEM: {project_dem}\n")
        f.write(f"\tCreate Hillshade: {'True' if create_hillshade else 'False'}\n")
        f.write(f"\tCreate Slope: {'True' if create_slope else 'False'}\n")
        f.write(f"\tCreate Depth Grid: {'True' if create_depth_grid else 'False'}\n")


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

### ESRI Environment Settings ###
env.overwriteOutput = True
env.resamplingMethod = 'BILINEAR'
env.pyramid = 'PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP'

### Input Parameters ###
project_dem = GetParameterAsText(0)
create_hillshade = GetParameter(1)
create_slope = GetParameter(2)
create_depth_grid = GetParameter(3)

### Locate Project GDB ###
project_dem_path = Describe(project_dem).CatalogPath
if 'EngPro.gdb' in project_dem_path and 'DEM' in project_dem_path:
    project_gdb = project_dem_path[:project_dem_path.find('.gdb')+4]
else:
    AddMsgAndPrint('\nThe selected DEM is not from an Engineering Tools project or is not compatible with this version of the toolbox. Exiting...', 2)
    exit()

### Set Paths and Variables ###
support_dir = path.dirname(argv[0])
project_workspace = path.dirname(project_gdb)
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")
smoothed_dem_name = path.join(project_gdb, f"{project_name}_Smooth_3_3")
smoothed_dem_path = path.join(project_gdb, smoothed_dem_name)
hillshade_name = f"{project_name}_Hillshade"
hillshade_path = path.join(project_gdb, hillshade_name)
slope_name = f"{project_name}_Slope"
slope_path = path.join(project_gdb, slope_name)
depth_grid_name = f"{project_name}_DepthGrid"
depth_grid_path = path.join(project_gdb, depth_grid_name)
z_factor = 0.3048 # Intl Feet to Meters

try:
    remove_layers = []
    if create_hillshade: remove_layers.append(hillshade_name)
    if create_slope: remove_layers.append(slope_name)
    if create_depth_grid: remove_layers.append(depth_grid_name)
    removeMapLayers(map, remove_layers)
    logBasicSettings(log_file_path, project_dem, create_hillshade, create_slope, create_depth_grid)

    if create_hillshade:
        ### Create Hillshade ###
        SetProgressorLabel('Creating Hillshade...')
        AddMsgAndPrint('\nCreating Hillshade...', log_file_path=log_file_path)
        output_hillshade = Hillshade(project_dem, '315', '45', 'NO_SHADOWS', z_factor)
        output_hillshade.save(hillshade_path)

    if create_slope:
        ### Create Smoothed DEM (3x3) ###
        SetProgressorLabel('Smoothing DEM with Focal Statistics...')
        AddMsgAndPrint('\nSmoothing DEM with Focal Statistics...')
        output_focal_stats = FocalStatistics(project_dem, 'RECTANGLE 3 3 CELL', 'MEAN', 'DATA')
        output_focal_stats.save(smoothed_dem_path)

        ### Create Slope ###
        SetProgressorLabel('Creating Slope...')
        AddMsgAndPrint('\nCreating Slope...', log_file_path=log_file_path)
        output_slope = Slope(smoothed_dem_path, 'PERCENT_RISE', z_factor)
        output_slope.save(slope_path)

    if create_depth_grid:
        ### Create Depth Grid ###
        SetProgressorLabel('Creating Depth Grid...')
        AddMsgAndPrint('\nCreating Depth Grid...', log_file_path=log_file_path)
        output_fill = Fill(project_dem)
        output_minus = Minus(output_fill, project_dem)
        output_depth_grid = Con(output_minus, output_minus, '', 'VALUE > 0')
        output_depth_grid.save(depth_grid_path)

    ### Add Outputs to Map ###
    SetProgressorLabel('Adding outputs to map...')
    AddMsgAndPrint('\nAdding outputs to map...', log_file_path=log_file_path)
    if create_slope: SetParameterAsText(4, slope_path)
    if create_hillshade: SetParameterAsText(5, hillshade_path)
    if create_depth_grid: SetParameterAsText(6, depth_grid_path)

    ### Compact Project GDB ###
    try:
        SetProgressorLabel('Compacting project geodatabase...')
        AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
        Compact(project_gdb)
    except:
        pass

    AddMsgAndPrint('\nCreate Hillshade, Slope, Depth Grid completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Create Hillshade, Slope, Depth Grid'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Create Hillshade, Slope, Depth Grid'), 2)

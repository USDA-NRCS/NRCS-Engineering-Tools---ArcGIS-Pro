from getpass import getuser
from os import path
from sys import exit
from time import ctime

from arcpy import Describe, env, Exists, GetInstallInfo, GetParameterAsText, SetProgressorLabel
from arcpy.management import CopyFeatures, SelectLayerByAttribute
from arcpy.mp import ArcGISProject

from utils import AddMsgAndPrint, errorMsg


def logBasicSettings(log_file_path, input_basins):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Export Project Data for GPS\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tInput Basins: {input_basins}\n")


### Initial Tool Validation ###
try:
    aprx = ArcGISProject('CURRENT')
    map = aprx.listMaps('Engineering')[0]
except:
    AddMsgAndPrint('\nThis tool must be run from an ArcGIS Pro project template distributed with the Engineering Tools. Exiting...', 2)
    exit()

### Input Parameter ###
input_basins = GetParameterAsText(0)

### Locate WASCOB GDB ###
basins_path = Describe(input_basins).catalogPath
basins_name = path.basename(basins_path)
if '_WASCOB.gdb' in basins_path:
    wascob_gdb = basins_path[:basins_path.find('.gdb')+4]
else:
    AddMsgAndPrint('\nThe selected WASCOB Basins layer is not from an Engineering Tools project or is not compatible with this version of the toolbox. Exiting...', 2)
    exit()

### Set Paths and Variables ###
project_workspace = path.dirname(wascob_gdb)
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")
output_dir = path.join(project_workspace, 'GIS_Output')
wascob_fd = path.join(wascob_gdb, 'Layers')
embankments_name = f"{basins_name}_Embankments"
embankments_path = path.join(wascob_fd, embankments_name)
stakeout_points_name = 'Stakeout_Points'
stakeout_points_path = path.join(wascob_fd, stakeout_points_name)
station_points_name = 'Station_Points'
station_points_path = path.join(wascob_fd, station_points_name)
ridge_station_points_name = 'Ridge_Station_Points'
ridge_station_points_path = path.join(wascob_fd, ridge_station_points_name)
tile_lines_name = 'Tile_Lines'
tile_lines_path = path.join(wascob_fd, tile_lines_name)
ridge_lines_name = 'Ridge_Lines'
ridge_lines_path = path.join(wascob_fd, ridge_lines_name)

# Shapefile Outputs
embankments_output = path.join(output_dir, 'Embankments.shp')
stakeout_points_output = path.join(output_dir, 'StakeoutPoints.shp')
stations_output = path.join(output_dir, 'StationPoints.shp')
ridge_stations_output = path.join(output_dir, 'RidgeStationPoints.shp')
tile_line_output = path.join(output_dir, 'TileLines.shp')
ridge_line_output = path.join(output_dir, 'RidgeLines.shp')

### ESRI Environment Settings ###
env.parallelProcessingFactor = '75%'
env.overwriteOutput = True

try:
    logBasicSettings(log_file_path, input_basins)

    ### Clear Selections from Layers ###
    SetProgressorLabel('Clearing any selections from layers...')
    AddMsgAndPrint('\nClearing any selections from layers...', log_file_path=log_file_path)

    if Exists(embankments_name):
        SelectLayerByAttribute(embankments_name, 'CLEAR_SELECTION')
    if Exists(stakeout_points_path):
        SelectLayerByAttribute(stakeout_points_path, 'CLEAR_SELECTION')
    if Exists(station_points_name):
        SelectLayerByAttribute(station_points_name, 'CLEAR_SELECTION')
    if Exists(ridge_station_points_name):
        SelectLayerByAttribute(ridge_station_points_name, 'CLEAR_SELECTION')
    if Exists(tile_lines_name):
        SelectLayerByAttribute(tile_lines_name, 'CLEAR_SELECTION')
    if Exists(ridge_lines_name):
        SelectLayerByAttribute(ridge_lines_name, 'CLEAR_SELECTION')

    ### Export Layers to Shapefiles ###
    SetProgressorLabel('Exporting layers to shapefiles...')
    AddMsgAndPrint('\nExporting layers to shapefiles...', log_file_path=log_file_path)

    if Exists(embankments_path):
        CopyFeatures(embankments_path, embankments_output)
    else:
        AddMsgAndPrint('\nUnable to find Embankments in project workspace. Copy failed. Export them manually.', log_file_path, 1)

    if Exists(stakeout_points_path):
        CopyFeatures(stakeout_points_path, stations_output)
    else:
        AddMsgAndPrint('\nUnable to find Stakeout Points in project workspace. Copy failed. Export them manually.', log_file_path, 1)

    if Exists(station_points_path):
        CopyFeatures(station_points_path, stakeout_points_output)
    else:
        AddMsgAndPrint('\nUnable to find Station Points in project workspace. Copy failed. Export them manually.', log_file_path, 1)

    if Exists(ridge_station_points_path):
        CopyFeatures(ridge_station_points_path, ridge_stations_output)
    else:
        AddMsgAndPrint('\nUnable to find Ridge Station Points in project workspace. Copy failed. Export them manually.', log_file_path, 1)

    if Exists(tile_lines_path):
        CopyFeatures(tile_lines_path, tile_line_output)
    else:
        AddMsgAndPrint('\nUnable to find Tile Lines in project workspace. Copy failed. Export them manually.', log_file_path, 1)

    if Exists(ridge_lines_path):
        CopyFeatures(ridge_lines_path, ridge_line_output)
    else:
        AddMsgAndPrint('\nUnable to find Ridge Lines in project workspace. Copy failed. Export them manually.', log_file_path, 1)

    AddMsgAndPrint('\nData was exported using the coordinate system of your project or DEM data.')
    AddMsgAndPrint('\nIf this coordinate system is not suitable for use with your GPS system, please use the Project (Data Management) tool.')

    AddMsgAndPrint('\nExport Project Data for GPS completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Export Project Data for GPS'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Export Project Data for GPS'), 2)

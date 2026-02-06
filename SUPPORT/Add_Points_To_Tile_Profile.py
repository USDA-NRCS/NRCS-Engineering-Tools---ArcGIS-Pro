from getpass import getuser
from os import path
from sys import argv, exit
from time import ctime

from arcpy import CheckExtension, CheckOutExtension, Describe, env, Exists, GetInstallInfo, GetParameterAsText, \
    ListFields, SetParameterAsText, SetProgressorLabel
from arcpy.analysis import Buffer, GenerateNearTable
from arcpy.conversion import TableToTable
from arcpy.da import SearchCursor, UpdateCursor
from arcpy.lr import CreateRoutes, MakeRouteEventLayer
from arcpy.management import AddField, AddJoin, AddXY, Append, CalculateField, Compact, CopyFeatures, CopyRows, \
    DeleteField, GetCount, MakeFeatureLayer, RemoveJoin, Sort
from arcpy.mp import ArcGISProject
from arcpy.sa import ZonalStatisticsAsTable

from utils import AddMsgAndPrint, deleteESRIAddedFields, emptyScratchGDB, errorMsg


def logBasicSettings(log_file_path, station_points):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Add Points To Tile Profile\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tStation Points Layer: {station_points}\n")


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
station_points = GetParameterAsText(0)
input_points = GetParameterAsText(1)

### Validate Number of Input Points Digitized ###
points_count = int(GetCount(input_points).getOutput(0))
if points_count < 1:
    AddMsgAndPrint('\nAdd least one station point is required to run this tool. Exiting...', 2)
    exit()

### Locate Project GDB ###
stations_path = Describe(station_points).catalogPath
if '_WASCOB.gdb' in stations_path and '_Station_Points' in stations_path:
    wascob_gdb = stations_path[:stations_path.find('.gdb')+4]
    basins_name = path.basename(stations_path).replace('_Station_Points','')
else:
    AddMsgAndPrint('\nThe selected Station Points layer is not from an Engineering Tools project or is not compatible with this version of the toolbox. Exiting...', 2)
    exit()

### Set Paths and Variables ###
support_dir = path.dirname(argv[0])
scratch_gdb = path.join(support_dir, 'Scratch.gdb')
project_workspace = path.dirname(wascob_gdb)
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")
wascob_dem_path = path.join(wascob_gdb, f"{project_name}_DEM_WASCOB")
wascob_fd = path.join(wascob_gdb, 'Layers')
station_points_name = f"{basins_name}_Station_Points"
tile_lines_path = path.join(wascob_fd, f"{basins_name}_Tile_Lines")
tables_dir = path.join(project_workspace, 'GIS_Output', 'Tables')
stations_dbf = path.join(tables_dir, f"{basins_name}_Stations.dbf")
stations_lyr = 'Stations_Lyr'
stations_lyr_2 = 'Stations_Lyr_2'
stations_temp = path.join(scratch_gdb, 'Stations_Temp')
stations_temp_2 = path.join(scratch_gdb, 'Stations_Temp_2')
station_table_temp = path.join(scratch_gdb, 'Station_Table_Temp')
lines_near = path.join(scratch_gdb, 'Lines_Near')
points_near = path.join(scratch_gdb, 'Points_Near')
routes_temp = path.join(scratch_gdb, 'Routes_Temp')
events_temp = path.join(scratch_gdb, 'Events_Temp')
buffer_temp = path.join(scratch_gdb, 'Buffer_Temp')
station_stats_temp = path.join(scratch_gdb, 'Station_Stats_Temp')

### Validate Required Datasets Exist ###
if not Exists(wascob_dem_path):
    AddMsgAndPrint('\nThe WASCOB project DEM was not found. Exiting...', 2)
    exit()
if not Exists(tile_lines_path):
    AddMsgAndPrint('\nThe Tile Lines for the input Station Points layer was not found. Exiting...', 2)
    exit()

### DEM Properties ###
dem_desc = Describe(wascob_dem_path)
dem_cell_size = dem_desc.meanCellWidth
z_factor = 1

### ESRI Environment Settings ###
env.resamplingMethod = 'BILINEAR'
env.pyramid = 'PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP'
env.parallelProcessingFactor = '75%'
env.overwriteOutput = True

try:
    logBasicSettings(log_file_path, station_points)

    # Copy points input and add fields if not present
    CopyFeatures(input_points, stations_temp)
    field_list = [field.name for field in ListFields(stations_temp)]
    if 'ID' not in field_list:
        AddField(stations_temp, 'ID', 'LONG')
    if 'STATION' not in field_list:
        AddField(stations_temp, 'STATION', 'LONG')
    if 'POINT_X' not in field_list:
        AddField(stations_temp, 'POINT_X', 'DOUBLE')
    if 'POINT_Y' not in field_list:
        AddField(stations_temp, 'POINT_Y', 'DOUBLE')
    if 'POINT_Z' not in field_list:
        AddField(stations_temp, 'POINT_Z', 'DOUBLE')

    # Find nearest Tile Line
    SetProgressorLabel('Finding nearest tile lines to input points...')
    AddMsgAndPrint('\nFinding nearest tile lines to input points...', log_file_path=log_file_path)
    GenerateNearTable(stations_temp, tile_lines_path, lines_near, '', 'NO_LOCATION', 'NO_ANGLE', 'ALL', '1')

    with SearchCursor(lines_near, ['OID@','NEAR_FID']) as cursor:
        for row in cursor:
            pointID = row[0]
            tileID = row[1]

            with UpdateCursor(stations_temp, ['ID'], where_clause=f"OBJECTID={pointID}") as cursor:
                for row2 in cursor:
                    row2[0] = tileID
                    cursor.updateRow(row2)

    # Find Distance from point "0" along each tile line
    SetProgressorLabel('Calculating station distances...')
    AddMsgAndPrint('\nCalculating station distances...', log_file_path=log_file_path)

    MakeFeatureLayer(station_points, stations_lyr, 'STATION=0')
    GenerateNearTable(stations_temp, stations_lyr, points_near, '', 'NO_LOCATION', 'NO_ANGLE', 'ALL', '1')

    # Calculate stations in new points
    with SearchCursor(points_near, ['OID@', 'NEAR_DIST']) as cursor:
        for row in cursor:
            pointID = row[0]
            distance = row[1]
            station = int(distance * 3.280839896) # XY in Meters

            with UpdateCursor(stations_temp, ['STATION'], where_clause=f"OBJECTID={pointID}") as cursor:
                for row2 in cursor:
                    row2[0] = station
                    cursor.updateRow(row2)

    # Append to existing stations and copy to temp table
    Append(stations_temp, station_points, 'NO_TEST')
    CopyRows(station_points, station_table_temp)

    SetProgressorLabel('Creating new stations along tile line...')
    AddMsgAndPrint('\nCreating new stations along tile line...', log_file_path=log_file_path)
    CreateRoutes(tile_lines_path, 'ID', routes_temp, 'TWO_FIELDS', 'FROM_PT', 'LENGTH_FT', 'UPPER_LEFT', '1', '0', 'IGNORE', 'INDEX')

    MakeRouteEventLayer(routes_temp, 'ID', station_table_temp, 'ID POINT STATION', events_temp, '', 'NO_ERROR_FIELD', 'NO_ANGLE_FIELD', 'NORMAL', 'ANGLE', 'LEFT', 'POINT')
    AddField(events_temp, 'STATIONID', 'TEXT', field_length='25')
    CalculateField(events_temp, 'STATIONID', "str(!STATION!) + '_' + str(!ID!)", 'PYTHON3')

    CopyFeatures(events_temp, stations_temp_2)

    AddXY(stations_temp_2)
    AddField(stations_temp_2, 'POINT_Z', 'DOUBLE')

    MakeFeatureLayer(stations_temp_2, stations_lyr_2)

    # Retrieve Elevation values
    SetProgressorLabel('Retrieving station elevations...')
    AddMsgAndPrint('\nRetrieving station elevations...', log_file_path=log_file_path)

    Buffer(stations_temp_2, buffer_temp, f"{dem_cell_size} Meters", 'FULL', 'ROUND', 'NONE')

    ZonalStatisticsAsTable(buffer_temp, 'STATIONID', wascob_dem_path, station_stats_temp, 'NODATA', 'ALL')

    AddJoin(stations_lyr_2, 'StationID', station_stats_temp, 'StationID', 'KEEP_ALL')

    expression = f"round(!station_stats_temp.MEAN! * {z_factor},1)"
    CalculateField(stations_lyr_2, 'POINT_Z', expression, 'PYTHON3')

    RemoveJoin(stations_lyr_2, 'station_stats_temp')
    DeleteField(stations_temp_2, 'STATIONID; POINT_M')

    # Copy Station Points
    Sort(stations_temp_2, stations_path, [['ID', 'ASCENDING'],['STATION', 'ASCENDING']])
    DeleteField(stations_path, 'ORIG_FID')

    ### Delete Fields Added if Digitized ###
    deleteESRIAddedFields(stations_path)

    # Copy output to tables folder
    TableToTable(stations_path, tables_dir, f"{basins_name}_Stations.dbf")

    ### Remove Digitized Layer (if present) ###
    for lyr in map.listLayers():
        if lyr.supports("NAME"):
            if 'Add Points To Tile Profile' in lyr.name:
                map.removeLayer(lyr)

    ### Add Output to Map ###
    SetParameterAsText(2, stations_path)

    ### Compact Project GDB ###
    try:
        SetProgressorLabel('Compacting project geodatabase...')
        AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
        Compact(wascob_gdb)
    except:
        pass

    AddMsgAndPrint('\nAdd Points To Tile Profile completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Add Points To Tile Profile'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Add Points To Tile Profile'), 2)

finally:
    emptyScratchGDB(scratch_gdb)

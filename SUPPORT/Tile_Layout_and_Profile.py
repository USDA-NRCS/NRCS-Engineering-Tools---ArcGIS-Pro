from getpass import getuser
from os import path
from sys import argv, exit
from time import ctime

from arcpy import CheckExtension, CheckOutExtension, Describe, env, Exists, GetInstallInfo, GetParameterAsText, \
    ListFields, SetParameterAsText, SetProgressorLabel
from arcpy.analysis import Buffer
from arcpy.conversion import TableToTable
from arcpy.da import InsertCursor, UpdateCursor
from arcpy.ddd import InterpolateShape
from arcpy.lr import CreateRoutes, MakeRouteEventLayer
from arcpy.management import AddField, AddJoin, AddXY, CalculateField, Compact, CopyFeatures, CreateTable, \
    DeleteField, GetCount, MakeFeatureLayer, RemoveJoin, Sort
from arcpy.mp import ArcGISProject
from arcpy.sa import ZonalStatisticsAsTable

from utils import AddMsgAndPrint, deleteESRIAddedFields, emptyScratchGDB, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, input_basins, interval):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Tile Layout and Profile\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tWASCOB Basins Layer: {input_basins}\n")
        f.write(f"\tStation Interval (ft): {interval}\n")


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
if CheckExtension('3d') == 'Available':
    CheckOutExtension('3d')
else:
    AddMsgAndPrint('\n3D Analyst Extension not enabled. Please enable 3D Analyst from Project, Licensing, Configure licensing options. Exiting...', 2)
    exit()

### Input Parameters ###
input_basins = GetParameterAsText(0)
input_line = GetParameterAsText(1)
interval = GetParameterAsText(2)

### Locate Project GDB ###
basins_path = Describe(input_basins).catalogPath
basins_name = path.basename(basins_path)
if '_WASCOB.gdb' in basins_path:
    wascob_gdb = basins_path[:basins_path.find('.gdb')+4]
else:
    AddMsgAndPrint('\nThe selected WASCOB Basins layer is not from an Engineering Tools project or is not compatible with this version of the toolbox. Exiting...', 2)
    exit()

### Validate Input Interval ###
try:
    interval = float(interval)
except:
    AddMsgAndPrint('\nInvalid station interval. Exiting...', 2)
    exit()

### Set Paths and Variables ###
support_dir = path.dirname(argv[0])
scratch_gdb = path.join(support_dir, 'Scratch.gdb')
project_workspace = path.dirname(wascob_gdb)
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")
wascob_dem_path = path.join(wascob_gdb, f"{project_name}_DEM_WASCOB")
wascob_fd = path.join(wascob_gdb, 'Layers')
stakeout_points_path = path.join(wascob_fd, f"{basins_name}_Stakeout_Points")
tables_dir = path.join(project_workspace, 'GIS_Output', 'Tables')
output_lines_name = f"{basins_name}_Tile_Lines"
output_lines_path = path.join(wascob_fd, output_lines_name)
output_stations_name = f"{basins_name}_Station_Points"
output_stations_path = path.join(wascob_fd, output_stations_name)
stations_lyr = 'Stations_Lyr'
station_stats_temp = path.join(scratch_gdb, 'Station_Stats_Temp')
stations_temp = path.join(scratch_gdb, 'Stations_Temp')
line_temp = path.join(scratch_gdb, 'Line_Temp')
routes_temp = path.join(scratch_gdb, 'Routes_Temp')
events_temp = path.join(scratch_gdb, 'Events_Temp')
buffer_temp = path.join(scratch_gdb, 'Buffer_Temp')

### Validate Required Datasets Exist ###
if not Exists(wascob_dem_path):
    AddMsgAndPrint('\nThe WASCOB project DEM was not found. Exiting...', 2)
    exit()
if not Exists(stakeout_points_path):
    AddMsgAndPrint('\nThe Stakeout Points layer was not found. Exiting...', 2)
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
    removeMapLayers(map, [output_lines_name, output_stations_name])
    logBasicSettings(log_file_path, input_basins, interval)

    # Copy line input and add fields if not present
    CopyFeatures(input_line, line_temp)
    field_list = [field.name for field in ListFields(line_temp)]
    if 'ID' not in field_list:
        AddField(line_temp, 'ID', 'LONG')
    if 'NO_STATIONS' not in field_list:
        AddField(line_temp, 'NO_STATIONS', 'LONG')
    if 'FROM_PT' not in field_list:
        AddField(line_temp, 'FROM_PT', 'LONG')
    if 'LENGTH_FT' not in field_list:
        AddField(line_temp, 'LENGTH_FT', 'DOUBLE')

    CalculateField(line_temp, 'ID', '!OBJECTID!', 'PYTHON3')
    CalculateField(line_temp, 'LENGTH_FT', "!shape!.getLength('PLANAR', 'FeetInt')", 'PYTHON3')

    # Create Table to hold station values
    station_table = 'in_memory\station_table'
    CreateTable('in_memory', 'station_table')
    AddField(station_table, 'ID', 'LONG')
    AddField(station_table, 'STATION', 'LONG')
    AddField(station_table, 'POINT_X', 'DOUBLE')
    AddField(station_table, 'POINT_Y', 'DOUBLE')
    AddField(station_table, 'POINT_Z', 'DOUBLE')

    # Calculate number of stations / remainder
    SetProgressorLabel('Calculating number of stations...')
    AddMsgAndPrint('\nCalculating number of stations...', log_file_path=log_file_path)
    AddMsgAndPrint(f"\tStation Point interval: {interval} Feet", log_file_path=log_file_path)

    with UpdateCursor(line_temp,['ID','NO_STATIONS','FROM_PT','LENGTH_FT']) as cursor:
        for row in cursor:
            if row[3] < interval:
                AddMsgAndPrint(f"\nThe length of line {row[0]} is less than the specified interval of {interval} ft. Use a smaller interval or a longer line. Exiting...", 2, log_file_path)
                exit()

            remainder = row[3] % interval
            if remainder == 0:
                number_of_stations = row[3] / interval
                equidistant_stations = number_of_stations
            else:
                number_of_stations = (row[3] // interval) + 2
                equidistant_stations = number_of_stations - 1

            row[1] = number_of_stations
            row[2] = 0
            cursor.updateRow(row)

            AddMsgAndPrint(f"\tLine ID {row[0]} Total Length: {row[3]} Feet", log_file_path=log_file_path)
            AddMsgAndPrint(f"\tEquidistant Stations (Including Station 0): {equidistant_stations}", log_file_path=log_file_path)

            if remainder > 0:
                AddMsgAndPrint(f"\tPlus 1 covering the remaining {remainder} Feet", log_file_path=log_file_path)

            insertCursor = InsertCursor(station_table, ['ID','STATION'])
            insertCursor.insertRow((row[0], int(row[3])))

            currentStation = 0
            while currentStation < (row[1]-1):
                insertCursor.insertRow((row[0], currentStation*interval))
                currentStation += 1
            del insertCursor

    # Create Route(s) lyr and define events along each route
    SetProgressorLabel('Creating stations...')
    AddMsgAndPrint('\nCreating stations...', log_file_path=log_file_path)
    CreateRoutes(line_temp, 'ID', routes_temp, 'TWO_FIELDS', 'FROM_PT', 'LENGTH_FT', 'UPPER_LEFT', '1', '0', 'IGNORE', 'INDEX')

    MakeRouteEventLayer(routes_temp, 'ID', station_table, 'ID POINT STATION', events_temp, '', 'NO_ERROR_FIELD', 'NO_ANGLE_FIELD', 'NORMAL', 'ANGLE', 'LEFT', 'POINT')
    AddField(events_temp, 'STATIONID', 'TEXT', field_length='25')
    CalculateField(events_temp, 'STATIONID', "str(!STATION!) + '_' + str(!ID!)", 'PYTHON3')

    CopyFeatures(events_temp, stations_temp)

    AddXY(stations_temp)
    AddField(stations_temp, 'POINT_Z', 'DOUBLE')

    MakeFeatureLayer(stations_temp, stations_lyr)
    AddMsgAndPrint(f"\nCreated a total of {GetCount(stations_lyr)[0]} stations for the {GetCount(line_temp)[0]} provided line(s)...", log_file_path=log_file_path)

    # Retrieve Elevation values
    SetProgressorLabel('Retrieving station elevations...')
    AddMsgAndPrint('\nRetrieving station elevations...', log_file_path=log_file_path)

    Buffer(stations_temp, buffer_temp, f"{dem_cell_size} Meters", 'FULL', 'ROUND', 'NONE')

    ZonalStatisticsAsTable(buffer_temp, 'STATIONID', wascob_dem_path, station_stats_temp, 'NODATA', 'ALL')

    AddJoin(stations_lyr, 'StationID', station_stats_temp, 'StationID', 'KEEP_ALL')

    expression = f"round(!station_stats_temp.MEAN! * {z_factor},1)"
    CalculateField(stations_lyr, 'POINT_Z', expression, 'PYTHON3')

    RemoveJoin(stations_lyr, 'station_stats_temp')
    DeleteField(stations_temp, 'STATIONID; POINT_M')

    # Interpolate Line to 3d via Z factor
    InterpolateShape(wascob_dem_path, line_temp, output_lines_path, '', z_factor)

    # Copy Station Points
    Sort(stations_temp, output_stations_path, [['ID', 'ASCENDING'],['STATION', 'ASCENDING']])
    DeleteField(output_stations_path, 'ORIG_FID')

    ### Delete Fields Added if Digitized ###
    deleteESRIAddedFields(output_lines_path)

    # Copy output to tables folder
    TableToTable(output_stations_path, tables_dir, f"{basins_name}_Stations.dbf")
    TableToTable(stakeout_points_path, tables_dir, f"{basins_name}_Stakeout_Points.dbf")

    ### Remove Digitized Layer (if present) ###
    for lyr in map.listLayers():
        if lyr.supports("NAME"):
            if '09. Tile Layout and Profile' in lyr.name:
                map.removeLayer(lyr)

    ### Add Output to Map ###
    SetParameterAsText(3, output_lines_path)
    SetParameterAsText(4, output_stations_path)

    ### Compact Project GDB ###
    try:
        SetProgressorLabel('Compacting project geodatabase...')
        AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
        Compact(wascob_gdb)
    except:
        pass

    AddMsgAndPrint('\nTile Layout and Profile completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Tile Layout and Profile'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Tile Layout and Profile'), 2)

finally:
    emptyScratchGDB(scratch_gdb)

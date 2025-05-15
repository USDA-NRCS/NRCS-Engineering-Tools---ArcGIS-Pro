from getpass import getuser
from os import path
from sys import argv, exit
from time import ctime

from arcpy import CheckExtension, CheckOutExtension, Describe, env, Exists, GetInstallInfo, GetParameter, \
    GetParameterAsText, ListFields, SetParameterAsText, SetProgressorLabel
from arcpy.analysis import Buffer
from arcpy.da import InsertCursor, SearchCursor, UpdateCursor
from arcpy.ddd import InterpolateShape
from arcpy.lr import CreateRoutes, MakeRouteEventLayer
from arcpy.management import AddField, AddJoin, AddXY, CalculateField, Compact, CopyFeatures, CreateTable, \
    Delete, DeleteField, GetCount, MakeFeatureLayer, RemoveJoin, Sort
from arcpy.mp import ArcGISProject
from arcpy.sa import ZonalStatisticsAsTable

from utils import AddMsgAndPrint, removeMapLayers


def logBasicSettings(log_file_path, project_dem, interval, output_text):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Create Cross Section Profiles\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tProject DEM: {project_dem}\n")
        f.write(f"\tInterval: {interval}\n")
        f.write(f"\tCreate text file: {output_text}\n")


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
project_dem = GetParameterAsText(0)
input_line = GetParameterAsText(1)
interval = GetParameterAsText(2)
output_text = GetParameter(3)

### Locate Project GDB ###
dem_desc = Describe(project_dem)
dem_cell_size = dem_desc.meanCellWidth
project_dem_path = dem_desc.CatalogPath
if 'EngPro.gdb' in project_dem_path and 'DEM' in project_dem_path:
    project_gdb = project_dem_path[:project_dem_path.find('.gdb')+4]
else:
    AddMsgAndPrint('\nThe selected DEM is not from an Engineering Tools project or is not compatible with this version of the toolbox. Exiting...', 2)
    exit()

### Validate Station Interval ###
try:
    interval = float(interval)
except:
    AddMsgAndPrint('\nInvalid station interval. Exiting...', 2)
    exit()

### Set Paths and Variables ###
support_dir = path.dirname(argv[0])
scratch_gdb = path.join(support_dir, 'Scratch.gdb')
project_workspace = path.dirname(project_gdb)
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")
project_fd = path.join(project_gdb, 'Layers')
station_elev_temp = path.join(scratch_gdb, 'station_elev')
station_table_temp = path.join(scratch_gdb, 'station_table')
line_temp = path.join(scratch_gdb, 'line_temp')
routes_temp = path.join(scratch_gdb, 'routes')
events_temp = path.join(scratch_gdb, 'station_events')
buffer_temp = path.join(scratch_gdb, 'station_buffer')
output_line_name = f"{project_name}_XYZ_line"
output_line_path = path.join(project_fd, output_line_name)
output_points_name = f"{project_name}_XYZ_points"
output_points_path = path.join(project_fd, output_points_name)
output_text_file = path.join(project_workspace, f"{project_name}_XYZ_line.txt")
stations_lyr_name = 'stations'

### ESRI Environment Settings ###
env.resamplingMethod = 'BILINEAR'
env.pyramid = 'PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP'
env.parallelProcessingFactor = '75%'
env.overwriteOutput = True

logBasicSettings(log_file_path, project_dem, interval, output_text)

#TODO: confirm with Chris is we can overwrite output here and not name unique
# Must Have a unique name for output -- Append a unique digit to output if required
# x = 1
# y = 0
# while x > 0:
#     if Exists(outLine):
#         outLine = watershedFD + sep + projectName + "_XYZ_line" + str(x)
#         x += 1
#         y += 1
#     else:
#         x = 0
# if y > 0:
#     outPoints = watershedFD + sep + projectName + "_XYZ_points" + str(y)
#     outTxt = userWorkspace + sep + projectName + "_XYZ_line" + str(y) + ".txt"
# else:
#     outPoints = watershedFD + sep + projectName + "_XYZ_points"
#     outTxt = userWorkspace + sep + projectName + "_XYZ_line.txt"
# outLineLyr = path.basename(outLine)
# outPointsLyr = path.basename(outPoints)

try:
    if interval < float(dem_cell_size):
        AddMsgAndPrint(f"\nThe interval specified is less than the DEM cell size {dem_cell_size}. Please use a higher interval value. Exiting...", 2)
        exit()
except:
    AddMsgAndPrint('\nThere may be an issue with the DEM cell size. Exiting...', 2)
    exit()

# zUnits will determine Zfactor for the conversion of elevation values to a profile in feet
#TODO: I dont think this original logic is correct here
z_factor = 0.3048
# if zUnits == "Meters":
#     Zfactor = 3.280839896
# elif zUnits == "Centimeters":
#     Zfactor = 0.03280839896
# elif zUnits == "Inches":
#     Zfactor = 0.0833333
# else:
#     Zfactor = 1

#TODO: why copy input lines here?
# Copy the input line before deleting the TOC layer reference in case input line IS the previous line selected from the TOC
CopyFeatures(input_line, line_temp)

# Delete previous toc lyrs if present
removeMapLayers(map, [output_line_name, output_points_name])

# Copy input and create routes / points
# Check for fields: if user input is previous line they will already exist
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
CreateTable(scratch_gdb, 'station_table')
AddField(station_table_temp, 'ID', 'LONG')
AddField(station_table_temp, 'STATION', 'LONG')
AddField(station_table_temp, 'POINT_X', 'DOUBLE')
AddField(station_table_temp, 'POINT_Y', 'DOUBLE')
AddField(station_table_temp, 'POINT_Z', 'DOUBLE')

# Calculate number of stations / remainder
AddMsgAndPrint('\nCalculating number of stations...')
AddMsgAndPrint(f"\tStation Point interval: {interval} Feet")

with UpdateCursor(line_temp, ['ID','NO_STATIONS','FROM_PT','LENGTH_FT']) as u_cursor:
    for row in u_cursor:
        if row[3] < interval:
            AddMsgAndPrint(f"\nThe length of line {row[0]} is less than the specified interval of {interval} ft. Use a smaller interval or a longer line. Exiting...", 2)
            exit()

        exp = row[3] / interval - 0.5 + 1
        row[1] = round(exp)
        row[2] = 0
        u_cursor.updateRow(row)

        AddMsgAndPrint(f"\tLine ID {row[0]} Total Length: {row[3]} Feet")
        AddMsgAndPrint(f"\tEquidistant stations (Including Station 0): {row[1]}")

        remainder = (round(exp) * interval) - row[3]
        if remainder > 0:
            AddMsgAndPrint(f"\tPlus 1 covering the remaining {remainder} Feet")

        i_cursor = InsertCursor(station_table_temp, ['ID','STATION'])
        i_cursor.insertRow((row[0],int(row[3])))

        currentStation = 0
        while currentStation < row[1]:
            i_cursor.insertRow((row[0], currentStation*interval))
            currentStation+=1
        del i_cursor

# Create Route(s) lyr and define events along each route
AddMsgAndPrint('\nCreating stations...')
CreateRoutes(line_temp, 'ID', routes_temp, 'TWO_FIELDS', 'FROM_PT', 'LENGTH_FT', 'UPPER_LEFT', '1', '0', 'IGNORE', 'INDEX')

MakeRouteEventLayer(routes_temp, 'ID', station_table_temp, 'ID POINT STATION', events_temp, '', 'NO_ERROR_FIELD', 'NO_ANGLE_FIELD', 'NORMAL', 'ANGLE', 'LEFT', 'POINT')
AddField(events_temp, 'STATIONID', 'TEXT', field_length='25')
CalculateField(events_temp, 'STATIONID', "str(!STATION!) + '_' + str(!ID!)", 'PYTHON3')

# Should this next sort actually be done with STATIONID, instead of STATION?
stationTemp = path.join(scratch_gdb, 'stations')
Sort(events_temp, stationTemp, [['STATION', 'ASCENDING']])

AddXY(stationTemp)
AddField(stationTemp, 'POINT_Z', 'DOUBLE')

MakeFeatureLayer(stationTemp, stations_lyr_name)
AddMsgAndPrint(f"\nCreated a total of {GetCount(stations_lyr_name)[0]} stations for the {GetCount(line_temp)[0]} provided line(s)...")

# Retrieve Elevation values
AddMsgAndPrint('\nRetrieving station elevations...')

Buffer(stationTemp, buffer_temp, f"{dem_cell_size} Meters", 'FULL', 'ROUND', 'NONE', '')

ZonalStatisticsAsTable(buffer_temp, 'STATIONID', project_dem, station_elev_temp, 'NODATA', 'ALL')

AddJoin(stations_lyr_name, 'StationID', station_elev_temp, 'StationID', 'KEEP_ALL')

expression = f"round(!station_elev_temp.MEAN! * {z_factor},1)"
CalculateField(stations_lyr_name, 'stations.POINT_Z', expression, 'PYTHON3')

RemoveJoin(stations_lyr_name)
DeleteField(stationTemp, 'STATIONID; POINT_M')

# Interpolate Line to 3d via Z factor
InterpolateShape(project_dem, line_temp, output_line_path, '', z_factor)

# Copy Station Points
CopyFeatures(stationTemp, output_points_path)

# Create Txt file if selected and write attributes of station points
if output_text:
    AddMsgAndPrint('\nCreating output text file...')

    with open(output_text_file, 'w') as f:
        f.write('ID, STATION, X, Y, Z')

        with SearchCursor(output_points_path, ['ID','STATION','POINT_X','POINT_Y','POINT_Z'], sql_clause=(None,'ORDER BY STATION')) as cursor:
            for row in cursor:
                f.write(f"{row[0]},{row[1]},{row[2]},{row[3]},{row[4]}\n")

SetParameterAsText(4, output_line_path)
SetParameterAsText(5, output_points_path)

Compact(project_gdb)

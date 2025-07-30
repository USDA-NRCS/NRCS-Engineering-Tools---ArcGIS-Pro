from getpass import getuser
from os import path
from sys import argv, exit
from time import ctime

from arcpy import CheckExtension, CheckOutExtension, Describe, env, Exists, GetInstallInfo, GetParameter, \
    GetParameterAsText, SetParameterAsText, SetProgressorLabel
from arcpy.da import InsertCursor, SearchCursor
from arcpy.ddd import AddSurfaceInformation
from arcpy.management import AddXY, CalculateField, Compact, CopyFeatures, CreateFolder, DeleteField, Project
from arcpy.mp import ArcGISProject

from utils import AddMsgAndPrint, emptyScratchGDB, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, input_points, input_dem, elevation_units, output_sr, transformation, output_text):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Change Point Coordinates\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tInput Profile Points: {input_points}\n")
        f.write(f"\tInput DEM: {input_dem}\n")
        f.write(f"\tElevation Units: {elevation_units}\n")
        f.write(f"\tOutput Coordinate System: {output_sr}\n")
        f.write(f"\tTransformation: {transformation}\n")
        f.write(f"\tCreate Text File: {output_text}\n")


### Initial Tool Validation ###
try:
    aprx = ArcGISProject('CURRENT')
    map = aprx.listMaps('Engineering')[0]
except:
    AddMsgAndPrint('\nThis tool must be run from an ArcGIS Pro project template distributed with the Engineering Tools. Exiting!', 2)
    exit()

if CheckExtension('3d') == 'Available':
    CheckOutExtension('3d')
else:
    AddMsgAndPrint('\n3D Analyst Extension not enabled. Please enable 3D Analyst from Project, Licensing, Configure licensing options. Exiting...', 2)
    exit()

### Input Parameters ###
input_points = GetParameterAsText(0)
input_dem = GetParameterAsText(1)
elevation_units = GetParameterAsText(2)
output_sr = GetParameterAsText(4)
transformation = GetParameterAsText(5)
output_text = GetParameter(6)

### Locate Project GDB ###
points_path = Describe(input_points).catalogPath
dem_desc = Describe(input_dem)
dem_path = dem_desc.catalogPath
if ('_EngPro.gdb' in points_path and '_EngPro.gdb' in dem_path) or ('_WASCOB.gdb' in points_path and '_WASCOB.gdb' in dem_path):
    project_gdb = points_path[:points_path.find('.gdb')+4]
elif ('_EngPro.gdb' in points_path and '_WASCOB.gdb' in dem_path) or ('_WASCOB.gdb' in points_path and '_EngPro.gdb' in dem_path):
    AddMsgAndPrint('\nThe Profile Points and DEM must be in the same project geodatabase. Exiting...', 2)
    exit()
else:
    AddMsgAndPrint('\nThe Profile Points layer is not from an Engineering Tools project or is not compatible with this version of the toolbox. Exiting...', 2)
    exit()

### Set Paths and Variables ###
support_dir = path.dirname(argv[0])
scratch_gdb = path.join(support_dir, 'Scratch.gdb')
project_workspace = path.dirname(project_gdb)
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")
gis_output_dir = path.join(project_workspace, 'GIS_Output')
output_points_name = f"{project_name}_XYZ_Projected"
output_points_path = path.join(project_gdb, output_points_name)
output_points_shp = path.join(gis_output_dir, f"{output_points_name}.shp")
output_text_file = path.join(project_workspace, f"{output_points_name}.txt")
points_temp = path.join(scratch_gdb, 'Points_Temp')

# Append a unique digit to output if required
x = 0
while Exists(output_points_path):
    x += 1
    output_points_path = f"{output_points_path}_{x}"

if x > 0:
    output_points_name = f"{output_points_name}_{x}"
    output_points_path = path.join(project_gdb, output_points_name)
    output_points_shp = path.join(gis_output_dir, f"{output_points_name}.shp")
    output_text_file = path.join(project_workspace, f"{output_points_name}.txt")

### ESRI Environment Settings ###
env.resamplingMethod = 'BILINEAR'
env.pyramid = 'PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP'
env.parallelProcessingFactor = '75%'
env.overwriteOutput = True

# Set z-factor based on XYZ units of DEM
z_factor = 1
dem_xy_units = dem_desc.spatialReference.linearUnitName
if dem_xy_units in ['Foot', 'Foot_US']:
    xy_units = 'Feet'
    if elevation_units == 'Meters':
        z_factor = 3.28084
elif dem_xy_units == 'Meter':
    xy_units = 'Meters'
    if elevation_units in ['International Feet', 'US Survey Feet']:
        z_factor = 0.3048
else:
    AddMsgAndPrint('\nLinear units of the input DEM are not supported. Exiting...', 2)
    exit()

try:
    # removeMapLayers(map, [])
    logBasicSettings(log_file_path, input_points, input_dem, elevation_units, output_sr, transformation, output_text)

    ### Create GIS_Output Folder ###
    if not Exists(gis_output_dir):
        SetProgressorLabel('Creating GIS_Output folder...')
        AddMsgAndPrint('\nCreating GIS_Output folder...', log_file_path=log_file_path)
        CreateFolder(project_workspace, 'GIS_Output')

    ### Project Input Points ###
    if transformation:
        Project(input_points, points_temp, output_sr, transformation)
    else:
        Project(input_points, points_temp, output_sr)

    ### Update XY Values ###
    AddXY(points_temp)

    ### Update Z Values ###
    AddSurfaceInformation(points_temp, input_dem, 'Z', '', '', z_factor)
    CalculateField(points_temp, 'POINT_Z', 'round(!Z!,1)', 'PYTHON3')
    DeleteField(points_temp, 'POINT_M')
    DeleteField(points_temp, 'Z')

    ### Save Output as Feature Class and Shapefile ###
    CopyFeatures(points_temp, output_points_path)
    CopyFeatures(points_temp, output_points_shp)

    ### Create Text File ###
    if output_text:
        SetProgressorLabel('Creating output text file...')
        AddMsgAndPrint('\nCreating output text file...', log_file_path=log_file_path)

        with open(output_text_file, 'w') as f:
            f.write('ID, STATION, X, Y, Z')

            with SearchCursor(output_points_path, ['ID','STATION','POINT_X','POINT_Y','POINT_Z'], sql_clause=(None,'ORDER BY STATION')) as cursor:
                for row in cursor:
                    f.write(f"{row[0]},{row[1]},{row[2]},{row[3]},{row[4]}\n")

    ### Add Outputs to Map ###
    SetParameterAsText(7, output_points_path)

    ### Compact Project GDB ###
    try:
        SetProgressorLabel('Compacting project geodatabase...')
        AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
        Compact(project_gdb)
    except:
        pass

    AddMsgAndPrint('\nChange Point Coordinates completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Change Point Coordinates'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Change Point Coordinates'), 2)

finally:
    emptyScratchGDB(scratch_gdb)

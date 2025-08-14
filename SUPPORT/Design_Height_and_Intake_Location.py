from getpass import getuser
from os import path
from sys import argv, exit
from time import ctime

from arcpy import CheckExtension, CheckOutExtension, Describe, env, Exists, GetInstallInfo, GetParameterAsText, \
    SetParameterAsText, SetProgressorLabel
from arcpy.analysis import Clip
from arcpy.conversion import RasterToPolygon
from arcpy.management import AddField, AddXY, Append, CalculateField, CreateFeatureclass, Compact, CopyFeatures, \
    DeleteFeatures, FeatureVerticesToPoints, GetCount, MakeFeatureLayer, SelectLayerByAttribute
from arcpy.mp import ArcGISProject
from arcpy.sa import ExtractByMask, Int, SetNull, Times

from utils import AddMsgAndPrint, emptyScratchGDB, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, input_basins, subbasin_number, design_elevation, intake_elevation):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Design Height and Intake Location\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tWASCOB Basins Layer: {input_basins}\n")
        f.write(f"\tSubbasin Number: {subbasin_number}\n")
        f.write(f"\tDesign Elevation: {design_elevation}\n")
        f.write(f"\tIntake Elevation: {intake_elevation}\n")


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
input_basins = GetParameterAsText(0)
subbasin_number = GetParameterAsText(1)
design_elevation = GetParameterAsText(2)
intake_elevation = GetParameterAsText(3)
intake_location = GetParameterAsText(4)

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
scratch_gdb = path.join(support_dir, 'Scratch.gdb')
project_workspace = path.dirname(wascob_gdb)
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")
wascob_dem_path = path.join(wascob_gdb, f"{project_name}_DEM_WASCOB")
wascob_fd = path.join(wascob_gdb, 'Layers')
embankments_name = f"{basins_name}_Embankments"
embankments_path = path.join(wascob_fd, embankments_name)
embankments_lyr = f"{embankments_name}_Lyr"
stakeout_points_name = f"{basins_name}_Stakeout_Points"
stakeout_points_path = path.join(wascob_fd, stakeout_points_name)
stakeout_points_lyr = f"{stakeout_points_name}_Lyr"
intake_point_temp = path.join(scratch_gdb, 'intake_temp')
dem_polygon_temp = path.join(scratch_gdb, 'dem_poly_temp')
embankment_points_temp = path.join(scratch_gdb, 'embankment_points_temp')
embankment_clip_temp = path.join(scratch_gdb, 'embankment_clip_temp')

### Validate Required Datasets Exist ###
if not Exists(wascob_dem_path):
    AddMsgAndPrint('\nThe WASCOB project DEM was not found. Exiting...', 2)
    exit()
if not Exists(embankments_path):
    AddMsgAndPrint('\nThe WASCOB Embankments layer was not found. Exiting...', 2)
    exit()

### Validate Number of Intake Locations ###
intake_count = int(GetCount(intake_location).getOutput(0))
if intake_count == 0:
    AddMsgAndPrint('\nOne intake location point is required to run this tool. Exiting...', 2)
    exit()
if intake_count > 1:
    AddMsgAndPrint('\nMore than one intake location found. This tool must be run with one intake location per subbasin. Exiting...', 2)
    exit()

### ESRI Environment Settings ###
env.resamplingMethod = 'BILINEAR'
env.pyramid = 'PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP'
env.parallelProcessingFactor = '75%'
env.overwriteOutput = True

try:
    removeMapLayers(map, [stakeout_points_name])
    logBasicSettings(log_file_path, input_basins, subbasin_number, design_elevation, intake_elevation)

    ### Validate Embankment Exists for Subbasin ###
    where_clause = f"Subbasin = {subbasin_number}"
    MakeFeatureLayer(embankments_path, embankments_lyr, where_clause)
    if not int(GetCount(embankments_lyr).getOutput(0)) > 0:
        AddMsgAndPrint(f"\nNo embankment found for subbasin {subbasin_number}. Exiting...", 2, log_file_path)
        exit()

    ### Create Stakeout Points Feature Class ###
    if not Exists(stakeout_points_path):
        SetProgressorLabel('Creating Stakeout Points feature class...')
        AddMsgAndPrint('\nCreating Stakeout Points feature class...', log_file_path=log_file_path)
        CreateFeatureclass(wascob_fd, stakeout_points_name, 'POINT', '', 'DISABLED', 'DISABLED', '', '', '0', '0', '0')
        AddField(stakeout_points_path, 'ID', 'LONG')
        AddField(stakeout_points_path, 'Subbasin', 'LONG')
        AddField(stakeout_points_path, 'Elev', 'DOUBLE')
        AddField(stakeout_points_path, 'Notes', 'TEXT', field_length='50')

    ### Delete Stakeout Points Record for Subbain if Exists ###
    MakeFeatureLayer(stakeout_points_path, stakeout_points_lyr, where_clause)
    if int(GetCount(stakeout_points_lyr).getOutput(0)) > 0:
        DeleteFeatures(stakeout_points_lyr)
    SelectLayerByAttribute(stakeout_points_lyr, 'CLEAR_SELECTION')

    ### Create Temp Intake Point and Append to Stakeout Points ###
    SetProgressorLabel('Updating Intake Location fields...')
    AddMsgAndPrint('\nUpdating Intake Location fields...', log_file_path=log_file_path)

    CopyFeatures(intake_location, intake_point_temp)
    AddField(intake_point_temp, 'ID', 'LONG')
    AddField(intake_point_temp, 'Subbasin', 'LONG')
    AddField(intake_point_temp, 'Elev', 'DOUBLE')
    AddField(intake_point_temp, 'Notes', 'TEXT', field_length='50')

    CalculateField(intake_point_temp, 'ID', subbasin_number, 'PYTHON3')
    CalculateField(intake_point_temp, 'Subbasin', subbasin_number, 'PYTHON3')
    CalculateField(intake_point_temp, 'Elev', intake_elevation, 'PYTHON3')
    CalculateField(intake_point_temp, 'Notes', "'Intake'", 'PYTHON3')

    SetProgressorLabel('Apending Intake Location to Stakeout Points...')
    AddMsgAndPrint('\nApending Intake Location to Stakeout Points...', log_file_path=log_file_path)
    Append(intake_point_temp, stakeout_points_path, 'NO_TEST')

    ### Intersect Embankment with Plane at Design Elevation ###
    MakeFeatureLayer(input_basins, 'subbasin_lyr', where_clause)
    subbasin_dem = ExtractByMask(wascob_dem_path, 'subbasin_lyr')
    dem_setnull = SetNull(subbasin_dem, subbasin_dem, f"VALUE > {design_elevation}")
    dem_times_0 = Times(dem_setnull, 0)
    dem_int = Int(dem_times_0)
    RasterToPolygon(dem_int, dem_polygon_temp, 'NO_SIMPLIFY', 'VALUE')

    ### Create Points from Embankment Vertices ###
    SetProgressorLabel('Creating points along Embankment at design elevation...')
    AddMsgAndPrint('\nCreating points along Embankment at design elevation...', log_file_path=log_file_path)
    Clip(embankments_lyr, dem_polygon_temp, embankment_clip_temp)

    FeatureVerticesToPoints(embankment_clip_temp, embankment_points_temp, 'BOTH_ENDS')

    AddField(embankment_points_temp, 'ID', 'LONG')
    AddField(embankment_points_temp, 'Elev', 'DOUBLE')
    AddField(embankment_points_temp, 'Notes', 'TEXT', field_length=50)

    CalculateField(embankment_points_temp, 'ID', subbasin_number, 'PYTHON3')
    CalculateField(embankment_points_temp, 'Elev', design_elevation, 'PYTHON3')
    CalculateField(embankment_points_temp, 'Notes', "'Embankment'", 'PYTHON3')

    SetProgressorLabel('Appending Embankment Points to Stakeout Points...')
    AddMsgAndPrint('\nAppending Embankment Points to Stakeout Points...', log_file_path=log_file_path)
    Append(embankment_points_temp, stakeout_points_path, 'NO_TEST')

    SetProgressorLabel('Adding XY Coordinates to Stakeout Points...')
    AddMsgAndPrint('\nAdding XY Coordinates to Stakeout Points...', log_file_path=log_file_path)
    AddXY(stakeout_points_path)

    ### Remove Digitized Layer (if present) ###
    for lyr in map.listLayers():
        if '08. Design Height' in lyr.name:
            map.removeLayer(lyr)

    ### Add Output to Map ###
    SetParameterAsText(5, stakeout_points_path)

    ### Compact Project GDB ###
    try:
        SetProgressorLabel('Compacting project geodatabase...')
        AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
        Compact(wascob_gdb)
    except:
        pass

    AddMsgAndPrint('\nDesign Height and Intake Location completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Design Height and Intake Location'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Design Height and Intake Location'), 2)

finally:
    emptyScratchGDB(scratch_gdb)

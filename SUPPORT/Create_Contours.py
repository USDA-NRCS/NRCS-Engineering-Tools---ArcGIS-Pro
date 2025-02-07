from getpass import getuser
from os import path
from sys import argv
from time import ctime

from arcpy import CheckExtension, CheckOutExtension, Describe, env, Exists, GetInstallInfo, GetParameterAsText, \
    SetParameterAsText, SetProgressorLabel
from arcpy.management import AddField, CalculateField, Compact, CopyFeatures, DeleteField, MakeFeatureLayer, \
    SelectLayerByAttribute
from arcpy.mp import ArcGISProject
from arcpy.sa import Contour, FocalStatistics

from utils import AddMsgAndPrint, emptyScratchGDB, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, project_workspace, project_dem, contour_interval):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Create Contours\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tProject Workspace: {project_workspace}\n")
        f.write(f"\tProject DEM: {project_dem}\n")
        f.write(f"\tContour Interval: {contour_interval}\n")


### Initial Tool Validation ###
try:
    aprx = ArcGISProject('CURRENT')
    map = aprx.listMaps('Engineering')[0]
except:
    AddMsgAndPrint('This tool must be run from an ArcGIS Pro project that was developed from the template distributed with this toolbox. Exiting!', 2)
    exit()

if CheckExtension('Spatial') == 'Available':
    CheckOutExtension('Spatial')
else:
    AddMsgAndPrint('Spatial Analyst Extension not enabled. Please enable Spatial Analyst from Project, Licensing, Configure licensing options. Exiting...', 2)
    exit()

### ESRI Environment Settings ###
env.overwriteOutput = True
env.resamplingMethod = 'BILINEAR'
env.pyramid = 'PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP'

### Input Parameters ###
project_dem = GetParameterAsText(0)
contour_interval = GetParameterAsText(1)

### Locate Project GDB ###
project_dem_path = Describe(project_dem).CatalogPath
if 'EngPro.gdb' in project_dem_path and 'DEM' in project_dem_path:
    project_gdb = project_dem_path[:project_dem_path.find('.gdb')+4]
else:
    AddMsgAndPrint('\nThe selected DEM is not from an Engineering Tools project or is not compatible with this version of the toolbox. Exiting...', 2)
    exit()

### Validate Contour Interval (1 - 1000) ###
if not 0 < float(contour_interval) <= 1000:
    AddMsgAndPrint('\nThe contour interval must be between 1 and 1000. Exiting...', 2)
    exit()

### Set Paths and Variables ###
support_dir = path.dirname(argv[0])
scratch_gdb = path.join(support_dir, 'Scratch.gdb')
project_workspace = path.dirname(project_gdb)
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")
smoothed_dem_path = path.join(project_gdb, f"{project_name}_Smooth_3_3")
temp_contour_path = path.join(scratch_gdb, 'temp_contour')
contour_name = f"{project_name}_Contour_{contour_interval.replace('.','_dot_')}"
contour_path = path.join(project_gdb, 'Layers', contour_name)

try:
    emptyScratchGDB(scratch_gdb)
    removeMapLayers(map, [contour_name])
    logBasicSettings(log_file_path, project_workspace, project_dem, contour_interval)

    ### Create Smoothed DEM if Needed ###
    if not Exists(smoothed_dem_path):
        SetProgressorLabel('Smoothing DEM with Focal Statistics...')
        AddMsgAndPrint('\nSmoothing DEM with Focal Statistics...')
        output_focal_stats = FocalStatistics(project_dem, 'RECTANGLE 3 3 CELL', 'MEAN', 'DATA')
        output_focal_stats.save(smoothed_dem_path)

    ### Create Contours ###
    SetProgressorLabel('Creating temporary Contours layer...')
    AddMsgAndPrint('\nCreating temporary Contours layer...', log_file_path=log_file_path)
    Contour(smoothed_dem_path, temp_contour_path, contour_interval)

    ### Add Index Field ###
    SetProgressorLabel('Updating fields in temporary Contours layer...')
    AddMsgAndPrint('\nUpdating fields in temporary Contours layer...', log_file_path=log_file_path)
    DeleteField(temp_contour_path, 'Id')
    AddField(temp_contour_path, 'Index', 'DOUBLE')

    ### Update Every 5th Index to 1 ###
    SetProgressorLabel('Updating contour index field...')
    AddMsgAndPrint('\nUpdating contour index field...', log_file_path=log_file_path)
    MakeFeatureLayer(temp_contour_path, 'contour_lyr')
    expression = "MOD( \"CONTOUR\"," + str(float(contour_interval) * 5) + ") = 0"
    SelectLayerByAttribute('contour_lyr', 'NEW_SELECTION', expression)
    CalculateField('contour_lyr', 'Index', 1, 'PYTHON3')

    ### Update All Other Indexes to 0 ###
    SelectLayerByAttribute('contour_lyr', 'SWITCH_SELECTION')
    CalculateField('contour_lyr', 'Index', 0, 'PYTHON3')

    ### Copy Final Contour Output ###
    SetProgressorLabel('Finalizing Contour output...')
    AddMsgAndPrint('\nFinalizing Contour output...', log_file_path=log_file_path)
    SelectLayerByAttribute('contour_lyr', 'CLEAR_SELECTION')
    CopyFeatures('contour_lyr', contour_path)

    ### Add Output to Map ###
    AddMsgAndPrint('\nAdding Contours to map...', log_file_path=log_file_path)
    SetProgressorLabel('Adding Contours to map...')
    SetParameterAsText(2, contour_path)

    ### Compact Project GDB ###
    try:
        SetProgressorLabel('Compacting project geodatabase...')
        AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
        Compact(project_gdb)
    except:
        pass

    AddMsgAndPrint('\nCreate Contours completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Create Contours'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Create Contours'), 2)

finally:
    emptyScratchGDB(scratch_gdb)

from getpass import getuser
from os import path, startfile
from shutil import copyfile
from sys import argv, exit
from time import ctime

from arcpy import Describe, env, Exists, GetInstallInfo, GetParameterAsText, ListFields, SetParameterAsText, SetProgressorLabel
from arcpy.conversion import TableToTable
from arcpy.da import SearchCursor
from arcpy.management import AddField, Compact, CreateFeatureclass, CreateFolder
from arcpy.mp import ArcGISProject

from utils import AddMsgAndPrint, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, input_watershed):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Design Worksheet\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tInput Watershed: {input_watershed}\n")


### Initial Tool Validation ###
try:
    aprx = ArcGISProject('CURRENT')
    map = aprx.listMaps('Engineering')[0]
except:
    AddMsgAndPrint('\nThis tool must be run from an ArcGIS Pro project template distributed with the Engineering Tools. Exiting!', 2)
    exit()

### Input Parameters ###
input_watershed = GetParameterAsText(0)

### Locate Project GDB ###
watershed_path = Describe(input_watershed).catalogPath
if 'EngPro.gdb' in watershed_path:
    project_gdb = watershed_path[:watershed_path.find('.gdb')+4]
else:
    AddMsgAndPrint('\nThe selected Watershed layer is not from an Engineering Tools project or is not compatible with this version of the toolbox. Exiting...', 2)
    exit()

### Set Paths and Variables ###
support_dir = path.dirname(argv[0])
project_workspace = path.dirname(project_gdb)
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")
project_fd = path.join(project_gdb, 'Layers')
watershed_name = path.basename(watershed_path)
rcn_path = path.join(project_fd, f"{watershed_name}_RCN")
output_points_name = 'Stakeout_Points'
output_points_path = path.join(project_fd, output_points_name)
template_worksheet = path.join(support_dir, 'LiDAR_WASCOB.xlsm')
documents_dir = path.join(project_workspace, 'Documents')
output_dir = path.join(project_workspace, 'GIS_Output')
tables_dir = path.join(output_dir, 'Tables')

### Validate Required Datasets Exist ###
if '_Land_Use' in input_watershed or '_Soils' in input_watershed or '_RCN' in input_watershed:
    AddMsgAndPrint('\nInput layer appears to be either a Land Use, Soils, or RCN layer, not the Watershed layer. Exiting...', 2)
    exit()
if 'Subbasin' not in [field.name for field in ListFields(input_watershed)]:
    AddMsgAndPrint()
    exit()
if not Exists(rcn_path):
    AddMsgAndPrint('\nCould not locate the RCN layer for the specified Watershed. Please run tool B.02.02 Calculate Runoff Curve Number and try this tool again. Exiting...', 2)
    exit()
if 'RCN' not in [field.name for field in ListFields(rcn_path)]:
    AddMsgAndPrint('\nRCN field not found in input Watershed layer. Please run tool B.02.02 Calculate Runoff Curve Number and try this tool again. Exiting...', 2)
    exit()
if not Exists(template_worksheet):
    AddMsgAndPrint('\nLiDAR_WASCOB.xlsm Worksheet template not found in SUPPORT folder. Exiting...', 2)
    exit()

### ESRI Environment Settings ###
env.resamplingMethod = 'BILINEAR'
env.pyramid = 'PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP'
env.parallelProcessingFactor = '75%'
env.overwriteOutput = True

try:
    removeMapLayers(map, [output_points_name])
    logBasicSettings(log_file_path, input_watershed)

    ### Validate RCN Field ###
    null_values = [row[0] for row in SearchCursor(rcn_path, ['RCN'], 'RCN IS NULL')]
    if len(null_values) > 0:
        AddMsgAndPrint('\nRCN field in input Watershed contains NULL values. Please run tool B.02.02 Calculate Runoff Curve Number or manually correct RCN values. Exiting...', 2, log_file_path)
        exit()

    ### Create Output Folders ###
    if not Exists(output_dir):
        SetProgressorLabel('Creating GIS_Output folder...')
        AddMsgAndPrint('\nCreating GIS_Output folder...', log_file_path=log_file_path)
        CreateFolder(project_workspace, 'GIS_Output')
    if not Exists(tables_dir):
        SetProgressorLabel('Creating Tables folder...')
        AddMsgAndPrint('\nCreating Tables folder...', log_file_path=log_file_path)
        CreateFolder(output_dir, 'Tables')
    if not Exists(documents_dir):
        SetProgressorLabel('Creating Documents folder...')
        AddMsgAndPrint('\nCreating Documents folder...', log_file_path=log_file_path)
        CreateFolder(project_workspace, 'Documents')

    ### Create Tables from Input Watershed and RCN ###
    SetProgressorLabel('\nCreating Watershed and RCN tables...')
    AddMsgAndPrint('\nCreating Watershed and RCN tables...', log_file_path=log_file_path)
    TableToTable(input_watershed, tables_dir, 'Watershed.dbf')
    TableToTable(rcn_path, tables_dir, 'RCNsummary.dbf')

    ### Create WASCOB Worksheet ###
    #TODO: Does naming here need to be unique?
    SetProgressorLabel('Creating WASCOB Worksheet...')
    AddMsgAndPrint('\nCreating WASCOB Worksheet...', log_file_path=log_file_path)
    output_worksheet = path.join(documents_dir, f"{project_name}_WASCOB.xlsm")
    x = 1
    while x > 0:
        if Exists(output_worksheet):
            output_worksheet = path.join(documents_dir, f"{project_name}_WASCOB_{x}.xlsm")
            x += 1
        else:
            x = 0
    copyfile(template_worksheet, output_worksheet)

    ### Create Stakeout Points Feature Class ###
    #TODO: Should this check for existence or always create new/overwrite?
    if not Exists(output_points_path):
        SetProgressorLabel('Creating Stakeout points feature class...')
        AddMsgAndPrint('\nCreating Stakeout points feature class...', log_file_path=log_file_path)
        CreateFeatureclass(project_fd, output_points_name, 'POINT', '', 'DISABLED', 'DISABLED', '', '', '0', '0', '0')
        AddField(output_points_path, 'ID', 'LONG')
        AddField(output_points_path, 'Subbasin', 'LONG')
        AddField(output_points_path, 'Elev', 'DOUBLE')
        AddField(output_points_path, 'Notes', 'TEXT', field_length='50')

    ### Launch WASCOB Worksheet ###
    AddMsgAndPrint(f"\nThe LiDAR_WASCOB worksheet was saved to {documents_dir}. If Excel does not open automatically, navigate to it and open manually. \
                   Once Excel is open, enable macros (if not already enabled), and set the path to your project folder to import your gis data. \
                   Once you have completed the Wascob Design Sheet(s) you can return to Pro and complete Design Height and Tile Layout steps.", log_file_path=log_file_path)
    try:
        startfile(output_worksheet)
    except:
        AddMsgAndPrint('\nExcel failed to open. Please try opening the worksheet manually.', 1, log_file_path)

    ### Add Output to Map ###
    SetParameterAsText(1, output_points_path)

    ### Compact Project GDB ###
    try:
        SetProgressorLabel('Compacting project geodatabase...')
        AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
        Compact(project_gdb)
    except:
        pass

    AddMsgAndPrint('\nDesign Worksheet completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Design Worksheet'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Design Worksheet'), 2)

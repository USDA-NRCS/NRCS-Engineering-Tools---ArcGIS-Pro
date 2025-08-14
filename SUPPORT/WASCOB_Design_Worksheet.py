from getpass import getuser
from os import path, startfile
from shutil import copyfile
from sys import argv, exit
from time import ctime

from arcpy import Describe, env, Exists, GetInstallInfo, GetParameterAsText, ListFields, SetProgressorLabel
from arcpy.conversion import TableToTable
from arcpy.da import SearchCursor
from arcpy.mp import ArcGISProject

from utils import AddMsgAndPrint, errorMsg


def logBasicSettings(log_file_path, input_basins):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: WASCOB Design Worksheet\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tWASCOB Basins Layer: {input_basins}\n")


### Initial Tool Validation ###
try:
    aprx = ArcGISProject('CURRENT')
    map = aprx.listMaps('Engineering')[0]
except:
    AddMsgAndPrint('\nThis tool must be run from an ArcGIS Pro project template distributed with the Engineering Tools. Exiting!', 2)
    exit()

### Input Parameters ###
input_basins = GetParameterAsText(0)

### Locate Project GDB ###
basins_path = Describe(input_basins).catalogPath
if '_WASCOB.gdb' in basins_path:
    wascob_gdb = basins_path[:basins_path.find('.gdb')+4]
else:
    AddMsgAndPrint('\nThe selected WASCOB Basins layer is not from an Engineering Tools project or is not compatible with this version of the toolbox. Exiting...', 2)
    exit()

### Set Paths and Variables ###
support_dir = path.dirname(argv[0])
project_workspace = path.dirname(wascob_gdb)
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")
wascob_fd = path.join(wascob_gdb, 'Layers')
basins_name = path.basename(basins_path)
rcn_path = path.join(wascob_fd, f"{basins_name}_RCN_WASCOB")
template_worksheet = path.join(support_dir, 'LiDAR_WASCOB.xlsm')
documents_dir = path.join(project_workspace, 'Documents')
output_dir = path.join(project_workspace, 'GIS_Output')
tables_dir = path.join(output_dir, 'Tables')

### Validate Required Datasets Exist ###
if '_Land_Use' in input_basins or '_Soils' in input_basins or '_RCN' in input_basins:
    AddMsgAndPrint('\nInput layer appears to be either a Land Use, Soils, or RCN layer, not the WASCOB Basins layer. Exiting...', 2)
    exit()
if 'Subbasin' not in [field.name for field in ListFields(input_basins)]:
    AddMsgAndPrint()
    exit()
if not Exists(rcn_path):
    AddMsgAndPrint('\nCould not locate the RCN layer for the specified Basins. Please run tool Calculate Runoff Curve Number (WASCOB) and try this tool again. Exiting...', 2)
    exit()
if 'RCN' not in [field.name for field in ListFields(rcn_path)]:
    AddMsgAndPrint('\nRCN field not found in input Basins layer. Please run tool Calculate Runoff Curve Number (WASCOB) and try this tool again. Exiting...', 2)
    exit()
if not Exists(template_worksheet):
    AddMsgAndPrint('\nLiDAR_WASCOB.xlsm Worksheet template not found in SUPPORT folder. Exiting...', 2)
    exit()

### ESRI Environment Settings ###
env.overwriteOutput = True

try:
    logBasicSettings(log_file_path, input_basins)

    ### Validate RCN Field ###
    null_values = [row[0] for row in SearchCursor(rcn_path, ['RCN'], 'RCN IS NULL')]
    if len(null_values) > 0:
        AddMsgAndPrint('\nRCN field in input Basins contains NULL values. Please run tool Calculate Runoff Curve Number (WASCOB) or manually correct RCN values. Exiting...', 2, log_file_path)
        exit()

    ### Create Tables from Input Basins and RCN ###
    SetProgressorLabel('\nCreating Basins and RCN tables...')
    AddMsgAndPrint('\nCreating Basins and RCN tables...', log_file_path=log_file_path)
    TableToTable(input_basins, tables_dir, 'WASCOB_Basins.dbf')
    TableToTable(rcn_path, tables_dir, 'RCN_Summary.dbf')

    ### Create WASCOB Worksheet ###
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

    ### Launch WASCOB Worksheet ###
    AddMsgAndPrint(f"\nThe LiDAR_WASCOB worksheet was saved to {documents_dir}. If Excel does not open automatically, navigate to it and open manually. \
                   Once Excel is open, enable macros (if not already enabled), and set the path to your project folder to import your gis data. \
                   Once you have completed the Wascob Design Sheet(s) you can return to Pro and complete Design Height and Tile Layout steps.", log_file_path=log_file_path)
    try:
        startfile(output_worksheet)
    except:
        AddMsgAndPrint('\nExcel failed to open. Please try opening the worksheet manually.', 1, log_file_path)

    AddMsgAndPrint('\nWASCOB Design Worksheet completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('WASCOB Design Worksheet'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('WASCOB Design Worksheet'), 2)

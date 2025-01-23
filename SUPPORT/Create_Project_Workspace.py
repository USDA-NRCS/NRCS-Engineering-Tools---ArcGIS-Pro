from getpass import getuser
from os import mkdir, path
from sys import exit
from time import ctime

from arcpy import Exists, GetParameter, GetParameterAsText, SetProgressorLabel
from arcpy.management import CreateFeatureDataset, CreateFileGDB
from arcpy.mp import ArcGISProject

from utils import AddMsgAndPrint


def logBasicSettings(log_file_path, output_folder, project_name, output_sr_name):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Create Project Workspace\n')
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tOutput Folder: {output_folder}\n")
        f.write(f"\tProject Name: {project_name}\n")
        f.write(f"\tSpatial Reference: {output_sr_name}\n")


### Initial Tool Validation ###
try:
    aprx = ArcGISProject('CURRENT')
    map = aprx.listMaps('Engineering')[0]
except:
    AddMsgAndPrint('This tool must be run from an ArcGIS Pro project template distributed with the Engineering Tools. Exiting...', 2)
    exit()

### Input Parameters ###
output_folder = GetParameterAsText(0)
project_name = GetParameterAsText(1).replace(' ','_')
output_sr = GetParameter(2)

### Set Paths and Variables ###
workspace_path = path.join(output_folder, project_name)
log_file_path = path.join(workspace_path, f"{project_name}_log.txt")
gdb_name = f"{project_name}.gdb"
gdb_path = path.join(workspace_path, gdb_name)
fd_path = path.join(gdb_path, 'Layers')
output_sr_name = output_sr.name
output_sr_code = output_sr.factoryCode

### Create Project Folder ###
if path.exists(workspace_path):
    AddMsgAndPrint('A project workspace with this name already exists. Exiting...', 1)
    exit()
else:
    try:
        SetProgressorLabel('Creating project folder...')
        AddMsgAndPrint('\nCreating project folder...')
        mkdir(workspace_path)
    except:
        AddMsgAndPrint('\nThe project folder could not be created. Please check your write access to the output location and try again. Exiting...', 2)
        exit()

# Create log file in project folder
logBasicSettings(log_file_path, output_folder, project_name, output_sr_name)

### Create Geodatabase ###
if not Exists(gdb_path):
    try:
        SetProgressorLabel('Creating project geodatabase...')
        AddMsgAndPrint('\nCreating project geodatabase...', textFilePath=log_file_path)
        CreateFileGDB(workspace_path, gdb_name)
    except:
        AddMsgAndPrint('\nThe project geodatabase could not be created. Exiting...', 2)
        exit()

### Create Feature Dataset ###
if not Exists(fd_path):
    try:
        SetProgressorLabel('Creating project feature dataset...')
        AddMsgAndPrint('\nCreating project feature dataset...', textFilePath=log_file_path)
        CreateFeatureDataset(gdb_path, 'Layers', output_sr_code)
    except:
        AddMsgAndPrint('\nThe project feature dataset could not be created. Exiting...', 2)
        exit()

### Update Project Folder Connections ###
try:
    connection_list = [item for item in aprx.folderConnections]
    new_connection = {'alias': '', 'connectionString': workspace_path, 'isHomeFolder': False}
    if new_connection not in connection_list:
        SetProgressorLabel('Updating folder connections...')
        AddMsgAndPrint('\nUpdating folder connections...', textFilePath=log_file_path)
        connection_list.append(new_connection)
        aprx.updateFolderConnections(connection_list, validate=True)
except:
    AddMsgAndPrint('\nFailed to update project folder connections. End of script...', 1, textFilePath=log_file_path)


AddMsgAndPrint('\nCreate Project Workspace completed successfully', textFilePath=log_file_path)

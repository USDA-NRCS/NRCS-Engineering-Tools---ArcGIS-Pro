## ===============================================================================================================
## Name:    Create Project Workspace
## Purpose:
## Create a project folder and geodatabase with a user-specified name at a user-specified location.
## Set coordinate system for the project as specified by the user.
## Add new folder to the APRX's Folder Connections list.
##
## Created: 9/19/2024
##
## ===============================================================================================================
## Changes
## ===============================================================================================================
##
## start 9/19/2024
## Initial tool creation 
##
## ===============================================================================================================
## ===============================================================================================================    

## ===============================================================================================================
#### Imports
from os import mkdir, path
from sys import argv, exit
from time import ctime
from datetime import datetime
from getpass import getuser

from arcpy import AddMessage, Exists, GetParameter, GetParameterAsText, SetProgressorLabel
from arcpy.da import Describe
from arcpy.management import CreateFileGDB, CreateFeatureDataset, Compact
from arcpy.mp import ArcGISProject

from utils import AddMsgAndPrint, errorMsg

## ===============================================================================================================
#### Functions
def logBasicSettings(textFilePath, output_loc, wk_name, sr_name):
    with open (textFilePath, 'a+') as f:
        f.write("\n######################################################################\n")
        f.write("Executing Tool: Create Project Workspace\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tOutput Location: {output_loc}\n")
        f.write(f"\tWorkspace Name: {wk_name}\n")
        f.write(f"\tSpatial Reference: {sr_name}\n")

## ===============================================================================================================
#### Initialize
try:
    aprx = ArcGISProject('CURRENT')
except:
    AddMsgAndPrint('This tool must be run from an ArcGIS Pro project. Exiting...', 2)
    exit()

try:
    m = aprx.listMaps("Engineering")[0]
except:
    AddMsgAndPrint('There is no Map object named "Engineering" in the project. Engineering Tools expect "Engineering" to be the primary Map object for its work. Exiting...', 2)
    exit()
    
#### Input Parameters
output_loc = GetParameterAsText(0)
wk_name = (GetParameterAsText(1)).replace(' ','_')
sr = GetParameter(2)

#### Execution
try:
    ## Variables
    wk_path = path.join(output_loc, wk_name)
    textFilePath = path.join(wk_path, f"{wk_name}_EngTools.txt")
    gdb_name = wk_name + '_EngTools.gdb'
    gdb_path = path.join(wk_path, gdb_name)
    fd_name = 'Layers'
    fd_path = path.join(gdb_path, fd_name)
    sr_name = sr.name
    sr_code = sr.factoryCode

    ## Set default geodatabase and Map spatial reference.
    aprx.defaultGeodatabase = path.join(path.dirname(argv[0]), 'Scratch.gdb')
    m.spatialReference = sr
    
    ## Create project folder
    SetProgressorLabel('Checking project directories...')
    AddMsgAndPrint('\nChecking project directories...', textFilePath=textFilePath)
    if not path.exists(wk_path):
        try:
            SetProgressorLabel('Creating project folder...')
            mkdir(wk_path)
        except:
            AddMsgAndPrint('\nThe project folder cannot be created. Please check the Output Location and your write access to the Output Location and try again. Exiting...\n', 2)
            exit()

    ## Start logging in the project folder
    logBasicSettings(textFilePath, output_loc, wk_name, sr_name)

    ## Create project geodatabase and feature dataset
    SetProgressorLabel('Creating project contents...')
    if not Exists(gdb_path):
        AddMsgAndPrint('\nCreating project geodatabase...', textFilePath=textFilePath)
        SetProgressorLabel('Creating project geodatabase...')
        CreateFileGDB(wk_path, gdb_name)

    if not Exists(fd_path):
        SetProgressorLabel('Creating project feature dataset...')
        AddMsgAndPrint('\nCreating project feature dataset...', textFilePath=textFilePath)
        CreateFeatureDataset(gdb_path, fd_name, sr_code)

    ##  Update Folder Connections to add the new project without removing existing Folder Connections from the aprx
    SetProgressorLabel('Updating Catalog...')
    AddMsgAndPrint('\nUpdating Catalog...', textFilePath=textFilePath)
    fc_list = []
    for item in aprx.folderConnections:
        fc_list.append(item)
    fcDict = {'alias':'', 'connectionString':wk_path, 'isHomeFolder':False}
    if fcDict not in fc_list:
        fc_list.append(fcDict)
        aprx.updateFolderConnections(fc_list, validate=True)


    ## Finish up
    try:
        AddMsgAndPrint("\nCompacting File Geodatabase...", textFilePath=textFilePath)
        SetProgressorLabel("Compacting File Geodatabase...")
        Compact(gdb_path)
    except:
        pass

    AddMsgAndPrint('\nCreate Project Workspace completed successfully!', textFilePath=textFilePath)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Create Project Workspace'), 2, textFilePath)
    except:
        AddMsgAndPrint(errorMsg('Create Project Workspace'), 2)

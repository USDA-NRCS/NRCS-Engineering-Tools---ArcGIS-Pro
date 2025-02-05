from getpass import getuser
from os import path
from sys import argv, exit
from time import ctime

from arcpy import Describe, env, Exists, GetParameterAsText, SetParameterAsText, SetProgressorLabel
from arcpy.management import Append, CalculateGeometryAttributes, CalculateField, Compact, \
    CreateFeatureclass, GetCount, MakeFeatureLayer
from arcpy.mp import ArcGISProject

from utils import AddMsgAndPrint, emptyScratchGDB, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, project_workspace):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Create Project Workspace\n')
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tProject Workspace: {project_workspace}\n")


### Initial Tool Validation ###
try:
    aprx = ArcGISProject('CURRENT')
    map = aprx.listMaps('Engineering')[0]
except:
    AddMsgAndPrint('This tool must be run from an ArcGIS Pro project template distributed with the Engineering Tools. Exiting...', 2)
    exit()

### Input Parameters ###
project_workspace = GetParameterAsText(0)
input_aoi = GetParameterAsText(1)

### Set Paths and Variables ###
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")
gdb_name = f"{project_name}_EngPro.gdb"
gdb_path = path.join(project_workspace, gdb_name)
fd_path = path.join(gdb_path, 'Layers')
input_aoi_path = Describe(input_aoi).catalogPath
output_aoi_name = f"{project_name}_AOI"
output_aoi_path = path.join(fd_path, output_aoi_name)
template_aoi = path.join(path.dirname(argv[0]), 'Support.gdb', 'aoi_template')
scratch_gdb = path.join(path.dirname(argv[0]), 'Scratch.gdb')

### Verify Project Workspace and GDB ###
if not path.exists(project_workspace) or not Exists(gdb_path) or not Exists(fd_path):
    AddMsgAndPrint('\nThe project folder or geodatabase does not exist or is not compatible with this version of the toolbox. Please run the Create Project Workspace tool. Exiting...', 2)
    exit()
else:
    fd_sr = Describe(fd_path).spatialReference
    if 'WGS' not in fd_sr.name or '1984' not in fd_sr.name or 'UTM' not in fd_sr.name:
        AddMsgAndPrint('\nThe geodatabase found in the selected workspace is not using a WGS 1984 UTM coordinate system. Please run the Create Project Workspace tool. Exiting...', 2)
        exit()

logBasicSettings(log_file_path, project_workspace)

### ESRI Environment Settings ###
project_sr = Describe(fd_path).spatialReference
env.outputCoordinateSystem = project_sr
env.overwriteOutput = True

try:
    ### Validate Input AOI Layer ###
    if int(GetCount(input_aoi).getOutput(0)) > 1:
        AddMsgAndPrint('\nThe defined AOI can only have one polygon. Exiting...', 2, log_file_path)
        exit()

    removeMapLayers(map, [output_aoi_name])

    ### Create New AOI Layer from Input ###
    if input_aoi_path != output_aoi_path:
        SetProgressorLabel('Creating new project AOI layer...')
        AddMsgAndPrint('\nCreating new project AOI layer...', log_file_path=log_file_path)
        # Create new feature class using template_aoi
        CreateFeatureclass(fd_path, output_aoi_name, 'POLYGON', template_aoi)
        # Append any existing records from input aoi
        MakeFeatureLayer(input_aoi, 'input_aoi_temp')
        Append('input_aoi_temp', output_aoi_path, 'NO_TEST')
    else:
        AddMsgAndPrint('\nExisting project AOI layer used as input...', log_file_path=log_file_path)

    ### Update Acres Fields ###
    SetProgressorLabel('Updating acres fields...')
    AddMsgAndPrint('\nUpdating acres fields...', log_file_path=log_file_path)
    CalculateGeometryAttributes(output_aoi_path, 'acres_us AREA', '', 'ACRES_US', project_sr, 'SAME_AS_INPUT')
    CalculateGeometryAttributes(output_aoi_path, 'acres_intl AREA', '', 'ACRES', project_sr, 'SAME_AS_INPUT')
    CalculateField(output_aoi_path, 'acres_us', 'Round($feature.acres_us,2)', 'ARCADE')
    CalculateField(output_aoi_path, 'acres_intl', 'Round($feature.acres_intl,2)', 'ARCADE')

    ### Add AOI Layer to Map ###
    SetProgressorLabel('Adding AOI layer to the map...')
    AddMsgAndPrint('\nAdding AOI layer to the map...', log_file_path=log_file_path)
    SetParameterAsText(2, output_aoi_path)

    ### Remove Digitized Layer (if present) ###
    for lyr in map.listLayers():
        if '02. Create AOI' in lyr.name:
            map.removeLayer(lyr)

    ### Compact Project GDB ###
    try:
        SetProgressorLabel('Compacting project geodatabase...')
        AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
        Compact(gdb_path)
    except:
        pass

    AddMsgAndPrint('\nCreate AOI completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Create AOI'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Create AOI'), 2)

finally:
    emptyScratchGDB(scratch_gdb)

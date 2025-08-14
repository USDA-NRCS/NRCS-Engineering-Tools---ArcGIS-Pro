from getpass import getuser
from os import path
from sys import argv, exit
from time import ctime

from arcpy import Describe, env, Exists, GetInstallInfo, GetParameterAsText, SetParameterAsText, SetProgressorLabel
from arcpy.analysis import Clip
from arcpy.management import Compact, Merge
from arcpy.mp import ArcGISProject

from utils import AddMsgAndPrint, emptyScratchGDB, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, project_aoi, input_datasets, output_name):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Combine Adjacent Datasets By AOI\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tProject AOI: {project_aoi}\n")
        f.write(f"\tInputs Datasets: {input_datasets}\n")
        f.write(f"\tOutput Name: {output_name}\n")


### Initial Tool Validation ###
try:
    aprx = ArcGISProject('CURRENT')
    map = aprx.listMaps('Engineering')[0]
except:
    AddMsgAndPrint('\nThis tool must be run from an ArcGIS Pro project template distributed with the Engineering Tools. Exiting!', 2)
    exit()

### Input Parameters ###
project_aoi = GetParameterAsText(0)
input_datasets = GetParameterAsText(1).split(';')
output_name = GetParameterAsText(2).replace(' ','_')

### Locate Project GDB ###
project_aoi_path = Describe(project_aoi).catalogPath
if 'EngPro.gdb' in project_aoi_path and 'AOI' in project_aoi_path:
    project_gdb = project_aoi_path[:project_aoi_path.find('.gdb')+4]
else:
    AddMsgAndPrint('\nThe selected AOI layer is not from an Engineering Tools project or is not compatible with this version of the toolbox. Exiting...', 2)
    exit()

### Set Paths and Variables ###
support_dir = path.dirname(argv[0])
support_gdb = path.join(support_dir, 'Support.gdb')
scratch_gdb = path.join(support_dir, 'Scratch.gdb')
project_workspace = path.dirname(project_gdb)
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")
project_fd = path.join(project_gdb, 'Layers')
output_merge_path = path.join(project_fd, output_name)

if Exists(output_merge_path):
    AddMsgAndPrint(f"\nOutput name: {output_name} already exists in project geodatabase and will be overwritten...", 1)

### ESRI Environment Settings ###
env.overwriteOutput = True

try:
    removeMapLayers(map, [output_name])
    logBasicSettings(log_file_path, project_aoi, input_datasets, output_name)

    ### Clip Input Datasets ###
    SetProgressorLabel('Clipping input data...')
    AddMsgAndPrint('\nClipping input data...', log_file_path=log_file_path)
    dataset_count = len(input_datasets)
    x = 0
    while x < dataset_count:
        dataset = input_datasets[x].replace("'",'')
        temp_clip = path.join(scratch_gdb, f"Clip_{x}")
        Clip(dataset, project_aoi, temp_clip)
        if x == 0:
            merge_list = f"{temp_clip}"
        else:
            merge_list = f"{merge_list};{temp_clip}"
        x+=1

    ### Merge Clipped Datasets ###
    SetProgressorLabel('Merging clipped data...')
    AddMsgAndPrint('\nMerging clipped data...', log_file_path=log_file_path)
    Merge(merge_list, output_merge_path)

    ### Add Outputs to Map ###
    SetProgressorLabel('Adding output layers to map...')
    AddMsgAndPrint('\nAdding output layers to map...', log_file_path=log_file_path)
    SetParameterAsText(3, output_merge_path)

    ### Compact Project GDB ###
    try:
        SetProgressorLabel('Compacting project geodatabase...')
        AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
        Compact(project_gdb)
    except:
        pass

    AddMsgAndPrint('\nCombine Adjacent Datasets By AOI completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Combine Adjacent Datasets By AOI'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Combine Adjacent Datasets By AOI'), 2)

finally:
    emptyScratchGDB(scratch_gdb)  

from getpass import getuser
from os import path
from sys import exit
from time import ctime

from arcpy import CheckExtension, CheckOutExtension, Describe, env, GetInstallInfo, GetParameterAsText
from arcpy.mp import ArcGISProject
from arcpy.sa import Times

from utils import AddMsgAndPrint, errorMsg


def logBasicSettings(log_file_path, project_dem, output_z_units):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Export Project DEM\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tProject DEM: {project_dem}\n")
        f.write(f"\tOutput Z Units: {output_z_units}\n")


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

### ESRI Environment Settings ###
env.overwriteOutput = True
env.resamplingMethod = 'BILINEAR'
env.pyramid = 'PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP'

### Input Parameters ###
project_dem = GetParameterAsText(0)
output_z_units = GetParameterAsText(1)
output_dem_path = GetParameterAsText(2)

### Locate Project GDB ###
project_dem_path = Describe(project_dem).CatalogPath
if 'EngPro.gdb' in project_dem_path and 'DEM' in project_dem_path:
    project_gdb = project_dem_path[:project_dem_path.find('.gdb')+4]
else:
    AddMsgAndPrint('\nThe selected DEM is not from an Engineering Tools project or is not compatible with this version of the toolbox. Exiting...', 2)
    exit()

### Set Paths and Variables ###
project_workspace = path.dirname(project_gdb)
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")

# Set z-factor for converting vertical units from International Feet
if output_z_units == 'Meters':
    z_factor = 0.3048
elif output_z_units == 'Centimeters':
    z_factor = 30.48
elif output_z_units == 'International Feet':
    z_factor = 1
elif output_z_units == 'International Inches':
    z_factor = 12
elif output_z_units == 'US Survey Feet':
    z_factor = 1.000002000
elif output_z_units == 'US Survey Inches':
    z_factor = 12.000002400

try:
    logBasicSettings(log_file_path, project_dem, output_z_units)

    output_dem = Times(project_dem, z_factor)
    output_dem.save(output_dem_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Export Project DEM'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Export Project DEM'), 2) 

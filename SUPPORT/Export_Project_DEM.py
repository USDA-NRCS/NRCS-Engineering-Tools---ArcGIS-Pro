from getpass import getuser
from os import path
from sys import exit
from time import ctime

from arcpy import CheckExtension, CheckOutExtension, Describe, env, Exists, GetInstallInfo, GetParameterAsText, ListFields
from arcpy.da import SearchCursor
from arcpy.mp import ArcGISProject
from arcpy.sa import Times

from utils import AddMsgAndPrint, errorMsg


def logBasicSettings(log_file_path, project_dem, project_z_units, output_z_units, z_factor):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Export Project DEM\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tProject DEM: {project_dem}\n")
        f.write(f"\tProject DEM Vertical Units: {project_z_units}\n")
        f.write(f"\tOutput Z Units: {output_z_units}\n")
        f.write(f"\tExport Z-Factor: {z_factor}\n")


def normalizeVerticalUnits(unit_name):
    if not unit_name:
        return ''

    unit_lookup = {
        'Meter': 'Meters',
        'Meters': 'Meters',
        'Foot': 'International Feet',
        'Feet': 'International Feet',
        'International Foot': 'International Feet',
        'International Feet': 'International Feet',
        'Foot_US': 'US Survey Feet',
        'US Survey Foot': 'US Survey Feet',
        'US Survey Feet': 'US Survey Feet'
    }
    return unit_lookup.get(unit_name, unit_name)


def getVerticalConversionFactor(input_units, output_units):
    input_units = normalizeVerticalUnits(input_units)
    output_units = normalizeVerticalUnits(output_units)

    conversion_lookup = {
        'Meters': {
            'Meters': 1,
            'International Feet': 3.280839895,
            'US Survey Feet': 3.2808333333
        },
        'International Feet': {
            'Meters': 0.3048,
            'International Feet': 1,
            'US Survey Feet': 0.999998
        },
        'US Survey Feet': {
            'Meters': 0.3048006096,
            'International Feet': 1.000002,
            'US Survey Feet': 1
        }
    }

    try:
        return conversion_lookup[input_units][output_units]
    except:
        return None


def getProjectVerticalUnits(project_units_table_path):
    if not Exists(project_units_table_path):
        return ''

    field_names = [field.name.upper() for field in ListFields(project_units_table_path)]
    if 'OUTPUT_Z_UNITS' not in field_names:
        return ''

    with SearchCursor(project_units_table_path, ['OUTPUT_Z_UNITS']) as cursor:
        for row in cursor:
            return normalizeVerticalUnits(row[0])

    return ''


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
project_units_table_path = path.join(project_gdb, f"{project_name}_Project_Units")
project_z_units = getProjectVerticalUnits(project_units_table_path)
output_z_units = normalizeVerticalUnits(output_z_units)

if project_z_units == '':
    AddMsgAndPrint('\nProject unit settings table is missing or does not contain output DEM vertical units. Exiting...', 2)
    exit()

z_factor = getVerticalConversionFactor(project_z_units, output_z_units)
if z_factor is None:
    AddMsgAndPrint(f"\nUnable to determine the correct vertical unit conversion from {project_z_units} to {output_z_units}. Exiting...", 2)
    exit()

try:
    logBasicSettings(log_file_path, project_dem, project_z_units, output_z_units, z_factor)
    output_dem = Times(project_dem, z_factor)
    output_dem.save(output_dem_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Export Project DEM'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Export Project DEM'), 2) 

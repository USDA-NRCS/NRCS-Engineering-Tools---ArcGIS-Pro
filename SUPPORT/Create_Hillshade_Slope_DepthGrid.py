from getpass import getuser
from os import path
from sys import exit
from time import ctime

from arcpy import CheckExtension, CheckOutExtension, Describe, env, Exists, GetInstallInfo, GetParameterAsText, \
    GetParameter, ListFields, SetParameterAsText, SetParameterSymbology, SetProgressorLabel

from arcpy.da import SearchCursor
from arcpy.management import Compact
from arcpy.mp import ArcGISProject
from arcpy.sa import Con, Fill, Hillshade, Minus, Slope

from utils import AddMsgAndPrint, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, project_dem, project_xy_units, project_z_units, z_factor, create_hillshade, create_slope, create_depth_grid):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Create Hillshade, Slope, Depth Grid\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tProject DEM: {project_dem}\n")
        f.write(f"\tProject XY Units: {project_xy_units}\n")
        f.write(f"\tProject DEM Vertical Units: {project_z_units}\n")
        f.write(f"\tHillshade/Slope Z-Factor: {z_factor}\n")
        f.write(f"\tCreate Hillshade: {'True' if create_hillshade else 'False'}\n")
        f.write(f"\tCreate Slope: {'True' if create_slope else 'False'}\n")
        f.write(f"\tCreate Depth Grid: {'True' if create_depth_grid else 'False'}\n")


# unit helpers so XY/Z units are read explicitly instead of assuming a fixed z-factor.
def normalizeLinearUnits(unit_name):

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


def getProjectedXYUnits(spatial_ref):
    sr_type = getattr(spatial_ref, 'type', getattr(spatial_ref, 'Type', ''))
    if sr_type != 'Projected':
        return ''

    linear_unit_name = getattr(spatial_ref, 'linearUnitName', getattr(spatial_ref, 'LinearUnitName', ''))
    return normalizeLinearUnits(linear_unit_name)


def getUnitConversionFactor(input_units, output_units):
    input_units = normalizeLinearUnits(input_units)
    output_units = normalizeLinearUnits(output_units)

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


def getProjectUnitSettings(project_units_table_path):
    if not Exists(project_units_table_path):
        return '', ''

    field_names = [field.name for field in ListFields(project_units_table_path)]
    if 'XY_UNITS' not in field_names or 'OUTPUT_Z_UNITS' not in field_names:
        return '', ''

    with SearchCursor(project_units_table_path, ['XY_UNITS', 'OUTPUT_Z_UNITS']) as cursor:
        for row in cursor:
            return normalizeLinearUnits(row[0]), normalizeLinearUnits(row[1])

    return '', ''


# depth-grid symbology now switches by project vertical units.
def getDepthGridSymbologyPath(project_z_units):

    project_z_units = normalizeLinearUnits(project_z_units)

    if project_z_units == 'Meters':
        symbology_file_name = 'DepthGrid_meters.lyrx'
    elif project_z_units in ['International Feet', 'US Survey Feet']:
        symbology_file_name = 'DepthGrid_feet.lyrx'
    else:
        return ''

    return path.join(path.dirname(__file__), 'layer_files', symbology_file_name)
    

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
create_hillshade = GetParameter(1)
create_slope = GetParameter(2)
create_depth_grid = GetParameter(3)

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
hillshade_name = f"{project_name}_Hillshade"
hillshade_path = path.join(project_gdb, hillshade_name)
slope_name = f"{project_name}_Slope"
slope_path = path.join(project_gdb, slope_name)
depth_grid_name = f"{project_name}_DepthGrid"
depth_grid_path = path.join(project_gdb, depth_grid_name)
project_units_table_name = f"{project_name}_Project_Units"
project_units_table_path = path.join(project_gdb, project_units_table_name)

dem_desc = Describe(project_dem_path)
project_sr = dem_desc.spatialReference
# derive XY units from the DEM spatial reference and validate against project settings.
project_xy_units = getProjectedXYUnits(project_sr)

if project_xy_units == '':
    AddMsgAndPrint('\nThe selected DEM is not in a projected coordinate system or its XY units could not be determined. Exiting...', 2)
    exit()

# require explicit project XY/Z units from the project settings table for processing/logging.
project_xy_units_from_table, project_z_units = getProjectUnitSettings(project_units_table_path)

if project_xy_units_from_table == '' or project_z_units == '':
    AddMsgAndPrint('\nProject unit settings table is missing or does not contain valid XY and vertical units. This tool requires explicit project units for troubleshooting and processing. Exiting...', 2, log_file_path=log_file_path)
    exit()

if project_xy_units_from_table != project_xy_units:
    AddMsgAndPrint(f"\nProject unit settings table XY units ({project_xy_units_from_table}) do not match DEM XY units ({project_xy_units}). This project has inconsistent unit settings and must be corrected before running this tool. Exiting...", 2, log_file_path=log_file_path)
    exit()

depth_grid_symbology_path = getDepthGridSymbologyPath(project_z_units)
if depth_grid_symbology_path == '':
    AddMsgAndPrint(f"\nProject unit settings table contains unsupported vertical units ({project_z_units}). Exiting...", 2, log_file_path=log_file_path)
    exit()

# replaced hardcoded z-factor with unit-aware conversion.
z_factor = getUnitConversionFactor(project_z_units, project_xy_units)
if z_factor is None:
    AddMsgAndPrint(f"\nUnable to determine the correct z-factor using DEM vertical units ({project_z_units}) and XY units ({project_xy_units}). Exiting...", 2)
    exit()

env.snapRaster = project_dem_path
env.cellSize = project_dem_path
env.outputCoordinateSystem = project_sr

try:
    remove_layers = []
    if create_hillshade: remove_layers.append(hillshade_name)
    if create_slope: remove_layers.append(slope_name)
    if create_depth_grid: remove_layers.append(depth_grid_name)
    removeMapLayers(map, remove_layers)
    logBasicSettings(log_file_path, project_dem, project_xy_units, project_z_units, z_factor, create_hillshade, create_slope, create_depth_grid)

    if create_hillshade:
        ### Create Hillshade ###
        SetProgressorLabel('Creating Hillshade...')
        AddMsgAndPrint('\nCreating Hillshade...', log_file_path=log_file_path)
        output_hillshade = Hillshade(project_dem, '315', '45', 'NO_SHADOWS', z_factor)
        output_hillshade.save(hillshade_path)

    if create_slope:
        ### Create Slope ###
        SetProgressorLabel('Creating Slope...')
        AddMsgAndPrint('\nCreating Slope...', log_file_path=log_file_path)
        output_slope = Slope(project_dem, 'PERCENT_RISE', z_factor)
        output_slope.save(slope_path)

    if create_depth_grid:
        ### Create Depth Grid ###
        SetProgressorLabel('Creating Depth Grid...')
        AddMsgAndPrint('\nCreating Depth Grid...', log_file_path=log_file_path)
        output_fill = Fill(project_dem)
        output_minus = Minus(output_fill, project_dem)
        output_depth_grid = Con(output_minus, output_minus, '', 'VALUE > 0')
        output_depth_grid.save(depth_grid_path)

        ### Add Outputs to Map ###
        SetProgressorLabel('Adding outputs to map...')
        AddMsgAndPrint('\nAdding outputs to map...', log_file_path=log_file_path)
    if create_slope: SetParameterAsText(4, slope_path)
    if create_hillshade: SetParameterAsText(5, hillshade_path)
    if create_depth_grid:
    # apply unit-specific depth-grid symbology to the output parameter.
        AddMsgAndPrint(f"\nApplying depth grid symbology: {path.basename(depth_grid_symbology_path)}", log_file_path=log_file_path)

    SetParameterSymbology(6, depth_grid_symbology_path)
    SetParameterAsText(6, depth_grid_path)

    ### Compact Project GDB ###
    try:
        SetProgressorLabel('Compacting project geodatabase...')
        AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
        Compact(project_gdb)
    except:
        pass

    AddMsgAndPrint('\nCreate Hillshade, Slope, Depth Grid completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Create Hillshade, Slope, Depth Grid'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Create Hillshade, Slope, Depth Grid'), 2)

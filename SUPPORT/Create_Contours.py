from getpass import getuser
from os import path
from sys import argv, exit
from time import ctime
from arcpy import CheckExtension, CheckOutExtension, Describe, env, Exists, GetInstallInfo, GetParameterAsText, \
    ListFields, SetParameterAsText, SetProgressorLabel
from arcpy.da import SearchCursor
from arcpy.management import AddField, CalculateField, Compact, CopyFeatures, Delete, DeleteField, MakeFeatureLayer, \
    SelectLayerByAttribute
from arcpy.mp import ArcGISProject
from arcpy.sa import Contour
from utils import AddMsgAndPrint, emptyScratchGDB, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, project_dem, project_xy_units, project_z_units, contour_interval, contour_interval_units, z_factor):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Create Contours\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tProject DEM: {project_dem}\n")
        f.write(f"\tProject XY Units: {project_xy_units}\n")
        f.write(f"\tProject DEM Vertical Units: {project_z_units}\n")
        f.write(f"\tContour Interval: {contour_interval}\n")
        f.write(f"\tContour Interval Units: {contour_interval_units}\n")
        f.write(f"\tContour Z-Factor: {z_factor}\n")


# XY-unit helper for projected-coordinate validation and logging.
def getProjectedXYUnits(spatial_ref):

    sr_type = getattr(spatial_ref, 'type', getattr(spatial_ref, 'Type', ''))
    if sr_type != 'Projected':
        return ''

    linear_unit_name = getattr(spatial_ref, 'linearUnitName', getattr(spatial_ref, 'LinearUnitName', ''))
    return normalizeVerticalUnits(linear_unit_name)


# vertical-unit helpers so contour processing can reference project DEM Z-units.
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


def getContourUnitSuffix(contour_units):
    contour_units = normalizeVerticalUnits(contour_units)

    if contour_units == 'US Survey Feet':
        return 'USFT'
    if contour_units == 'International Feet':
        return 'IFT'

    return contour_units.replace(' ', '_') if contour_units else ''


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
GetParameterAsText(1)  # Display-only reminder of the project vertical units.
contour_interval = GetParameterAsText(2)
target_contour_units = normalizeVerticalUnits(GetParameterAsText(4))

### Locate Project GDB ###
project_dem_path = Describe(project_dem).CatalogPath
if 'EngPro.gdb' in project_dem_path and 'DEM' in project_dem_path:
    project_gdb = project_dem_path[:project_dem_path.find('.gdb')+4]
else:
    AddMsgAndPrint('\nThe selected DEM is not from an Engineering Tools project or is not compatible with this version of the toolbox. Exiting...', 2)
    exit()

# DEM-driven environment settings for more consistent contour output.
dem_desc = Describe(project_dem_path)
project_sr = dem_desc.spatialReference
project_xy_units = getProjectedXYUnits(project_sr)

if project_xy_units == '':
    AddMsgAndPrint('\nThe selected DEM is not in a projected coordinate system or its XY units could not be determined. Exiting...', 2)
    exit()

env.snapRaster = project_dem_path
env.cellSize = project_dem_path
env.outputCoordinateSystem = project_sr

### Validate Contour Interval (> 0 and <= 1000) ###
if not 0 < float(contour_interval) <= 1000:
    AddMsgAndPrint('\nThe contour interval must be greater than 0 and less than or equal to 1000. Exiting...', 2)
    exit()

### Validate Output Contour Units ###
if target_contour_units not in ('US Survey Feet', 'International Feet'):
    AddMsgAndPrint('\nThe output contour vertical units must be either US Survey Feet or International Feet. Exiting...', 2)
    exit()

### Set Paths and Variables ###
support_dir = path.dirname(argv[0])
scratch_gdb = path.join(support_dir, 'Scratch.gdb')
project_workspace = path.dirname(project_gdb)
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")
temp_contour_path = r"memory\temp_contour"
contour_unit_suffix = getContourUnitSuffix(target_contour_units)
contour_name = f"{project_name}_Contour_{contour_interval.replace('.','_dot_')}_{contour_unit_suffix}"
layers_fd = path.join(project_gdb, 'Layers')

# validation for the required Layers feature dataset.
if not Exists(layers_fd):
    AddMsgAndPrint('\nThe project Layers feature dataset does not exist. Please run the Create AOI tool for this project. Exiting...', 2)
    exit()

contour_path = path.join(layers_fd, contour_name)
project_units_table_name = f"{project_name}_Project_Units"
project_units_table_path = path.join(project_gdb, project_units_table_name)
# contours now read/log project vertical units from the project settings table.
project_vertical_units = getProjectVerticalUnits(project_units_table_path)

if project_vertical_units == '':
    AddMsgAndPrint('\nProject unit settings table is missing or does not contain output DEM vertical units. This tool requires valid project vertical units so the correct contour z-factor can be applied. Exiting...', 2)
    exit()
else:
    z_factor = getVerticalConversionFactor(project_vertical_units, target_contour_units)
    if z_factor is None:
        AddMsgAndPrint(f"\nUnable to determine the correct contour z-factor using DEM vertical units ({project_vertical_units}) and requested output contour units ({target_contour_units}). Exiting...", 2)
        exit()

try:
    removeMapLayers(map, [contour_name])
    logBasicSettings(log_file_path, project_dem, project_xy_units, project_vertical_units, contour_interval, target_contour_units, z_factor)

    ### Create Contours ###
    SetProgressorLabel('Creating temporary contours layer...')
    AddMsgAndPrint('\nCreating temporary contours layer...', log_file_path=log_file_path)
    AddMsgAndPrint(f"\tProject XY units: {project_xy_units}", log_file_path=log_file_path)
    if project_vertical_units != '':
        AddMsgAndPrint(f"\tSource DEM vertical units: {project_vertical_units}", log_file_path=log_file_path)
        AddMsgAndPrint(f"\tTarget contour units: {target_contour_units}", log_file_path=log_file_path)
    AddMsgAndPrint(f"\tContour z-factor: {z_factor}", log_file_path=log_file_path)

    # Scale DEM elevations into the requested output contour units so the
    # contour interval and CONTOUR values are produced in the selected feet type.
    Contour(project_dem, temp_contour_path, contour_interval, 0, z_factor)

    ### Add Index Field ###
    DeleteField(temp_contour_path, 'Id')
    AddField(temp_contour_path, 'Index', 'DOUBLE')

    ### Update Every 5th Index to 1 ###
    SetProgressorLabel('Updating contour indexing...')
    AddMsgAndPrint('\nUpdating contour indexing...', log_file_path=log_file_path)
    MakeFeatureLayer(temp_contour_path, 'contour_lyr')
    expression = "MOD( \"CONTOUR\"," + str(float(contour_interval) * 5) + ") = 0"
    SelectLayerByAttribute('contour_lyr', 'NEW_SELECTION', expression)
    CalculateField('contour_lyr', 'Index', 1, 'PYTHON3')

    ### Update All Other Indexes to 0 ###
    SelectLayerByAttribute('contour_lyr', 'SWITCH_SELECTION')
    CalculateField('contour_lyr', 'Index', 0, 'PYTHON3')

    ### Copy Final Contour Output ###
    SetProgressorLabel('Finalizing contour layer...')
    AddMsgAndPrint('\nFinalizing contour layer...', log_file_path=log_file_path)
    SelectLayerByAttribute('contour_lyr', 'CLEAR_SELECTION')
    CopyFeatures('contour_lyr', contour_path)

    ### Add Output to Map ###
    AddMsgAndPrint('\nAdding to map...', log_file_path=log_file_path)
    SetProgressorLabel('Adding to map...')
    # output parameter index shifted because param 1 is now display-only.
    SetParameterAsText(3, contour_path)

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
    try:
        Delete(temp_contour_path)
    except:
        pass
    emptyScratchGDB(scratch_gdb)

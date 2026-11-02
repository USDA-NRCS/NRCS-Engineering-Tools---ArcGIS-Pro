from getpass import getuser
from os import path
from sys import exit
from time import ctime

from arcpy import CheckExtension, CheckOutExtension, Describe, env, Exists, GetInstallInfo, GetParameterAsText, SetProgressorLabel
from arcpy.da import SearchCursor
from arcpy import ListFields
from arcpy.management import Compact
from arcpy.mp import ArcGISProject
from arcpy.sa import Con, Divide, Ln, Plus, Raster, Slope, Tan, Times

from utils import AddMsgAndPrint, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, project_dem, project_xy_units, project_z_units, z_factor):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Compound Topographic Index (CTI)\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tProject DEM: {project_dem}\n")
        f.write(f"\tProject XY Units: {project_xy_units}\n")
        f.write(f"\tProject DEM Vertical Units: {project_z_units}\n")
        f.write(f"\tSlope Z-Factor: {z_factor}\n")
        f.write(f"\tCTI Specific Catchment Area Units: {project_xy_units}\n")



def normalizeLinearUnits(unit_name):
    # Match ArcGIS unit names and project table labels to common lookup keys.
    unit_lookup = {
        'Meter': 'Meters',
        'Meters': 'Meters',
        'Foot': 'International Feet',
        'Feet': 'International Feet',
        'International Foot': 'International Feet',
        'International Feet': 'International Feet',
        'Foot_US': 'US Survey Feet',
        'US Survey Foot': 'US Survey Feet',
        'US Survey Feet': 'US Survey Feet',
    }
    return unit_lookup.get(unit_name, '')


def getProjectUnitSettings(project_units_table_path):
    if not Exists(project_units_table_path):
        return '', ''

    field_names = {field.name.upper() for field in ListFields(project_units_table_path)}
    if not {'XY_UNITS', 'OUTPUT_Z_UNITS'}.issubset(field_names):
        return '', ''

    with SearchCursor(project_units_table_path, ['XY_UNITS', 'OUTPUT_Z_UNITS']) as cursor:
        for xy_units, z_units in cursor:
            return normalizeLinearUnits(xy_units), normalizeLinearUnits(z_units)

    return '', ''


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

### Input Parameters ###
project_dem = GetParameterAsText(0)

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
project_flow_accum = path.join(project_gdb, 'Flow_Accumulation')
output_cti_name = f"{project_name}_CTI"
output_cti_path = path.join(project_gdb, output_cti_name)
project_units_table_path = path.join(project_gdb, f"{project_name}_Project_Units")

### Locate Flow Accumulation Raster ###
if not Exists(project_flow_accum):
    AddMsgAndPrint('\nCould not locate Flow Accumulation raster for specified project DEM. Run the "Create Stream Network" tool and try again. Exiting...', 2)
    exit()

### ESRI Environment Settings ###
dem_desc = Describe(project_dem_path)
dem_cell_size = dem_desc.meanCellWidth
project_sr = dem_desc.spatialReference
project_xy_units = normalizeLinearUnits(project_sr.linearUnitName)

# Require explicit, consistent XY/Z settings rather than assuming elevation units.
if project_sr.type != 'Projected' or not project_xy_units:
    AddMsgAndPrint('\nThe DEM must use a projected coordinate system with supported linear units. Exiting...', 2, log_file_path=log_file_path)
    exit()

project_xy_units_from_table, project_z_units = getProjectUnitSettings(project_units_table_path)
if not project_xy_units_from_table or not project_z_units:
    AddMsgAndPrint('\nProject unit settings table is missing, empty, or contains missing or unsupported XY/vertical units. Exiting...', 2, log_file_path=log_file_path)
    exit()
if project_xy_units_from_table != project_xy_units:
    AddMsgAndPrint(f"\nProject table XY units ({project_xy_units_from_table}) do not match DEM XY units ({project_xy_units}). Correct the project settings before running this tool. Exiting...", 2, log_file_path=log_file_path)
    exit()

# Convert elevation units (outer key) to horizontal units (inner key).
z_factor_lookup = {
    'Meters': {
        'Meters': 1,
        'International Feet': 3.280839895,
        'US Survey Feet': 3.2808333333,
    },
    'International Feet': {
        'Meters': 0.3048,
        'International Feet': 1,
        'US Survey Feet': 0.999998,
    },
    'US Survey Feet': {
        'Meters': 0.3048006096,
        'International Feet': 1.000002,
        'US Survey Feet': 1,
    },
}
z_factor = z_factor_lookup[project_z_units][project_xy_units]
env.overwriteOutput = True
env.resamplingMethod = 'BILINEAR'
env.pyramid = 'PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP'
env.parallelProcessingFactor = '75%'
env.extent = 'MINOF'
env.cellSize = dem_cell_size
env.snapRaster = project_dem_path
env.outputCoordinateSystem = dem_desc.spatialReference

try:
    removeMapLayers(map, [output_cti_name])
    logBasicSettings(log_file_path, project_dem, project_xy_units, project_z_units, z_factor)

    ### Compute and Filter CTI ###
    # CTI is defined by the following equation: Ln [a/tan ß], where:
    # a represents the catchment area per pixel
    # ß refers to the slope, in degrees
    # Final equation is Ln (As / tan ß)
    SetProgressorLabel('Computing Compound Topographic Index...')
    AddMsgAndPrint('\nComputing Compound Topographic Index...', log_file_path=log_file_path)

    # Specific catchment area: contributing cell count times cell width in DEM native XY units.
    flow_accum_raster = Raster(project_flow_accum)
    As = Times(Plus(flow_accum_raster,1), dem_cell_size)

    # Match elevation units to horizontal units before calculating slope in degrees.
    slope_degrees = Slope(project_dem, 'DEGREE', z_factor)

    # Convert slope (ß) to radians / 90
    # 1.570796 values comes from (pi / 2)
    slope_radians = Divide(Times(slope_degrees,1.570796), 90)

    # denomoniator of the above equation
    # If slope value is greater than 0 compute the tangent of the slope value
    # otherwise assign 0.001 - why 0.001???
    slope_tangent = Con(slope_radians > 0, Tan(slope_radians), 0.001)

    # Final Equation
    natural_log = Ln(Divide(As,slope_tangent))
    natural_log.save(output_cti_path)

    ### Add Output CTI to Map and Symbolize ###
    SetProgressorLabel('Adding CTI layer to map...')
    AddMsgAndPrint('\nAdding CTI layer to map...', log_file_path=log_file_path)
    map.addDataFromPath(output_cti_path)
    cti_layer = map.listLayers(output_cti_name)[0]
    sym = cti_layer.symbology
    sym.colorizer.resamplingType = 'Bilinear' #NOTE: Pro does not seem to honor this
    sym.colorizer.stretchType = 'StandardDeviation'
    sym.colorizer.standardDeviation = 2
    sym.colorizer.colorRamp = aprx.listColorRamps('Yellow to Dark Red')[0]
    cti_layer.symbology = sym

    ### Compact Project GDB ###
    try:
        SetProgressorLabel('Compacting project geodatabase...')
        AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
        Compact(project_gdb)
    except:
        pass

    AddMsgAndPrint('\nCompound Topographic Index (CTI) completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Compound Topographic Index (CTI)'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Compound Topographic Index (CTI)'), 2)

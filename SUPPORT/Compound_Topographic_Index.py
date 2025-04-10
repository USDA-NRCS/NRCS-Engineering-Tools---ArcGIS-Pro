from getpass import getuser
from os import path
from sys import exit
from time import ctime

from arcpy import CheckExtension, CheckOutExtension, Describe, env, Exists, GetInstallInfo, GetParameterAsText, SetParameterAsText, SetProgressorLabel
from arcpy.management import Compact, GetCount
from arcpy.mp import ArcGISProject
from arcpy.sa import Con, Divide, ExtractByMask, Ln, Plus, Raster, Slope, Tan, Times

from utils import AddMsgAndPrint, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, project_dem, input_pool):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Compound Topographic Index (CTI)\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tProject DEM: {project_dem}\n")
        f.write(f"\tInput Pool Polygon: {input_pool if input_pool else 'None'}\n")


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
input_pool = GetParameterAsText(1)

### Locate Project GDB ###
project_dem_path = Describe(project_dem).CatalogPath
if 'EngPro.gdb' in project_dem_path and 'DEM' in project_dem_path:
    project_gdb = project_dem_path[:project_dem_path.find('.gdb')+4]
else:
    AddMsgAndPrint('\nThe selected DEM is not from an Engineering Tools project or is not compatible with this version of the toolbox. Exiting...', 2)
    exit()

### Validate Input Pool Count ###
if input_pool:
    if int(GetCount(input_pool).getOutput(0)) > 1:
        AddMsgAndPrint('\nThe input pool must be a single polygon feature. If using the project Watershed layer, select a single Subbasin. If using a different layer, dissolve it to create a single polygon, or select a single polygon and try again. Exiting...', 2)
        exit()

### Set Paths and Variables ###
project_workspace = path.dirname(project_gdb)
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")
project_flow_accum = path.join(project_gdb, 'Flow_Accumulation')
output_cti_name = f"{project_name}_CTI"
output_cti_path = path.join(project_gdb, output_cti_name)

### Locate Flow Accumulation Raster ###
if not Exists(project_flow_accum):
    AddMsgAndPrint('Could not locate Flow Accumulation raster for specified project DEM. Run the "Create Stream Network" tool and try again. Exiting...', 2)
    exit()

### ESRI Environment Settings ###
dem_desc = Describe(project_dem_path)
dem_cell_size = dem_desc.meanCellWidth
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
    logBasicSettings(log_file_path, project_dem, input_pool)

    if input_pool:
        SetProgressorLabel('Clipping DEM to input pool polygon...')
        AddMsgAndPrint('\nClipping DEM to input pool polygon...', log_file_path=log_file_path)
        clipped_dem = ExtractByMask(project_dem, input_pool)

        SetProgressorLabel('Clipping Flow Accumulation to input pool polygon...')
        AddMsgAndPrint('\nClipping Flow Accumulation to input pool polygon...', log_file_path=log_file_path)
        clipped_flow_accum = ExtractByMask(project_flow_accum, input_pool)

        # Reset variables to DEM and Flow Accum
        project_dem = clipped_dem
        project_flow_accum = clipped_flow_accum

    ### Compute and Filter CTI ###
    # CTI is defined by the following equation: Ln [a/tan ß], where:
    # a represents the catchment area per pixel
    # ß refers to the slope, in degrees
    # Final equation is Ln (As / tan ß)
    SetProgressorLabel('Computing Compound Topographic Index...')
    AddMsgAndPrint('Computing Compound Topographic Index...', log_file_path=log_file_path)

    # In the above equation, a needs to be converted to As so as to account for DEM resolution
    flow_accum_raster = Raster(project_flow_accum)
    As = Times(Plus(flow_accum_raster,1), dem_cell_size)

    # Calculate slope (ß) in degrees.
    slope_degrees = Slope(project_dem, 'DEGREE', 0.3048)

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

    ### Add Output to Map ###
    SetParameterAsText(2, output_cti_path)

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

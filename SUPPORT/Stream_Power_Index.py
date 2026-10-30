from getpass import getuser
from os import path
from sys import exit
from time import ctime

from arcpy import CheckExtension, CheckOutExtension, Describe, env, Exists, GetInstallInfo, GetParameterAsText, SetProgressorLabel
from arcpy.management import Compact
from arcpy.mp import ArcGISProject
from arcpy.sa import Divide, FlowLength, Ln, Plus, Raster, SetNull, Times

from utils import AddMsgAndPrint, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, project_dem, min_flow, max_drainage, project_xy_units):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Stream Power Index (SPI)\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tProject DEM: {project_dem}\n")
        f.write(f"\tProject XY Units: {project_xy_units}\n")
        f.write(f"\tOverland Flow Threshold (feet): {min_flow}\n")
        f.write(f"\tIn-channel Contributing Area Threshold (acres): {max_drainage}\n")


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
min_flow = GetParameterAsText(1)
max_drainage = GetParameterAsText(2)

if float(max_drainage) <= 0:
    AddMsgAndPrint('In-channel contributing area threshold must be greater than zero. Exiting...', 2)
    exit()

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
project_flow_direc = path.join(project_gdb, 'Flow_Direction')
project_slope_path = path.join(project_gdb, f"{project_name}_Slope")
output_spi_name = f"{project_name}_SPI_{min_flow}"
output_spi_path = path.join(project_gdb, output_spi_name)

### Locate Flow Accumulation and Flow Direction Rasters ###
if not Exists(project_flow_accum):
    AddMsgAndPrint('\nCould not locate Flow Accumulation raster for specified project DEM. Run the "Create Stream Network" tool and try again. Exiting...', 2)
    exit()
if not Exists(project_flow_direc):
    AddMsgAndPrint('\nCould not locate Flow Direction raster for specified project DEM. Run the "Create Stream Network" tool and try again. Exiting...', 2)
    exit()

# Reuse the project percent-rise slope raster; no new Z-factor is needed.
if not Exists(project_slope_path):
    AddMsgAndPrint(f"\nThe project slope raster was not found: {project_slope_path}. Generate it using Create Hillshade, Slope, and Depth Grid before running this tool. Exiting...", 2, log_file_path=log_file_path)
    exit()

### ESRI Environment Settings ###
dem_desc = Describe(project_dem_path)
dem_cell_size = dem_desc.meanCellWidth
dem_units = dem_desc.spatialReference.linearUnitName
# Square DEM units per acre, using the project conversion table.
square_units_per_acre = {
    'Meter': 4046.85642,
    'Foot': 43560,
    'Foot_US': 43560.174,
}
unit_labels = {
    'Meter': 'Meters',
    'Foot': 'International Feet',
    'Foot_US': 'US Survey Feet',
}
if dem_desc.spatialReference.type != 'Projected' or dem_units not in square_units_per_acre:
    AddMsgAndPrint(f"\nUnsupported DEM coordinate system or linear units: {dem_units}. Expected projected meters, International Feet, or US Survey Feet. Exiting...", 2, log_file_path=log_file_path)
    exit()
project_xy_units = unit_labels[dem_units]
env.overwriteOutput = True
env.resamplingMethod = 'BILINEAR'
env.pyramid = 'PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP'
env.parallelProcessingFactor = '75%'
env.extent = 'MINOF'
env.cellSize = dem_cell_size
env.snapRaster = project_dem_path
env.outputCoordinateSystem = dem_desc.spatialReference

try:
    removeMapLayers(map, [output_spi_name])
    logBasicSettings(log_file_path, project_dem, min_flow, max_drainage, project_xy_units)

    # Convert overland flow input to DEM XY units.
    if dem_units == 'Meter':
        overland_thresh = float(min_flow) / 3.280839895013123
    elif dem_units == 'Foot':
        overland_thresh = float(min_flow)
    elif dem_units == 'Foot_US':
        overland_thresh = float(min_flow) / 1.000002
    else:
        AddMsgAndPrint(f"\nUnsupported DEM linear units: {dem_units}. Exiting...", 2, log_file_path=log_file_path)
        exit()

    # Convert drainage area threshold (acres) to raster cell count using DEM XY units.
    if dem_units == 'Meter':
        channel_thresh = float(max_drainage) * 4046.85642 / dem_cell_size**2
    elif dem_units in ('Foot', 'Foot_US'):
        channel_thresh = float(max_drainage) * 43560 / dem_cell_size**2
    else:
        AddMsgAndPrint(f"\nUnsupported DEM linear units: {dem_units}. Exiting...", 2, log_file_path=log_file_path)
        exit()

    # Calculate Upstream Flow Length
    SetProgressorLabel('Calculating upstream flow lengths...')
    AddMsgAndPrint('\nCalculating upstream flow lengths...', log_file_path=log_file_path)
    flow_length = FlowLength(Raster(project_flow_direc), 'UPSTREAM')

    # Filter Out Overland Flow
    SetProgressorLabel('Filtering out overland flow...')
    AddMsgAndPrint(f"\nFiltering out flow accumulation with overland flow < {min_flow} feet...", log_file_path=log_file_path)
    filter_1 = SetNull(Raster(project_flow_accum), flow_length, f"VALUE < {overland_thresh}")

    # Filter Out Channelized Flow
    SetProgressorLabel('Filtering out channelized flow...')
    AddMsgAndPrint(f"\nFiltering out channelized flow with > {max_drainage} acre drainage area...", log_file_path=log_file_path)
    filter_2 = SetNull(filter_1, filter_1, f"VALUE > {channel_thresh}")

    # Existing project slope stores percent rise with XY/Z conversion already applied.
    SetProgressorLabel('Using existing project slope...')
    AddMsgAndPrint('\nUsing existing project slope...', log_file_path=log_file_path)
    slope = Raster(project_slope_path)

    # Create and Filter Stream Power Index
    SetProgressorLabel('Calculating stream power index...')
    AddMsgAndPrint('\nCalculating stream power index...', log_file_path=log_file_path)
    spiTemp = Raster(Ln(Times(Plus(filter_2,0.001),Plus(Divide(slope,100),0.001))))

    # Set Index Values < 0 to NULL
    SetProgressorLabel('Filtering index values less than zero...')
    AddMsgAndPrint('\nFiltering index values less than zero...', log_file_path=log_file_path)
    setNegativeNulls = SetNull(spiTemp, spiTemp, 'VALUE <= 0.0')
    setNegativeNulls.save(output_spi_path)

    ### Add Output SPI to Map and Symbolize ###
    SetProgressorLabel('Adding SPI layer to map...')
    AddMsgAndPrint('\nAdding SPI layer to map...', log_file_path=log_file_path)
    map.addDataFromPath(output_spi_path)
    spi_layer = map.listLayers(output_spi_name)[0]
    sym = spi_layer.symbology
    sym.colorizer.resamplingType = 'Bilinear' #NOTE: Pro does not seem to honor this
    sym.colorizer.stretchType = 'PercentClip'
    sym.colorizer.min = 0.5
    sym.colorizer.max = 0.5
    sym.colorizer.colorRamp = aprx.listColorRamps('Spectrum By Wavelength-Full Bright')[0]
    spi_layer.symbology = sym

    ### Compact Project GDB ###
    try:
        SetProgressorLabel('Compacting project geodatabase...')
        AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
        Compact(project_gdb)
    except:
        pass

    AddMsgAndPrint('\nStream Power Index (SPI) completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Stream Power Index (SPI)'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Stream Power Index (SPI)'), 2)

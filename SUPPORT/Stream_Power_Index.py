from getpass import getuser
from os import path
from sys import exit
from time import ctime

from arcpy import CheckExtension, CheckOutExtension, Describe, env, Exists, GetInstallInfo, GetParameterAsText, SetProgressorLabel
from arcpy.management import Compact
from arcpy.mp import ArcGISProject
from arcpy.sa import Divide, FlowLength, Ln, Plus, Raster, SetNull, Slope, Times

from utils import AddMsgAndPrint, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, project_dem, min_flow, max_drainage):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Stream Power Index (SPI)\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tProject DEM: {project_dem}\n")
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

### Locate Project GDB ###
project_dem_path = Describe(project_dem).CatalogPath
if 'EngPro.gdb' in project_dem_path and 'DEM' in project_dem_path:
    project_gdb = project_dem_path[:project_dem_path.find('.gdb')+4]
else:
    AddMsgAndPrint('\nThe selected DEM is not from an Engineering Tools project or is not compatible with this version of the toolbox. Exiting...', 2)
    exit()

# TODO: Validate min_flow, max_drainage?

### Set Paths and Variables ###
project_workspace = path.dirname(project_gdb)
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")
project_flow_accum = path.join(project_gdb, 'Flow_Accumulation')
project_flow_direc = path.join(project_gdb, 'Flow_Direction')
output_spi_name = f"{project_name}_SPI"
output_spi_path = path.join(project_gdb, output_spi_name)

### Locate Flow Accumulation and Flow Direction Rasters ###
if not Exists(project_flow_accum):
    AddMsgAndPrint('\nCould not locate Flow Accumulation raster for specified project DEM. Run the "Create Stream Network" tool and try again. Exiting...', 2)
    exit()
if not Exists(project_flow_direc):
    AddMsgAndPrint('\nCould not locate Flow Direction raster for specified project DEM. Run the "Create Stream Network" tool and try again. Exiting...', 2)
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
    removeMapLayers(map, [output_spi_name])
    logBasicSettings(log_file_path, project_dem, min_flow, max_drainage)

    # Set minimum flow length / in-channel threshold to proper units
    overland_thresh = float(min_flow) / 3.280839895013123
    channel_thresh = float(max_drainage) * 4046 / dem_cell_size**2

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

    # Calculate percent slope with proper z-factor
    SetProgressorLabel('Calculating slope percentage...')
    AddMsgAndPrint('\nCalculating slope percentage...', log_file_path=log_file_path)
    slope = Slope(project_dem_path, 'PERCENT_RISE', 0.3048)

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
    sym.colorizer.stretchType = 'StandardDeviation'
    sym.colorizer.standardDeviation = 2
    sym.colorizer.colorRamp = aprx.listColorRamps('Condition Number')[0]
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

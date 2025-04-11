from getpass import getuser
from os import path
from sys import argv, exit
from time import ctime

from arcpy import CheckExtension, CheckOutExtension, Describe, env, Exists, GetInstallInfo, GetParameterAsText, \
    SetParameterAsText, SetProgressorLabel
from arcpy.analysis import Buffer, Clip
from arcpy.management import AddField, CalculateField, CalculateStatistics, Compact, GetCount, MosaicToNewRaster
from arcpy.mp import ArcGISProject
from arcpy.sa import Con, Fill, FlowAccumulation, FlowDirection, StreamLink, StreamToFeature, ZonalStatistics

from utils import AddMsgAndPrint, emptyScratchGDB, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, project_aoi, input_culverts, stream_threshold):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Create Stream Network\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tProject AOI: {project_aoi}\n")
        f.write(f"\tInput Culverts: {input_culverts if input_culverts else 'None'}\n")
        f.write(f"\tStream Threshold (acres): {stream_threshold}\n")


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
project_aoi = GetParameterAsText(0)
input_culverts = GetParameterAsText(1)
stream_threshold = float(GetParameterAsText(2))

### Locate Project GDB ###
project_aoi_path = Describe(project_aoi).catalogPath
if 'EngPro.gdb' in project_aoi_path and 'AOI' in project_aoi_path:
    project_gdb = project_aoi_path[:project_aoi_path.find('.gdb')+4]
else:
    AddMsgAndPrint('\nThe selected AOI layer is not from an Engineering Tools project or is not compatible with this version of the toolbox. Exiting...', 2)
    exit()

### Set Paths and Variables ###
support_dir = path.dirname(argv[0])
scratch_gdb = path.join(support_dir, 'Scratch.gdb')
project_workspace = path.dirname(project_gdb)
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")
project_dem_name = f"{project_name}_DEM"
project_dem_path = path.join(project_gdb, project_dem_name)
culverts_buffer_temp = path.join(scratch_gdb, 'Culverts_Buffer')
culverts_raster_temp = path.join(scratch_gdb, 'Culverts_Raster')
hydro_dem_temp = path.join(scratch_gdb, 'Hydro_DEM')
culverts_name = f"{project_name}_Culverts"
culverts_path = path.join(project_gdb, 'Layers', culverts_name)
streams_name = f"{project_name}_Streams"
streams_path = path.join(project_gdb, 'Layers', streams_name)
flow_accum_name = 'Flow_Accumulation'
flow_accum_path = path.join(project_gdb, flow_accum_name)
flow_dir_name = 'Flow_Direction'
flow_dir_path = path.join(project_gdb, flow_dir_name)

### Ensure Project DEM Exists ###
if not Exists(project_dem_path):
    AddMsgAndPrint('\nCould not locate the project DEM layer for specified AOI. Exiting...', 2)
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
    removeMapLayers(map, [culverts_name, streams_name, flow_accum_name, flow_dir_name])
    logBasicSettings(log_file_path, project_aoi, input_culverts, stream_threshold)

    ### Process Input Culverts ###
    if input_culverts:
        SetProgressorLabel('Processing input culverts...')
        AddMsgAndPrint('\nProcessing input culverts...', log_file_path=log_file_path)

        input_culverts_path = Describe(input_culverts).catalogPath
        if input_culverts_path != culverts_path:
            SetProgressorLabel('Clipping input culverts to project AOI layer...')
            AddMsgAndPrint('\nClipping input culverts to project AOI layer...', log_file_path=log_file_path)
            Clip(input_culverts, project_aoi, culverts_path)
        else:
            AddMsgAndPrint('\nExisting project culverts layer used as input...', log_file_path=log_file_path)

        # Ensure output culverts layer has at least one feature in AOI
        if int(GetCount(culverts_path).getOutput(0)) > 0:

            # Buffer the culverts to 1 pixel
            SetProgressorLabel('Buffering culverts by DEM cell size...')
            AddMsgAndPrint('\nBuffering culverts by DEM cell size...', log_file_path=log_file_path)
            Buffer(culverts_path, culverts_buffer_temp, f"{str(dem_cell_size)} Meters", 'FULL', 'ROUND', 'NONE')

            # Dummy field just to execute Zonal Stats on each feature
            AddField(culverts_buffer_temp, 'ZONE', 'TEXT')
            CalculateField(culverts_buffer_temp, 'ZONE', f"!{Describe(culverts_buffer_temp).OIDFieldName}!", 'PYTHON3')

            # Get the minimum elevation value for each culvert
            SetProgressorLabel('Finding minimum elevation of culverts...')
            AddMsgAndPrint('\nFinding minimum elevation of culverts...', log_file_path=log_file_path)
            culverts_min_value = ZonalStatistics(culverts_buffer_temp, 'ZONE', project_dem_path, 'MINIMUM', 'NODATA')

            # Elevation cells that overlap the culverts will get the minimum elevation value
            mosaic_list = f"{project_dem_path};{culverts_min_value}"
            MosaicToNewRaster(mosaic_list, scratch_gdb, 'Hydro_DEM', '#', '32_BIT_FLOAT', dem_cell_size, '1', 'LAST')

            hydro_dem_fill = Fill(hydro_dem_temp)

    else:
        AddMsgAndPrint('\nNo culverts within project AOI...', log_file_path=log_file_path)
        hydro_dem_fill = Fill(project_dem_path)

    ### Create Flow Direction Grid ###
    SetProgressorLabel('Creating Flow Direction...')
    AddMsgAndPrint('\nCreating Flow Direction...', log_file_path=log_file_path)
    flow_direction = FlowDirection(hydro_dem_fill, 'NORMAL')
    flow_direction.save(flow_dir_path)

    ### Create Flow Accumulation Grid ###
    SetProgressorLabel('Creating Flow Accumulation...')
    AddMsgAndPrint('\nCreating Flow Accumulation...', log_file_path=log_file_path)
    flow_accumulation = FlowAccumulation(flow_dir_path, data_type='INTEGER')
    flow_accumulation.save(flow_accum_path)
    # Compute a histogram for the FlowAccumulation layer so that the full range of values are captured for subsequent stream generation
    # This tries to fix a bug of the primary channel not generating for large watersheds with high values in flow accumulation grid
    CalculateStatistics(flow_accum_path)

    ### Create Stream Link ###
    if stream_threshold > 0:
        # created using pixels that have a flow accumulation greater than the user-specified acre threshold
        acre_threshold = round((stream_threshold * 4046.8564224)/(dem_cell_size**2))

        # Select all cells that are greater than or equal to the acre stream threshold value
        con_flow_accumulation = Con(flow_accum_path, flow_accum_path, where_clause=f"Value >= {str(acre_threshold)}")

        # Create Stream Link Works
        SetProgressorLabel('Creating Stream Link...')
        AddMsgAndPrint('\nCreating Stream Link...', log_file_path=log_file_path)
        stream_link = StreamLink(con_flow_accumulation, flow_dir_path)

    # All values in Flow Accumulation will be used to create stream link
    else:
        SetProgressorLabel('Creating Stream Link...')
        AddMsgAndPrint('\nCreating Stream Link...', log_file_path=log_file_path)
        stream_link = StreamLink(flow_accum_path, flow_dir_path)

    ### Convert Raster to Stream Network ###
    SetProgressorLabel('Creating Stream Network...')
    AddMsgAndPrint('\nCreating Stream Network...', log_file_path=log_file_path)
    StreamToFeature(stream_link, flow_dir_path, streams_path, 'SIMPLIFY')

    ### Add Outputs to Map ###
    SetParameterAsText(3, streams_path)
    SetParameterAsText(4, culverts_path)

    ### Remove Digitized Layer (if present) ###
    for lyr in map.listLayers():
        if '01. Create Stream Network' in lyr.name:
            map.removeLayer(lyr)

    ### Compact Project GDB ###
    try:
        SetProgressorLabel('Compacting project geodatabase...')
        AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
        Compact(project_gdb)
    except:
        pass

    AddMsgAndPrint('\nCreate Stream Network completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Create Stream Network'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Create Stream Network'), 2)

finally:
    emptyScratchGDB(scratch_gdb)

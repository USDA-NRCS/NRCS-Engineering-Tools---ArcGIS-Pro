from getpass import getuser
from os import path
from sys import argv, exit
from time import ctime

from arcpy import AddFieldDelimiters, CheckExtension, CheckOutExtension, Describe, env, Exists, GetInstallInfo, GetMessages, \
    GetParameter, GetParameterAsText, SetParameterAsText, SetProgressorLabel
from arcpy.analysis import Buffer, Clip, Intersect
from arcpy.cartography import SmoothLine
from arcpy.conversion import PolygonToRaster, RasterToPolygon
from arcpy.da import SearchCursor, UpdateCursor
from arcpy.management import AddField, AssignDomainToField, CalculateField, Compact, CreateFeatureclass, Delete, DeleteField, \
    Dissolve, GetCount, TableToDomain
from arcpy.mp import ArcGISProject
from arcpy.sa import Con, FlowLength, GreaterThan, Minus, Plus, Slope, StreamLink, StreamToFeature, Watershed, ZonalStatistics, \
    ZonalStatisticsAsTable

from utils import AddMsgAndPrint, emptyScratchGDB, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, streams, outlets, watershed_name, create_flow_paths):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Create Watershed\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tStreams Layer: {streams}\n")
        f.write(f"\tOutlets Layer: {outlets}\n")
        f.write(f"\tWatershed Name: {watershed_name}\n")
        f.write(f"\tCreate Flow Lengths: {create_flow_paths}\n")


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
streams = GetParameterAsText(0)
outlets = GetParameterAsText(1)
watershed_name = GetParameterAsText(2).replace(' ','_')
create_flow_paths = GetParameter(3)

### Locate Project GDB ###
streams_path = Describe(streams).catalogPath
if 'EngPro.gdb' in streams_path and 'Streams' in streams_path:
    project_gdb = streams_path[:streams_path.find('.gdb')+4]
else:
    AddMsgAndPrint('\nThe selected Streams layer is not from an Engineering Tools project or is not compatible with this version of the toolbox. Exiting...', 2)
    exit()

### Set Paths and Variables ###
support_dir = path.dirname(argv[0])
support_gdb = path.join(support_dir, 'Support.gdb')
scratch_gdb = path.join(support_dir, 'Scratch.gdb')
project_workspace = path.dirname(project_gdb)
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")
project_fd = path.join(project_gdb, 'Layers')
project_aoi_path = path.join(project_fd, f"{project_name}_AOI")
project_dem_path = path.join(project_gdb, f"{project_name}_DEM")
flow_accum_path = path.join(project_gdb, 'Flow_Accumulation')
flow_dir_path = path.join(project_gdb, 'Flow_Direction')
outlets_name = f"{watershed_name}_Outlets"
outlets_path = path.join(project_fd, outlets_name)
watershed_path = path.join(project_fd, watershed_name)
flow_length_name = f"{watershed_name}_FlowPaths"
flow_length_path = path.join(project_fd, flow_length_name)
id_domain_table = path.join(support_gdb, 'ID_TABLE')
reach_domain_table = path.join(support_gdb, 'REACH_TYPE')
outlet_buffer_temp = path.join(scratch_gdb, 'Outlet_Buffer')
pour_point_temp = path.join(scratch_gdb, 'Pour_Point')
watershed_temp = path.join(scratch_gdb, 'Watershed_Temp')
lp_smooth_temp = path.join(scratch_gdb, 'LP_Smooth')
longest_path_temp = path.join(scratch_gdb, 'Longpath_Temp')
slope_stats_temp = path.join(scratch_gdb, 'Slope_Stats')

### Validate Required Datasets Exist ###
if not Exists(project_dem_path):
    AddMsgAndPrint('\nThe project DEM was not found. Exiting...', 2)
    exit()
if not Exists(flow_accum_path):
    AddMsgAndPrint('\nThe project Flow Accumulation Grid was not found. Exiting...', 2)
    exit()
if not Exists(flow_dir_path):
    AddMsgAndPrint('\nThe project Flow Direction Grid was not found. Exiting...', 2)
    exit()
if not Exists(streams_path):
    AddMsgAndPrint('\nThe selected Streams feature class was not found. Exiting...', 2)
    exit()
if not int(GetCount(outlets).getOutput(0)) > 0:
    AddMsgAndPrint('\nAt least one Pour Point must be used. Exiting...', 2)
    exit()
if Describe(outlets).shapeType != 'Polyline':
    AddMsgAndPrint('\nThe Pour Point layer must be Polyline geometry. Exiting...', 2)
    exit()
if Exists(watershed_path):
    AddMsgAndPrint(f"\nWatershed name: {watershed_name} already exists in project geodatabase and will be overwritten...", 1)

### ESRI Environment Settings ###
dem_desc = Describe(project_dem_path)
dem_cell_size = dem_desc.meanCellWidth
env.overwriteOutput = True
env.resamplingMethod = 'BILINEAR'
env.pyramid = 'PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP'
env.parallelProcessingFactor = '75%'
env.extent = 'MAXOF'
env.cellSize = dem_cell_size
env.snapRaster = project_dem_path
env.outputCoordinateSystem = dem_desc.spatialReference
env.workspace = project_gdb

try:
    removeMapLayers(map, [outlets_name, watershed_name, flow_length_name])
    logBasicSettings(log_file_path, streams, outlets, watershed_name, create_flow_paths)

    ### Clip Outlets to AOI ###
    if Describe(outlets).catalogPath != outlets_path:
        SetProgressorLabel('Clipping outlets to project AOI layer...')
        AddMsgAndPrint('\nClipping outlets to project AOI layer...', log_file_path=log_file_path)
        Clip(outlets, project_aoi_path, outlets_path)
    else:
        AddMsgAndPrint('\nExisting project outlets layer used as input...', log_file_path=log_file_path)

    # Validate AOI contains at least one outlet after clip
    if int(GetCount(outlets_path).getOutput(0)) < 1:
        AddMsgAndPrint('\nThere were no outlets digitized within the project AOI. Exiting...', 2, log_file_path)
        Delete(outlets_path)
        exit()

    ### Delineate Watershed(s) from Outlets ###
    SetProgressorLabel('Delineating Watershed(s)...')
    AddMsgAndPrint('\nDelineating Watershed(s)...', log_file_path=log_file_path)

    # Add dummy field for buffer dissolve and raster conversion using OBJECTID (which becomes subbasin ID)
    AddField(outlets_path, 'IDENT', 'DOUBLE')
    CalculateField(outlets_path, 'IDENT', f"!{Describe(outlets_path).OIDFieldName}!", 'PYTHON3')

    # Buffer outlet features by  raster cell size
    Buffer(outlets_path, outlet_buffer_temp, f"{str(dem_cell_size)} Meters", 'FULL', 'ROUND', 'LIST', 'IDENT')

    # Convert bufferd outlet to raster
    PolygonToRaster(outlet_buffer_temp, 'IDENT', pour_point_temp, 'MAXIMUM_AREA', 'NONE', dem_cell_size)

    # Delete intermediate data
    DeleteField(outlets_path, 'IDENT')

    # Create Watershed Raster using the raster pour point
    watershed_grid = Watershed(flow_dir_path, pour_point_temp, 'VALUE')

    # Convert results to simplified polygon
    RasterToPolygon(watershed_grid, watershed_temp, 'SIMPLIFY', 'VALUE')

    # Dissolve watershed_temp by GRIDCODE or grid_code
    Dissolve(watershed_temp, watershed_path, 'GRIDCODE', '', 'MULTI_PART', 'DISSOLVE_LINES')
    AddMsgAndPrint(f"\nCreated {str(int(GetCount(watershed_path).getOutput(0)))} Watershed(s) from {outlets_name}...", log_file_path=log_file_path)
    env.mask = watershed_path

    # Add Subbasin Field in watershed and calculate it to be the same as GRIDCODE
    AddField(watershed_path, 'Subbasin', 'LONG')
    CalculateField(watershed_path, 'Subbasin', '!GRIDCODE!', 'PYTHON3')
    DeleteField(watershed_path, 'GRIDCODE')

    # Add Acres Field in watershed and calculate them and notify the user
    AddField(watershed_path, 'Acres', 'DOUBLE')
    CalculateField(watershed_path, 'Acres', "!shape!.getArea('PLANAR', 'ACRES')", 'PYTHON3')

    ### Flow Length Analysis ###
    if create_flow_paths:
        SetProgressorLabel('Calculating watershed flow path(s)...')
        AddMsgAndPrint('\nCalculating watershed flow path(s)...', log_file_path=log_file_path)
        try:
            # Derive Longest flow path for each subbasin
            # Create Longest Path Feature Class
            CreateFeatureclass(project_fd, flow_length_name, 'POLYLINE')
            AddField(flow_length_path, 'Subbasin', 'LONG')
            AddField(flow_length_path, 'Reach', 'LONG')
            AddField(flow_length_path, 'Type', 'TEXT')
            AddField(flow_length_path, 'Length_ft', 'DOUBLE')

            # Calculate total upstream flow length on FlowDir grid
            upstream_grid = FlowLength(flow_dir_path, 'UPSTREAM')

            # Calculate total downsteam flow length on FlowDir grid
            downstream_grid = FlowLength(flow_dir_path, 'DOWNSTREAM')

            # Sum total upstream and downstream flow lengths
            sum_grid = Plus(upstream_grid, downstream_grid)

            # Get Maximum downstream flow length in each subbasin
            downstream_max_grid = ZonalStatistics(watershed_path, 'Subbasin', downstream_grid, 'MAXIMUM', 'DATA')

            # Subtract tolerance from Maximum flow length -- where do you get tolerance from?
            minus_grid = Minus(downstream_max_grid, 0.3)

            # Extract cells with positive difference to isolate longest flow path(s)
            longest_path = GreaterThan(sum_grid, minus_grid)
            longest_path_extract = Con(longest_path, longest_path, '', 'VALUE = 1')

            # Try to use Stream to Feature process to convert the raster Con result to a line (DUE TO 10.5.0 BUG) TODO: Still relevant here?
            longest_path_stream_link = StreamLink(longest_path_extract, flow_dir_path)
            StreamToFeature(longest_path_stream_link, flow_dir_path, longest_path_temp, 'NO_SIMPLIFY')

            # Smooth and Dissolve results
            SmoothLine(longest_path_temp, lp_smooth_temp, 'PAEK', '100 Feet', 'FIXED_CLOSED_ENDPOINT', 'NO_CHECK')

            # Intersect with watershed to get subbasin ID
            Intersect(lp_smooth_temp + '; ' + watershed_path, longest_path_temp, 'ALL', '', 'INPUT')

            # Dissolve to create single lines for each subbasin
            Dissolve(longest_path_temp, flow_length_path, 'Subbasin', '', 'MULTI_PART', 'DISSOLVE_LINES')

            # Add Fields / attributes & calculate length in feet
            AddField(flow_length_path, 'Reach', 'SHORT')
            CalculateField(flow_length_path, 'Reach', f"!{Describe(flow_length_path).OIDFieldName}!", 'PYTHON3')

            AddField(flow_length_path, 'Type', 'TEXT')
            CalculateField(flow_length_path, 'Type', "'Natural Watercourse'", 'PYTHON3')

            AddField(flow_length_path, 'Length_ft', 'DOUBLE')
            CalculateField(flow_length_path, 'Length_ft', "!shape!.getLength('PLANAR', 'FEET')", 'PYTHON3')

            # Set up Domains
            domains = Describe(project_gdb).domains
            if not 'Reach_Domain' in domains:
                TableToDomain(id_domain_table, 'IDENT', 'ID_DESC', project_gdb, 'Reach_Domain', 'Reach_Domain', 'REPLACE')
            if not 'Type_Domain' in domains:
                TableToDomain(reach_domain_table, 'TYPE', 'TYPE', project_gdb, 'Type_Domain', 'Type_Domain', 'REPLACE')

            # Assign domain to flow length fields for User Edits...
            AssignDomainToField(flow_length_path, 'Reach', 'Reach_Domain')
            AssignDomainToField(flow_length_path, 'TYPE', 'Type_Domain')

        except:
            # If Calc LHL fails prompt user to delineate manually and continue...capture error for reference
            AddMsgAndPrint('\nAn error occured while calculating Flow Path(s).\nYou will have to trace your stream network to create them manually. Continuing...\n' + GetMessages(2), 1, log_file_path=log_file_path)

    ### Calculate Average Slope ###
    SetProgressorLabel('Calculating average slope...')
    AddMsgAndPrint('\nCalculating average slope...', log_file_path=log_file_path)
    slope_grid = Slope(project_dem_path, 'PERCENT_RISE', 0.3048) # Z-factor Intl Feet to Meters
    ZonalStatisticsAsTable(watershed_path, 'Subbasin', slope_grid, slope_stats_temp, 'DATA')

    AddMsgAndPrint('\nWatershed Results:', log_file_path=log_file_path)
    AddMsgAndPrint(f"\tUser Watershed: {str(watershed_name)}", log_file_path=log_file_path)

    AddField(watershed_path, 'Avg_Slope', 'DOUBLE')
    with UpdateCursor(watershed_path, ['Subbasin','Avg_Slope','Acres','SHAPE@AREA']) as cursor:
        for row in cursor:
            subbasin_number = row[0]
            where_clause = (u'{} = ' + str(subbasin_number)).format(AddFieldDelimiters(slope_stats_temp, 'Subbasin'))
            avg_slope = [row[0] for row in SearchCursor(slope_stats_temp, ['MEAN'], where_clause=where_clause)][0]
            row[1] = avg_slope
            cursor.updateRow(row)

            # Inform the user of Watershed Acres, area and avg. slope
            AddMsgAndPrint(f"\n\tSubbasin: {str(subbasin_number)}", log_file_path=log_file_path)
            AddMsgAndPrint(f"\t\tAcres: {str(round(row[2], 2))}", log_file_path=log_file_path)
            AddMsgAndPrint(f"\t\tArea: {str(round(row[3], 2))} Sq. Meters", log_file_path=log_file_path)
            AddMsgAndPrint(f"\t\tAvg. Slope: {str(round(avg_slope, 2))}", log_file_path=log_file_path)

    ### Add Outputs to Map ###
    SetProgressorLabel('Adding output layers to map...')
    AddMsgAndPrint('\nAdding output layers to map...', log_file_path=log_file_path)
    SetParameterAsText(4, outlets_path)
    SetParameterAsText(5, watershed_path)
    if create_flow_paths:
        SetParameterAsText(6, flow_length_path)

    ### Remove Digitized Layer (if present) ###
    for lyr in map.listLayers():
        if '02. Create Watershed' in lyr.name:
            map.removeLayer(lyr)

    ### Compact Project GDB ###
    try:
        SetProgressorLabel('Compacting project geodatabase...')
        AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
        Compact(project_gdb)
    except:
        pass

    AddMsgAndPrint('\nCreate Watershed completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Create Watershed'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Create Watershed'), 2)

finally:
    emptyScratchGDB(scratch_gdb)

from getpass import getuser
from os import path
from sys import argv, exit
from time import ctime

from arcpy import AddFieldDelimiters, CheckExtension, CheckOutExtension, Describe, env, Exists, GetInstallInfo, \
    GetParameterAsText, ListFields, SetParameterAsText, SetProgressorLabel
from arcpy.analysis import Buffer, Clip
from arcpy.conversion import PolygonToRaster, RasterToPolygon
from arcpy.da import SearchCursor, UpdateCursor
from arcpy.management import AddField, CalculateField, Compact, Delete, DeleteField, Dissolve, GetCount
from arcpy.mp import ArcGISProject
from arcpy.sa import Slope, Watershed, ZonalStatisticsAsTable

from utils import AddMsgAndPrint, deleteESRIAddedFields, emptyScratchGDB, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, streams, outlets, basins_name):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Create WASCOB Basins\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tStreams Layer: {streams}\n")
        f.write(f"\tOutlets Layer: {outlets}\n")
        f.write(f"\tWatershed Name: {basins_name}\n")


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
basins_name = GetParameterAsText(2).replace(' ','_')

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
flow_accum_path = path.join(project_gdb, 'Flow_Accumulation')
flow_dir_path = path.join(project_gdb, 'Flow_Direction')
wascob_gdb_path = path.join(project_workspace, f"{project_name}_WASCOB.gdb")
wascob_fd_path = path.join(wascob_gdb_path, 'Layers')
wascob_dem_path = path.join(wascob_gdb_path, f"{project_name}_DEM_WASCOB")
basins_path = path.join(project_fd, basins_name)
outlets_name = f"{basins_name}_Outlets"
outlets_path = path.join(wascob_fd_path, outlets_name)
outlet_buffer_temp = path.join(scratch_gdb, 'Outlet_Buffer')
pour_point_temp = path.join(scratch_gdb, 'Pour_Point')
watershed_temp = path.join(scratch_gdb, 'Watershed_Temp')
outlet_stats_temp = path.join(scratch_gdb, 'Outlet_Stats')
slope_stats_temp = path.join(scratch_gdb, 'Slope_Stats')

### Validate Required Datasets Exist ###
if not Exists(wascob_dem_path):
    AddMsgAndPrint('\nThe WASCOB project DEM was not found. Exiting...', 2)
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
#TODO: Naming consistency? we call this Embankments, Pour Points, and Outlets?
if Describe(outlets).shapeType != 'Polyline':
    AddMsgAndPrint('\nThe Pour Point layer must be Polyline geometry. Exiting...', 2)
    exit()
if Exists(basins_path):
    AddMsgAndPrint(f"\nBasins name: {basins_name} already exists in project's WASCOB geodatabase and will be overwritten...", 1)

### ESRI Environment Settings ###
dem_desc = Describe(wascob_dem_path)
dem_sr = dem_desc.spatialReference
dem_cell_size = dem_desc.meanCellWidth
dem_linear_units = dem_sr.linearUnitName
env.overwriteOutput = True
env.resamplingMethod = 'BILINEAR'
env.pyramid = 'PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP'
env.parallelProcessingFactor = '75%'
env.extent = 'MAXOF'
env.cellSize = dem_cell_size
env.snapRaster = wascob_dem_path
env.outputCoordinateSystem = dem_sr

### Validate DEM XY Units ###
if dem_linear_units in ['Meter', 'Meters']:
    linear_units = 'Meters'
    z_factor = 0.3048
elif dem_linear_units in ['Foot', 'Foot_US']:
    linear_units = 'Feet'
    z_factor = 1
else:
    AddMsgAndPrint(f"\nUnsupported DEM linear units {dem_linear_units}. Exiting...", 2)
    exit()

try:
    removeMapLayers(map, [outlets_name, basins_name])
    logBasicSettings(log_file_path, streams, outlets, basins_name)

    ### Clip Outlets to AOI ###
    if Describe(outlets).catalogPath != outlets_path:
        SetProgressorLabel('Clipping outlets to project AOI layer...')
        AddMsgAndPrint('\nClipping outlets to project AOI layer...', log_file_path=log_file_path)
        Clip(outlets, project_aoi_path, outlets_path)
    else:
        AddMsgAndPrint('\nExisting WASCOB project outlets layer used as input...', log_file_path=log_file_path)

    # Validate AOI contains at least one outlet after clip
    if int(GetCount(outlets_path).getOutput(0)) < 1:
        AddMsgAndPrint('\nThere were no outlets digitized within the project AOI. Exiting...', 2, log_file_path)
        Delete(outlets_path)
        exit()

    ### Add Fields to Outlets Layer ###
    fields = ListFields(outlets_path)
    if 'Subbasin' not in fields:
        AddField(outlets_path, 'Subbasin', 'LONG')
    if 'MaxElev' not in fields:
        AddField(outlets_path, 'MaxElev', 'DOUBLE')
    if 'MinElev' not in fields:
        AddField(outlets_path, 'MinElev', 'DOUBLE')
    if 'MeanElev' not in fields:
        AddField(outlets_path, 'MeanElev', 'DOUBLE')
    if 'LengthFt' not in fields:
        AddField(outlets_path, 'LengthFt', 'DOUBLE')

    ### Calculate Subbasin and Length Fields ###
    CalculateField(outlets_path, 'Subbasin', f"!{Describe(outlets_path).OIDFieldName}!", 'PYTHON3')
    CalculateField(outlets_path, 'LengthFt', "!shape!.getLength('PLANAR', 'FEET')", 'PYTHON3')

    #TODO: Original Create Watershed does not multiple by 2 here
    # Buffer outlet features by raster cell size
    buffer_dist = f"{(dem_cell_size * 2)} {linear_units}"
    Buffer(outlets_path, outlet_buffer_temp, buffer_dist, 'FULL', 'ROUND', 'LIST', 'Subbasin')

    # Get Reference Line Elevation Properties (Uses WASCOB DEM which is vertical feet by 1/10ths)
    ZonalStatisticsAsTable(outlet_buffer_temp, 'Subbasin', wascob_dem_path, outlet_stats_temp, 'DATA')

    # Update the outlet FC with the zonal stats
    with UpdateCursor(outlets_path, ['Subbasin','MinElev','MaxElev','MeanElev']) as cursor:
        for row in cursor:
            subBasinNumber = row[0]
            expression = (u'{} = ' + str(subBasinNumber)).format(AddFieldDelimiters(outlet_stats_temp, 'Subbasin'))
            stats = [(row[0],row[1],row[2]) for row in SearchCursor(outlet_stats_temp,['MIN','MAX','MEAN'], where_clause=expression)][0]
            row[1] = stats[0] # Min Elev
            row[2] = stats[1] # Max Elev
            row[3] = stats[2] # Mean Elev
            cursor.updateRow(row)

    # Convert bufferd outlet to raster
    SetProgressorLabel("Converting Buffered Reference Line to Raster")
    PolygonToRaster(outlet_buffer_temp, 'Subbasin', pour_point_temp, 'MAXIMUM_AREA', 'NONE', dem_cell_size)

    # Create Watershed Raster using the raster pour point
    watershed_grid = Watershed(flow_dir_path, pour_point_temp, 'VALUE')

    # Convert results to simplified polygon
    RasterToPolygon(watershed_grid, watershed_temp, 'SIMPLIFY', 'VALUE')

    # Dissolve watershedTemp by GRIDCODE or grid_code
    Dissolve(watershed_temp, basins_path, 'GRIDCODE', '', 'MULTI_PART', 'DISSOLVE_LINES')
    AddMsgAndPrint(f"\nCreated {str(int(GetCount(basins_path).getOutput(0)))} Watershed(s) from {outlets_name}...", log_file_path=log_file_path)
    env.mask = basins_path

    # Add Subbasin Field in watershed and calculate it to be the same as GRIDCODE
    AddField(basins_path, 'Subbasin', 'LONG')
    CalculateField(basins_path, 'Subbasin', '!GRIDCODE!', 'PYTHON3')
    DeleteField(basins_path, 'GRIDCODE')

    # Add Acres Field in watershed and calculate them and notify the user
    AddField(basins_path, 'Acres', 'DOUBLE')
    CalculateField(basins_path, 'Acres', "!shape!.getArea('PLANAR', 'ACRES')", 'PYTHON3')

    #NOTE: Create DEM tool already does this, project_dem is "smoothed"
    # Run Focal Statistics on the DEM_aoi to remove exteraneous values
    # SetProgressorLabel("Recreating " + projectName  + "_DEMsmooth")
    # outFocalStats = FocalStatistics(ProjectDEM, "RECTANGLE 3 3 CELL","MEAN","DATA")
    # outFocalStats.save(DEMsmooth)

    ### Calculate Average Slope ###
    SetProgressorLabel('Calculating average slope...')
    AddMsgAndPrint('\nCalculating average slope...', log_file_path=log_file_path)
    slope_grid = Slope(wascob_dem_path, 'PERCENT_RISE', z_factor)
    ZonalStatisticsAsTable(basins_path, 'Subbasin', slope_grid, slope_stats_temp, 'DATA')

    AddField(basins_path, 'Avg_Slope', 'DOUBLE')
    with UpdateCursor(basins_path, ['Subbasin','Avg_Slope','Acres','SHAPE@AREA']) as cursor:
        for row in cursor:
            subbasin_number = row[0]
            where_clause = (u'{} = ' + str(subbasin_number)).format(AddFieldDelimiters(slope_stats_temp, 'Subbasin'))
            avg_slope = [row[0] for row in SearchCursor(slope_stats_temp, ['MEAN'], where_clause=where_clause)][0]
            row[1] = avg_slope
            cursor.updateRow(row)

            # Inform the user of Watershed Acres, area and avg. slope
            AddMsgAndPrint(f"\n\tSubbasin: {str(subbasin_number)}", log_file_path=log_file_path)
            AddMsgAndPrint(f"\t\tAcres: {str(round(row[2], 2))}", log_file_path=log_file_path)
            AddMsgAndPrint(f"\t\tArea: {str(round(row[3], 2))} Sq. {linear_units}", log_file_path=log_file_path)
            AddMsgAndPrint(f"\t\tAvg. Slope: {str(round(avg_slope, 2))}", log_file_path=log_file_path)
            if row[2] > 40:
                AddMsgAndPrint(f"\t\tSubbasin {subbasin_number} is greater than the 40 acre 638 standard.", 1)
                AddMsgAndPrint('\t\tConsider re-delineating to split basins or move upstream.', 1)

    ### Delete Fields Added if Digitized ###
    deleteESRIAddedFields(outlets_path)

    ### Add Outputs to Map ###
    SetProgressorLabel('Adding output layers to map...')
    AddMsgAndPrint('\nAdding output layers to map...', log_file_path=log_file_path)
    SetParameterAsText(3, outlets_path)
    SetParameterAsText(4, basins_path)

    ### Remove Digitized Layer (if present) ###
    for lyr in map.listLayers():
        if '02. Create WASCOB Basins' in lyr.name:
            map.removeLayer(lyr)

    ### Compact Project GDB ###
    try:
        SetProgressorLabel('Compacting project geodatabase...')
        AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
        Compact(wascob_gdb_path)
    except:
        pass

    AddMsgAndPrint('\nCreate WASCOB Basins completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Create WASCOB Basins'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Create WASCOB Basins'), 2)

finally:
    emptyScratchGDB(scratch_gdb)

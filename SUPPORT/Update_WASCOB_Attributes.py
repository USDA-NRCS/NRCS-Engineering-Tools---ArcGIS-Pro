from getpass import getuser
from math import floor
from os import path
from sys import argv, exit
from time import ctime

from arcpy import AddFieldDelimiters, CheckExtension, CheckOutExtension, Describe, env, Exists, GetInstallInfo, \
    GetParameterAsText, ListFields, SetProgressorLabel
from arcpy.analysis import Buffer
from arcpy.da import SearchCursor, UpdateCursor
from arcpy.ddd import SurfaceVolume
from arcpy.management import AddField, Append, CalculateField, Compact, CopyRows, Delete, DeleteRows, GetRasterProperties, \
    MakeFeatureLayer, SelectLayerByAttribute
from arcpy.mp import ArcGISProject
from arcpy.sa import ExtractByMask, Slope, ZonalStatisticsAsTable

from utils import AddMsgAndPrint, emptyScratchGDB, errorMsg


def logBasicSettings(log_file_path, input_basins):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Update WASCOB Attributes\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tWASCOB Basins Layer: {input_basins}\n")


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
if CheckExtension('3d') == 'Available':
    CheckOutExtension('3d')
else:
    AddMsgAndPrint('\n3D Analyst Extension not enabled. Please enable 3D Analyst from Project, Licensing, Configure licensing options. Exiting...', 2)
    exit()

### Input Parameters ###
input_basins = GetParameterAsText(0)

### Locate Project GDB ###
basins_path = Describe(input_basins).catalogPath
basins_name = path.basename(basins_path)
if '_WASCOB.gdb' in basins_path:
    wascob_gdb = basins_path[:basins_path.find('.gdb')+4]
else:
    AddMsgAndPrint('\nThe selected WASCOB Basins layer is not from an Engineering Tools project or is not compatible with this version of the toolbox. Exiting...', 2)
    exit()

### Set Paths and Variables ###
support_dir = path.dirname(argv[0])
scratch_gdb = path.join(support_dir, 'Scratch.gdb')
project_workspace = path.dirname(wascob_gdb)
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")
wascob_fd = path.join(wascob_gdb, 'Layers')
wascob_dem_path = path.join(wascob_gdb, f"{project_name}_DEM_WASCOB")
embankments_name = f"{basins_name}_Embankments"
embankments_path = path.join(wascob_fd, embankments_name)
embankment_buffer_temp = path.join(scratch_gdb, 'Embankment_Buffer')
embankment_stats_temp = path.join(scratch_gdb, 'Embankment_Stats')
slope_stats_temp = path.join(scratch_gdb, 'Slope_Stats')
subbasin_mask_temp = path.join(scratch_gdb, 'Subbasin_Mask')
storage_table_temp = path.join(scratch_gdb, 'Storage')
storage_dbf_template = path.join(support_dir, 'storage.dbf')
tables_dir = path.join(project_workspace, 'GIS_Output', 'Tables')
storage_dbf = path.join(tables_dir, 'Storage.dbf')
embankments_dbf = path.join(tables_dir, 'Embankments.dbf')

### Validate Required Datasets Exist ###
if not Exists(wascob_dem_path):
    AddMsgAndPrint('\nThe WASCOB project DEM was not found. Exiting...', 2)
    exit()
if not Exists(embankments_path):
    AddMsgAndPrint('\nThe WASCOB Embankments layer was not found. Exiting...', 2)
    exit()

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
    to_acres = 4046.8564224
    to_square_feet = 0.092903
    to_acre_foot = 1233.48184
    to_cubic_meters = 1
    to_cubic_feet = 35.3147
elif dem_linear_units in ['Foot', 'Foot_US']:
    linear_units = 'Feet'
    z_factor = 1
else:
    AddMsgAndPrint(f"\nUnsupported DEM linear units {dem_linear_units}. Exiting...", 2)
    exit()

try:
    logBasicSettings(log_file_path, input_basins)

    ### Update Basin Acreage ###
    SetProgressorLabel('Updating basin acreage...')
    AddMsgAndPrint('\nUpdating basin acreage...', log_file_path=log_file_path)
    if 'Acres' not in [f.name for f in ListFields(basins_path)]:
        AddField(basins_path, 'Acres', 'DOUBLE')
    CalculateField(basins_path, 'Acres', "!shape!.getArea('PLANAR', 'ACRES')", 'PYTHON3')

    ### Update Average Slope ###
    SetProgressorLabel('Updating average slope...')
    AddMsgAndPrint('\nUpdating average slope...', log_file_path=log_file_path)
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

    ### Update Embankment Attributes ###
    fields = [f.name for f in ListFields(embankments_path)]
    if 'Subbasin' not in fields:
        AddField(embankments_path, 'Subbasin', 'LONG')
    if 'MaxElev' not in fields:
        AddField(embankments_path, 'MaxElev', 'DOUBLE')
    if 'MinElev' not in fields:
        AddField(embankments_path, 'MinElev', 'DOUBLE')
    if 'MeanElev' not in fields:
        AddField(embankments_path, 'MeanElev', 'DOUBLE')
    if 'LengthFt' not in fields:
        AddField(embankments_path, 'LengthFt', 'DOUBLE')

    CalculateField(embankments_path, 'Subbasin', f"!{Describe(embankments_path).OIDFieldName}!", 'PYTHON3')
    CalculateField(embankments_path, 'LengthFt', "!shape!.getLength('PLANAR', 'FEET')", 'PYTHON3')

    # Buffer embankment features by raster cell size
    buffer_dist = f"{(dem_cell_size * 2)} {linear_units}"
    Buffer(embankments_path, embankment_buffer_temp, buffer_dist, 'FULL', 'ROUND', 'LIST', 'Subbasin')

    # Get Reference Line Elevation Properties (Uses WASCOB DEM which is vertical feet by 1/10ths)
    ZonalStatisticsAsTable(embankment_buffer_temp, 'Subbasin', wascob_dem_path, embankment_stats_temp, 'DATA')

    CopyRows(storage_dbf_template, storage_dbf)

    # Update the embankment with subbasin and elevation values
    with UpdateCursor(embankments_path, ['Subbasin','MinElev','MaxElev','MeanElev']) as cursor:
        for row in cursor:
            subbasin_number = row[0]
            expression = (u'{} = ' + str(subbasin_number)).format(AddFieldDelimiters(embankment_stats_temp, 'Subbasin'))
            stats = [(row[0],row[1],row[2]) for row in SearchCursor(embankment_stats_temp,['MIN','MAX','MEAN'], where_clause=expression)][0]
            row[1] = stats[0] # Min Elev
            row[2] = stats[1] # Max Elev
            row[3] = stats[2] # Mean Elev

            MakeFeatureLayer(input_basins, 'subbasin_mask_lyr', f"Subbasin = {subbasin_number}")
            subbasin_raster = ExtractByMask(wascob_dem_path, 'subbasin_mask_lyr')

            AddMsgAndPrint(f"\n\tRetrieving Minumum Elevation for subbasin {subbasin_number}")
            max_elev = stats[1]
            min_elev = round(float(GetRasterProperties(subbasin_raster, 'MINIMUM').getOutput(0)), 1)
            total_elev = round(float(max_elev - min_elev), 1)
            remainder = total_elev - floor(total_elev)
            plane_height = min_elev + remainder

            output_txt = path.join(tables_dir, f"subbasin_{subbasin_number}.txt")
            with open(output_txt, 'w') as file:
                file.write('Dataset, Plane_Heig, Reference, Z_Factor, Area_2D, Area_3D, Volume, Subbasin\n')

            while plane_height <= max_elev:
                AddMsgAndPrint(f"\n\tCalculating storage at elevation {round(plane_height,1)}")
                SurfaceVolume(subbasin_raster, output_txt, 'BELOW', plane_height, 1)
                plane_height += 1

            CopyRows(output_txt, storage_table_temp)
            CalculateField(storage_table_temp, 'Subbasin', subbasin_number, 'PYTHON3')
            Append(storage_table_temp, storage_dbf, 'NO_TEST')

            cursor.updateRow(row)

    CopyRows(embankments_path, embankments_dbf)

    SelectLayerByAttribute(input_basins, 'CLEAR_SELECTION')

    ### Finalize Storage Table ###
    SetProgressorLabel('Finalizing storage table...')
    AddMsgAndPrint('\nFinalizing storage table...', log_file_path=log_file_path)

    if Exists(storage_dbf):
        DeleteRows(storage_dbf)

    CopyRows(storage_table_temp, storage_dbf)

    AddField(storage_dbf, 'ELEV_FEET', 'DOUBLE', '5', '1')
    AddField(storage_dbf, 'DEM_ELEV', 'DOUBLE')
    AddField(storage_dbf, 'POOL_ACRES', 'DOUBLE')
    AddField(storage_dbf, 'POOL_SQFT', 'DOUBLE')
    AddField(storage_dbf, 'ACRE_FOOT', 'DOUBLE')
    AddField(storage_dbf, 'CUBIC_FEET', 'DOUBLE')
    AddField(storage_dbf, 'CUBIC_MTRS', 'DOUBLE')

    elevation_feet = 'round(!Plane_Heig!*3.28084,1)'
    dem_elevation = 'round(!Plane_Heig!)'
    area_acres = 'round(!Area_2D! /' + str(to_acres) + ',1)'
    area_sqft = 'round(!Area_2D! /' + str(to_square_feet) + ',1)'
    volume_acre_foot = 'round(!Volume! /' + str(to_acre_foot) + ',1)'
    volume_cubic_feet = 'round(!Volume! *' + str(to_cubic_feet) + ',1)'
    volume_cubic_meters = 'round(!Volume! *' + str(to_cubic_meters) + ',1)'

    CalculateField(storage_dbf, 'DEM_ELEV', dem_elevation, 'PYTHON3')
    CalculateField(storage_dbf, 'ELEV_FEET', elevation_feet, 'PYTHON3')
    CalculateField(storage_dbf, 'POOL_ACRES', area_acres, 'PYTHON3')
    CalculateField(storage_dbf, 'POOL_SQFT', area_sqft, 'PYTHON3')
    CalculateField(storage_dbf, 'ACRE_FOOT', volume_acre_foot, 'PYTHON3')
    CalculateField(storage_dbf, 'CUBIC_FEET', volume_cubic_feet, 'PYTHON3')
    CalculateField(storage_dbf, 'CUBIC_MTRS', volume_cubic_meters, 'PYTHON3')

    ### Clean Up Temp Datasets ###
    if Exists(storage_table_temp):
        Delete(storage_table_temp)
    if Exists(subbasin_raster):
        Delete(subbasin_raster)

    ### Compact Project GDB ###
    try:
        SetProgressorLabel('Compacting project geodatabase...')
        AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
        Compact(wascob_gdb)
    except:
        pass

    AddMsgAndPrint('\nUpdate WASCOB Attributes completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Update WASCOB Attributes'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Update WASCOB Attributes'), 2)

finally:
    emptyScratchGDB(scratch_gdb)

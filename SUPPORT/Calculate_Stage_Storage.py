from getpass import getuser
from os import path
from sys import argv, exit
from time import ctime

from arcpy import AlterAliasName, Describe, CheckExtension, CheckOutExtension, env, Exists, GetInstallInfo, GetParameterAsText, \
    GetParameter, ListFeatureClasses, SetParameterAsText, SetProgressorLabel
from arcpy.conversion import RasterToPolygon
from arcpy.da import SearchCursor
from arcpy.ddd import SurfaceVolume
from arcpy.management import AddField, CalculateField, Compact, CopyRows, Delete, Dissolve, GetCount, GetRasterProperties, Merge, TruncateTable
from arcpy.mp import ArcGISProject
from arcpy.sa import ExtractByMask, Int, SetNull, Times

from utils import AddMsgAndPrint, emptyScratchGDB, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, project_dem, input_pool, max_elevation, increment, create_pools_layer):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Calculate State Storage\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tProject DEM: {project_dem}\n")
        f.write(f"\tInput Pool Polygon: {input_pool}\n")
        f.write(f"\tMaximum Elevation: {max_elevation} Feet\n")
        f.write(f"\tAnalysis Increment: {increment} Feet\n")
        f.write(f"\tCreate Pool Polygons: {'Yes' if create_pools_layer else 'No'}\n")


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
project_dem = GetParameterAsText(0)
input_pool = GetParameterAsText(1)
max_elevation = float(GetParameterAsText(2))
analysis_increment = float(GetParameterAsText(3))
create_pools_layer = GetParameter(4)

### Locate Project GDB ###
project_dem_path = Describe(project_dem).CatalogPath
if 'EngPro.gdb' in project_dem_path and 'DEM' in project_dem_path:
    project_gdb = project_dem_path[:project_dem_path.find('.gdb')+4]
else:
    AddMsgAndPrint('\nThe selected DEM is not from an Engineering Tools project or is not compatible with this version of the toolbox. Exiting...', 2)
    exit()

### Validate Input Pool Count ###
if int(GetCount(input_pool).getOutput(0)) > 1:
    AddMsgAndPrint('\nThe input pool must be a single polygon feature. If using the project Watershed layer, select a single Subbasin. If using a different layer, dissolve it to create a single polygon, or select a single polygon and try again. Exiting...', 2)
    exit()

### Set Paths and Variables ###
support_dir = path.dirname(argv[0])
scratch_gdb = path.join(support_dir, 'Scratch.gdb')
project_workspace = path.dirname(project_gdb)
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")
project_fd = path.join(project_gdb, 'Layers')
input_pool_name = path.splitext(path.basename(input_pool))[0]
storage_table_temp = path.join(project_workspace, f"{input_pool_name}_StorageCSV.txt")
temp_pool = path.join(scratch_gdb, 'Temp_Pool')

# Include Subbasin number in output names if input polygon is Watershed layer
if '_Watershed' in input_pool_name:
    subbasin_number = [row[0] for row in SearchCursor(input_pool, ['Subbasin'])][0]
    output_pool_name = f"{input_pool_name}_{subbasin_number}_Pools"
    storage_table_name = f"{input_pool_name}_{subbasin_number}_Stage_Storage"
else:
    output_pool_name = f"{input_pool_name}_Pools"
    storage_table_name = f"{input_pool_name}_Stage_Storage"
output_pool_path = path.join(project_fd, output_pool_name)
storage_table_path = path.join(project_gdb, storage_table_name)

### ESRI Environment Settings ###
dem_desc = Describe(project_dem_path)
dem_cell_size = dem_desc.meanCellWidth
env.cellSize = dem_cell_size
env.snapRaster = project_dem_path
env.outputCoordinateSystem = dem_desc.spatialReference
env.resamplingMethod = 'BILINEAR'
env.pyramid = 'PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP'
env.parallelProcessingFactor = '75%'
env.extent = 'MINOF'
env.overwriteOutput = True

### Conversion Factors - Linear Units of DEM Meters ###
to_acres = 4046.8564224
to_square_feet = 0.092903
to_acre_foot = 1233.48184
to_cubic_meters = 1
to_cubic_feet = 35.3147

try:
    removeMapLayers(map, [output_pool_name, storage_table_name])
    logBasicSettings(log_file_path, project_dem, input_pool, max_elevation, analysis_increment, create_pools_layer)

    ### Clip DEM to Input Polygon and get Min/Max ###
    SetProgressorLabel('Clipping DEM to input pool polygon...')
    AddMsgAndPrint('\nClipping DEM to input pool polygon...', log_file_path=log_file_path)
    temp_dem = ExtractByMask(project_dem, input_pool)
    temp_dem_min = round(float(GetRasterProperties(temp_dem, 'MINIMUM').getOutput(0)))
    temp_dem_max = round(float(GetRasterProperties(temp_dem, 'MAXIMUM').getOutput(0)))
    if not temp_dem_min < max_elevation <= temp_dem_max:
        AddMsgAndPrint(f"\nThe maximum elevation value specified is not within range of your watershed-pool area:\n\tMinimum Elevation: {temp_dem_min} Feet\n\tMaximum Elevation: {temp_dem_max} Feet", 2, log_file_path)
        exit()

    ### Calculate Volume and Surface Area Incrementally ###
    SetProgressorLabel(f"Calulating volume and surface area every {analysis_increment} ft...")
    AddMsgAndPrint(f"\nCalulating volume and surface area every {analysis_increment} ft between {temp_dem_min} and {round(max_elevation)} ft...", log_file_path=log_file_path)
    AddMsgAndPrint(f"\n{round(((max_elevation-temp_dem_min)//analysis_increment)+1)} pools will be created...")

    # Convert DEM elevation units to meters for processing
    temp_dem_meters = Times(temp_dem, 0.3048)
    temp_dem_meters_min = round(float(GetRasterProperties(temp_dem_meters, 'MINIMUM').getOutput(0)))
    elevation_to_process = max_elevation * 0.3048
    increment_meters = analysis_increment * 0.3048

    while elevation_to_process > temp_dem_meters_min:
        SetProgressorLabel(f"Processing elevation {elevation_to_process}...")
        AddMsgAndPrint(f"\nProcessing elevation {elevation_to_process}...", log_file_path=log_file_path)

        SurfaceVolume(temp_dem_meters, storage_table_temp, 'BELOW', elevation_to_process, '1')

        if create_pools_layer:
            try:
                increment_pool_name = f"Pool_{str(round(elevation_to_process,1)).replace('.','_')}"
                increment_pool_path = path.join(scratch_gdb, increment_pool_name)

                # Create new raster of only values below an elevation value by nullifying cells above the desired elevation value
                above_elevation = SetNull(temp_dem_meters, temp_dem_meters, f"Value > {elevation_to_process}")

                # Multiply every pixel by 0 and convert to integer for vectorizing
                zeros = Times(above_elevation, 0)
                zero_int = Int(zeros)

                # Convert to polygon and dissolve
                RasterToPolygon(zero_int, temp_pool, 'NO_SIMPLIFY', 'VALUE')
                Dissolve(temp_pool, increment_pool_path)

                AddField(increment_pool_path, 'ELEV_FEET', 'DOUBLE')
                AddField(increment_pool_path, 'DEM_ELEV', 'DOUBLE')
                AddField(increment_pool_path, 'POOL_ACRES', 'DOUBLE')
                AddField(increment_pool_path, 'POOL_SQFT', 'DOUBLE')
                AddField(increment_pool_path, 'ACRE_FOOT', 'DOUBLE')
                AddField(increment_pool_path, 'CUBIC_FEET', 'DOUBLE')
                AddField(increment_pool_path, 'CUBIC_METERS', 'DOUBLE')

                # Open surface volume text file - last line should represent the last pool
                with open(storage_table_temp) as file:
                    lines = file.readlines()

                area2D = float(lines[len(lines)-1].split(',')[4])
                volume = float(lines[len(lines)-1].split(',')[6])

                elevation_feet = round(elevation_to_process*3.28084, 1)
                area_acres = round(area2D / to_acres, 1)
                area_sqft = round(area2D / to_square_feet, 1)
                volume_acre_foot = round(volume / to_acre_foot, 1)
                volume_cubic_meters = round(volume * to_cubic_meters, 1)
                volume_cubic_feet = round(volume * to_cubic_feet, 1)

                CalculateField(increment_pool_path, 'ELEV_FEET', elevation_feet, 'PYTHON3')
                CalculateField(increment_pool_path, 'DEM_ELEV', elevation_to_process, 'PYTHON3')
                CalculateField(increment_pool_path, 'POOL_ACRES', area_acres, 'PYTHON3')
                CalculateField(increment_pool_path, 'POOL_SQFT', area_sqft, 'PYTHON3')
                CalculateField(increment_pool_path, 'ACRE_FOOT', volume_acre_foot, 'PYTHON3')
                CalculateField(increment_pool_path, 'CUBIC_METERS', volume_cubic_meters, 'PYTHON3')
                CalculateField(increment_pool_path, 'CUBIC_FEET', volume_cubic_feet, 'PYTHON3')

                AddMsgAndPrint(f"\n\tCreated {increment_pool_name}:")
                AddMsgAndPrint(f"\t\tElevation {elevation_feet*3.28084} Feet")
                AddMsgAndPrint(f"\t\tArea: {area_sqft} Square Feet")
                AddMsgAndPrint(f"\t\tArea: {area_acres} Acres")
                AddMsgAndPrint(f"\t\tVolume: {volume_acre_foot} Acre Feet")
                AddMsgAndPrint(f"\t\tVolume: {volume_cubic_meters} Cubic Meters")
                AddMsgAndPrint(f"\t\tVolume: {volume_cubic_feet} Cubic Feet")

            except:
                AddMsgAndPrint(f"\nFailed to create pool at elevation: {elevation_to_process}. Exiting...", 2, log_file_path)
                AddMsgAndPrint(errorMsg('Calculate Stage Storage'), 2, log_file_path)
                exit()

        elevation_to_process = elevation_to_process - increment_meters

    ### Finalize Storage Table ###
    SetProgressorLabel('Finalizing storage table...')
    AddMsgAndPrint('\nFinalizing storage table...', log_file_path=log_file_path)

    if Exists(storage_table_path):
        TruncateTable(storage_table_path)

    CopyRows(storage_table_temp, storage_table_path)
    AlterAliasName(storage_table_path, storage_table_name)

    AddField(storage_table_path, 'ELEV_FEET', 'DOUBLE', '5', '1')
    AddField(storage_table_path, 'DEM_ELEV', 'DOUBLE')
    AddField(storage_table_path, 'POOL_ACRES', 'DOUBLE')
    AddField(storage_table_path, 'POOL_SQFT', 'DOUBLE')
    AddField(storage_table_path, 'ACRE_FOOT', 'DOUBLE')
    AddField(storage_table_path, 'CUBIC_FEET', 'DOUBLE')
    AddField(storage_table_path, 'CUBIC_METERS', 'DOUBLE')

    dem_elevation = 'round(!Plane_Height!)'
    elevation_feet = 'round(!Plane_Height!*3.28084,1)'
    area_acres = 'round(!Area_2D! /' + str(to_acres) + ',1)'
    area_sqft = 'round(!Area_2D! /' + str(to_square_feet) + ',1)'
    volume_acre_foot = 'round(!Volume! /' + str(to_acre_foot) + ',1)'
    volume_cubic_meters = 'round(!Volume! *' + str(to_cubic_meters) + ',1)'
    volume_cubic_feet = 'round(!Volume! *' + str(to_cubic_feet) + ',1)'

    CalculateField(storage_table_path, 'DEM_ELEV', dem_elevation,  'PYTHON3')
    CalculateField(storage_table_path, 'ELEV_FEET', elevation_feet, 'PYTHON3')
    CalculateField(storage_table_path, 'POOL_ACRES', area_acres, 'PYTHON3')
    CalculateField(storage_table_path, 'POOL_SQFT', area_sqft, 'PYTHON3')
    CalculateField(storage_table_path, 'ACRE_FOOT', volume_acre_foot, 'PYTHON3')
    CalculateField(storage_table_path, 'CUBIC_METERS', volume_cubic_meters,  'PYTHON3')
    CalculateField(storage_table_path, 'CUBIC_FEET', volume_cubic_feet,  'PYTHON3')

    ### Clean Up Temp Datasets ###
    if Exists(storage_table_temp):
        Delete(storage_table_temp)
    if Exists(temp_dem):
        Delete(temp_dem)

    ### Create Pools Feature Class ###
    if create_pools_layer:
        SetProgressorLabel('Finalizing pools feature class...')
        AddMsgAndPrint('\nFinalizing pools feature class...', log_file_path=log_file_path)
        env.workspace = scratch_gdb
        poolFCs = ListFeatureClasses('Pool_*')
        Merge(poolFCs, output_pool_path)

    ### Add Outputs to Map ###
    SetParameterAsText(5, storage_table_path)
    if create_pools_layer: SetParameterAsText(6, output_pool_path)

    ### Compact Project GDB ###
    try:
        SetProgressorLabel('Compacting project geodatabase...')
        AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
        Compact(project_gdb)
    except:
        pass

    AddMsgAndPrint('\nCalculate Stage Storage completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Calculate Stage Storage'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Calculate Stage Storage'), 2)

finally:
    emptyScratchGDB(scratch_gdb)

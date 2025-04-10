from getpass import getuser
from os import path
from sys import argv, exit
from time import ctime

from arcpy import CheckExtension, CheckOutExtension, Describe, env, Exists, GetInstallInfo, GetParameterAsText, SetParameterAsText, SetProgressorLabel
from arcpy.conversion import RasterToPolygon
from arcpy.da import SearchCursor
from arcpy.ddd import SurfaceVolume
from arcpy.management import AddField, CalculateField, Compact, Delete, Dissolve, GetCount, GetRasterProperties
from arcpy.mp import ArcGISProject
from arcpy.sa import ExtractByMask, Int, SetNull, Times

from utils import AddMsgAndPrint, emptyScratchGDB, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, project_dem, input_pool, pool_elevation):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Create Pool at Specified Elevation\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tProject DEM: {project_dem}\n")
        f.write(f"\tInput Pool Polygon: {input_pool}\n")
        f.write(f"\tPool Elevation: {pool_elevation} Feet\n")


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
pool_elevation = float(GetParameterAsText(2))

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
    output_pool_name = f"{input_pool_name}_{subbasin_number}_Pool_{round(pool_elevation)}_ft"
else:
    output_pool_name = f"{input_pool_name}_Pool_{round(pool_elevation)}_ft"
output_pool_path = path.join(project_fd, output_pool_name)

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
to_feet = 0.092903
to_acre_foot = 1233.48184
to_cubic_meters = 1
to_cubic_feet = 35.3147

try:
    removeMapLayers(map, [output_pool_name])
    logBasicSettings(log_file_path, project_dem, input_pool, pool_elevation)

    ### Clip DEM to Input Polygon and get Min/Max ###
    SetProgressorLabel('Clipping DEM to input pool polygon...')
    AddMsgAndPrint('\nClipping DEM to input pool polygon...', log_file_path=log_file_path)
    temp_dem = ExtractByMask(project_dem, input_pool)
    temp_dem_min = round(float(GetRasterProperties(temp_dem, 'MINIMUM').getOutput(0)))
    temp_dem_max = round(float(GetRasterProperties(temp_dem, 'MAXIMUM').getOutput(0)))
    if not temp_dem_min < pool_elevation <= temp_dem_max:
        AddMsgAndPrint(f"\nThe pool elevation value specified is not within range of your watershed-pool area:\n\tMinimum Elevation: {temp_dem_min} Feet\n\tMaximum Elevation: {temp_dem_max} Feet", 2, log_file_path)
        exit()

    ### Calculate Volume and Surface Area ###
    SetProgressorLabel(f"Processing elevation {pool_elevation}...")
    AddMsgAndPrint(f"\nProcessing elevation {pool_elevation}...", log_file_path=log_file_path)
    SurfaceVolume(temp_dem, storage_table_temp, 'BELOW', pool_elevation, '1')

    try:
        # Create new raster of only values below an elevation value by nullifying cells above the desired elevation value
        above_elevation = SetNull(temp_dem, temp_dem, f"Value > {pool_elevation}")

        # Multiply every pixel by 0 and convert to integer for vectorizing
        zeros = Times(above_elevation, 0)
        zero_int = Int(zeros)

        # Convert to polygon and dissolve
        RasterToPolygon(zero_int, temp_pool, 'NO_SIMPLIFY', 'VALUE')
        Dissolve(temp_pool, output_pool_path)

        AddField(output_pool_path, 'ELEV_FEET', 'DOUBLE')
        AddField(output_pool_path, 'DEM_ELEV', 'DOUBLE')
        AddField(output_pool_path, 'POOL_ACRES', 'DOUBLE')
        AddField(output_pool_path, 'POOL_SQFT', 'DOUBLE')
        AddField(output_pool_path, 'ACRE_FOOT', 'DOUBLE')
        AddField(output_pool_path, 'CUBIC_FEET', 'DOUBLE')
        AddField(output_pool_path, 'CUBIC_METERS', 'DOUBLE')

        # Open surface volume text file - last line should represent the last pool
        with open(storage_table_temp) as file:
            lines = file.readlines()

        area2D = float(lines[len(lines)-1].split(',')[4])
        volume = float(lines[len(lines)-1].split(',')[6])

        elevation_feet = round(pool_elevation, 1)
        area_acres = round(area2D / to_acres, 1)
        area_sqft = round(area2D / to_feet, 1)
        volume_acre_foot = round(volume / to_acre_foot, 1)
        volume_cubic_meters = round(volume * to_cubic_meters, 1)
        volume_cubic_feet = round(volume * to_cubic_feet, 1)

        CalculateField(output_pool_path, 'ELEV_FEET', elevation_feet, 'PYTHON3')
        CalculateField(output_pool_path, 'DEM_ELEV', pool_elevation, 'PYTHON3')
        CalculateField(output_pool_path, 'POOL_ACRES', area_acres, 'PYTHON3')
        CalculateField(output_pool_path, 'POOL_SQFT', area_sqft, 'PYTHON3')
        CalculateField(output_pool_path, 'ACRE_FOOT', volume_acre_foot, 'PYTHON3')
        CalculateField(output_pool_path, 'CUBIC_METERS', volume_cubic_meters, 'PYTHON3')
        CalculateField(output_pool_path, 'CUBIC_FEET', volume_cubic_feet, 'PYTHON3')

        AddMsgAndPrint(f"\n\tCreated {output_pool_path}:")
        AddMsgAndPrint(f"\t\tElevation {elevation_feet} Feet")
        AddMsgAndPrint(f"\t\tArea: {area_sqft} Square Feet")
        AddMsgAndPrint(f"\t\tArea: {area_acres} Acres")
        AddMsgAndPrint(f"\t\tVolume: {volume_acre_foot} Acre Feet")
        AddMsgAndPrint(f"\t\tVolume: {volume_cubic_meters} Cubic Meters")
        AddMsgAndPrint(f"\t\tVolume: {volume_cubic_feet} Cubic Feet")

    except:
        AddMsgAndPrint(f"\nFailed to create pool at elevation: {pool_elevation}. Exiting...", 2, log_file_path)
        AddMsgAndPrint(errorMsg('Calculate Stage Storage'), 2, log_file_path)
        exit()

    ### Clean Up Temp Datasets ###
    if Exists(storage_table_temp):
        Delete(storage_table_temp)
    if Exists(temp_dem):
        Delete(temp_dem)

    ### Add Output to Map ###
    SetParameterAsText(3, output_pool_path)

    ### Compact Project GDB ###
    try:
        SetProgressorLabel('Compacting project geodatabase...')
        AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
        Compact(project_gdb)
    except:
        pass

    AddMsgAndPrint('\nCreate Pool At Specified Elevation completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Create Pool At Specified Elevation'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Create Pool At Specified Elevation'), 2)

finally:
    emptyScratchGDB(scratch_gdb)

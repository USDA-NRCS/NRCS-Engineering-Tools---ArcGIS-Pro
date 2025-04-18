from getpass import getuser
from os import path
from sys import argv, exit
from time import ctime

from arcpy import CheckExtension, CheckOutExtension, Describe, env, GetInstallInfo, GetParameter, GetParameterAsText, SetProgressorLabel
from arcpy.da import SearchCursor, UpdateCursor
from arcpy.management import AddField, CalculateField, Compact, CopyFeatures, GetCount
from arcpy.mp import ArcGISProject
from arcpy.sa import Plus, ZonalStatisticsAsTable

from utils import AddMsgAndPrint, emptyScratchGDB, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, project_dem):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Calibrate DEM to Field Survey\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tProject DEM: {project_dem}\n")


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
input_points = GetParameterAsText(1)  
input_field = GetParameterAsText(2)
input_value = GetParameter(3)

### Locate Project GDB ###
project_dem_path = Describe(project_dem).CatalogPath
if 'EngPro.gdb' in project_dem_path and 'DEM' in project_dem_path:
    project_gdb = project_dem_path[:project_dem_path.find('.gdb')+4]
else:
    AddMsgAndPrint('\nThe selected DEM is not from an Engineering Tools project or is not compatible with this version of the toolbox. Exiting...', 2)
    exit()

### Set Paths and Variables ###
support_dir = path.dirname(argv[0])
scratch_gdb = path.join(support_dir, 'Scratch.gdb')
project_workspace = path.dirname(project_gdb)
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")
project_fd = path.join(project_gdb, 'Layers')
survey_points = path.join(project_fd, 'DEM_Calibration_Points')
adjusted_dem_name = f"{project_name}_DEM_adjusted"
adjusted_dem_path = path.join(project_gdb, adjusted_dem_name)
temp_points = path.join(scratch_gdb, 'temp_points')
temp_stats = path.join(scratch_gdb, 'temp_stats')
elevation_adjustment = 0

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

try:
    removeMapLayers(map, [adjusted_dem_name])
    logBasicSettings(log_file_path, project_dem)

    ### Survey Points Layer Provided ###
    if input_points and int(GetCount(input_points).getOutput(0)) > 0:
        SetProgressorLabel('Processing survey points...')
        AddMsgAndPrint('\nProcessing survey points...', log_file_path=log_file_path)
        
        number_of_points = int(GetCount(input_points).getOutput(0))
        elevation_difference = 0

        CopyFeatures(input_points, temp_points)
        AddField(temp_points, 'POINTID', 'LONG')
        AddField(temp_points, 'DEM_ELEV', 'DOUBLE')
        AddField(temp_points, 'DIFF', 'DOUBLE')
        CalculateField(temp_points, 'POINTID', '!OBJECTID!', 'PYTHON3')

        # Use Zonal Statistics to get elevations at point locations from DEM
        ZonalStatisticsAsTable(temp_points, 'POINTID', project_dem, temp_stats, 'DATA')

        with SearchCursor(temp_stats, ['POINTID', 'MEAN']) as s_cur:
            for s_row in s_cur:
                point_id = s_row[0]
                dem_elevation = s_row[1]

                with UpdateCursor(temp_points, ['DEM_ELEV', 'DIFF', input_field], f"POINTID={point_id}") as u_cur:
                    for u_row in u_cur:
                        u_row[0] = round(dem_elevation, 1)
                        u_row[1] = round(u_row[2]-dem_elevation, 1)
                        u_cur.updateRow(u_row)
                        elevation_difference += u_row[1]

        elevation_adjustment = round(elevation_difference/number_of_points, 1)

        CopyFeatures(temp_points, survey_points)

    ### Adjustment Value Provided ###
    elif input_value != 0:
        elevation_adjustment = input_value

    else:
        AddMsgAndPrint('\nInput survey points layer has no features or adjustment value not specified. Exiting...', 2, log_file_path)
        exit()

    ### Adjust and Finalize DEM ###
    if elevation_adjustment == 0:
        AddMsgAndPrint('\nAverage elevation difference not greater than 0.1 feet. DEM will not be adjusted. Exiting...', 2, log_file_path)
        exit()
    else:
        SetProgressorLabel(f"\nAdjusting DEM elevation by {elevation_adjustment} feet...")
        AddMsgAndPrint(f"\nAdjusting DEM elevation by {elevation_adjustment} feet...", log_file_path=log_file_path)
        dem_plus = Plus(project_dem, elevation_adjustment)
        dem_plus.save(adjusted_dem_path)

    ### Add Output DEM to Map and Symbolize ###
    SetProgressorLabel('Adding adjusted DEM to map...')
    AddMsgAndPrint('\nAdding adjusted DEM to map...', log_file_path=log_file_path)
    map.addDataFromPath(adjusted_dem_path)
    dem_layer = map.listLayers(adjusted_dem_name)[0]
    sym = dem_layer.symbology
    sym.colorizer.resamplingType = 'Bilinear' #NOTE: Pro does not seem to honor this
    sym.colorizer.stretchType = 'StandardDeviation'
    sym.colorizer.standardDeviation = 2.5
    sym.colorizer.colorRamp = aprx.listColorRamps('Elevation #1')[0]
    dem_layer.symbology = sym

    ### Update Layer Order in TOC ###
    project_dem_name = f"{project_name}_DEM"
    try:
        if map.listLayers(project_dem_name)[0]:
            map.moveLayer(map.listLayers(project_dem_name)[0], dem_layer, 'BEFORE')
    except:
        pass

    ### Compact Project GDB ###
    try:
        SetProgressorLabel('Compacting project geodatabase...')
        AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
        Compact(project_gdb)
    except:
        pass

    AddMsgAndPrint('\nCalibrate DEM to Field Survey completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Calibrate DEM to Field Survey'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Calibrate DEM to Field Survey'), 2)

finally:
    emptyScratchGDB(scratch_gdb)

from getpass import getuser
from os import path
from sys import argv
from time import ctime

from arcpy import CheckExtension, CheckOutExtension, Describe, env, GetParameterAsText, SetParameterAsText, SetProgressorLabel
from arcpy.management import Clip, Compact, CopyRaster, Delete, MosaicToNewRaster, Project, ProjectRaster
from arcpy.mp import ArcGISProject
from arcpy.sa import Con, Fill, Hillshade, Minus, Slope, Times

from utils import AddMsgAndPrint, emptyScratchGDB, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, project_workspace, project_dem):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Create DEM\n')
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tProject Workspace: {project_workspace}\n")
        f.write(f"\tProject DEM: {project_dem}\n")


### Initial Tool Validation ###
try:
    aprx = ArcGISProject('CURRENT')
    map = aprx.listMaps()[0]
except:
    AddMsgAndPrint('This tool must be run from an ArcGIS Pro project that was developed from the template distributed with this toolbox. Exiting!', 2)
    exit()

if CheckExtension('Spatial') == 'Available':
    CheckOutExtension('Spatial')
else:
    AddMsgAndPrint('Spatial Analyst Extension not enabled. Please enable Spatial Analyst from Project, Licensing, Configure licensing options. Exiting...', 2)
    exit()

### ESRI Environment Settings ###
env.overwriteOutput = True
env.resamplingMethod = 'BILINEAR'
env.pyramid = 'PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP'

### Input Parameters ###
project_dem = GetParameterAsText(0)

### Locate Project GDB ###
project_dem_path = Describe(project_dem).CatalogPath
if project_dem_path.find('.gdb') > 0 and 'DEM' in project_dem_path:
    project_gdb = project_dem_path[:project_dem_path.find('.gdb')+4]
else:
    AddMsgAndPrint('\nSelected DEM layer is not from an Engineering project workspace. Exiting...', 2)
    exit()

### Set Paths and Variables ###
project_workspace = path.dirname(project_gdb)
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")
hillshade_name = f"{project_name}_Hillshade"
hillshade_path = path.join(project_gdb, hillshade_name)
slope_name = f"{project_name}_Slope"
slope_path = path.join(project_gdb, slope_name)
depth_grid_name = f"{project_name}_DepthGrid"
depth_grid_path = path.join(project_gdb, depth_grid_name)

### Set Unit Conversion Variables ###
# if elevation_units == 'Meters':
#     z_factor = 1
#     cz_factor = 3.28084
# elif elevation_units == 'Centimeters':
#     z_factor = 0.01
#     cz_factor = 0.0328084
# elif elevation_units == 'Feet':
#     z_factor = 0.3048
#     cz_factor = 1
# elif elevation_units == 'Inches':
#     z_factor = 0.0254
#     cz_factor = 0.0833333

try:
    logBasicSettings(log_file_path, project_workspace, project_dem)
    removeMapLayers(map, [hillshade_name, slope_name, depth_grid_name])
    
    ### Create Hillshade ###
    SetProgressorLabel('Creating Hillshade...')
    AddMsgAndPrint('\nCreating Hillshade...', log_file_path=log_file_path)
    output_hillshade = Hillshade(project_dem, '315', '45', 'NO_SHADOWS', z_factor)
    output_hillshade.save(hillshade_path)

    #TODO: Is this necessary?
    # # Create a temporary smoothed DEM to use for creating a slope layer and a contours layer
    # AddMsgAndPrint('\tCreating a 3-meter pixel resolution version of the DEM for use in contours and slopes...')
    # SetProgressorLabel('Creating 3-meter resolution DEM...')
    # ProjectRaster(tempDEM, DEMagg, cluSR, 'BILINEAR', '3', '#', '#', '#')

    # AddMsgAndPrint('\tSmoothing the DEM with Focal Statistics...')
    # SetProgressorLabel('Smoothing DEM with Focal Stats...')
    # outFocalStats = FocalStatistics(DEMagg, 'RECTANGLE 3 3 CELL', 'MEAN', 'DATA')
    # outFocalStats.save(DEMsmooth)

    ### Create Slope ###
    SetProgressorLabel('Creating Slope...')
    AddMsgAndPrint('\nCreating Slope...', log_file_path=log_file_path)
    output_slope = Slope(project_dem, 'PERCENT_RISE', z_factor)
    output_slope.save(slope_path)

    ### Create Depth Grid ###
    SetProgressorLabel('Creating Depth Grid...')
    AddMsgAndPrint('\nCreating Depth Grid...', log_file_path=log_file_path)
    fill = False
    try:
        # Fills sinks in project DEM to remove small imperfections in the data.
        # Convert the projectDEM to a raster with z units in feet to create this layer
        Temp_DEMbase = Times(project_dem, cz_factor)
        Fill_DEMaoi = Fill(Temp_DEMbase, '')
        fill = True
    except:
        pass
    #TODO: if this is False, Depth Grid wont be created?
    if fill:
        FilMinus = Minus(Fill_DEMaoi, Temp_DEMbase)
        # Create a Depth Grid whereby any pixel with a difference is written to a new raster
        output_depth_grid = Con(FilMinus, FilMinus, '', 'VALUE > 0')
        output_depth_grid.save(depth_grid_path)

    ### Add Outputs to Map ###
    #TODO: Does layer order/visibility matter here?
    #TODO: Update lyrx files if needed
    SetParameterAsText(1, hillshade_path)
    SetParameterAsText(2, slope_path)
    SetParameterAsText(3, depth_grid_path)

    AddMsgAndPrint('\nCreate Hillshade, Slope, Depth Grid completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Create Hillshade, Slope, Depth Grid'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Create Hillshade, Slope, Depth Grid'), 2)

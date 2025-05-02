from getpass import getuser
from os import path
from sys import exit
from time import ctime

from arcpy import CheckExtension, CheckOutExtension, Describe, env, Exists, GetInstallInfo, GetParameterAsText, SetProgressorLabel
from arcpy.management import Compact
from arcpy.mp import ArcGISProject
from arcpy.sa import FocalStatistics, Minus

from utils import AddMsgAndPrint, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, project_dem, window_size):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Topographic Position Index (TPI)\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tProject DEM: {project_dem}\n")
        f.write(f"\tFocalStatistics Window Size: {window_size}\n")


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
window_size = GetParameterAsText(1)

if int(window_size) <= 0:
    AddMsgAndPrint('Window size for FocalStatistics must be greater than zero. Exiting...', 2)
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
extracted_dem_path = path.join(project_gdb, f"{project_name}_DEM_extract") #TODO: validate this exists?
output_tpi_name = f"{project_name}_TPI_{window_size}"
output_tpi_path = path.join(project_gdb, output_tpi_name)

### Locate Extracted (non-smoothed) DEM ###
if not Exists(extracted_dem_path):
    AddMsgAndPrint('\nCould not locate the non-smoothed extracted DEM. Run the "Create DEM" tool and try again. Exiting...', 2)
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
    removeMapLayers(map, [output_tpi_name])
    logBasicSettings(log_file_path, project_dem, window_size)

    SetProgressorLabel('Computing Topographic Position Index...')
    AddMsgAndPrint('Computing Topographic Position Index...', log_file_path=log_file_path)

    output_focal_stats = FocalStatistics(extracted_dem_path, f"RECTANGLE {window_size} {window_size} CELL", 'MEAN', 'DATA')
    output_tpi = Minus(extracted_dem_path, output_focal_stats)
    output_tpi.save(output_tpi_path)

    ### Add Output CTI to Map and Symbolize ###
    SetProgressorLabel('Adding TPI layer to map...')
    AddMsgAndPrint('\nAdding TPI layer to map...', log_file_path=log_file_path)
    map.addDataFromPath(output_tpi_path)
    tpi_layer = map.listLayers(output_tpi_name)[0]
    sym = tpi_layer.symbology
    sym.updateColorizer('RasterClassifyColorizer')
    sym.colorizer.resamplingType = 'Bilinear' #NOTE: Pro does not seem to honor this
    sym.colorizer.colorRamp = aprx.listColorRamps('Inferno')[0]
    tpi_layer.symbology = sym

    ### Update Layer Order in TOC ###
    hillshade_lyr_name = f"{project_name}_Hillshade"
    try:
        if map.listLayers(hillshade_lyr_name)[0]:
            map.moveLayer(map.listLayers(hillshade_lyr_name)[0], tpi_layer, 'AFTER')
            map.listLayers(hillshade_lyr_name)[0].visible = True
    except:
        pass

    ### Compact Project GDB ###
    try:
        SetProgressorLabel('Compacting project geodatabase...')
        AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
        Compact(project_gdb)
    except:
        pass

    AddMsgAndPrint('\nTopographic Position Index (TPI) completed successfully', log_file_path=log_file_path)
    AddMsgAndPrint('\nOverlay the results with a hillshade to best view cell transitions')

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Topographic Position Index (TPI)'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Topographic Position Index (TPI)'), 2)

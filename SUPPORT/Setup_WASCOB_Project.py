from getpass import getuser
from os import path
from sys import argv, exit
from time import ctime

from arcpy import Describe, env, Exists, GetInstallInfo, GetParameter, GetParameterAsText, SetParameterAsText, SetProgressorLabel
from arcpy.management import AddField, CalculateField, Compact, CopyFeatures, CreateFeatureDataset, CreateFileGDB, CreateFolder, \
    DeleteField, MakeFeatureLayer, SelectLayerByAttribute
from arcpy.mp import ArcGISProject
from arcpy.sa import Contour, Int, Minus, Plus, Times, ZonalStatistics

from utils import AddMsgAndPrint, emptyScratchGDB, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, project_dem, input_z_units, relative_survey, contour_interval):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: WASCOB Create AOI\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tProject DEM: {project_dem}\n")
        f.write(f"\tDEM Elevation Units: {input_z_units}\n")
        f.write(f"\tCreate Relative Survey: {relative_survey}\n")
        if relative_survey:
            f.write(f"\tContour Interval: {contour_interval}\n")

### Initial Tool Validation ###
try:
    aprx = ArcGISProject('CURRENT')
    map = aprx.listMaps('Engineering')[0]
except:
    AddMsgAndPrint('\nThis tool must be run from an ArcGIS Pro project template distributed with the Engineering Tools. Exiting...', 2)
    exit()

### Input Parameters ###
project_dem = GetParameterAsText(0)
input_z_units = GetParameterAsText(1)
relative_survey = GetParameter(2)
contour_interval = GetParameterAsText(3)

### Locate Project GDB ###
project_dem_path = Describe(project_dem).CatalogPath
if 'EngPro.gdb' in project_dem_path and 'DEM' in project_dem_path:
    project_gdb = project_dem_path[:project_dem_path.find('.gdb')+4]
else:
    AddMsgAndPrint('\nThe selected DEM is not from an Engineering Tools project or is not compatible with this version of the toolbox. Exiting...', 2)
    exit()

### Validate Contour Interval ###
if relative_survey and float(contour_interval) not in [0.5, 1, 2, 5, 10]:
    AddMsgAndPrint('\nInvalid contour interval. Exiting...', 2)
    exit()

### Set Paths and Variables ###
support_dir = path.dirname(argv[0])
scratch_gdb = path.join(support_dir, 'Scratch.gdb')
project_workspace = path.dirname(project_gdb)
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")
project_aoi = path.join(project_gdb, 'Layers', f"{project_name}_AOI")
wascob_gdb_name = f"{project_name}_WASCOB.gdb"
wascob_gdb_path = path.join(project_workspace, wascob_gdb_name)
wascob_fd_path = path.join(wascob_gdb_path, 'Layers')
documents_dir = path.join(project_workspace, 'Documents')
output_dir = path.join(project_workspace, 'GIS_Output')
tables_dir = path.join(output_dir, 'Tables')
wascob_dem_name = f"{project_name}_DEM_WASCOB"
wascob_dem_path = path.join(wascob_gdb_path, wascob_dem_name)
contours_name = f"Relative_Contour_{contour_interval.replace('.','_dot_')}"
contours_path = path.join(wascob_fd_path, contours_name)
temp_contours_path = path.join(scratch_gdb, contours_name)

### ESRI Environment Settings ###
dem_desc = Describe(project_dem_path)
dem_sr = dem_desc.spatialReference
env.overwriteOutput = True
env.resamplingMethod = 'BILINEAR'
env.pyramid = 'PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP'
env.outputCoordinateSystem = dem_sr

# Set z-factor for converting vertical units to International Feet
if input_z_units == 'Meters':
    z_factor = 3.28083989501
elif input_z_units == 'Centimeters':
    z_factor = 328.083989501
elif input_z_units == 'International Feet':
    z_factor = 1
elif input_z_units == 'International Inches':
    z_factor = 12
elif input_z_units == 'US Survey Feet':
    z_factor = 1.000002000
elif input_z_units == 'US Survey Inches':
    z_factor = 12.000002400

try:
    removeMapLayers(map, [wascob_dem_name, contours_name])
    logBasicSettings(log_file_path, project_dem, input_z_units, relative_survey, contour_interval)

    ### Create WASCOB GDB, Documents and GIS_Output Folders ###
    if not Exists(wascob_gdb_path):
        SetProgressorLabel('Creating project geodatabase...')
        AddMsgAndPrint('\nCreating project geodatabase...', log_file_path=log_file_path)
        CreateFileGDB(project_workspace, wascob_gdb_name)

    if not Exists(wascob_fd_path):
        SetProgressorLabel('Creating project feature dataset...')
        AddMsgAndPrint('\nCreating project feature dataset...', log_file_path=log_file_path)
        CreateFeatureDataset(wascob_gdb_path, 'Layers', dem_sr)

    if not Exists(output_dir):
        SetProgressorLabel('Creating GIS_Output folder...')
        AddMsgAndPrint('\nCreating GIS_Output folder...', log_file_path=log_file_path)
        CreateFolder(project_workspace, 'GIS_Output')

    if not Exists(tables_dir):
        SetProgressorLabel('Creating Tables folder...')
        AddMsgAndPrint('\nCreating Tables folder...', log_file_path=log_file_path)
        CreateFolder(output_dir, 'Tables')

    if not Exists(documents_dir):
        SetProgressorLabel('Creating Documents folder...')
        AddMsgAndPrint('\nCreating Documents folder...', log_file_path=log_file_path)
        CreateFolder(project_workspace, 'Documents')

    ### Convert DEM Values to Feet ###
    if input_z_units != 'International Feet':
        SetProgressorLabel('Converting DEM values to feet...')
        AddMsgAndPrint(f"\nConverting DEM values to feet using z-factor of {z_factor}...", log_file_path=log_file_path)
        project_dem_ft = Times(project_dem, z_factor)
        project_dem = project_dem_ft

    ### Adjust DEM Values for Relative Survey ###
    if relative_survey:
        SetProgressorLabel('Adjusting DEM to relative elevations...')
        AddMsgAndPrint('\nAdjusting DEM to relative elevations (0 ft. to maximum rise)...', log_file_path=log_file_path)
        min_dem = ZonalStatistics(project_aoi, 'OBJECTID', project_dem, 'MINIMUM', 'DATA')
        # Subtract Minimum Elevation from all cells in AOI
        minus_dem = Minus(project_dem, min_dem)
        project_dem = minus_dem

    ### Round DEM Values to Nearest 10th ###
    SetProgressorLabel('Rounding DEM values to nearest 1/10th ft...')
    AddMsgAndPrint('\nRounding DEM values to nearest 1/10th ft...', log_file_path=log_file_path)
    # Multiply DEM by 10 for rounding
    int_dem = Int(Plus(Times(project_dem, 10),0.5))
    # Restore the decimal point for 1/10th foot
    outTimes = Times(int_dem, 0.1)
    outTimes.save(wascob_dem_path)

    ### Create Relative Contours ###
    if relative_survey:
        SetProgressorLabel('Creating relative contours...')
        AddMsgAndPrint(f"\nCreating relative contours with a {contour_interval} ft interval...", log_file_path=log_file_path)
        # # Run Focal Statistics on the Project DEM to generate smooth contours
        # outFocal = FocalStatistics(projectDEM,"RECTANGLE 3 3 CELL","MEAN","DATA")
        # outFocal.save(DEMsmooth)
        # Create Contours from DEMsmooth
        # Z factor to use here is 1 because vertical values of the input DEM have been forced to be feet.
        Contour(wascob_dem_path, temp_contours_path, contour_interval, '0', 1)

        ### Add Index Field ###
        DeleteField(temp_contours_path, 'Id')
        AddField(temp_contours_path, 'Index', 'DOUBLE')

        ### Update Every 5th Index to 1 ###
        SetProgressorLabel('Updating contour indexing...')
        AddMsgAndPrint('\nUpdating contour indexing...', log_file_path=log_file_path)
        MakeFeatureLayer(temp_contours_path, 'contour_lyr')
        expression = "MOD( \"CONTOUR\"," + str(float(contour_interval) * 5) + ") = 0"
        SelectLayerByAttribute('contour_lyr', 'NEW_SELECTION', expression)
        CalculateField('contour_lyr', 'Index', 1, 'PYTHON3')

        ### Update All Other Indexes to 0 ###
        SelectLayerByAttribute('contour_lyr', 'SWITCH_SELECTION')
        CalculateField('contour_lyr', 'Index', 0, 'PYTHON3')

        ### Copy Final Contour Output ###
        SetProgressorLabel('Finalizing contour layer...')
        AddMsgAndPrint('\nFinalizing lontour layer...', log_file_path=log_file_path)
        SelectLayerByAttribute('contour_lyr', 'CLEAR_SELECTION')
        CopyFeatures('contour_lyr', contours_path)

    ### Add Output to Map ###
    ### Add Output DEM to Map and Symbolize ###
    SetProgressorLabel('Adding DEM to map...')
    AddMsgAndPrint('\nAdding DEM to map...', log_file_path=log_file_path)
    map.addDataFromPath(wascob_dem_path)
    dem_layer = map.listLayers(wascob_dem_name)[0]
    sym = dem_layer.symbology
    sym.colorizer.resamplingType = 'Bilinear' #NOTE: Pro does not seem to honor this
    sym.colorizer.stretchType = 'StandardDeviation'
    sym.colorizer.standardDeviation = 2.5
    sym.colorizer.colorRamp = aprx.listColorRamps('Elevation #1')[0]
    dem_layer.symbology = sym
    # SetParameterAsText(4, wascob_dem_path)
    SetParameterAsText(5, contours_path)

    ### Update Layer Order in TOC ###
    if map.listLayers()[0].name == wascob_dem_name:
        SetProgressorLabel('Updating layer order...')
        AddMsgAndPrint('\nUpdating layer order...', log_file_path=log_file_path)
        map.moveLayer(map.listLayers()[1], dem_layer, 'AFTER')

    ### Compact Project GDB ###
    try:
        SetProgressorLabel('Compacting project geodatabase...')
        AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
        Compact(wascob_gdb_path)
    except:
        pass

    AddMsgAndPrint('\nSetup WASCOB Project completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Setup WASCOB Project'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Setup WASCOB Project'), 2)

finally:
    emptyScratchGDB(scratch_gdb)

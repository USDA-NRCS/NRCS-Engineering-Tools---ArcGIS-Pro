from getpass import getuser
from os import path
from sys import argv
from time import ctime

from arcpy import CheckExtension, CheckOutExtension, Describe, env, GetInstallInfo, GetParameter, \
    GetParameterAsText, SetParameterAsText, SetProgressorLabel
from arcpy.management import Clip, Compact, CopyRaster, Delete, MosaicToNewRaster, Project, ProjectRaster
from arcpy.mp import ArcGISProject
from arcpy.sa import Contour

from utils import AddMsgAndPrint, emptyScratchGDB, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, project_workspace, project_dem, contour_interval):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Create Contours\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tProject Workspace: {project_workspace}\n")
        f.write(f"\tProject DEM: {project_dem}\n")
        f.write(f"\tElevation Units: {contour_interval}\n")


### Initial Tool Validation ###
try:
    aprx = ArcGISProject('CURRENT')
    map = aprx.listMaps('Engineering')[0]
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
contour_interval = GetParameterAsText(1)

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
smoothed_dem_path = path.join(project_gdb, f"{project_name}_Smooth_3_3")
contour_name = f"{project_name}_Contour_{contour_interval}"
contour_path = path.join(project_gdb, 'Layers', contour_name)
# z_factor = 0.3048 # Meters to Intl Feet

try:
    removeMapLayers(map, [contour_name])
    logBasicSettings(log_file_path, project_workspace, project_dem, contour_interval)

    ### Create Contours ###
    SetProgressorLabel('Creating Contours...')
    AddMsgAndPrint('\nCreating Contours...', log_file_path=log_file_path)
    Contour(smoothed_dem_path, contour_path, contour_interval)

    # arcpy.AddField_management(ContoursTemp, "Index", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    # if Exists("ContourLYR"):
    #     try:
    #         arcpy.Delete_management("ContourLYR")
    #     except:
    #         pass

    # arcpy.MakeFeatureLayer_management(ContoursTemp,"ContourLYR","","","")

    # # Every 5th contour will be indexed to 1
    # expression = "MOD( \"CONTOUR\"," + str(float(interval) * 5) + ") = 0"
    # arcpy.SelectLayerByAttribute_management("ContourLYR", "NEW_SELECTION", expression)
    # del expression

    # indexValue = 1
    # #arcpy.CalculateField_management("ContourLYR", "Index", indexValue, "VB","")
    # arcpy.CalculateField_management("ContourLYR", "Index", indexValue, "PYTHON_9.3")
    # del indexValue

    # # All othe contours will be indexed to 0
    # arcpy.SelectLayerByAttribute_management("ContourLYR", "SWITCH_SELECTION")
    # indexValue = 0
    # #arcpy.CalculateField_management("ContourLYR", "Index", indexValue, "VB","")
    # arcpy.CalculateField_management("ContourLYR", "Index", indexValue, "PYTHON_9.3")
    # del indexValue

    # # Clear selection and write all contours to a new feature class
    # arcpy.SelectLayerByAttribute_management("ContourLYR","CLEAR_SELECTION")
    # arcpy.CopyFeatures_management("ContourLYR", Contours)

    AddMsgAndPrint('\nCreate Contours completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Create Contours'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Create Contours'), 2)

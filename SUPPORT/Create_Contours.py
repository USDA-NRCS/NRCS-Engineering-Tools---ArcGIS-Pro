from getpass import getuser
from os import path
from sys import argv
from time import ctime

from arcpy import CheckExtension, CheckOutExtension, Describe, env, GetParameter, GetParameterAsText, SetParameterAsText, SetProgressorLabel
from arcpy.management import Clip, Compact, CopyRaster, Delete, MosaicToNewRaster, Project, ProjectRaster
from arcpy.mp import ArcGISProject
from arcpy.sa import Contour, FocalStatistics

from utils import AddMsgAndPrint, emptyScratchGDB, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, project_workspace, project_dem, contour_interval):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Create DEM\n')
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
contour_interval = GetParameter(1)

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
contour_name = f"{project_name}_Contour_{str(contour_interval)}"
contour_path = path.join(project_gdb, contour_name)

try:
    logBasicSettings(log_file_path, project_workspace, project_dem, str(contour_interval))

    # Run Focal Statistics on the DEM_aoi for the purpose of generating smooth contours
    outFocalStats = FocalStatistics(DEM_aoi, "RECTANGLE 3 3 CELL","MEAN","DATA")
    outFocalStats.save(DEMsmooth)
    AddMsgAndPrint("\nSuccessully Smoothed " + path.basename(DEM_aoi),0)

    Contour(DEMsmooth, ContoursTemp, interval, "0", Zfactor)
    AddMsgAndPrint("\nSuccessfully Created " + str(interval) + " foot Contours using a Z-factor of " + str(Zfactor),0)

    arcpy.AddField_management(ContoursTemp, "Index", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    if Exists("ContourLYR"):
        try:
            arcpy.Delete_management("ContourLYR")
        except:
            pass

    arcpy.MakeFeatureLayer_management(ContoursTemp,"ContourLYR","","","")

    # Every 5th contour will be indexed to 1
    expression = "MOD( \"CONTOUR\"," + str(float(interval) * 5) + ") = 0"
    arcpy.SelectLayerByAttribute_management("ContourLYR", "NEW_SELECTION", expression)
    del expression

    indexValue = 1
    #arcpy.CalculateField_management("ContourLYR", "Index", indexValue, "VB","")
    arcpy.CalculateField_management("ContourLYR", "Index", indexValue, "PYTHON_9.3")
    del indexValue

    # All othe contours will be indexed to 0
    arcpy.SelectLayerByAttribute_management("ContourLYR", "SWITCH_SELECTION")
    indexValue = 0
    #arcpy.CalculateField_management("ContourLYR", "Index", indexValue, "VB","")
    arcpy.CalculateField_management("ContourLYR", "Index", indexValue, "PYTHON_9.3")
    del indexValue

    # Clear selection and write all contours to a new feature class
    arcpy.SelectLayerByAttribute_management("ContourLYR","CLEAR_SELECTION")
    arcpy.CopyFeatures_management("ContourLYR", Contours)

    AddMsgAndPrint('\nCreate DEM completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Create Contours'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Create Contours'), 2)

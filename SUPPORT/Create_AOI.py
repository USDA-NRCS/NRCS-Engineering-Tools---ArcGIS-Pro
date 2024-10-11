## ===============================================================================================================
## Name: Create AOI
## Purpose:
## Create a project area of interest from importing a user-selected polygon file or the user drawing a polygon.
##
## Created: 9/19/2024
##
## ===============================================================================================================
## Changes
## ===============================================================================================================
##
## start 9/19/2024
## Initial tool creation 
##
## ===============================================================================================================
## ===============================================================================================================    

## ===============================================================================================================
#### Imports
from os import path
from sys import argv, exit
from time import ctime
from datetime import datetime
from getpass import getuser

from arcpy import AddMessage, env, Exists, GetParameterAsText, SetParameterAsText, SetProgressorLabel, SpatialReference
from arcpy.da import Describe
from arcpy.management import Append, CalculateGeometryAttributes, CalculateField, CreateFeatureclass, CopyFeatures, Delete, GetCount
from arcpy.mp import ArcGISProject

from utils import AddMsgAndPrint, calc_acres_us, calc_acres_intl, delete_datasets, emptyScratchGDB, errorMsg, removeMapLayers

## ===============================================================================================================
#### Functions
def logBasicSettings(textFilePath, wk_path):
    with open (textFilePath, 'a+') as f:
        f.write("\n######################################################################\n")
        f.write("Executing Tool: Create AOI\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tProject Folder: {wk_path}\n")

## ===============================================================================================================
#### Initialize
try:
    aprx = ArcGISProject('CURRENT')
except:
    AddMsgAndPrint('This tool must be run from an ArcGIS Pro project. Exiting...', 2)
    exit()

try:
    m = aprx.listMaps("Engineering")[0]
except:
    AddMsgAndPrint('There is no Map object named "Engineering" in the project. Engineering Tools expect "Engineering" to be the primary Map object for its work. Exiting...', 2)
    exit()

env.overwriteOutput = True
        
#### Input Parameters
wk_path = GetParameterAsText(0)
aoi_in = arcpy.GetParameterAsText(1)

#### Execution
try:
    ## Variables
    wk_name = path.basename(wk_path)
    textFilePath = path.join(wk_path, f"{wk_name}_EngTools.txt")
    gdb_name = wk_name + '_EngTools.gdb'
    gdb_path = path.join(wk_path, gdb_name)
    fd_name = 'Layers'
    fd_path = path.join(gdb_path, fd_name)
    aoi_in_path = Describe(aoi_in)['catalogPath']
    aoi_name = wk_name + "_AOI"
    template_aoi = path.join(path.dirname(argv[0]), 'Support.gdb', 'aoi_template')

    ### Permanent Datasets
    project_aoi = path.join(fd_path, aoi_name)
    datasets_to_delete = [project_aoi]

    ### ArcGIS Pro Layers
    aoi_out = "" + wk_name + "_AOI"
    m_layers = [aoi_out]
    
    ## Set default geodatabase
    scratch_gdb = path.join(path.dirname(argv[0]), 'Scratch.gdb')
    aprx.defaultGeodatabase = path.join(path.dirname(argv[0]), 'Scratch.gdb')

    ## Start logging in the project folder
    if not Exists(wk_path):
        AddMsgAndPrint('\nThe project folder does not exist. Please run Create Project Workspace. Exiting...\n', 2)
        exit()
    logBasicSettings(textFilePath, wk_path)

    ## Check project integrity. On fail, exit and direct user back to Create Project Workspace tool.
    SetProgressorLabel('Checking project integrity...')
    if not Exists(gdb_path):
        AddMsgAndPrint('\nNo project geodatabase found in specified folder. Run Create Project Workspace. Exiting...', 2, textFilePath)
    if not Exists(fd_path):
        AddMsgAndPrint('\nProject geodatabase integrity check failed. Run Create Project Workspace. Exiting...', 2, textFilePath)
    else:
        fd_sr = Describe(fd_path)['spatialReference']
        m.spatialReference = fd_sr
        env.outputCoordinateSystem = fd_sr

    ## Exit if AOI contains more than 1 digitized area
    if int(GetCount(aoi_in).getOutput(0)) > 1:
        AddMsgAndPrint('\nThe defined AOI can only have one polygon! Please try again. Exiting...', 2, textFilePath)

    ## Remove AOI layer from ArcGIS Pro session, if present
    removeMapLayers(m, m_layers)

    ## Create or re-use the AOI
    if aoi_in_path != project_aoi:
        ### Attempt to delete the existing project_aoi and create the new one
        SetProgressorLabel("Creating a new project AOI...")
        AddMsgAndPrint("\nCreating a new project AOI...", textFilePath=textFilePath)
        delete_datasets(datasets_to_delete)
        
        ### Create AOI from a template AOI feature class (fields already exist) and then append records from input AOI
        CreateFeatureclass(fd_path, aoi_name, "POLYGON", template_aoi)
        Append(aoi_in, project_aoi, 'NO_TEST')

        ### Update acres fields
        SetProgressorLabel("Updating acres...")
        AddMsgAndPrint("\nUpdating acres...", textFilePath=textFilePath)
        CalculateGeometryAttributes(project_aoi,"acres_us AREA_GEODESIC","","ACRES_US",fd_sr,"SAME_AS_INPUT")
        CalculateGeometryAttributes(project_aoi,"acres_intl AREA_GEODESIC","","ACRES",fd_sr,"SAME_AS_INPUT")
        CalculateField(project_aoi, "acres_us", "Round($feature.acres_us,2)", "ARCADE")
        CalculateField(project_aoi, "acres_intl", "Round($feature.acres_intl,2)", "ARCADE")
    else:
        AddMsgAndPrint("\nExisting Project AOI was defined as input...", textFilePath=textFilePath)
        ### Update acres fields, in case the input AOI was manually edited between initial creation and re-run
        SetProgressorLabel("Updating acres...")
        AddMsgAndPrint("\nUpdating acres...", textFilePath=textFilePath)
        CalculateGeometryAttributes(project_aoi,"acres_us AREA_GEODESIC","","ACRES_US",fd_sr,"SAME_AS_INPUT")
        CalculateGeometryAttributes(project_aoi,"acres_intl AREA_GEODESIC","","ACRES",fd_sr,"SAME_AS_INPUT")
        CalculateField(project_aoi, "acres_us", "Round($feature.acres_us,2)", "ARCADE")
        CalculateField(project_aoi, "acres_intl", "Round($feature.acres_intl,2)", "ARCADE")

    ## Delete the temporary edit layer (for drawn AOI input)
    emptyScratchGDB(scratch_gdb)

    ## Add results to map
    SetProgressorLabel("Adding results to the map...")
    AddMsgAndPrint("\nAdding results to the map...", textFilePath=textFilePath)
    SetParameterAsText(2, project_aoi)

    
    ## Finish up
    try:
        SetProgressorLabel("Compacting File Geodatabase...")
        AddMsgAndPrint("\nCompacting File Geodatabase...", textFilePath=textFilePath)
        Compact(gdb_path)
    except:
        pass

    AddMsgAndPrint('\nCreate AOI completed successfully!', textFilePath=textFilePath)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Create AOI'), 2, textFilePath)
    except:
        AddMsgAndPrint(errorMsg('Create AOI'), 2)

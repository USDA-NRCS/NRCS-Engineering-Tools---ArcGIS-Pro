## MergeVectorData.py
##
## Author unknown - Likely Mead, Diaz, and/or Morse, 2013
## Updated by Chris Morse, USDA NRCS, 2019
##
## Clips and merges multiple vector datasets into a single vector dataset within a project AOI

## ================================================================================================================ 
def print_exception():
    
    tb = sys.exc_info()[2]
    l = traceback.format_tb(tb)
    l.reverse()
    tbinfo = "".join(l)
    AddMsgAndPrint("\n----------ERROR Start-------------------\n",2)
    AddMsgAndPrint("Traceback Info: \n" + tbinfo + "Error Info: \n    " +  str(sys.exc_type)+ ": " + str(sys.exc_value) + "",2)
    AddMsgAndPrint("----------ERROR End-------------------- \n",2)

## ================================================================================================================    
def AddMsgAndPrint(msg, severity=0):
    # prints message to screen if run as a python script
    # Adds tool message to the geoprocessor
    # Split the message on  \n first, so that if it's multiple lines, a GPMessage will be added for each line

    print(msg)
    
    try:
        f = open(textFilePath,'a+')
        f.write(msg + " \n")
        f.close
        del f
        
        if severity == 0:
            arcpy.AddMessage(msg)
        elif severity == 1:
            arcpy.AddWarning(msg)
        elif severity == 2:
            arcpy.AddError(msg)
            
    except:
        pass

## ================================================================================================================
def logBasicSettings():    
    # record basic user inputs and settings to log file for future purposes

    import getpass, time

    f = open(textFilePath,'a+')
    f.write("\n##################################################################\n")
    f.write("Executing \"Clip and Merge Vector Data\" Tool\n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write("ArcGIS Version: " + str(arcpy.GetInstallInfo()['Version']) + "\n")
    f.write("User Parameters:\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tInput Datasets " + inDatasets.replace(";",", ") + "\n")
    f.write("\tOutput Dataset " + mergedDataset + "\n")
    
    f.close
    del f

## ================================================================================================================
# Import system modules
import arcpy, sys, os, traceback
#import arcgisscripting

# Environment settings
arcpy.env.overwriteOutput = True
arcpy.env.geographicTransformations = "WGS_1984_(ITRF00)_To_NAD_1983"
arcpy.env.resamplingMethod = "BILINEAR"
arcpy.env.pyramid = "PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP"

### Version check
##version = str(arcpy.GetInstallInfo()['Version'])
##if version.find("10.") > 0:
##    ArcGIS10 = True
##else:
##    ArcGIS10 = False
#### Convert version string to a float value (needed for numeric comparison)
##versionFlt = float(version[0:4])
##if versionFlt < 10.5:
##    arcpy.AddError("\nThis tool requires ArcGIS version 10.5 or greater. Exiting...\n")
##    sys.exit()       

# Main - wrap everything in a try statement
try:
    # ----------------------------------------------- Input Parameters
    userWorkspace = arcpy.GetParameterAsText(0)
    AOI = arcpy.GetParameterAsText(1)
    inDatasets = arcpy.GetParameterAsText(2)
    outputName = arcpy.GetParameterAsText(3)

    # ------------------------------------------------------------------- Variables
    
    projectName = os.path.basename(userWorkspace).replace(" ","_")
    outputName =  outputName.replace(" ","_")

    watershedGDB_name = os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.gdb"  # replace spaces for new FGDB name
    watershedGDB_path = userWorkspace + os.sep + watershedGDB_name
    watershedFD = watershedGDB_path + os.sep + "Layers"
    
    # ------------------------------------------------------------------ Permanent Datasets
    mergedDataset = watershedGDB_path + os.sep + outputName
    # Must Have a unique name for output -- Append a unique digit to watershed if required
    x = 1
    while x > 0:
        if arcpy.Exists(mergedDataset):
            mergedDataset = mergedDataset + str(x)
            x += 1
        else:
            x = 0
    del x

    projectAOI = watershedFD + os.sep + os.path.basename(mergedDataset) + "_AOI"

    # ------------------------------- Map Layers
    aoiOut = "" + os.path.basename(projectAOI) + ""
    mergeOut = "" + os.path.basename(mergedDataset) + ""
    
    # start log file
    textFilePath = userWorkspace + os.sep + projectName + "_EngTools.txt"
    logBasicSettings()    

    
    # ------------------------------------------------------------------- Remove previous data from arcMap if present
    layersToRemove = (mergeOut,aoiOut)
    x = 0
    for layer in layersToRemove:
        if arcpy.Exists(layer):
            if x == 0:
                AddMsgAndPrint("\nRemoving previous layers from your ArcMap session " + watershedGDB_name ,0)
                x+=1
            try:
                arcpy.Delete_management(layer)
                AddMsgAndPrint("\tRemoving " + layer + "",0)
            except:
                pass
    del x
    del layer
    del layersToRemove

    # ----------------------------------- Capture Default Environments
    tempExtent = arcpy.env.extent
    tempMask = arcpy.env.mask
    tempSnapRaster = arcpy.env.snapRaster
    tempCoordSys = arcpy.env.outputCoordinateSystem
    
    # ------------------------------------------------------------------ Retrieve properties of first raster
    firstDataset = inDatasets.split(';')[0].replace("'","")
    AddMsgAndPrint("\nAssigning output properties from first dataset in list: \"" + str(firstDataset) + "\"",0)
    
    desc = arcpy.Describe(firstDataset)
    sr = desc.SpatialReference
    units = sr.LinearUnitName

    AddMsgAndPrint("\n\tOutput Projection Name: " + sr.Name,0)
    AddMsgAndPrint("\tOutput XY Linear Units: " + units,0)

    # ----------------------------------- Set Environment Settings
    arcpy.env.extent = "MINOF"
    arcpy.env.mask = ""
    arcpy.env.snapRaster = ""
    arcpy.env.outputCoordinateSystem = sr
    
    # ---------------------------------------------------------------------------------------------- Create FGDB, FeatureDataset
    # Boolean - Assume FGDB already exists
    FGDBexists = True
                      
    # Create Watershed FGDB and feature dataset if it doesn't exist
    if not arcpy.Exists(watershedGDB_path):
        arcpy.CreateFileGDB_management(userWorkspace, watershedGDB_name)
        arcpy.CreateFeatureDataset_management(watershedGDB_path, "Layers", sr)
        AddMsgAndPrint("\nSuccessfully created File Geodatabase: " + watershedGDB_name,0)
        FGDBexists = False

    # if GDB already existed but feature dataset doesn't
    if not arcpy.Exists(watershedFD):
        arcpy.CreateFeatureDataset_management(watershedGDB_path, "Layers", sr)

    # ----------------------------------------------------------------------------------------------- Clean old files if FGDB already existed.
    if FGDBexists:    
        gridsToRemove = (mergedDataset)
        x = 0        
        for grid in gridsToRemove:
            if arcpy.Exists(grid):
                # strictly for formatting
                if x == 0:
                    AddMsgAndPrint("\nRemoving old files from FGDB: " + watershedGDB_name ,0)
                    x += 1
                try:
                    arcpy.Delete_management(grid)
                    AddMsgAndPrint("\tDeleting..." + os.path.basename(grid),0)
                except:
                    pass
        del x
        del grid
        del gridsToRemove

    # ----------------------------------------------------------------------------------------------- Create New AOI
    # if paths are not the same then assume AOI was manually digitized
    # or input is some from some other feature class/shapefile
    if not arcpy.Describe(AOI).CatalogPath == projectAOI:       
        # delete the AOI feature class; new one will be created           
        if arcpy.Exists(projectAOI):
            try:
                arcpy.Delete_management(projectAOI)
                arcpy.CopyFeatures_management(AOI, projectAOI)
                AddMsgAndPrint("\nSuccessfully Recreated Area of Interest: " + str(os.path.basename(projectAOI)),0)
            except:
                print_exception()
                arcpy.env.overwriteOutput = True
            
        else:
            arcpy.CopyFeatures_management(AOI, projectAOI)
            AddMsgAndPrint("\nSuccessfully Created Area of Interest: " + str(os.path.basename(projectAOI)),0)

    # paths are the same therefore input IS projectAOI
    else:
        AddMsgAndPrint("\nUsing existing " + str(os.path.basename(projectAOI)) + " feature class:",0)

    if arcpy.Describe(projectAOI).ShapeType != "Polygon":
        AddMsgAndPrint("\n\nYour Area of Interest must be a polygon layer. Exiting...\n",2)
        sys.exit()

    # --------------------------------------------------------------------------------------------------- Clip Rasters
    x = 0
    # Get number of datasets to merge
    datasets = len(inDatasets.split(';'))
    inDatasets = inDatasets.replace(";",",")
    AddMsgAndPrint("\nClipping input data to " + str(os.path.basename(projectAOI)) + "...",0)
    while x < datasets:
        dataset = inDatasets.split(',')[x].replace("'","")
        AddMsgAndPrint("\tClipping " + str(dataset) + "...",0)
        outClip = watershedGDB_path + os.sep + "clip" + "_" + str(x)
        arcpy.Clip_analysis(dataset, projectAOI, outClip)
        if x == 0:
            # Start mosaic list
            mosaicList = "" + str(outClip) + ""
        else:
            # Append to list
            mosaicList = mosaicList + ";" + str(outClip)
        x += 1
    del x
    del outClip
    
    # ------------------------------------------------------------------------------------------------- Merge Clipped Data
    if arcpy.Exists(mergedDataset):
        arcpy.Delete_management(mergedDataset)# Redundant, I know but just in case....
        
    # Merge Clipped Datasets
    AddMsgAndPrint("\nMerging clipped data...",0)
    arcpy.Merge_management(mosaicList, mergedDataset, "")
    AddMsgAndPrint("\tSuccessfully merged " + str(datasets) + " datasets",0)
    
    del datasets
    del mosaicList
    # ----------------------------------------------------------------------------------------------------- Delete intermediate data
    AddMsgAndPrint("\nDeleting intermediate data...",0)
    arcpy.env.workspace = watershedGDB_path
    fcs = arcpy.ListFeatureClasses("clip_*")
    rasts = arcpy.ListRasters("clip_*", "All")
    for fc in fcs:
        arcpy.Delete_management(fc, "")
    for rast in rasts:
        arcpy.Delete_management(rast, "")
    del fcs
    del rasts

    # ------------------------------------------------------------------------------------------------ Compact FGDB
    try:
        arcpy.Compact_management(watershedGDB_path)
        AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path),0)    
    except:
        pass
    
    # ------------------------------------------------------------------------------------------------ Add to ArcMap
    arcpy.SetParameterAsText(4, projectAOI)
    arcpy.SetParameterAsText(5, mergedDataset)
    AddMsgAndPrint("\nAdding Layers to ArcMap...",0)

    # ----------------------------------- Restore Default Environments
    arcpy.env.extent = tempExtent
    arcpy.env.mask = tempMask
    arcpy.env.snapRaster = tempSnapRaster
    arcpy.env.outputCoordinateSystem = tempCoordSys

    AddMsgAndPrint("\nProcessing Complete!",0)
    
    # ---------------------------------------------------------------------------------------------------- Cleanup
except SystemExit:
    pass

except KeyboardInterrupt:
    AddMsgAndPrint("Interruption requested....exiting")

except:
    print_exception()     
    

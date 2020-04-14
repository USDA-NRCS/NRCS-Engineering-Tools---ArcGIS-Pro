## MergeDEMs.py
##
## Author unknown - Likely Mead, Diaz, and/or Morse, 2013
## Updated by Chris Morse, USDA NRCS, 2019
##
## Clips and merges multiple raster datasets (intended for DEMs) into a single raster dataset within a project AOI
## Not appropriate for multi-band rasters

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
    f.write("Executing \"Clip and Merge Adjacent DEM\" Tool\n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write("ArcGIS Version: " + str(arcpy.GetInstallInfo()['Version']) + "\n")
    f.write("User Parameters:\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tInput Rasters " + inRasters.replace(";",", ") + "\n")
    f.write("\tOutput Raster " + mergedDEM + "\n")
    
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
    # ----------------------------------------------- Check out Spatial Analyst License
    if arcpy.CheckExtension("spatial") == "Available":
        arcpy.CheckOutExtension("spatial")
    else:
        arcpy.AddError("\nSpatial Analyst Extension not enabled. Please enable Spatial Analyst and try again. Exiting...\n")
        sys.exit()
        
    # ----------------------------------------------- Input Parameters
    userWorkspace = arcpy.GetParameterAsText(0)
    AOI = arcpy.GetParameterAsText(1)
    inRasters = arcpy.GetParameterAsText(2)

    # ------------------------------------------------------------------- Variables
    projectName = arcpy.ValidateTableName(os.path.basename(userWorkspace).replace(" ","_"))

    watershedGDB_name = os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.gdb"  # replace spaces for new FGDB name
    watershedGDB_path = userWorkspace + os.sep + watershedGDB_name
    watershedFD = watershedGDB_path + os.sep + "Layers"

    #arcpy.env.workspace = watershedGDB_path
    # ------------------------------------------------------------------ Permanent Datasets
    mergedDEM = watershedGDB_path + os.sep + projectName + "_mergedDEM"
    # Must Have a unique name for output -- Append a unique digit to watershed if required
    x = 1
    while x > 0:
        if arcpy.Exists(mergedDEM):
            mergedDEM = watershedGDB_path + os.sep + projectName + "_mergedDEM" + str(x)
            x += 1
        else:
            x = 0
    del x
    
    projectAOI = watershedFD + os.sep + os.path.basename(mergedDEM) + "_AOI"
    
    # Start log file
    textFilePath = userWorkspace + os.sep + projectName + "_EngTools.txt"
    logBasicSettings()    
    
    # ------------------------------------------------------------------ Intermediate Data
    tempDEM = watershedGDB_path + os.sep + "tempDEM"
    #outCLip = userWorkspace + os.sep + "clip" --- defined below in loop

    # ------------------------------- Map Layers
    aoiOut = "" + os.path.basename(projectAOI) + ""
    demOut = "" + os.path.basename(mergedDEM) + ""
    
    # ----------------------------------- Capture Default Environments
    
    tempExtent = arcpy.env.extent
    tempMask = arcpy.env.mask
    tempSnapRaster = arcpy.env.snapRaster
    tempCellSize = arcpy.env.cellSize
    tempCoordSys = arcpy.env.outputCoordinateSystem
    
    # ------------------------------------------------------------------ Retrieve properties of first raster
    #firstRast = inRasters.split(';')[0]
    firstRast = (inRasters.split(';')[0]).replace("'","")
    
    AddMsgAndPrint("\nAssigning output raster properties from first raster in list: \"" + str(firstRast) + "\"",0)

    desc = arcpy.Describe(firstRast)
    sr = desc.SpatialReference
    units = sr.LinearUnitName
    cellSize = desc.MeanCellWidth

    AddMsgAndPrint("\n\tOutput Projection Name: " + sr.Name,0)
    AddMsgAndPrint("\tOutput XY Linear Units: " + units,0)
    AddMsgAndPrint("\tOutput Cell Size: " + str(desc.MeanCellWidth) + " x " + str(desc.MeanCellHeight) + " " + units,0)    

    # ----------------------------------- Set Environment Settings
    arcpy.env.extent = "MINOF"
    arcpy.env.cellSize = cellSize
    arcpy.env.mask = ""
    arcpy.env.snapRaster = ""
    arcpy.env.outputCoordinateSystem = sr
    
    # ------------------------------------------------------------------- Remove previous data from arcMap if present
    layersToRemove = (demOut,aoiOut)

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
        gridsToRemove = (mergedDEM,tempDEM)
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
    # Get number of rasters to merge
    grids = len(inRasters.split(';'))
    inRasters = inRasters.replace(";",",")

    while x < grids:
        raster = inRasters.split(',')[x].replace("'","")
        AddMsgAndPrint("\nClipping " + str(raster) + " to " + str(os.path.basename(projectAOI)) + "...",0)
        outClip = watershedGDB_path + os.sep + "clip" + "_" + str(x)
        extractedDEM = arcpy.sa.ExtractByMask(raster, projectAOI)
        extractedDEM.save(outClip)
        if x == 0:
            # Start mosaic list
            mosaicList = "" + str(outClip) + ""
        else:
            # Append to list
            mosaicList = mosaicList + ";" + str(outClip)
        x += 1
        
    del x
    del raster
    del outClip
    
    # ------------------------------------------------------------------------------------------------- Merge Clipped Data

    if arcpy.Exists(tempDEM):
        arcpy.Delete_management(tempDEM)# Redundant, I know but just in case....
        
    # Mosaic Clipped Rasters
    arcpy.MosaicToNewRaster_management(mosaicList, watershedGDB_path, "tempDEM", "#", "32_BIT_FLOAT", cellSize, "1", "MEAN", "#")
    AddMsgAndPrint("\nSuccessfully merged " + str(grids) + " rasters",0)
    
    del grids

    # ------------------------------------------------------------------------------------------------- Fill any gaps with focal mean
    # RasterCalculator is not available in arcpy. Need to do this as separate steps now (10.16.2019).
    # 1. Create the focal mean surface.
    # 2. Execute Con and if null, then use the focal mean surface, else use the normal surface.
    outFocal = arcpy.sa.FocalStatistics(tempDEM, "RECTANGLE 3 3 CELL", "MEAN", "DATA")
    outCon = arcpy.sa.Con(arcpy.sa.IsNull(tempDEM), outFocal, tempDEM)
    outCon.save(mergedDEM)
    arcpy.Delete_management(outFocal)
    
##    expression = "con(isnull([" + str(tempDEM) + "]),focalmean([" + str(tempDEM) + "], rectangle, 3, 3, DATA),[" + str(tempDEM) + "])"
##    outSOMA = arcpy.sa.RasterCalculator(expression)
##    outSOMA.save(mergedDEM)
    
    AddMsgAndPrint("\nSuccessfully removed any gaps in merged data",0)

    arcpy.Delete_management(tempDEM) 
##    del expression   

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

    arcpy.SetParameterAsText(3, projectAOI)
    arcpy.SetParameterAsText(4, mergedDEM)
    AddMsgAndPrint("\nAdding Layers to ArcMap...",0)

    # ----------------------------------- Restore Default Environments
    arcpy.env.extent = tempExtent
    arcpy.env.mask = tempMask
    arcpy.env.snapRaster = tempSnapRaster
    arcpy.env.cellSize = tempCellSize
    arcpy.env.outputCoordinateSystem = tempCoordSys

    AddMsgAndPrint("\nProcessing Complete!",0)

except SystemExit:
    pass

except KeyboardInterrupt:
    AddMsgAndPrint("Interruption requested....exiting")

except:
    print_exception()     
    

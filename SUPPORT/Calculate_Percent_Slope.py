## Calculate_Percent_Slope.py
##
## Created by Peter Mead, Adolfo Diaz, USDA NRCS, 2013
## Updated by Chris Morse, USDA NRCS, 2019
##
## Create a slope percent raster by area of interest

## ================================================================================================================ 
def print_exception():
    tb = sys.exc_info()[2]
    l = traceback.format_tb(tb)
    l.reverse()
    tbinfo = "".join(l)
    AddMsgAndPrint("----------ERROR Start-------------------",2)
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
    except:
        pass
    
    if severity == 0:
        arcpy.AddMessage(msg)
    elif severity == 1:
        arcpy.AddWarning(msg)
    elif severity == 2:
        arcpy.AddError(msg)

## ================================================================================================================
def logBasicSettings():    
    # record basic user inputs and settings to log file for future purposes

    import getpass, time

    f = open(textFilePath,'a+')
    f.write("\n##################################################################\n")
    f.write("Executing \"Calculate Percent Slope\" Tool" + "\n")
    f.write("User Name: " + getpass.getuser()+ "\n")
    f.write("Date Executed: " + time.ctime()+ "\n")
    f.write("ArcGIS Version: " + str(arcpy.GetInstallInfo()['Version']) + "\n")
    f.write("User Parameters:\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tDem: " + inputDEM + "\n")
    f.write("\tElevation Z-units: " + zUnits + "\n")
    
    f.close
    del f

## ================================================================================================================
def splitThousands(someNumber):
# will determine where to put a thousands seperator if one is needed.
# Input is an integer.  Integer with or without thousands seperator is returned.

    try:
        return re.sub(r'(\d{3})(?=\d)', r'\1,', str(someNumber)[::-1])[::-1]
    except:
        print_exception()
        return someNumber  

## ================================================================================================================
# Import system modules
import arcpy, sys, os, traceback, re
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
    # Check out Spatial Analyst License        
    if arcpy.CheckExtension("Spatial") == "Available":
        arcpy.CheckOutExtension("Spatial")
    else:
        arcpy.AddError("\nSpatial Analyst Extension not enabled. Please enable Spatial Analyst from the Tools/Extensions menu. Exiting...\n")
        sys.exit()

    arcpy.SetProgressorLabel("Setting Variables")
    #--------------------------------------------------------------------- Input Parameters
    userWorkspace = arcpy.GetParameterAsText(0)
    inputDEM = arcpy.GetParameterAsText(1)
    zUnits = arcpy.GetParameterAsText(2)
    AOI = arcpy.GetParameterAsText(3)

    # --------------------------------------------------------------------------------------------- Define Variables
    projectName = arcpy.ValidateTableName(os.path.basename(userWorkspace).replace(" ","_"))
    watershedGDB_name = os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.gdb"  # replace spaces for new FGDB name
    watershedGDB_path = userWorkspace + os.sep + watershedGDB_name
    watershedFD = watershedGDB_path + os.sep + "Layers"

    # ---------------------------------------------------------- Datasets
    # ------------------------------ Permanent Datasets
    projectAOI = watershedFD + os.sep + projectName + "_AOI"
    slopeGrid = watershedGDB_path + os.sep + projectName + "_Slope"
    
    # ----------------------------- Temporary Datasets
    DEM_aoi = watershedGDB_path + os.sep + "slopeDEM"
    DEMsmooth = watershedGDB_path + os.sep + "DEMsmooth_prcntSlope"

    # Feature Layers to Arcmap
    aoiOut = "" + projectName + "_AOI"
    slopeOut = "" + projectName + "_Slope"

    # log inputs and settings to file
    textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.txt"
    logBasicSettings()

    # ---------------------------------------------------------------------------------------------- Validate Inputs
    arcpy.SetProgressorLabel("Validating Inputs")
    AddMsgAndPrint("\nValidating Inputs...",0)

    # Exit if AOI contains more than 1 digitized area.
    if int(arcpy.GetCount_management(AOI).getOutput(0)) > 1:
        AddMsgAndPrint("\n\nYou can only digitize 1 Area of interest or provide an AOI with one feature. Please try again. Exiting...",2)
        sys.exit()

    # --------------------------------------------------------------------- Gather DEM Info
    arcpy.SetProgressorLabel("Gathering information about input DEM file")
    AddMsgAndPrint("\nInformation about input DEM file " + os.path.basename(inputDEM)+ ":",0)
    
    desc = arcpy.Describe(inputDEM)
    sr = desc.SpatialReference
    cellSize = desc.MeanCellWidth
    units = sr.LinearUnitName

    if units == "Meter":
        units = "Meters"
    elif units == "Foot":
        units = "Feet"
    elif units == "Foot_US":
        units = "Feet"
    elif units == "Feet":
        units = "Feet"

##    ## Remove this block because vertical units should be required to reduce chances of this tool producing improper results ##
##    # if zUnits were left blank than assume Z-values are the same as XY units.
##    if not len(zUnits) > 0:
##        zUnits = units

    # Coordinate System must be a Projected Type in order to continue.
    # zfactor will be applied to slope calculation if zUnits are different than XY units
    
    # Coordinate System must be a Projected Type in order to continue.
    # zfactor will be applied to slope calculation if zUnits are different than XY units
    
    if sr.Type == "Projected":
        if zUnits == "Meters":
            if units == "Feet":
                Zfactor = 3.280839896
            if units == "Meters":
                Zfactor = 1
        elif zUnits == "Feet":           
            if units == "Feet":
                Zfactor = 1
            if units == "Meters":
                Zfactor = 0.3048                  
        elif zUnits == "Centimeters":   
            if units == "Feet":
                Zfactor = 0.03280839896
            if units == "Meters":
                Zfactor = 0.01
        elif zUnits == "Inches":
            if units == "Feet":
                Zfactor = 0.0833333
            if units == "Meters":
                Zfactor = 0.0254
      
        AddMsgAndPrint("\tProjection Name: " + sr.Name,0)
        AddMsgAndPrint("\tXY Linear Units: " + units,0)
        AddMsgAndPrint("\tElevation Values (Z): " + zUnits,0) 
        AddMsgAndPrint("\tCell Size: " + str(desc.MeanCellWidth) + " x " + str(desc.MeanCellHeight) + " " + units,0)

    else:
        AddMsgAndPrint("\n\n\t" + os.path.basename(inputDEM) + " is NOT in a Projected Coordinate System. Exiting...",2)
        sys.exit(0)

    # ------------------------------------- Remove layers from ArcMap if they exist
    layersToRemove = (slopeOut)   
    x = 0
    for layer in layersToRemove:
        if arcpy.Exists(layer):
            if x == 0:
                AddMsgAndPrint("\nRemoving previous layers from your ArcMap Session..",0)
                x+=1
            try:
                arcpy.Delete_management(layer)
                AddMsgAndPrint("Removing..." + layer + "",0)
            except:
                pass
    del x, layersToRemove
    
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
        gridsToRemove = (DEM_aoi,DEMsmooth,slopeGrid)
        x = 0
        for grid in gridsToRemove:
            if arcpy.Exists(grid):
                # strictly for formatting
                if x < 1:
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
                AddMsgAndPrint("\nSuccessfully Recreated Area of Interest",0)
            except:
                print_exception()
                arcpy.env.overwriteOutput = True
        else:
            arcpy.CopyFeatures_management(AOI, projectAOI)
            AddMsgAndPrint("\nSuccessfully Created Area of Interest:" + str(os.path.basename(projectAOI)),0)

    # paths are the same therefore input IS projectAOI
    else:
        AddMsgAndPrint("\nUsing existing \"" + str(projectName) + "_AOI\" feature class:",0)

    if arcpy.Describe(projectAOI).ShapeType != "Polygon":
        AddMsgAndPrint("\n\nYour Area of Interest must be a polygon layer!.....Exiting!",2)
        sys.exit()

    # --------------------------------------------------------------------------------------------  Add DEM Properties to AOI
    # Write input DEM name to AOI 
    # Note: VB Expressions may need to be updated to Python to prepare for conversion to Pro
    if len(arcpy.ListFields(projectAOI,"INPUT_DEM")) < 1:
        arcpy.AddField_management(projectAOI, "INPUT_DEM", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    #arcpy.CalculateField_management(projectAOI, "INPUT_DEM", "\"" + os.path.basename(inputDEM) +  "\"", "VB", "")
    expression = '"' + os.path.basename(inputDEM) + '"'
    arcpy.CalculateField_management(projectAOI, "INPUT_DEM", expression, "PYTHON_9.3")
    del expression
    
    # Write XY Units to AOI
    if len(arcpy.ListFields(projectAOI,"XY_UNITS")) < 1:
        arcpy.AddField_management(projectAOI, "XY_UNITS", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    expression = '"' + str(units) + '"'
    #arcpy.CalculateField_management(projectAOI, "XY_UNITS", "\"" + str(units) + "\"", "VB", "")
    arcpy.CalculateField_management(projectAOI, "XY_UNITS", expression, "PYTHON_9.3")
    del expression
    
    # Write Z Units to AOI
    if len(arcpy.ListFields(projectAOI,"Z_UNITS")) < 1:
        arcpy.AddField_management(projectAOI, "Z_UNITS", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    expression = '"' + str(zUnits) + '"'
    #arcpy.CalculateField_management(projectAOI, "Z_UNITS", "\"" + str(zUnits) + "\"", "VB", "")
    arcpy.CalculateField_management(projectAOI, "Z_UNITS", expression, "PYTHON_9.3")
    del expression
    
   #--------------------------------------------------------------------- Add Acre Field
    if len(arcpy.ListFields(projectAOI,"Acres")) <1:
        arcpy.AddField_management(projectAOI, "Acres", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")      

    #--------------------------------------------------------------------- Calculate Acres            
    expression = "!Shape.Area@acres!"
    arcpy.CalculateField_management(projectAOI, "Acres", expression, "PYTHON_9.3")

    # ----------------------------------------------------------------------------------------------- Calculate slope and return Avg.Slope
    # extract AOI area
    maskedDEM = arcpy.sa.ExtractByMask(inputDEM, AOI)
    maskedDEM.save(DEM_aoi)
    AddMsgAndPrint("\nSuccessully Clipped " + os.path.basename(inputDEM) + " using " + os.path.basename(projectAOI),0)

    # Smooth the DEM to remove noise
    outFocalStats = arcpy.sa.FocalStatistics(DEM_aoi, "RECTANGLE 3 3 CELL","MEAN","DATA")
    outFocalStats.save(DEMsmooth)
    AddMsgAndPrint("\nSuccessully Smoothed the Clipped DEM",0)

    # Calculate Slope using appropriate Z factor
    slopeType = "PERCENT_RISE"
    outSlope = arcpy.sa.Slope(DEMsmooth, slopeType, Zfactor)
    outSlope.save(slopeGrid)
    AddMsgAndPrint("\nSuccessully Created Slope Grid using a Z-factor of " + str(Zfactor),0)       

    # ---------------------------------------------------------------------------------------------- Delete Intermediate data
    datasetsToRemove = (DEM_aoi,DEMsmooth)
    x = 0
    for dataset in datasetsToRemove:
        if arcpy.Exists(dataset):
            # Strictly Formatting
            if x < 1:
                x += 1
            try:
                arcpy.Delete_management(dataset)
            except:
                pass
    del dataset
    del datasetsToRemove
    del x

    # ------------------------------------------------------------------------------------------------ Compact FGDB
    try:
        arcpy.Compact_management(watershedGDB_path)
        AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path),0)    
    except:
        pass 

    # ------------------------------------------------------------------------------------------------ Prepare to Add to Arcmap
    arcpy.SetParameterAsText(4, projectAOI)
    arcpy.SetParameterAsText(5, slopeGrid)
    
    AddMsgAndPrint("\nAdding Results to ArcMap",0)    
    AddMsgAndPrint("\n",0)
    # ------------------------------------------------------------------------------------------------ Cleanup
    arcpy.RefreshCatalog(watershedGDB_path)
    
##    # Restore original environments
##    gp.extent = tempExtent
##    gp.mask = tempMask
##    gp.SnapRaster = tempSnapRaster
##    gp.CellSize = tempCellSize
##    gp.OutputCoordinateSystem = tempCoordSys

except SystemExit:
    pass

except KeyboardInterrupt:
    AddMsgAndPrint("Interruption requested....exiting")

except:
    print_exception()     

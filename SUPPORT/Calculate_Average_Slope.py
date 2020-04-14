## Calculate_Average_Slope.py
##
## Created by Peter Mead, Adolfo Diaz, USDA NRCS, 2013
## Updated by Chris Morse, USDA NRCS, 2019
##
## Compute average slope in defined area(s) by percent or degrees

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
    f.write("Executing \"Calculate Average Slope\" Tool \n")
    f.write("User Name: " + getpass.getuser()+ "\n")
    f.write("Date Executed: " + time.ctime()+ "\n")
    f.write("ArcGIS Version: " + str(arcpy.GetInstallInfo()['Version']) + "\n")
    f.write("User Parameters:\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tDem: " + inputDEM + "\n")
    f.write("\tElevation Z-units: " + zUnits + "\n")
    f.write("\tSlope Type: " + slopeType + "\n")
    
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
#import  arcgisscripting

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
    slopeType = arcpy.GetParameterAsText(4)
    
    # --------------------------------------------------------------------------------------------- Define Variables
    projectName = arcpy.ValidateTableName(os.path.basename(userWorkspace).replace(" ","_"))
    watershedGDB_name = os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.gdb"  # replace spaces for new FGDB name
    watershedGDB_path = userWorkspace + os.sep + watershedGDB_name
    watershedFD = watershedGDB_path + os.sep + "Layers"

    # ---------------------------------------------------------- Datasets
    # ------------------------------ Permanent Datasets
    projectAOI = watershedFD + os.sep + projectName + "_AOI"
    AOIname = projectName + "_AOI"
    
    # ----------------------------- Temporary Datasets
    DEM_aoi = watershedGDB_path + os.sep + "slopeDEM"
    DEMsmooth = watershedGDB_path + os.sep + "DEMsmooth_calcAvgSlope"
    slopeGrid = watershedGDB_path + os.sep + "slopeGrid_calcAvgSlope"
    slopeStats = watershedGDB_path + os.sep + "slopeStats"

    # ------------------------------- Map Layers
    aoiOut = "" + projectName + "_AOI"

    # log inputs and settings to file
    textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.txt"
    logBasicSettings()

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
        AddMsgAndPrint("\n\n\t" + os.path.basename(inputDEM) + " is NOT in a projected Coordinate System. Exiting...",2)
        sys.exit(0)
        
##    # ------------------------------------------------------------------------------- Capture default environments
##    tempExtent = gp.Extent
##    tempMask = gp.mask
##    tempSnapRaster = gp.SnapRaster
##    tempCellSize = gp.CellSize
##    tempCoordSys = gp.OutputCoordinateSystem
##
##    # ------------------------------------------------------------------------------- Set environments
##    gp.Extent = "MINOF"
##    gp.CellSize = cellSize
##    gp.mask = ""
##    gp.SnapRaster = inputDEM
##    gp.OutputCoordinateSystem = sr

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
        gridsToRemove = (DEM_aoi,DEMsmooth,slopeGrid,slopeStats)
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
        AddMsgAndPrint("\n\nYour Area of Interest must be a polygon layer. Exiting...",2)
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
    
   #--------------------------------------------------------------------- Add uniqueID, Acre Field, and Avg_Slope field
    if not len(arcpy.ListFields(projectAOI,"Acres")) > 0:
        arcpy.AddField_management(projectAOI, "Acres", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")      

    if not len(arcpy.ListFields(projectAOI,"Avg_Slope")) > 0:
        arcpy.AddField_management(projectAOI, "Avg_Slope", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

    if not len(arcpy.ListFields(projectAOI,"UID")) > 0:
        arcpy.AddField_management(projectAOI, "UID", "TEXT", "", "", "18", "", "NULLABLE", "NON_REQUIRED", "")

    #--------------------------------------------------------------------- Calculate GUID
    # This value is needed to standardize all possible inputs for objectID headings getting appended for cases where objectID already exists in inputs
    expression = "!OBJECTID!"
    arcpy.CalculateField_management(projectAOI, "UID", expression, "PYTHON_9.3")
    del expression

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

    # Calculate Slope using user specified slopeType and appropriate Z factor
    if slopeType == "Degrees":
        slopeType = "DEGREE"
    else:
        slopeType = "PERCENT_RISE"

    # create slopeGrid        
    outSlope = arcpy.sa.Slope(DEMsmooth, slopeType, Zfactor)
    outSlope.save(slopeGrid)
    AddMsgAndPrint("\nSuccessully Created Slope Grid using a Z-factor of " + str(Zfactor),0)

    # retreive slope average from raster properties if there is only 1 AOI delineation
    if int(arcpy.GetCount_management(projectAOI).getOutput(0)) < 2:
        # Retrieve mean and add to output
        avgSlope = arcpy.GetRasterProperties_management(slopeGrid, "MEAN").getOutput(0)
        #gp.CalculateField_management(projectAOI, "Avg_Slope", "" + avgSlope + "", "VB", "")
        arcpy.CalculateField_management(projectAOI, "Avg_Slope", avgSlope , "PYTHON_9.3")

        rows = arcpy.SearchCursor(projectAOI)
        row = rows.next()
        while row:
            AddMsgAndPrint("\nSuccessfully Calculated Average Slope",0)
            AddMsgAndPrint("\tAcres: " + str(splitThousands(round(row.Acres,2))),0)
            AddMsgAndPrint("\tArea: " + str(splitThousands(round(row.Shape_Area,2))) + " Sq. " + units,0)
            AddMsgAndPrint("\tAvg. Slope: " + str(round(float(avgSlope),2)),0)
            break            
        del rows
        del row

    # retreive slope average from zonal statistics if there is more than 1 AOI delineation
    else:
        arcpy.sa.ZonalStatisticsAsTable(projectAOI, "UID", slopeGrid, slopeStats, "DATA")
        AddMsgAndPrint("\nSuccessfully Calculated Average Slope for " + str(arcpy.GetCount_management(projectAOI).getOutput(0)) + " AOIs:",0)        

        # create an update cursor for each row of the AOI table and pull in the corresponding record from the slopestats table
        aoiRows = arcpy.UpdateCursor(projectAOI)
        aoiRow = aoiRows.next()
        while aoiRow:
            aoiID = aoiRow.UID
            rows = arcpy.SearchCursor(slopeStats)
            row = rows.next()
            while row:
                rowID = row.UID
                if rowID == aoiID:
                    zonalMeanValue = row.MEAN
                    aoiRow.Avg_Slope = zonalMeanValue
                    aoiRows.updateRow(aoiRow)
                    row = rows.next()
                else:
                    row = rows.next()
            aoiRow = aoiRows.next()      

        del aoiRows, aoiRow, aoiID, rows, row, rowID, zonalMeanValue

        # Tell the user the results
        rows = arcpy.SearchCursor(projectAOI)
        row = rows.next()
        while row:
            AddMsgAndPrint("\n\tAOI ID: " + str(row.UID),0)
            AddMsgAndPrint("\t\tAcres: " + str(splitThousands(round(row.Acres,2))),0)
            AddMsgAndPrint("\t\tArea: " + str(splitThousands(round(row.Shape_Area,2))) + " Sq. " + units,0)
            AddMsgAndPrint("\t\tAvg. Slope: " + str(round(row.Avg_Slope,2)),0)
            row = rows.next()

        del rows, row
       
    # ---------------------------------------------------------------------------------------------- Delete Intermediate data
    datasetsToRemove = (DEM_aoi,DEMsmooth,slopeStats,slopeGrid)
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
    # Remove the AOI from the map if it is present in the map
    if arcpy.Exists(projectAOI):
        mxd = arcpy.mapping.MapDocument("CURRENT")
        for df in arcpy.mapping.ListDataFrames(mxd):
            for lyr in arcpy.mapping.ListLayers(mxd, "", df):
                if lyr.name == AOIname:
                    arcpy.mapping.RemoveLayer(df, lyr)
    del mxd
    
    # Prep for proper layer file labels importing as determined by slope type selected to be run
    if slopeType == "PERCENT_RISE":
        arcpy.SetParameterAsText(5, projectAOI)
    else:
        arcpy.SetParameterAsText(6, projectAOI)
    
    AddMsgAndPrint("\nAdding " + str(aoiOut) + " to ArcMap",0)    
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

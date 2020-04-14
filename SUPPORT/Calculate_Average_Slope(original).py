# averageSlope.py
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
    # 
    # Split the message on \n first, so that if it's multiple lines, a GPMessage will be added for each line

    print msg
    
    try:

        f = open(textFilePath,'a+')
        f.write(msg + " \n")
        f.close

        del f

        if ArcGIS10:
            if not msg.find("\n") < 0 and msg.find("\n") < 4:
                gp.AddMessage(" ")        
        
        for string in msg.split('\n'):
            
            # Add a geoprocessing message (in case this is run as a tool)
            if severity == 0:
                gp.AddMessage(string)
                
            elif severity == 1:
                gp.AddWarning(string)
                
            elif severity == 2:
                gp.AddError(string)
                gp.AddMessage("    ")

        if ArcGIS10:
            if msg.find("\n") > 4:
                gp.AddMessage(" ")                
                
    except:
        pass

## ================================================================================================================
def logBasicSettings():    
    # record basic user inputs and settings to log file for future purposes

    import getpass, time

    f = open(textFilePath,'a+')
    f.write("\n################################################################################################################\n")
    f.write("Executing \"Calculate Average Slope\" Tool \n")
    f.write("User Name: " + getpass.getuser()+ "\n")
    f.write("Date Executed: " + time.ctime()+ "\n")
    f.write("ArcGIS Version: " + str(version) + "\n")
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
import sys, os, arcgisscripting, traceback, re

# Create the Geoprocessor object
gp = arcgisscripting.create(9.3)
gp.OverWriteOutput = 1

# Used to determine ArcGIS version
d = gp.GetInstallInfo('desktop')

keys = d.keys()

for k in keys:

    if k == "Version":

        version = " \nArcGIS %s : %s" % (k, d[k])
        print version

        if version.find("10.") > 0:
            ArcGIS10 = True

        else:
            ArcGIS10 = False

        break 

del d, keys
   
if version < 9.3:
    AddMsgAndPrint("\nThis tool requires ArcGIS version 9.3 or Greater.....EXITING",2)
    sys.exit("")            

try:
    # Check out Spatial Analyst License        
    if gp.CheckExtension("spatial") == "Available":
        gp.CheckOutExtension("spatial")
    else:
        gp.AddError("Spatial Analyst Extension not enabled. Please enable Spatial analyst from the Tools/Extensions menu")
        sys.exit("")
        
    #--------------------------------------------------------------------- Input Parameters
    userWorkspace = gp.GetParameterAsText(0)
    inputDEM = gp.GetParameterAsText(1)
    zUnits = gp.GetParameterAsText(2)
    AOI = gp.GetParameterAsText(3)
    slopeType = gp.GetParameterAsText(4)

    # Uncomment the following 5 lines to run from pythonWin 
##    userWorkspace = r'C:\flex'
##    inputDEM = r'G:\MLRAData\elevation\WI_Dane\Dane_LiDAR.gdb\wi025_dem_3m_utm16'
##    AOI = r'C:\flex\flex_EngTools.gdb\Layers\Project_AOI'
##    slopeType = "Percent"
##    zUnits = "Meters"

    # --------------------------------------------------------------------------------------------- Define Variables
    projectName = gp.ValidateTablename(os.path.basename(userWorkspace).replace(" ","_"))
    # Path of Log file; Log file will record everything done in a workspace
    textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.txt"

    watershedGDB_name = os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.gdb"  # replace spaces for new FGDB name
    watershedGDB_path = userWorkspace + os.sep + watershedGDB_name
    watershedFD = watershedGDB_path + os.sep + "Layers"

    # ---------------------------------------------------------- Datasets
    # ------------------------------ Permanent Datasets
    
    projectAOI = watershedFD + os.sep + projectName + "_AOI"   
    
    # ----------------------------- Temporary Datasets
    DEM_aoi = watershedGDB_path + os.sep + "slopeDEM"
    DEMsmooth = watershedGDB_path + os.sep + "DEMsmooth_calcAvgSlope"
    slopeGrid = watershedGDB_path + os.sep + "slopeGrid_calcAvgSlope"
    slopeStats = watershedGDB_path + os.sep + "slopeStats"

    # ------------------------------- Map Layers
    aoiOut = "" + projectName + "_AOI"

    # record basic user inputs and settings to log file for future purposes
    logBasicSettings()

    # ---------------------------------------------------------------------------------------------- Check DEM Coordinate System and Linear Units
    desc = gp.Describe(inputDEM)
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

    # if zUnits were left blank than assume Z-values are the same as XY units.
    if not len(zUnits) > 0:
        zUnits = units

    AddMsgAndPrint("\nGathering information about DEM: " + os.path.basename(inputDEM)+ ":",1)          

    # Coordinate System must be a Projected Type in order to continue.
    # zfactor will be applied to slope calculation if zUnits are different than XY units
    
    if sr.Type == "Projected":
        
        if zUnits == "Meters":
            if units == "Feet":
                Zfactor = 3.28084
            if units == "Meters":
                Zfactor = 1

        elif zUnits == "Feet":           
            if units == "Feet":
                Zfactor = 1
            if units == "Meters":
                Zfactor = 0.3048                  
                
        elif zUnits == "Centimeters":   
            if units == "Feet":
                Zfactor = 30.48
            if units == "Meters":
                Zfactor = 0.01

        # zUnits must be inches; no more choices                
        else:
            if units == "Feet":
                Zfactor = 12
            if units == "Meters":
                Zfactor = 39.3701
      
        AddMsgAndPrint("\tProjection Name: " + sr.Name,0)
        AddMsgAndPrint("\tXY Linear Units: " + units,0)
        AddMsgAndPrint("\tElevation Values (Z): " + zUnits,0) 
        AddMsgAndPrint("\tCell Size: " + str(desc.MeanCellWidth) + " x " + str(desc.MeanCellHeight) + " " + units,0)

    else:
        del desc
        del sr
        del units
        AddMsgAndPrint("\n\n\t" + os.path.basename(inputDEM) + " is NOT in a projected Coordinate System....EXITING",2)
        sys.exit(0)
    # ------------------------------------------------------------------------------- Capture default environments
    tempExtent = gp.Extent
    tempMask = gp.mask
    tempSnapRaster = gp.SnapRaster
    tempCellSize = gp.CellSize
    tempCoordSys = gp.OutputCoordinateSystem

    # ------------------------------------------------------------------------------- Set environments
    gp.Extent = "MINOF"
    gp.CellSize = cellSize
    gp.mask = ""
    gp.SnapRaster = inputDEM
    gp.OutputCoordinateSystem = sr

    # ---------------------------------------------------------------------------------------------- Create FGDB, FeatureDataset

    # Boolean - Assume FGDB already exists
    FGDBexists = True
                      
    # Create Watershed FGDB and feature dataset if it doesn't exist
    if not gp.exists(watershedGDB_path):
        gp.CreateFileGDB_management(userWorkspace, watershedGDB_name)
        gp.CreateFeatureDataset_management(watershedGDB_path, "Layers", sr)
        AddMsgAndPrint("\nSuccessfully created File Geodatabase: " + watershedGDB_name,1)
        FGDBexists = False

    # if GDB already existed but feature dataset doesn't
    if not gp.exists(watershedFD):
        gp.CreateFeatureDataset_management(watershedGDB_path, "Layers", sr)        

    # ----------------------------------------------------------------------------------------------- Clean old files if FGDB already existed.
    if FGDBexists:     
        
        gridsToRemove = (DEM_aoi,DEMsmooth,slopeGrid,slopeStats)

        x = 0
        for grid in gridsToRemove:

            if gp.exists(grid):
                
                # strictly for formatting
                if x < 1:
                    AddMsgAndPrint("\nRemoving old files from FGDB: " + watershedGDB_name ,1)
                    x += 1
                
                try:
                    gp.delete_management(grid)
                    AddMsgAndPrint("\tDeleting....." + os.path.basename(grid),1)
                except:
                    pass

        del x
        del grid
        del gridsToRemove

    # ----------------------------------------------------------------------------------------------- Create New AOI
    # if paths are not the same then assume AOI was manually digitized
    # or input is some from some other feature class/shapefile
    if not gp.Describe(AOI).CatalogPath == projectAOI:       

        # delete the AOI feature class; new one will be created            
        if gp.exists(projectAOI):
            
            try:
                gp.delete_management(projectAOI)
                gp.CopyFeatures_management(AOI, projectAOI)
                AddMsgAndPrint("\nSuccessfully Recreated Area of Interest",1)
            except:
                print_exception()
                gp.OverWriteOutput = 1
            
        else:
            gp.CopyFeatures_management(AOI, projectAOI)
            AddMsgAndPrint("\nSuccessfully Created Area of Interest:" + str(os.path.basename(projectAOI)),1)

    # paths are the same therefore input IS projectAOI
    else:
        AddMsgAndPrint("\nUsing existing \"" + str(projectName) + "_AOI\" feature class:",1)

    if gp.Describe(projectAOI).ShapeType != "Polygon":
        AddMsgAndPrint("\n\nYour Area of Interest must be a polygon layer!.....Exiting!",2)
        sys.exit()
    # --------------------------------------------------------------------------------------------  Add DEM Properties to AOI
    # Write input DEM name to AOI 
    if len(gp.ListFields(projectAOI,"INPUT_DEM")) <1:
        gp.AddField_management(projectAOI, "INPUT_DEM", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.CalculateField_management(projectAOI, "INPUT_DEM", "\"" + os.path.basename(inputDEM) +  "\"", "VB", "")
    # Write XY Units to AOI
    if len(gp.ListFields(projectAOI,"XY_UNITS")) <1:
        gp.AddField_management(projectAOI, "XY_UNITS", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.CalculateField_management(projectAOI, "XY_UNITS", "\"" + str(units) + "\"", "VB", "")
    # Write Z Units to AOI
    if len(gp.ListFields(projectAOI,"Z_UNITS")) <1:
        gp.AddField_management(projectAOI, "Z_UNITS", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.CalculateField_management(projectAOI, "Z_UNITS", "\"" + str(zUnits) + "\"", "VB", "")
    
   #--------------------------------------------------------------------- Add Acre Field and Avg_Slope field
    if not len(gp.ListFields(projectAOI,"Acres")) > 0:
        gp.AddField_management(projectAOI, "Acres", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")      

    if not len(gp.ListFields(projectAOI,"Avg_Slope")) > 0:
        gp.AddField_management(projectAOI, "Avg_Slope", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")         

    #--------------------------------------------------------------------- Calculate Acres            
    if units == "Meters":
        expression = "[Shape_Area] / 4046.86"
        gp.CalculateField_management(projectAOI, "Acres", expression, "VB", "")
        del expression

    elif units == "Feet":
        expression = "[Shape_Area] / 43560"
        gp.CalculateField_management(projectAOI, "Acres", expression, "VB", "")
        del expression

    else:
        AddMsgAndPrint("\tCould not calculate Acres",2)

    # ----------------------------------------------------------------------------------------------- Calculate slope and return Avg.Slope
    # extract AOI area
    gp.ExtractByMask_sa(inputDEM, AOI, DEM_aoi)
    AddMsgAndPrint("\nSuccessully Clipped " + os.path.basename(inputDEM) + " using " + os.path.basename(projectAOI),1)

    # Smooth the DEM to remove noise
    gp.Focalstatistics_sa(DEM_aoi, DEMsmooth,"RECTANGLE 3 3 CELL","MEAN","DATA")    
    AddMsgAndPrint("\nSuccessully Smoothed the Clipped DEM",1)

    # Calculate Slope using user specified slopeType and appropriate Z factor
    if slopeType == "Degrees":
        slopeType = "DEGREE"
    else:
        slopeType = "PERCENT_RISE"

    # create slopeGrid        
    gp.Slope_sa(DEMsmooth, slopeGrid, slopeType, Zfactor)

    AddMsgAndPrint("\nSuccessully Created Slope Grid using a Z-factor of " + str(Zfactor),1)

    # retreive slope average from raster properties if there is only 1 AOI delineation
    if int(gp.GetCount_management(projectAOI).getOutput(0)) < 2:

        # Retrieve mean and add to output
        avgSlope = gp.GetRasterProperties_management(slopeGrid, "MEAN").getOutput(0)
        gp.CalculateField_management(projectAOI, "Avg_Slope", "" + avgSlope + "", "VB", "")

        rows = gp.searchcursor(projectAOI)
        row = rows.next()

        while row:
            AddMsgAndPrint("\nSuccessfully Calculated Average Slope",1)
            AddMsgAndPrint("\tAcres: " + str(splitThousands(round(row.Acres,2))),0)
            AddMsgAndPrint("\tArea: " + str(splitThousands(round(row.Shape_Area,2))) + " Sq. " + units,0)
            AddMsgAndPrint("\tAvg. Slope: " + str(round(float(avgSlope),2)),0)

            break            

        del rows
        del row

    # retreive slope average from zonal statistics if there is more than 1 AOI delineation
    else:
        gp.ZonalStatisticsAsTable_sa(projectAOI, "OBJECTID", slopeGrid, slopeStats, "DATA")

        # go through each zonal Stat record and pull out the Mean value
        rows = gp.searchcursor(slopeStats)
        row = rows.next()

        AddMsgAndPrint("\nSuccessfully Calculated Average Slope for " + str(gp.GetCount_management(projectAOI).getOutput(0)) + " AOIs:",1)        

        while row:
            wtshdID = row.OBJECTID
            zonalValue = row.VALUE
            zonalMeanValue = row.MEAN

            whereclause = "OBJECTID = " + str(zonalValue)
            wtshdRows = gp.UpdateCursor(projectAOI,whereclause)
            wtshdRow = wtshdRows.next()

            # Pass the Mean value from the zonalStat table to the AOI FC.
            while wtshdRow:
                wtshdRow.Avg_Slope = zonalMeanValue
                wtshdRows.UpdateRow(wtshdRow)

                # Inform the user of Watershed Acres, area and avg. slope
                AddMsgAndPrint("\n\tAOI ID: " + str(wtshdRow.OBJECTID),1)
                AddMsgAndPrint("\t\tAcres: " + str(splitThousands(round(wtshdRow.Acres,2))),1)
                AddMsgAndPrint("\t\tArea: " + str(splitThousands(round(wtshdRow.Shape_Area,2))) + " Sq. " + units,1)
                AddMsgAndPrint("\t\tAvg. Slope: " + str(round(zonalMeanValue,2)),1)
                                   
                break

            row = rows.next()        

            del wtshdID
            del zonalValue
            del zonalMeanValue
            del whereclause
            del wtshdRows
            del wtshdRow

        del rows
        del row
       
    # ---------------------------------------------------------------------------------------------- Delete Intermediate data
    datasetsToRemove = (DEM_aoi,DEMsmooth,slopeStats,slopeGrid)

    x = 0
    for dataset in datasetsToRemove:

        if gp.exists(dataset):

            # Strictly Formatting
            if x < 1:
                x += 1
                
            try:
                gp.delete_management(dataset)
            except:
                pass
            
    del dataset
    del datasetsToRemove
    del x

    # ------------------------------------------------------------------------------------------------ Compact FGDB
    try:
        gp.compact_management(watershedGDB_path)
        AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path),1)    
    except:
        pass
    # ------------------------------------------------------------------------------------------------ Prepare to Add to Arcmap

    gp.SetParameterAsText(5, projectAOI)

    AddMsgAndPrint("\nAdding " + str(aoiOut) + " to ArcMap",1)    
    AddMsgAndPrint("\n",1)
    # ------------------------------------------------------------------------------------------------ Cleanup
    gp.RefreshCatalog(watershedGDB_path)
    
    # Restore original environments
    gp.extent = tempExtent
    gp.mask = tempMask
    gp.SnapRaster = tempSnapRaster
    gp.CellSize = tempCellSize
    gp.OutputCoordinateSystem = tempCoordSys

    try:
        del gp
        del userWorkspace
        del inputDEM
        del AOI
        del slopeType
        del zUnits
        del textFilePath
        del watershedGDB_name
        del watershedGDB_path
        del watershedFD
        del projectAOI
        del aoiOut
        del DEM_aoi
        del DEMsmooth
        del slopeGrid
        del desc
        del sr
        del units
        del FGDBexists
        del avgSlope
        del ArcGIS10
        del version
        del tempExtent
        del tempMask
        del tempSnapRaster
        del tempCellSize
        del tempCoordSys
    except:
        pass

except SystemExit:
    pass

except KeyboardInterrupt:
    AddMsgAndPrint("Interruption requested....exiting")

except:
    print_exception()     

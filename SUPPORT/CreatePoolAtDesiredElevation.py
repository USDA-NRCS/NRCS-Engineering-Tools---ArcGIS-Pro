# CreatePool.py
## ================================================================================================================ 
def print_exception():
    
    tb = sys.exc_info()[2]
    l = traceback.format_tb(tb)
    l.reverse()
    tbinfo = "".join(l)
    AddMsgAndPrint(" \n----------ERROR Start------------------- \n",2)
    AddMsgAndPrint("Traceback Info:  \n" + tbinfo + "Error Info:  \n    " +  str(sys.exc_type)+ ": " + str(sys.exc_value) + "",2)
    AddMsgAndPrint("----------ERROR End--------------------  \n",2)

## ================================================================================================================    
def AddMsgAndPrint(msg, severity=0):
    # prints message to screen if run as a python script
    # Adds tool message to the geoprocessor
    # 
    # Split the message on  \n first, so that if it's multiple lines, a GPMessage will be added for each line
    
    print msg
    
    try:

        f = open(textFilePath,'a+')
        f.write(msg + "  \n")
        f.close

        del f

        if ArcGIS10:
            if not msg.find("\n") < 0 and msg.find("\n") < 4:
                gp.AddMessage(" ")        
        
        for string in msg.split(' \n'):          
            
            # Add a geoprocessing message (in case this is run as a tool)
            if severity == 0:
                gp.AddMessage(string)
                
            elif severity == 1:
                gp.AddWarning(string)
                
            elif severity == 2:
                gp.AddError(string)

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
    f.write("Executing \"Create Pool at Desired Elevation\" Tool\n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write("ArcGIS Version: " + str(version) + "\n")    
    f.write("User Parameters:\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tInput Dem: " + gp.Describe(inputDEM).CatalogPath + "\n")
    f.write("\tInput Watershed Mask: " + str(inPool) + "\n")
    f.write("\tPool Elevation: " + str(poolElev) + "\n")
    f.write("\tOutput Pool Polygon: " + str(outPool) + "\n")    
    if len(zUnits) > 0:
        f.write("\tElevation Z-units: " + zUnits + "\n")
    else:
        f.write("\tElevation Z-units: BLANK" + "\n")
    f.close
    del f

## ================================================================================================================
# Import system modules
import sys, os, string, arcgisscripting, traceback

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
    # Check out SA license
    if gp.CheckExtension("spatial") == "Available":
        gp.CheckOutExtension("spatial")
    else:
        gp.AddError("\nSpatial Analyst Extension not enabled. Please enable Spatial analyst from the Tools/Extensions menu\n")
        sys.exit("")

    #----------------------------------------------------------------------------------------- Input Parameters
    inputDEM = gp.GetParameterAsText(0)
    zUnits = gp.GetParameterAsText(1)
    inMask = gp.GetParameterAsText(2)                
    poolElev = float(gp.GetParameterAsText(3))

    
##    inputDEM = "C:\demo\Data\Elevation\dem"
##    inPool = "C:\_LatestTools\Test3\Test3_EngTools.gdb\Layers\Watershed"                
##    poolElev = "1140"
##    zUnits = ""
    
    # ---------------------------------------------------------------------------------------- Define Variables
    inPool = gp.Describe(inMask).CatalogPath

    if inPool.find('.gdb') > -1 or inPool.find('.mdb') > -1:
        watershedGDB_path = inPool[:inPool.find('.')+4]
    elif inPool.find('.shp')> -1:
        watershedGDB_path = os.path.dirname(inPool) + os.sep + os.path.basename(os.path.dirname(inPool)).replace(" ","_") + "_EngTools.gdb"
    else:
        AddMsgAndPrint("\n\nPool Polygon must either be a feature class or shapefile!.....Exiting",2)
        sys.exit()

    watershedGDB_name = os.path.basename(watershedGDB_path)
    watershedFD = watershedGDB_path + os.sep + "Layers"
    poolName = os.path.basename(inPool) + "_Pool_" + str(poolElev).replace(".","_")
    userWorkspace = os.path.dirname(watershedGDB_path)
    
    # Path of Log file; Log file will record everything done in a workspace
    textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.txt"    

    # --------------------------------------------- Permanent Datasets
    outPool = watershedFD +os.sep + poolName

    # Must Have a unique name for pool -- Append a unique digit to watershed if required
    x = 1
    while x > 0:
        if gp.exists(outPool):
            outPool = watershedFD + os.sep + os.path.basename(inMask) + "_Pool" + str(x) + "_" + str(poolElev).replace(".","_")
            x += 1
        else:
            x = 0
    del x

    # record basic user inputs and settings to log file for future purposes
    logBasicSettings()
    
    # --------------------------------------------- Temporary Datasets
    tempDEM = watershedGDB_path + os.sep + "tempDEM"
    DEMminus = watershedGDB_path + os.sep + "DEMminus"
    DEMsn = watershedGDB_path + os.sep + "DEMsn"
    volGrid = watershedGDB_path + os.sep + "volGrid"
    volume = watershedGDB_path + os.sep + "volume"
    ExtentRaster = watershedGDB_path + os.sep + "ExtRast"
    poolTemp = watershedGDB_path + os.sep + "poolTemp"
    PoolRast1 = watershedGDB_path + os.sep + "poolRast1"
    PoolRast2 = watershedGDB_path + os.sep + "poolRast2"

    # --------------------------------------------- Layers in ArcMap
    outPoolLyr = "" + os.path.basename(outPool) + ""

    # ---------------------------------------------------------------------------------------------- Check Parameters
    # Exit if inPool has more than 1 polygon    
    if int(gp.GetCount_management(inPool).getOutput(0)) > 1:
        AddMsgAndPrint("\n\nOnly ONE Watershed or Pool Polygon can be submitted!.....Exiting!",2)
        AddMsgAndPrint("Either export an individual polygon from your " + os.path.basename(inPool) + " Layer",2)
        AddMsgAndPrint("make a single selection, or provide a different input...EXITING\n",2)
        sys.exit()

    # Exit if inPool is not a Polygon geometry
    if gp.Describe(inPool).ShapeType != "Polygon":
        AddMsgAndPrint("\n\nYour Watershed or Pool Area must be a polygon layer!.....Exiting!\n",2)
        sys.exit()        

    # Exit if Elevation value is less than 1
    if poolElev < 1:
        AddMsgAndPrint("\n\nPool Elevation Value must be greater than 0.....Exiting\n",2)
        sys.exit()     

    #--------------------------------------------------------------------- Retrieve Spatial Reference and units from DEM
    desc = gp.Describe(inputDEM)
    sr = desc.SpatialReference
    cellSize = int(desc.MeanCellWidth)
    cellArea = desc.MeanCellWidth * desc.MeanCellHeight
    units = sr.LinearUnitName

    AddMsgAndPrint("\nGathering information about Input DEM: " + os.path.basename(inputDEM),1)    

    # Coordinate System must be a Projected type in order to continue.
    # XY & Z Units will determine Zfactor for Elevation and Volume Conversions.
    
    if sr.Type == "Projected":              
        AddMsgAndPrint("\tProjection Name: " + sr.Name,0)
        AddMsgAndPrint("\tXY Linear Units: " + units,0)
        AddMsgAndPrint("\tCell Size: " + str(desc.MeanCellWidth) + " x " + str(desc.MeanCellHeight) + " " + units,0)

    else:
        AddMsgAndPrint("\n\n\t" + os.path.basename(inputDEM) + " is NOT in a projected Coordinate System....EXITING",2)
        sys.exit(0) 
                      
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
        
    # -------------------------------------------------------- Remove existing From arcMap
    if gp.Exists(outPoolLyr):
        AddMsgAndPrint("\nRemoving previous layers from your ArcMap session..",1)
        AddMsgAndPrint("\tRemoving ...." + str(outPoolLyr) + "",0)
        gp.Delete_management(outPoolLyr)
    # ------------------------------------------------------------------------------------------------ Delete old data from gdb
    datasetsToRemove = (ExtentRaster,tempDEM,DEMminus,DEMsn,volGrid,volume,PoolRast1,PoolRast2,poolTemp)

    x = 0
    for dataset in datasetsToRemove:

        if gp.exists(dataset):

            if x < 1:
                AddMsgAndPrint("\nRemoving old datasets from FGDB: " + watershedGDB_name ,1)
                x += 1
                
            try:
                gp.delete_management(dataset)
                AddMsgAndPrint("\tDeleting....." + os.path.basename(dataset),0)
            except:
                pass
            
    del dataset
    del datasetsToRemove
    del x 

    # -------------------------------------------------------- Set Conversion Factor for Volume Calculations and Elevation Conversions
    # Raster Volume Conversions
    if units == "Meter":
        convFactor = 0.000810713
        units = "Meters"
    if units == "Foot":
        convFactor = 0.000022957
        units = "Feet"
    if units == "Foot_US":
        convFactor = 0.000022957
        units = "Feet"
        
    # ------------------ zUnits will determine forward / backward elevation conversions.
    # ------------------ if zUnits were left blank than assume Z-values are the same as XY units.
    
    if not len(zUnits) > 0:
        zUnits = units
        
    # Elevation Conversions    
    if sr.Type == "Projected":
        if zUnits == "Meters":
            Zfactor = 0.304800609601219         # 0.3048 meters in a foot
            conversionFactor = 3.280839896      # 3.28 feet in a meter

        elif zUnits == "Centimeters":   
            Zfactor = 30.4800609601219          # 30.48 centimeters in a foot
            conversionFactor = 0.0328084        # 0.033 feet in a centimeter
            
        elif zUnits == "Inches":        
            Zfactor = 12                        # 12 inches in a foot
            conversionFactor = 0.0833333        # 0.083 feet in an inch
       
        else:
            Zfactor = 1
            conversionFactor = 1                # zUnits must be feet or unknown; no more choices
            
    # Convert Pool Elevation entered by user in feet to match the zUnits of the DEM specified by the user, using Zfactor
    demElev = poolElev * Zfactor
    
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

    # ---------------------------------------------------- Clip DEM to Watershed & Setnull above Pool Elevation
    gp.ExtractByMask_sa(inputDEM, inPool, tempDEM)

    # User specified max elevation value must be within min-max range of elevation values in clipped dem
    demTempMaxElev = round((float(gp.GetRasterProperties_management(tempDEM, "MAXIMUM").getOutput(0)) * conversionFactor),1)
    demTempMinElev = round((float(gp.GetRasterProperties_management(tempDEM, "MINIMUM").getOutput(0)) * conversionFactor),1)

    # Check to make sure specifies max elevation is within the range of elevation in clipped dem
    #if not demTempMinElev < demElev <= demTempMaxElev:
    if not demTempMinElev < poolElev <= demTempMaxElev:
        
        AddMsgAndPrint("\n\tThe Pool Elevation Specified is not within the range",2)
        AddMsgAndPrint("\tof elevations within your input Watershed....",2)
        AddMsgAndPrint("\tPlease specify a value between " + str(demTempMinElev) + " and " + str(demTempMaxElev) + "...EXITING\n",2)
        sys.exit("")

    AddMsgAndPrint("\nCreating Pool at " + str(poolElev) + " feet",1)
    
    gp.SetNull_sa(tempDEM,tempDEM, DEMsn, "Value > " + str(demElev) + "")
    gp.Times_sa(DEMsn, "0", PoolRast1)
    gp.Int_sa(PoolRast1, PoolRast2)

# -------------------------------------------------------------    Convert results to simplified polygon
    if ArcGIS10:
        
        try:
            # Convert pool grid to a polygon feature class
            gp.RasterToPolygon_conversion(PoolRast2,poolTemp,"NO_SIMPLIFY","VALUE")

        except:
            if gp.exists(poolTemp):

                try:
                    gp.MakeRasterLayer_management(poolTemp,"poolTempLyr")
                except:
                    print_exception
            else:
                AddMsgAndPrint(" \n" + gp.GetMessages(2),2)
                sys.exit()


    # Do the following for ArcGIS 9.3
    else:                

        try:
            # Convert pool grid to a polygon feature class
            gp.RasterToPolygon_conversion(PoolRast2,poolTemp,"SIMPLIFY","VALUE")

        except:
            if gp.exists(poolTemp):
                
                if int(gp.GetCount_management(poolTemp).getOutput(0)) > 0:
                    AddMsgAndPrint("",1)
                else:
                    AddMsgAndPrint(" \n" + gp.GetMessages(2),2)
                    sys.exit()
                    
            else:
                AddMsgAndPrint(" \n" + gp.GetMessages(2),2)
                sys.exit()
                
    gp.AddField_management(poolTemp, "DemElev", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.CalculateField_management(poolTemp, "DemElev", demElev, "VB", "")
        
    # Dissolve poolTemp and add fields
    gp.Dissolve_management(poolTemp, outPool, "", "", "MULTI_PART", "DISSOLVE_LINES")        
    gp.AddField_management(outPool, "ID", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.AddField_management(outPool, "DemElev", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.AddField_management(outPool, "PoolElev", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.AddField_management(outPool, "PoolAcres", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.AddField_management(outPool, "RasterVol", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.AddField_management(outPool, "AcreFt", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    AddMsgAndPrint("\tCreated pool polygon",1)

    # ------------------------------------------------------- Insert Cursor to populate attributes, Create and Sum Volume Grid.
    rows = gp.UpdateCursor(outPool)
    row = rows.next()
    
    while row:
        
        row.ID = row.OBJECTID
        row.DemElev = str(demElev)
        row.PoolElev = str(poolElev)
        
        if units == "Meters":
            row.PoolAcres = str(round(row.Shape_Area / 4046.86,1))
        else:
            row.PoolAcres = str(round(row.Shape_Area / 43560,1))

        rows.UpdateRow(row)
        
        AddMsgAndPrint("\tCalculated pool area",1)
        
        gp.FeatureToRaster_conversion(poolTemp, "DemElev", ExtentRaster, cellSize)
        gp.Minus_sa(ExtentRaster, tempDEM, DEMminus)
        gp.SetNull_sa(DEMminus,DEMminus, DEMsn, "Value <= 0")
        gp.Times_sa(DEMsn, cellArea, volGrid)
        gp.ZonalStatistics_sa(outPool, "ID", volGrid, volume, "SUM")
        
        row.RasterVol = str(round((float(gp.GetRasterProperties_management(volume, "MAXIMUM").getOutput(0))),1))
        row.AcreFt = str(round(float(row.RasterVol * convFactor),1))
        rows.UpdateRow(row)
        
        AddMsgAndPrint("\tCalculated Pool volume..",1)
        AddMsgAndPrint("\n\t==================================================",0)
        AddMsgAndPrint("\tOutput Pool Polygon: " + os.path.basename(outPool) + "",0)
        AddMsgAndPrint("\tPool Elevation: " + str(row.PoolElev) + " Feet",0)
        AddMsgAndPrint("\tArea: " + str(row.poolAcres) + " Acres",0)
        AddMsgAndPrint("\tVolume: " + str(row.RasterVol) + " Cubic " + str(units),0)
        AddMsgAndPrint("\tVolume: " + str(row.AcreFt) + " Acre Feet",0)
        AddMsgAndPrint("\t====================================================",0)

        break        
        
        row = rows.next()
        
    del row
    del rows
    
    # ------------------------------------------------------------------------------------------------ Delete Intermediate Data            
    datasetsToRemove = (ExtentRaster,tempDEM,DEMminus,DEMsn,volGrid,volume,DEMsn,poolTemp,PoolRast1,PoolRast2)

    x = 0
    for dataset in datasetsToRemove:

        if gp.exists(dataset):

            if x < 1:
                AddMsgAndPrint("\nDeleting intermediate data...",1)
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
    gp.SetParameterAsText(4, outPool)
    AddMsgAndPrint("\nAdding output to ArcMap",1)
    
    AddMsgAndPrint("\nProcessing Complete!\n",1)

    # ----------------------------------------------------------  Cleanup
    gp.RefreshCatalog(watershedGDB_path)

    # Restore original environments
    gp.extent = tempExtent
    gp.mask = tempMask
    gp.SnapRaster = tempSnapRaster
    gp.CellSize = tempCellSize
    gp.OutputCoordinateSystem = tempCoordSys
    
    try:    
        del inputDEM
        del inmask
        del inPool
        del poolElev
        del zUnits
        del watershedGDB_path
        del userWorkspace
        del textFilePath
        del watershedGDB_name
        del watershedFD
        del outPool
        del tempDEM
        del DEMminus
        del DEMsn
        del volGrid
        del volume
        del ExtentRaster
        del PoolRast1
        del PoolRast2
        del poolTemp
        del desc
        del sr
        del cellSize
        del units
        del FGDBexists
        del units
        del convFactor
        del Zfactor
        del conversionFactor
        del demElev
        del demTempMinElev
        del demTempMaxElev
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

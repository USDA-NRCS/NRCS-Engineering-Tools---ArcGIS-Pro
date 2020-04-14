# StageStorage.py
## ================================================================================================================ 
def print_exception():
    
    tb = sys.exc_info()[2]
    l = traceback.format_tb(tb)
    l.reverse()
    tbinfo = "".join(l)
    AddMsgAndPrint("\n----------ERROR Start-------------------",2)
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
    f.write("Executing \"Calculate Stage Storage Volume\" Tool\n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write("User Parameters:\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tInput Dem: " + gp.Describe(inputDEM).CatalogPath + "\n")
    f.write("\tMaximum Elevation: " + str(maxElev) + " Feet\n")
    f.write("\tAnalysis Increment: " + str(userIncrement) + " Feet\n")

    if len(zUnits) > 0:
        f.write("\tElevation Z-units: " + zUnits + "\n")
    else:
        f.write("\tElevation Z-units: BLANK" + "\n")

    f.write("\tInput Watershed or Pool Mask: " + str(inPool) + "\n")

    if b_createPools:
        f.write("\tCreate Pool Polygons: YES\n")  
    else:
        f.write("\tCreate Pool Polygons: NO\n")
    
    f.close
    del f

## ================================================================================================================
def createPool(elevationValue,storageTxtFile):

    try:

        global conversionFactor,acreConversion,ftConversion,volConversion

        tempDEM2 = watershedGDB_path + os.sep + "tempDEM2"
        tempDEM3 = watershedGDB_path + os.sep + "tempDEM3"
        tempDEM4 = watershedGDB_path + os.sep + "tempDEM4"
        poolTemp = watershedFD + os.sep + "poolTemp"
        poolTempLayer = os.path.dirname(watershedGDB_path) + os.sep + "poolTemp.shp"

        # Just in case they exist Remove them
        layersToRemove = (tempDEM2,tempDEM3,tempDEM4,poolTemp,poolTempLayer)
           
        for layer in layersToRemove:
            if gp.exists(layer):
                try:
                    gp.delete_management(layer)
                except:
                    pass

        fcName =  ("Pool_" + str(round((elevationValue * conversionFactor),1))).replace(".","_")
        
        poolExit = watershedFD + os.sep + fcName        

        # Create new raster of only values below an elevation value
        conStatement = "Value > " + str(elevationValue)
        gp.SetNull_sa(tempDEM, tempDEM, tempDEM2, conStatement)

        # Multiply every pixel by 0 and convert to integer for vectorizing
        # with geoprocessor 9.3 you need to have 0 w/out quotes.
        gp.Times_sa(tempDEM2, 0, tempDEM3)
        gp.Int_sa(tempDEM3, tempDEM4)

        # Convert to polygon and dissolve
        # This continuously fails despite changing env settings.  Works fine from python win
        # but always fails from arcgis 10 not 9.3.  Some reason ArcGIS 10 thinks that the
        # output of RasterToPolygon is empty....WTF!!!!
        try:
            gp.RasterToPolygon_conversion(tempDEM4, poolTemp, "NO_SIMPLIFY", "VALUE")
            
        except:
            if gp.exists(poolTemp):
                pass
                 #AddMsgAndPrint(" ",0)
                 
            else:
                AddMsgAndPrint("\n" + gp.GetMessages(2) + "\n",2)
                sys.exit()

        if ArcGIS10:
            gp.CopyFeatures_management(poolTemp,poolTempLayer)
            gp.Dissolve_management(poolTempLayer, poolExit, "", "", "MULTI_PART", "DISSOLVE_LINES")
            
        else:            
            gp.Dissolve_management(poolTemp, poolExit, "", "", "MULTI_PART", "DISSOLVE_LINES")
      
        gp.AddField_management(poolExit, "ELEV_FEET", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        gp.AddField_management(poolExit, "POOL_ACRES", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        gp.AddField_management(poolExit, "POOL_SQFT", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        gp.AddField_management(poolExit, "ACRE_FOOT", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

        # open storageCSV file and read the last line which should represent the last pool
        file = open(storageTxtFile)
        lines = file.readlines()
        file.close()    

        area2D = float(lines[len(lines)-1].split(',')[4])
        volume = float(lines[len(lines)-1].split(',')[6])

        elevFeetCalc = round(elevationValue * conversionFactor,1)
        poolAcresCalc = round(area2D / acreConversion,1)
        poolSqftCalc = round(area2D / ftConversion)
        acreFootCalc = round(volume / volConversion,1)
     
        gp.CalculateField_management(poolExit, "ELEV_FEET", elevFeetCalc, "VB")
        gp.CalculateField_management(poolExit, "POOL_ACRES", poolAcresCalc, "VB")
        gp.CalculateField_management(poolExit, "POOL_SQFT", poolSqftCalc, "VB")
        gp.CalculateField_management(poolExit, "ACRE_FOOT", acreFootCalc, "VB")

        AddMsgAndPrint("\n\tCreated " + fcName + ":",1)
        AddMsgAndPrint("\t\tArea:   " + str(splitThousands(round(poolSqftCalc,1))) + " Sq.Feet",0)
        AddMsgAndPrint("\t\tAcres:  " + str(splitThousands(round(poolAcresCalc,1))),0)
        AddMsgAndPrint("\t\tVolume: " + str(splitThousands(round(acreFootCalc,1))) + " Ac. Foot",0)

        #------------------------------------------------------------------------------------ Delete Temp Layers
        layersToRemove = (tempDEM2,tempDEM3,tempDEM4,poolTemp,poolTempLayer)
     
        for layer in layersToRemove:
            if gp.exists(layer):
                try:
                    gp.delete_management(layer)
                except:
                    pass

        del tempDEM2,tempDEM3,tempDEM4,poolTemp,poolTempLayer,poolExit,conStatement,file,lines,storageTxtFile
        del area2D,volume,elevFeetCalc,poolAcresCalc,poolSqftCalc,acreFootCalc,layersToRemove

    except:
        AddMsgAndPrint("\nFailed to Create Pool Polygon for elevation value: " + str(elevationValue),1)
        print_exception()
        sys.exit()
        return False


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
import sys, os, string, arcgisscripting, traceback, re

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
    gp.AddError("\nThis tool requires ArcGIS version 9.3 or Greater.....EXITING")
    sys.exit("")

try:

    # Check out 3D and SA licenses
    if gp.CheckExtension("3d") == "Available":
        gp.CheckOutExtension("3d")
        
    else:
        gp.AddError("\n3D analyst extension is not enabled. Please enable 3D analyst from the Tools/Extensions menu\n")
        sys.exit("")
        
    if gp.CheckExtension("spatial") == "Available":
        gp.CheckOutExtension("spatial")
        
    else:
        gp.AddError("\nSpatial Analyst Extension not enabled. Please enable Spatial analyst from the Tools/Extensions menu\n")
        sys.exit("")

    #----------------------------------------------------------------------------------------- Input Parameters
    inputDEM = gp.GetParameterAsText(0)
    zUnits = gp.GetParameterAsText(1)
    inPool = gp.GetParameterAsText(2)
    maxElev = float(gp.GetParameterAsText(3))
    userIncrement = float(gp.GetParameterAsText(4))
    b_createPools = gp.GetParameterAsText(5)

    # Uncomment the following 6 lines to run from pythonWin 
##    inputDEM = r'C:\flex\final\final_EngTools.gdb\DEM_aoi'
##    inPool = r'C:\flex\final\final_EngTools.gdb\Layers\stageStoragePoly'
##    maxElev = 1000
##    userIncrement = 20     #feet
##    zUnits = "Meters"
##    b_createPools = True
    
    # ---------------------------------------------------------------------------------------- Define Variables
    inPool = gp.Describe(inPool).CatalogPath

    if inPool.find('.gdb') > -1 or inPool.find('.mdb') > -1:
        watershedGDB_path = inPool[:inPool.find('.')+4]
        
    elif inPool.find('.shp')> -1:
        watershedGDB_path = os.path.dirname(inPool) + os.sep + os.path.basename(os.path.dirname(inPool)).replace(" ","_") + "_EngTools.gdb"
        
    else:
        AddMsgAndPrint("\n\nPool Polygon must either be a feature class or shapefile!.....Exiting",2)
        sys.exit()

    watershedGDB_name = os.path.basename(watershedGDB_path)
    watershedFD = watershedGDB_path + os.sep + "Layers"
    poolName = os.path.splitext(os.path.basename(inPool))[0]
    userWorkspace = os.path.dirname(watershedGDB_path)

    # ------------------------------------------- Layers in Arcmap
    poolMergeOut = "" + gp.ValidateTablename(poolName) + "_All_Pools"
    storageTableView = "Stage_Storage_Table"

    # Path of Log file; Log file will record everything done in a workspace
    textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.txt"

    # Storage CSV file
    storageCSV = userWorkspace + os.sep + poolName + "_storageCSV.txt"

    # ---------------------------------------------------------------------- Datasets
    tempDEM = watershedGDB_path + os.sep + "tempDEM"
    
    storageTable = watershedGDB_path + os.sep + gp.ValidateTablename(poolName) + "_storageTable"
    PoolMerge = watershedFD + os.sep + gp.ValidateTablename(poolName) + "_All_Pools"

    #can't do a length on a boolean; its an unsized object
    if b_createPools == "#" or b_createPools == "" or b_createPools == False or b_createPools == "false":
        b_createPools = False

    else:
        b_createPools = True

    # record basic user inputs and settings to log file for future purposes
    logBasicSettings()
    
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
    if maxElev < 1:
        AddMsgAndPrint("\n\nMaximum Elevation Value must be greater than 0.....Exiting\n",2)
        sys.exit()

    # Exit if elevation increment is not greater than 0
    if userIncrement < 0.5:
        AddMsgAndPrint("\n\nAnalysis Increment Value must be greater than or equal to 0.5.....Exiting\n",2)
        sys.exit()        
    
    # ---------------------------------------------------------------------------------------------- Check DEM Coordinate System and Linear Units
    desc = gp.Describe(inputDEM)
    sr = desc.SpatialReference
    cellSize = desc.MeanCellWidth

    units = sr.LinearUnitName

    # ----------------------------------------- Set Linear and Volume Conversion Factors
    if units == "Meter":
        units = "Meters"
        acreConversion = 4046.86    # 4046 sq meters in an acre
        ftConversion = 0.092903     # 0.093 sq meters in 1 sq foot
        volConversion = 1233.48184  # 1233 cubic meters in 1 acre @ 1FT depth

    elif units == "Foot":
        units = "Feet"
        acreConversion = 43560      # 43560 sq feet in an acre
        ftConversion = 1            # no conversion necessary
        volConversion = 43560       # 43560 cu feet in 1 acre @ 1FT depth

    elif units == "Foot_US":
        units = "Feet"
        acreConversion = 43560      # 43560 sq feet in an acre
        ftConversion = 1            # no conversion necessary
        volConversion = 43560       # 43560 cu feet in 1 acre @ 1FT depth
    else:
        AddMsgAndPrint("\nCould not determine linear units of DEM....Exiting!",2)
        sys.exit()

    # if zUnits were left blank than assume Z-values are the same as XY units.
    if not len(zUnits) > 0:
        zUnits = units

    # ----------------------------------------- Retrieve DEM Properties and set Z-unit conversion Factors
    AddMsgAndPrint("\nGathering information about DEM: " + os.path.basename(inputDEM),1)

    # Coordinate System must be a Projected type in order to continue.       
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
            conversionFactor = 1                # zUnits must be feet; no more choices

        AddMsgAndPrint("\tProjection Name: " + sr.Name,0)
        AddMsgAndPrint("\tXY Linear Units: " + units,0)
        AddMsgAndPrint("\tElevation Values (Z): " + zUnits,0) 
        AddMsgAndPrint("\tCell Size: " + str(desc.MeanCellWidth) + " x " + str(desc.MeanCellHeight) + " " + units,0)

    else:
        AddMsgAndPrint("\n\n\t" + os.path.basename(inputDEM) + " is NOT in a projected Coordinate System....EXITING",2)
        sys.exit()
        
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

    # --------------------------------------------------------------------------- Create FGDB, FeatureDataset
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

    # --------------------------------------------------------------------- Clean old files if FGDB already existed.
    if FGDBexists:    
        
        layersToRemove = (PoolMerge,storageTable,tempDEM,storageCSV)

        x = 0        
        for layer in layersToRemove:

            if gp.exists(layer):

                # strictly for formatting
                if x == 0:
                    AddMsgAndPrint("\nRemoving old files from FGDB: " + watershedGDB_name ,1)
                    x += 1
                
                try:
                    gp.delete_management(layer)
                    AddMsgAndPrint("\tDeleting....." + os.path.basename(layer),0)
                except:
                    pass

        gp.workspace = watershedFD
        
        poolFCs = gp.ListFeatureClasses("Pool_*")
        
        for poolFC in poolFCs:
            
            if gp.exists(poolFC):
                gp.delete_management(poolFC)
                AddMsgAndPrint("\tDeleting....." + poolFC,0)               

        if os.path.exists(storageCSV):
            os.remove(storageCSV)
            
        del x,layer,layersToRemove,poolFCs

    if os.path.exists(storageCSV):
        os.remove(storageCSV)
        AddMsgAndPrint("\tDeleting....." + storageCSV,0)
        
    # ------------------------------------- Remove layers from ArcMap if they exist
    layersToRemove = (poolMergeOut,storageTableView)

    x = 0
    for layer in layersToRemove:
        
        if gp.exists(layer):
            
            if x == 0:
                AddMsgAndPrint("",1)
                x+=1
                
            try:
                gp.delete_management(layer)
                AddMsgAndPrint("Removing previous " + layer + " from your ArcMap Session",1)
            except:
                pass

    del x
    del layer
    del layersToRemove
    # --------------------------------------------------------------------------------- ClipDEM to User's Pool or Watershed
    gp.ExtractByMask_sa(inputDEM, inPool, tempDEM)

    # User specified max elevation value must be within min-max elevation range of clipped dem
    demTempMaxElev = round(float(gp.GetRasterProperties_management(tempDEM, "MAXIMUM").getOutput(0)),1)
    demTempMinElev = round(float(gp.GetRasterProperties_management(tempDEM, "MINIMUM").getOutput(0)),1)

    # convert max elev value and increment(FT) to match the native Z-units of input DEM
    maxElevConverted = maxElev * Zfactor
    increment = userIncrement * Zfactor

    # if maxElevConverted is not within elevation range exit.    
    if not demTempMinElev < maxElevConverted <= demTempMaxElev:

        AddMsgAndPrint("\nThe Max Elevation value specified is not within the elevation range of your watershed-pool area",2)
        AddMsgAndPrint("Elevation Range of your watershed-pool polygon is:",2)
        AddMsgAndPrint("\tMaximum Elevation: " + str(demTempMaxElev) + " " + zUnits + " ---- " + str(round(float(demTempMaxElev*conversionFactor),1)) + " Feet",0)
        AddMsgAndPrint("\tMinimum Elevation: " + str(demTempMinElev) + " " + zUnits + " ---- " + str(round(float(demTempMinElev*conversionFactor),1)) + " Feet",0)
        AddMsgAndPrint("Please enter an elevation value within this range.....Exiting!\n\n",2)
        sys.exit()

    else:
        AddMsgAndPrint("\nSuccessfully clipped DEM to " + os.path.basename(inPool),1)

    # --------------------------------------------------------------------------------- Set Elevations to calculate volume and surface area                   
    try:

        i = 1    
        while maxElevConverted > demTempMinElev:

            if i == 1:
                AddMsgAndPrint("\nDeriving Surface Volume for elevation values between " + str(round(demTempMinElev * conversionFactor,1)) + " and " + str(maxElev) + " FT every " + str(userIncrement) + " FT" ,1)
                numOfPoolsToCreate = str(int(round((maxElevConverted - demTempMinElev)/increment)))
                AddMsgAndPrint(numOfPoolsToCreate + " Pool Feature Classes will be created",1)
                i+=1

            gp.SurfaceVolume_3d(tempDEM, storageCSV, "BELOW", maxElevConverted, "1")

            if b_createPools:

                if not createPool(maxElevConverted,storageCSV):
                    pass
                
            maxElevConverted = maxElevConverted - increment

        del i            
  
    except:
        print_exception()
        sys.exit()

    if gp.exists(tempDEM):
        gp.delete_management(tempDEM)
        
    #------------------------------------------------------------------------ Convert StorageCSV to FGDB Table and populate fields.
    gp.CopyRows_management(storageCSV, storageTable, "")
    gp.AddField_management(storageTable, "ELEV_FEET", "DOUBLE", "5", "1", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.AddField_management(storageTable, "POOL_ACRES", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.AddField_management(storageTable, "POOL_SQFT", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.AddField_management(storageTable, "ACRE_FOOT", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

    elevFeetCalc = "round([Plane_Height] *" + str(conversionFactor) + ",1)"
    poolAcresCalc = "round([Area_2D] /" + str(acreConversion) + ",1)"
    poolSqftCalc = "round([Area_2D] /" + str(ftConversion) + ",1)"
    acreFootCalc = "round([Volume] /" + str(volConversion) + ",1)"
    
    gp.CalculateField_management(storageTable, "ELEV_FEET", elevFeetCalc, "VB")
    gp.CalculateField_management(storageTable, "POOL_ACRES", poolAcresCalc, "VB")
    gp.CalculateField_management(storageTable, "POOL_SQFT", poolSqftCalc, "VB")
    gp.CalculateField_management(storageTable, "ACRE_FOOT", acreFootCalc, "VB")

    del elevFeetCalc,poolAcresCalc,poolSqftCalc,acreFootCalc

    AddMsgAndPrint("\nSuccessfully Created " + os.path.basename(storageTable),1)

    #------------------------------------------------------------------------ Append all Pool Polygons together
    if b_createPools:

        mergeList = ""

        i = 1
        gp.workspace = watershedFD
        poolFCs = gp.ListFeatureClasses("Pool_*")

        for poolFC in poolFCs:

            if i == 1:
                mergeList = gp.Describe(poolFC).CatalogPath + ";"

            else:
                mergeList = mergeList + ";" + gp.Describe(poolFC).CatalogPath

            i+=1

        gp.Merge_management(mergeList,PoolMerge)
                
        AddMsgAndPrint("\nSuccessfully Merged Pools into " + os.path.basename(PoolMerge),1)

        del mergeList,poolFCs,i

    # ------------------------------------------------------------------------------------------------ Compact FGDB
    try:
        gp.compact_management(watershedGDB_path)
        AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path),1)    
    except:
        pass

    # ------------------------------------------------------------------------------------------------ Prepare to Add to Arcmap

    if b_createPools:
        gp.SetParameterAsText(7, PoolMerge)
        
    # Create a table view from the storage table to add to Arcmap
    gp.maketableview_management(storageTable,storageTableView)


    #------------------------------------------------------------------------------------ Take care of a little housekeeping
    gp.RefreshCatalog(watershedGDB_path)

    # Restore original environments
    gp.extent = tempExtent
    gp.mask = tempMask
    gp.SnapRaster = tempSnapRaster
    gp.CellSize = tempCellSize
    gp.OutputCoordinateSystem = tempCoordSys

    try:
        del gp
        del inputDEM
        del inPool
        del maxElev
        del userIncrement
        del zUnits
        del b_createPools
        del watershedGDB_path
        del watershedFD
        del poolName
        del userWorkspace
        del poolMergeOut
        del storageTableView
        del textFilePath
        del storageTable
        del PoolMerge
        del b_createpools
        del desc
        del sr
        del units
        del cellSize
        del acreConversion
        del ftConversion
        del volConversion
        del zUnits
        del Zfactor
        del conversionFactor
        del FGDBexists
        del demTempMaxElev
        del demTempMinElev
        del maxElevConverted
        del increment
        del ArcGIS10
        del version
        del tempExtent
        del tempMask
        del tempSnapRaster
        del tempCellSize
        del tempCoordSys
    except:
        pass

    if os.path.exists(storageCSV):
        try:
            os.path.remove(storageCSV)
        except:
            pass

    del storageCSV        
    
except SystemExit:
    pass

except KeyboardInterrupt:
    AddMsgAndPrint("Interruption requested....exiting")

except:
    print_exception()

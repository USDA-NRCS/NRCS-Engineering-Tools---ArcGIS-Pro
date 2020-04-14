# ---------------------------------------------------------------------------
# addPoints.py
#
# Peter Mead USDA NRCS 
#
# Adds Points to WASCOB Tile Station Points
#
# ---------------------------------------------------------------------------
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
                #gp.AddMessage("    ")
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
    f.write("Executing \"Wascob Add Points to Profile\" Tool for ArcGIS 9.3 / 10")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write("User Parameters:\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tInput Stations: " + str(stationPoints) + "\n")
    f.close
    del f
## ================================================================================================================    
# Import system modules
import sys, os, arcgisscripting, string, traceback

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
        AddMsgAndPrint("\nSpatial Analyst Extension not enabled. Please enable Spatial analyst from the Tools/Extensions menu\n",2)
        sys.exit("")

    #------------------------------------------------------------------ Input Parameters
    stationPoints = gp.GetParameterAsText(0)
    inPoints = gp.GetParameterAsText(1)

##    stationPoints = r'C:\Projects\newerWascob_Wascob.gdb\Layers\stationPoints'
##    inPoints = r'C:\junk\AdditionalPoint.shp'

    # ----------------------------------------------------------------- Variables
    watershed_path = gp.Describe(stationPoints).CatalogPath
    watershedGDB_path = watershed_path[:watershed_path .find(".gdb")+4]
    watershedFD_path = watershedGDB_path + os.sep + "Layers"
    userWorkspace = os.path.dirname(watershedGDB_path)
    outputFolder = userWorkspace + os.sep + "gis_output"
    tables = outputFolder + os.sep + "tables"
    
    DEM_aoi = watershedGDB_path + os.sep + "Project_DEM"
    tileLines = watershedFD_path + os.sep + "tileLines"
    
    textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_WascobTools.txt"

    # record basic user inputs and settings to log file for future purposes
    logBasicSettings()
    
    if not gp.Exists(outputFolder):
        gp.CreateFolder_management(userWorkspace, "gis_output")
    if not gp.Exists(tables):
        gp.CreateFolder_management(outputFolder, "tables") 
    
    # ---------------------------------------------------------------- Permanent Datasets
    
    pointsTable = tables + os.sep + "stations.dbf"
    stations = watershedFD_path + os.sep + "stationPoints"

    # ---------------------------------------------------------------- Lyrs to ArcMap
    
    outPointsLyr = "StationPoints"
    
    # ---------------------------------------------------------------- Temporary Datasets

    pointsNear = watershedGDB_path + os.sep + "pointsNear"
    linesNear = watershedGDB_path + os.sep + "linesNear"   
    pointsTemp = watershedFD_path + os.sep + "pointsTemp"
    pointsLyr = "pointsLyr"
    pointsBuffer = watershedFD_path + os.sep + "pointsBuffer"
    stationsTemp = watershedFD_path + os.sep + "stationsTemp"    
    station_lyr = "stations"
    stationBuffer = watershedFD_path + os.sep + "stationsBuffer"
    stationElev = watershedGDB_path + os.sep + "stationElev"
    outlets = watershedFD_path + os.sep + "tileOutlets"
    # -------------------------------------------------------------- Create Temp Point(s)
    
    gp.CopyFeatures_management(inPoints, pointsTemp, "", "0", "0", "0")
    # Exit if no points were digitized
    count = int(gp.GetCount_management(pointsTemp).getOutput(0))
    if count < 1:
        AddMsgAndPrint("\n\tNo points provided.  You must use the Add Features tool to create",2)
        AddMsgAndPrint("\tat least one point to add to the stations...    ...EXITING",2)
        sys.exit("")
                              
    # Add Fields as necessary
    if len(gp.ListFields(pointsTemp,"ID")) < 1:
        gp.AddField_management(pointsTemp, "ID", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    if len(gp.ListFields(pointsTemp,"STATION")) < 1:
        gp.AddField_management(pointsTemp, "STATION", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    if len(gp.ListFields(pointsTemp,"POINT_X")) < 1:
        gp.AddField_management(pointsTemp, "POINT_X", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    if len(gp.ListFields(pointsTemp,"POINT_Y")) < 1:
        gp.AddField_management(pointsTemp, "POINT_Y", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")    
    if len(gp.ListFields(pointsTemp,"POINT_Z")) < 1:
        gp.AddField_management(pointsTemp, "POINT_Z", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    if len(gp.ListFields(pointsTemp,"STATIONID")) < 1:
        gp.AddField_management(pointsTemp, "STATIONID", "TEXT", "", "", "25", "", "NULLABLE", "NON_REQUIRED", "")
    # --------------------------------------------------------------------- Check for Project DEM & Retrieve Units
    if not gp.Exists(DEM_aoi):
        
        if gp.Exists("ProjectDEM"):
            # If Project DEM is Missing in GDB but present in TOC set to TOC lyr
            DEM_aoi = "ProjectDEM"      
        else:
            # Exit if not present either place and instruct user on remedy...
            AddMsgAndPrint("\nMissing Project_DEM from FGDB. Can not perform raster analysis.",2)
            AddMsgAndPrint("Project_DEM must be in the same geodatabase as your input watershed.",2)
            AddMsgAndPrint("\nCheck your the source of your provided watershed.",2)
            AddMsgAndPrint("and/or export ProjectDEM from the table of contents to",2)
            AddMsgAndPrint("the geodatabase where your watershed / stations reside",2)
            AddMsgAndPrint("as <yourworkspace>_Wascob.gdb\Project_DEM...EXITING",2)
            sys.exit("")

    # ----------------------------------- Capture Default Environments
    tempExtent = gp.Extent
    tempMask = gp.mask
    tempSnapRaster = gp.SnapRaster
    tempCellSize = gp.CellSize
    tempCoordSys = gp.OutputCoordinateSystem
    
    # ---------------------------------- Retrieve Raster Properties
    desc = gp.Describe(DEM_aoi)
    sr = desc.SpatialReference
    units = sr.LinearUnitName
    cellSize = desc.MeanCellWidth
    
    if units == "Meter":
        units = "Meters"
    elif units == "Foot":
        units = "Feet"
    elif units == "Foot_US":
        units = "Feet"
    # ----------------------------------- Set Environment Settings
    gp.Extent = "MINOF"
    gp.CellSize = cellSize
    gp.mask = ""
    gp.SnapRaster = ""
    gp.OutputCoordinateSystem = sr
    
    # -------------------------------------------------------------- Check for Tilelines - Exit if Not present
    if not gp.Exists(tileLines):
        if gp.Exists("TileLines"):
            tileLines = "TileLines"
        else:
            AddMsgAndPrint("\n\tTile Lines Feature Class not found in same directory as Station Points ",2)
            AddMsgAndPrint("\tor in Current ArcMap Document. Unable to Compute Stationing.",2)
            AddMsgAndPrint("\tCheck the source of your inputs and try again...   ...EXITING",2)
            sys.exit("")
    
    # --------------------------------------------------------------- Find Nearest Tile Line
    AddMsgAndPrint("\nFinding Nearest Tile Line(s)...",1)
    gp.GenerateNearTable_analysis(pointsTemp, tileLines, linesNear, "", "NO_LOCATION", "NO_ANGLE", "ALL", "1")

    # Populate Tile ID in new Points
    rows = gp.searchcursor(linesNear)
    row = rows.next()

    while row:
        pointID = row.IN_FID
        tileID = row.NEAR_FID
        whereclause = "OBJECTID = " + str(pointID)
        expression = "\"ID\" = " + str(tileID) + " AND \"STATION\" = 0"
        # Select each point corresponding "0utlet"
        gp.SelectLayerByAttribute_management(stationPoints, "NEW_SELECTION", expression)
        pointRows = gp.UpdateCursor(pointsTemp,whereclause)
        pointRow = pointRows.next()           

        # Pass the nearest Tile Line to temp points.
        while pointRow:
            pointRow.ID = tileID
            pointRows.UpdateRow(pointRow)

            break

        row = rows.next()        

        del pointID
        del tileID
        del whereclause
        del pointRows
        del pointRow

    del rows
    del row

    gp.Delete_management(linesNear)

    # -------------------------------------------------------------------- Find Distance from point "0" along each tile line
     
    # Clear any selected points 
    gp.SelectLayerByAttribute_management(stationPoints, "CLEAR_SELECTION", "")
    # Select each point "0"
    gp.SelectLayerByAttribute_management(stationPoints, "NEW_SELECTION", "\"STATION\" = 0")
    # Create layer from selection
    gp.MakeFeatureLayer_management(stationPoints, station_lyr, "", "", "")
    
    AddMsgAndPrint("\nCalculating station distance(s)...",1)    
    gp.GenerateNearTable_analysis(pointsTemp, station_lyr, pointsNear, "", "NO_LOCATION", "NO_ANGLE", "ALL", "1")
    gp.SelectLayerByAttribute_management(stationPoints, "CLEAR_SELECTION", "")

    # Calculate stations in new Points
    rows = gp.searchcursor(pointsNear)
    row = rows.next()

    while row:
        pointID = row.IN_FID
        distance = row.NEAR_DIST
        if units == "Meters":
            station = int(distance * 3.280839896)
        else:
            station = int(distance)
            
        whereclause = "OBJECTID = " + str(pointID)
        pointRows = gp.UpdateCursor(pointsTemp,whereclause)
        pointRow = pointRows.next()           

        # Pass the station distance to temp points.
        while pointRow:
            pointRow.STATION = station
            pointRows.UpdateRow(pointRow)

            break

        row = rows.next()        

        del pointID, distance, station, whereclause, pointRows, pointRow

    del rows
    del row

    gp.Delete_management(pointsNear)

    gp.RefreshCatalog(watershedGDB_path)
    # ------------------------------------------------------------------------------ Retrieve Elevation info
    
    AddMsgAndPrint("\nCalculating station elevation(s)...",1)
    # Calculate Dummy field
    gp.CalculateField_management(pointsTemp, "STATIONID", "[STATION] & \"_\" & [ID]", "VB", "")
    # Buffer Points and compute zonal stats
    bufferSize = str(cellSize) + " " + units
    gp.Buffer_analysis(pointsTemp, pointsBuffer, bufferSize, "FULL", "ROUND", "LIST", "STATIONID")
    gp.ZonalStatisticsAsTable_sa(pointsBuffer, "STATIONID", DEM_aoi, stationElev, "DATA")

    # Retrieve Elevations and pass to temp points
    elevRows = gp.searchcursor(stationElev)
    elevRow = elevRows.next()

    while elevRow:
        if len(gp.ListFields(stationElev,"VALUE")) > 0:
            pointID = elevRow.VALUE
        else:
            pointID = elevRow.STATIONID
            
        elevation = float(elevRow.MEAN)
        
        whereclause = "STATIONID = '" + str(pointID) + "'"
        pointsRows = gp.UpdateCursor(pointsTemp,whereclause)
        pointsRow = pointsRows.next()           

        # Pass the elevation to temp points.
        while pointsRow:
            pointsRow.POINT_Z = round(elevation,1)
            pointsRows.UpdateRow(pointsRow)

            break

        elevRow = elevRows.next()        

        del pointID, elevation, whereclause, pointsRows, pointsRow

    del elevRows
    del elevRow
    
    
    gp.Delete_management(stationElev)
    gp.Delete_management(pointsBuffer)

    # ----------------------------------------------------------------------------- Add X/Y Cordinates
    AddMsgAndPrint("\nAdding X Y Coordinates...",1) 
    gp.AddXY_management(pointsTemp)

    # ----------------------------------------------------------------------------- Append Results to Station Points
    AddMsgAndPrint("\nAppending new points to stationPoints Layer...",1)
    gp.CopyFeatures_management(stationPoints, stationsTemp, "", "0", "0", "0")
    
    # Delete Existing stationPoints - they'll be recreated and added to the Map again to avoid confusion over refreshing.
    gp.Delete_management(stationPoints)
    gp.CopyFeatures_management(stationsTemp, stations, "", "0", "0", "0")
    gp.Append_management(pointsTemp, stations, "NO_TEST", "", "")

    gp.Delete_management(stationsTemp)
    gp.Delete_management(pointsTemp)

    # ----------------------------------------------------------------------------- Copy output to tables folder
    # Delete existing points Table
    AddMsgAndPrint("\nUpdating Station Table...",1)
    if gp.Exists(pointsTable):
        gp.Delete_management(pointsTable)
    # Copy output to dbf for import        
    gp.CopyRows_management(stations, pointsTable, "")
    
    AddMsgAndPrint("\n\tSuccessfuly added a total of " + str(count) + " stations",1)
    del count
    
    # ------------------------------------------------------------------------------------------------ Compact FGDB
    gp.compact_management(watershedGDB_path)
    AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path) + "\n",1)

    # ---------------------------------------------------------------- Create Layers and apply symbology
        
    AddMsgAndPrint("Adding Output to ArcMap\n",1)  
    gp.SetParameterAsText(2, stations)

    AddMsgAndPrint("Processing Complete!\n",1)
    # ---------------------------------------------------------------------------- Cleanup
    gp.RefreshCatalog(watershedGDB_path)

    # Restore original environments
    gp.extent = tempExtent
    gp.mask = tempMask
    gp.SnapRaster = tempSnapRaster
    gp.CellSize = tempCellSize
    gp.OutputCoordinateSystem = tempCoordSys
    

    try:
        del stationPoints
        del inPoints
        del watershed_path
        del watershedGDB_path
        del watershedFD_path
        del userWorkspace
        del outputFolder
        del tables
        del DEM_aoi
        del tileLines
        del textFilePath
        del pointsTable
        del stations
        del outPointsLyr
        del pointsNear
        del linesNear
        del pointsTemp
        del stationsTemp
        del stationLyr
        del stationBuffer
        del stationElev
        del desc
        del sr
        del units
        del ArcGIS10
        del version
        del tempExtent
        del tempMask
        del tempSnapRaster
        del tempCellSize
        del tempCoordSys
        del gp
    except:
        pass

except SystemExit:
    pass

except KeyboardInterrupt:
    AddMsgAndPrint("Interruption requested....exiting")

except:
    print_exception() 
    
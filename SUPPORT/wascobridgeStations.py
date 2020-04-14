# ---------------------------------------------------------------------------
# wascobridgeStations.py
# revised by Matt Patton
# Peter Mead MN USDA NRCS 11/2012
#
# Creates points at user specified interval along digitized or provided lines,
# Derives stationing distances and XYZ values, providing Z values in feet,
# as well as interpolating the line(s) to 3d using the appropriate Zfactor.
#
# Optionally exports a comma delimited txt file for other applications
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
    f.write("Executing \"8. Wascob Tile Layout and Profile\" Tool for ArcGIS 9.3 / 10.0")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write("User Parameters:\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tInput Dem: " + gp.Describe(DEM_aoi).CatalogPath + "\n")
    f.write("\tInterval: " + str(interval) + "\n")

    if len(zUnits) > 0:
        f.write("\tElevation Z-units: " + zUnits + "\n")

    else:
        f.write("\tElevation Z-units: BLANK" + "\n")
    
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

    # Check out 3D and SA licenses
    if gp.CheckExtension("3d") == "Available":
        gp.CheckOutExtension("3d")
    else:
        AddMsgAndPrint("\n3D analyst extension is not enabled. Please enable 3D analyst from the Tools/Extensions menu\n",2)
        sys.exit("")
    if gp.CheckExtension("spatial") == "Available":
        gp.CheckOutExtension("spatial")
    else:
        AddMsgAndPrint("\nSpatial Analyst Extension not enabled. Please enable Spatial analyst from the Tools/Extensions menu\n",2)
        sys.exit("")

    #----------------------------------------------------------------------------------------- Input Parameters
    inWatershed = gp.GetParameterAsText(0)
    inputLine = gp.GetParameterAsText(1)
    interval = gp.GetParameterAsText(2)                
 
    # --------------------------------------------------------------------- Variables
    watershed_path = gp.Describe(inWatershed).CatalogPath
    watershedGDB_path = watershed_path[:watershed_path .find(".gdb")+4]
    watershedFD_path = watershedGDB_path + os.sep + "Layers"
    userWorkspace = os.path.dirname(watershedGDB_path)
    outputFolder = userWorkspace + os.sep + "gis_output"
    tables = outputFolder + os.sep + "tables"
    stakeoutPoints = watershedFD_path + os.sep + "stakeoutPoints"
    
    if not gp.Exists(outputFolder):
        gp.CreateFolder_management(userWorkspace, "gis_output")
    if not gp.Exists(tables):
        gp.CreateFolder_management(outputFolder, "tables") 

    DEM_aoi = watershedGDB_path + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_Project_DEM"    
    #DEM_aoi = watershedGDB_path + os.sep + "Project_DEM"
    zUnits = "Feet"
    
    textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_WascobTools.txt"

    # record basic user inputs and settings to log file for future purposes
    logBasicSettings()
    
    # --------------------------------------------------------------------- Permanent Datasets
    outLine = watershedFD_path + os.sep + "RidgeLines"
    outPoints = watershedFD_path + os.sep + "RidgeStationPoints"
    pointsTable = tables + os.sep + "ridgestations.dbf"
    stakeoutTable = tables + os.sep + "ridgestakeoutPoints.dbf"

    outLineLyr = "RidgeLines"
    outPointsLyr = "RidgeStationPoints"

    # --------------------------------------------------------------------- Temp Datasets
    lineTemp = watershedFD_path + os.sep + "lineTemp"
    routes = watershedFD_path + os.sep + "routes"
    stationTable = watershedGDB_path + os.sep + "stationTable"
    stationEvents = watershedGDB_path + os.sep + "stationEvents"
    stationTemp = watershedFD_path + os.sep + "stations"
    stationLyr = "stations"
    stationBuffer = watershedFD_path + os.sep + "stationsBuffer"
    stationElev = watershedGDB_path + os.sep + "stationElev"
    
    # --------------------------------------------------------------------- Check some parameters
    # Exit if interval not set propertly
    try:
        float(interval)
    except:
        AddMsgAndPrint("\nStation Interval was invalid; Cannot set interpolation interval.......EXITING",2)
        sys.exit()
        
    interval = float(interval)
    
    if not gp.Exists(DEM_aoi):
            
        AddMsgAndPrint("\nMissing Project_DEM from FGDB. Can not perform raster analysis.",2)
        AddMsgAndPrint("Project_DEM must be in the same geodatabase as your input watershed.",2)
        AddMsgAndPrint("\nCheck your the source of your provided watershed.",2)
        AddMsgAndPrint("and/or export ProjectDEM from the table of contents to",2)
        AddMsgAndPrint("the geodatabase where your provided watershed resides",2)
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
        
    # if zUnits were left blank than assume Z-values are the same as XY units.
    if not len(zUnits) > 0:
        zUnits = units
        
    if zUnits == "Meters":
        Zfactor = 3.280839896       # 3.28 feet in a meter

    elif zUnits == "Centimeters":   # 0.033 feet in a centimeter
        Zfactor = 0.0328084

    elif zUnits == "Inches":        # 0.083 feet in an inch
        Zfactor = 0.0833333

    # zUnits must be feet; no more choices       
    else:
        Zfactor = 1

    # ----------------------------------- Set Environment Settings
    gp.Extent = "MINOF"
    gp.CellSize = cellSize
    gp.mask = ""
    gp.SnapRaster = ""
    gp.OutputCoordinateSystem = sr
    
    del desc, sr


    
    # ------------------------------------------------------------- Delete [previous toc lyrs if present
    # Copy the input line before deleting the TOC layer reference in case input line IS the previous line selected from the TOC
    gp.CopyFeatures_management(inputLine, lineTemp)
    
    if gp.Exists(outLineLyr):
        AddMsgAndPrint("\nRemoving previous layers from ArcMap",1)
        gp.Delete_management(outLineLyr)
    if gp.Exists(outPointsLyr):
        gp.Delete_management(outPointsLyr)

    # ------------------------------------------------------------- Copy input and create routes / points
    #gp.CopyFeatures_management(inputLine, lineTemp)
    
    # Check for fields: if user input is previous line they will already exist
    if len(gp.ListFields(lineTemp,"ID")) < 1:
        gp.AddField_management(lineTemp, "ID", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    if len(gp.ListFields(lineTemp,"NO_STATIONS")) < 1:
        gp.AddField_management(lineTemp, "NO_STATIONS", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    if len(gp.ListFields(lineTemp,"FROM_PT")) < 1:
        gp.AddField_management(lineTemp, "FROM_PT", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    if len(gp.ListFields(lineTemp,"LENGTH_FT")) < 1:
        gp.AddField_management(lineTemp, "LENGTH_FT", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

    if units == "Feet":
        expression = "round([SHAPE_Length],1)"
    elif units == "Meters":
        expression = "round([SHAPE_Length] * 3.280839896,1)"
    else:
        AddMsgAndPrint("\tXY Units are UNKNOWN, unable to proceed..EXITING",2)
        sys.exit("")
        
    gp.CalculateField_management(lineTemp, "LENGTH_FT", expression, "VB", "")
    del expression

    # Calculate number of stations / remainder
    AddMsgAndPrint("\nCalculating the number of stations",1)
    AddMsgAndPrint("\n\tStation Point interval: " + str(interval) + " Feet",0)
    rows = gp.UpdateCursor(lineTemp)
    row = rows.next()
    while row:
        row.ID = row.OBJECTID
        if row.LENGTH_FT < interval:
            AddMsgAndPrint("\tThe Length of line " + str(row.ID) + " is less ",2)
            AddMsgAndPrint("\tthan the specified interval of " + str(interval) + " feet.",2)
            AddMsgAndPrint("\tChoose a lower interval or supply a longer line...EXITING",2)
            sys.exit("")
        exp = row.LENGTH_FT / interval - 0.5 + 1
        row.NO_STATIONS = str(round(exp))
        row.FROM_PT = 0
        rows.UpdateRow(row)
        AddMsgAndPrint("\n\tLine " + str(row.ID) + " Total Length: " + str(int(row.LENGTH_FT)) + " Feet",0)
        AddMsgAndPrint("\tEquidistant stations (Including Station 0): " + str(row.NO_STATIONS),0)
        remainder = (row.NO_STATIONS * interval) - row.LENGTH_FT
        if remainder > 0:
            AddMsgAndPrint("\tPlus 1 covering the remaining " + str(int(remainder)) + " feet\n",0)

        row = rows.next()
    del row
    del rows
    del remainder

    # Create Table to hold station values
    gp.CreateTable_management(watershedGDB_path, "stationTable")
    gp.AddField_management(stationTable, "ID", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.AddField_management(stationTable, "STATION", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.AddField_management(stationTable, "POINT_X", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.AddField_management(stationTable, "POINT_Y", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")    
    gp.AddField_management(stationTable, "POINT_Z", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

    # Calculate location for each station along the line
    rows = gp.SearchCursor(lineTemp)
    row = rows.next()
    while row:
        stations = row.NO_STATIONS
        length = int(row.LENGTH_FT)
        stationRows = gp.InsertCursor(stationTable)
        newRow = stationRows.newRow()
        newRow.ID = row.ID
        newRow.STATION = length
        stationRows.insertRow(newRow)
        currentStation = 0

        while currentStation < stations:
            newRow = stationRows.newRow()
            newRow.ID = row.ID
            newRow.STATION = currentStation * interval
            stationRows.insertRow(newRow)
            currentStation = currentStation + 1

        row = rows.next()

        del stationRows
        del newRow
    del row
    del rows

    # Create Route(s) lyr and define events along each route
    AddMsgAndPrint("Creating Stations...",1)
    gp.CreateRoutes_lr(lineTemp, "ID", routes, "TWO_FIELDS", "FROM_PT", "LENGTH_FT", "UPPER_LEFT", "1", "0", "IGNORE", "INDEX")
    gp.MakeRouteEventLayer_lr(routes, "ID", stationTable, "ID POINT STATION", stationEvents, "", "NO_ERROR_FIELD", "NO_ANGLE_FIELD", "NORMAL", "ANGLE", "LEFT", "POINT")
    gp.AddField_management(stationEvents, "STATIONID", "TEXT", "", "", "25", "", "NULLABLE", "NON_REQUIRED", "")  
    gp.CalculateField_management(stationEvents, "STATIONID", "[STATION] & \"_\" & [ID]", "VB", "")
    gp.CopyFeatures_management(stationEvents, stationTemp, "", "0", "0", "0")
    gp.AddXY_management(stationTemp)
    gp.AddField_management(stationTemp, "POINT_Z", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")  
    gp.MakeFeatureLayer_management(stationTemp, stationLyr, "", "", "")
    AddMsgAndPrint("\n\tSuccessfuly created a total of " + str(int(gp.GetCount_management(stationLyr).getOutput(0))) + " stations",0)
    AddMsgAndPrint("\tfor the " + str(int(gp.GetCount_management(lineTemp).getOutput(0))) + " line(s) provided\n",0)

    # --------------------------------------------------------------------- Retrieve Elevation values
    AddMsgAndPrint("Retrieving station elevations...\n",1)
    
    # Buffer the stations the width of one raster cell / unit
    if units == "Meters":
        bufferSize = str(cellSize) + " Meters"
    elif units == "Feet":
        bufferSize = str(cellSize) + " Feet"
    else:
        bufferSize = str(cellSize) + " Unknown"
        
    gp.Buffer_analysis(stationTemp, stationBuffer, bufferSize, "FULL", "ROUND", "NONE", "")
    gp.ZonalStatisticsAsTable_sa(stationBuffer, "STATIONID", DEM_aoi, stationElev, "NODATA", "ALL")
    gp.AddJoin_management(stationLyr, "StationID", stationElev, "StationID", "KEEP_ALL")
    expression = "round([stationElev.MEAN] * " + str(Zfactor) + ",1)"
    gp.CalculateField_management(stationLyr, "stations.POINT_Z", expression, "VB", "")
    gp.RemoveJoin_management(stationLyr, "stationElev")
    gp.DeleteField_management(stationTemp, "STATIONID; POINT_M")
    del expression
    
    # ---------------------------------------------------------------------- Create final output
    # Interpolate Line to 3d via Z factor
    gp.InterpolateShape_3d (DEM_aoi, lineTemp, outLine, "", Zfactor)

    # Copy Station Points
    gp.CopyFeatures_management(stationTemp, outPoints)

    # Copy output to tables folder
    gp.CopyRows_management(outPoints, pointsTable, "")
    gp.CopyRows_management(stakeoutPoints, stakeoutTable, "")

    # ------------------------------------------------------------------- Delete Temp Layers
    layersToRemove = (lineTemp,routes,stationTable,stationEvents,stationTemp,stationLyr,stationBuffer,stationElev)    
    AddMsgAndPrint("Deleting temporary files..\n",1)

    x = 0
    for layer in layersToRemove:
        
        if gp.exists(layer):
            if x == 0:
                AddMsgAndPrint("",1)
                x+=1
                
            try:
                gp.delete_management(layer)
            except:
                pass

    del x
    del layer
    del layersToRemove
    
    # ------------------------------------------------------------------------------------------------ Compact FGDB
    gp.compact_management(watershedGDB_path)
    AddMsgAndPrint("Successfully Compacted FGDB: " + os.path.basename(watershedGDB_path) + "\n",1)

    # ---------------------------------------------------------------- Create Layers and apply symbology
        
    AddMsgAndPrint("Adding Layers to ArcMap\n",1)
    gp.SetParameterAsText(3, outLine)    
    gp.SetParameterAsText(4, outPoints)

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
        del userWorkspace
        del DEM_aoi
        del inputLine
        del interval
        del zUnits
        del watershed_path
        del watershedGDB_path
        del watershedFD_path
        del textFilePath
        del outLine
        del outPoints
        del outLineLyr
        del outPointsLyr
        del lineTemp
        del routes
        del stationTable
        del stationEvents
        del stationTemp
        del stationLyr
        del stationBuffer
        del stationElev
        del units
        del cellSize
        del Zfactor
        del lineLyrFile
        del pointLyrFile
        del pointsTable
        del outputFolder
        del tables
        del stakeoutPoints
        del stakeoutTable
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
        
        
        

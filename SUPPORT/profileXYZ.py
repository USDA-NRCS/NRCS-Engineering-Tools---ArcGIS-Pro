## profileXYZ.py (Line to XYZ)
##
## Created by Peter Mead, Adolfo Diaz, USDA NRCS, 2013
## Updated by Chris Morse, USDA NRCS, 2018
## Updated by Chris Morse, USDA NRCS, 2019
##
## Creates points at user specified interval along digitized or provided lines,
## Derives stationing distances and XYZ values, providing Z values in feet,
## as well as interpolating the line(s) to 3d using the appropriate Zfactor.
#
## Optionally exports a comma delimited txt file for other applications

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
    f.write("Executing \"Line to XYZ\" Tool" + "\n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write("ArcGIS Version: " + str(arcpy.GetInstallInfo()['Version']) + "\n")    
    f.write("User Parameters:\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tInput Dem: " + arcpy.Describe(inputDEM).CatalogPath + "\n")
    f.write("\tInterval: " + str(interval) + "\n")
    f.write("\tElevation Z-units: " + zUnits + "\n")

    f.close
    del f
## ================================================================================================================    
# Import system modules
import arcpy, sys, os, traceback
#import arcgisscripting, string

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
    # Check out 3D and SA licenses
    if arcpy.CheckExtension("3d") == "Available":
        arcpy.CheckOutExtension("3d")
    else:
        arcpy.AddError("\n3D analyst extension is not enabled. Please enable 3D analyst from the Tools/Extensions menu. Exiting...\n")
        sys.exit()
    if arcpy.CheckExtension("spatial") == "Available":
        arcpy.CheckOutExtension("spatial")
    else:
        arcpy.AddError("\nSpatial Analyst Extension not enabled. Please enable Spatial Analyst from the Tools/Extensions menu. Exiting...\n")
        sys.exit()

    arcpy.SetProgressorLabel("Setting Variables")
    #----------------------------------------------------------------------------------------- Input Parameters
    userWorkspace = arcpy.GetParameterAsText(0)
    inputDEM = arcpy.GetParameterAsText(1)
    zUnits = arcpy.GetParameterAsText(2)
    inputLine = arcpy.GetParameterAsText(3)                
    interval = arcpy.GetParameterAsText(4)
    text = arcpy.GetParameter(5)

    # --------------------------------------------------------------------- Directory Paths
    watershedGDB_name = os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.gdb"  # replace spaces for new FGDB name
    watershedGDB_path = userWorkspace + os.sep + watershedGDB_name
    watershedFD = watershedGDB_path + os.sep + "Layers"
    projectName = arcpy.ValidateTableName(os.path.basename(userWorkspace).replace(" ","_"))

    # log inputs and settings to file
    textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.txt"
    logBasicSettings()
    
    # --------------------------------------------------------------------- Permanent Datasets
    outLine = watershedFD + os.sep + projectName + "_XYZ_line"
    # Must Have a unique name for output -- Append a unique digit to output if required
    x = 1
    y = 0
    while x > 0:
        if arcpy.Exists(outLine):
            outLine = watershedFD + os.sep + projectName + "_XYZ_line" + str(x)
            x += 1
            y += 1
        else:
            x = 0
    if y > 0:
        outPoints = watershedFD + os.sep + projectName + "_XYZ_points" + str(y)                                    
        outTxt = userWorkspace + os.sep + projectName + "_XYZ_line" + str(y) + ".txt"
    else:
        outPoints = watershedFD + os.sep + projectName + "_XYZ_points"                                   
        outTxt = userWorkspace + os.sep + projectName + "_XYZ_line.txt"
    del x
    del y
    
    outLineLyr = "" + os.path.basename(outLine) + ""
    outPointsLyr = "" + os.path.basename(outPoints) + ""

    # --------------------------------------------------------------------- Temp Datasets
    lineTemp = watershedFD + os.sep + "lineTemp"
    routes = watershedFD + os.sep + "routes"
    stationTable = watershedGDB_path + os.sep + "stationTable"
    stationEvents = watershedGDB_path + os.sep + "stationEvents"
    stationTemp = watershedFD + os.sep + "stations"
    stationLyr = "stations"
    stationBuffer = watershedFD + os.sep + "stationsBuffer"
    stationElev = watershedGDB_path + os.sep + "stationElev"
    
    # --------------------------------------------------------------------- Check station interval
    # Exit if interval not set propertly
    try:
        float(interval)
    except:
        AddMsgAndPrint("\nStation Interval was invalid; Cannot set interpolation interval. Exiting...\n",2)
        sys.exit()
        
    interval = float(interval)
    
    # --------------------------------------------------------------------- Check DEM Coordinate System and Linear Units
    desc = arcpy.Describe(inputDEM)
    sr = desc.SpatialReference
    units = sr.LinearUnitName
    cellSize = desc.MeanCellWidth

    try:
        if interval < float(cellSize):
            AddMsgAndPrint("\nThe interval specified is less than the DEM cell size. Please re-run with a higher interval value. Exiting...\n",2)
            sys.exit()
    except:
        AddMsgAndPrint("\nThere may be an issue with the DEM cell size. Exiting...\n",2)
        sys.exit()
    
    if units == "Meter":
        units = "Meters"
    elif units == "Foot":
        units = "Feet"
    elif units == "Foot_US":
        units = "Feet"
        
##    # if zUnits were left blank than assume Z-values are the same as XY units.
##    if not len(zUnits) > 0:
##        zUnits = units

    AddMsgAndPrint("\nGathering information about DEM: " + os.path.basename(inputDEM)+ "\n",0)

    # Coordinate System must be a Projected type in order to continue.
    # zUnits will determine Zfactor for the conversion of elevation values to a profile in feet
    
    if sr.Type == "Projected":
        if zUnits == "Meters":
            Zfactor = 3.280839896
        elif zUnits == "Centimeters":
            Zfactor = 0.03280839896
        elif zUnits == "Inches":
            Zfactor = 0.0833333
        # zUnits must be feet; no more choices       
        else:
            Zfactor = 1                 

        AddMsgAndPrint("\tProjection Name: " + sr.Name,0)
        AddMsgAndPrint("\tXY Linear Units: " + units,0)
        AddMsgAndPrint("\tElevation Values (Z): " + zUnits,0) 
        AddMsgAndPrint("\tCell Size: " + str(desc.MeanCellWidth) + " x " + str(desc.MeanCellHeight) + " " + units,0)

    else:
        AddMsgAndPrint("\n\n\t" + os.path.basename(inputDEM) + " is NOT in a projected Coordinate System. Exiting...\n",2)
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
    
    # ------------------------------------------------------------------------ Create FGDB, FeatureDataset
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

    # ------------------------------------------------------------- Copy input and create routes / points
    arcpy.CopyFeatures_management(inputLine, lineTemp)
    arcpy.AddField_management(lineTemp, "ID", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    arcpy.AddField_management(lineTemp, "NO_STATIONS", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    arcpy.AddField_management(lineTemp, "FROM_PT", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    arcpy.AddField_management(lineTemp, "LENGTH_FT", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

##    # Calculate the length_ft field.
##    # Change from a VB to Python expression to prep for ArcGIS Pro.
##    if units == "Feet":
##        #expression = "round([SHAPE_Length],1)"
##        expression = "round(!SHAPE_Length!,1)"
##    elif units == "Meters":
##        #expression = "round([SHAPE_Length] * 3.280839896,1)"
##        expression = "round(!SHAPE_Length! * 3.280839896,1)"
##    else:
##        AddMsgAndPrint("\tXY Units are unknown, unable to proceed. Exiting...\n",2)
##        sys.exit()

    #arcpy.CalculateField_management(lineTemp, "LENGTH_FT", expression, "VB", "")
    
    expression = "round(!Shape.Length@feet!,1)"
    arcpy.CalculateField_management(lineTemp, "LENGTH_FT", expression, "PYTHON_9.3")
    del expression

    # Calculate number of stations / remainder
    AddMsgAndPrint("\nCalculating the number of stations...",0)
    AddMsgAndPrint("\n\tStation Point interval: " + str(interval) + " Feet",0)
    rows = arcpy.UpdateCursor(lineTemp)
    row = rows.next()
    while row:
        row.ID = row.OBJECTID
        if row.LENGTH_FT < interval:
            AddMsgAndPrint("\tThe Length of line " + str(row.ID) + " is less ",2)
            AddMsgAndPrint("\tthan the specified interval of " + str(interval) + " feet.",2)
            AddMsgAndPrint("\tChoose a lower interval or supply a longer line. Exiting...\n",2)
            sys.exit()
        exp = row.LENGTH_FT / interval - 0.5 + 1
        row.NO_STATIONS = str(round(exp))
        row.FROM_PT = 0
        rows.updateRow(row)
        AddMsgAndPrint("\n\tLine " + str(row.ID) + " Total Length: " + str(row.LENGTH_FT) + " Feet",0)
        AddMsgAndPrint("\tNumber of equidistant stations: " + str(row.NO_STATIONS),0)
        remainder = (row.NO_STATIONS * interval) - row.LENGTH_FT
        if remainder > 0:
            AddMsgAndPrint("\tPlus 1 covering the remaining " + str(remainder) + " feet\n",0)
        row = rows.next()
    del row
    del rows
    del remainder

    # Create Table to hold station values
    arcpy.CreateTable_management(watershedGDB_path, "stationTable")
    arcpy.AddField_management(stationTable, "ID", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    arcpy.AddField_management(stationTable, "STATION", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    arcpy.AddField_management(stationTable, "POINT_X", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    arcpy.AddField_management(stationTable, "POINT_Y", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")    
    arcpy.AddField_management(stationTable, "POINT_Z", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

    # Calculate location for each station along the line
    rows = arcpy.SearchCursor(lineTemp)
    row = rows.next()
    while row:
        stations = row.NO_STATIONS
        length = int(row.LENGTH_FT)
        stationRows = arcpy.InsertCursor(stationTable)
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
    AddMsgAndPrint("Creating Stations...",0)
    arcpy.CreateRoutes_lr(lineTemp, "ID", routes, "TWO_FIELDS", "FROM_PT", "LENGTH_FT", "UPPER_LEFT", "1", "0", "IGNORE", "INDEX")
    arcpy.MakeRouteEventLayer_lr(routes, "ID", stationTable, "ID POINT STATION", stationEvents, "", "NO_ERROR_FIELD", "NO_ANGLE_FIELD", "NORMAL", "ANGLE", "LEFT", "POINT")
    arcpy.AddField_management(stationEvents, "STATIONID", "TEXT", "", "", "25", "", "NULLABLE", "NON_REQUIRED", "")
    # Change VB to PYTHON_9.3 for ArcGIS Pro Compatibility
    expression = '"' + "str(!STATION!)" + "_" + "str(!ID!)" + '"'
    #arcpy.CalculateField_management(stationEvents, "STATIONID", "[STATION] & \"_\" & [ID]", "VB", "")
    arcpy.CalculateField_management(stationEvents, "STATIONID", expression, "PYTHON_9.3")
    del expression
    # Should this next sort actually be done with STATIONID, instead of STATION?
    arcpy.Sort_management(stationEvents, stationTemp, [["STATION", "ASCENDING"]])
##    gp.CopyFeatures_management(stationEvents, stationTemp, "", "0", "0", "0")
    arcpy.AddXY_management(stationTemp)
    arcpy.AddField_management(stationTemp, "POINT_Z", "DOUBLE", "", "", "25", "", "NULLABLE", "NON_REQUIRED", "")  
    arcpy.MakeFeatureLayer_management(stationTemp, stationLyr, "", "", "")
    AddMsgAndPrint("\n\tSuccessfuly created a total of " + str(float(arcpy.GetCount_management(stationLyr).getOutput(0))) + " stations",0)
    AddMsgAndPrint("\tfor the " + str(float(arcpy.GetCount_management(lineTemp).getOutput(0))) + " line(s) provided\n",0)

    # --------------------------------------------------------------------- Retrieve Elevation values
    AddMsgAndPrint("Retrieving station elevations...\n",0)
    
    # Buffer the stations the width of one raster cell / unit
    if units == "Meters":
        bufferSize = str(cellSize) + " Meters"
    elif units == "Feet":
        bufferSize = str(cellSize) + " Feet"
    else:
        bufferSize = str(cellSize) + " Unknown"
        
    arcpy.Buffer_analysis(stationTemp, stationBuffer, bufferSize, "FULL", "ROUND", "NONE", "")
    arcpy.sa.ZonalStatisticsAsTable(stationBuffer, "STATIONID", inputDEM, stationElev, "NODATA", "ALL")
    arcpy.AddJoin_management(stationLyr, "StationID", stationElev, "StationID", "KEEP_ALL")
    # Change VB expression to Python to prep for ArcGIS Pro compatibility
    #expression = "round([stationElev.MEAN] * " + str(Zfactor) + ",1)"
    #arcpy.CalculateField_management(stationLyr, "stations.POINT_Z", expression, "VB", "")
    expression = "round(!stationElev.MEAN! * " + str(Zfactor) + ",1)"
    arcpy.CalculateField_management(stationLyr, "stations.POINT_Z", expression, "PYTHON_9.3")
    arcpy.RemoveJoin_management(stationLyr, "stationElev")
    arcpy.DeleteField_management(stationTemp, "STATIONID; POINT_M")
    del expression
    
    # ---------------------------------------------------------------------- Create final output
    # Interpolate Line to 3d via Z factor
    arcpy.ddd.InterpolateShape(inputDEM, lineTemp, outLine, "", Zfactor)

    # Copy Station Points
    arcpy.CopyFeatures_management(stationTemp, outPoints)

    # Create Txt file if selected and write attributes of station points
    if text == True:
        AddMsgAndPrint("Creating Output text file:\n",0)
        AddMsgAndPrint("\t" + str(outTxt) + "\n",0)

        t = open(outTxt, 'w')
        t.write("ID, STATION, X, Y, Z")
        t.close()
        
        #rows = gp.SearchCursor(outPoints, "", "", "STATION", "STATION" + " A")
        rows = arcpy.SearchCursor(outPoints,
                               fields="ID; STATION; POINT_X; POINT_Y; POINT_Z",
                               sort_fields="STATION")
        
        txtRows = arcpy.InsertCursor(outTxt)
        row = rows.next()

        while row:
            newRow = txtRows.newRow()
            newRow.ID = row.ID
            newRow.STATION = row.STATION
            newRow.X = row.POINT_X
            newRow.Y = row.POINT_Y
            newRow.Z = row.POINT_Z
            txtRows.insertRow(newRow)

            row = rows.next()
        
        del txtRows
        del newRow
        del row
        del rows
        del t
        
    # ---------------------------------------------------------------- Prepare to add to ArcMap
    AddMsgAndPrint("Adding Layers to ArcMap\n",0)
    arcpy.SetParameterAsText(6, outLine)    
    arcpy.SetParameterAsText(7, outPoints)

    # ------------------------------------------------------------------- Delete Temp Layers
    layersToRemove = (lineTemp,routes,stationTable,stationEvents,stationTemp,stationLyr,stationBuffer,stationElev)    
    AddMsgAndPrint("Deleting temporary files...\n",0)

    x = 0
    for layer in layersToRemove:
        if arcpy.Exists(layer):
            if x == 0:
                AddMsgAndPrint("",0)
                x+=1
            try:
                arcpy.Delete_management(layer)
            except:
                pass
    del x
    del layer
    del layersToRemove
    
    # ---------------------------------------------------------------------------------------------------------------------------- Compact FGDB
    try:
        arcpy.Compact_management(watershedGDB_path)
        AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path),0)    
    except:
        pass
    # ---------------------------------------------------------------------------- FIN!
    AddMsgAndPrint("Processing Complete!\n",0)

    # ---------------------------------------------------------------------------- Cleanup
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
        
        
        

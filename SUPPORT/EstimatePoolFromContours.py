## EstimatePoolFromContours.py
##
## Created by Peter Mead, Adolfo Diaz, USDA NRCS, 2013
## Updated by Chris Morse, USDA NRCS, 2019
##
## Creates a Pool Polygon and calculates area/volume from a LiDAR Derived DEM,
## using a set of contour lines and user provided "dam" or dams to limit the 
## analysis height and extent.
##
## The tool selects the heighest intersected contour that will create a "closed 
## polygon" to the topographic left of the dam, clips the dem to that extent,
## creates a volume raster, and returns the volume and surface area of a pool
## at that proposed elevation
##
## Additionally calculates length, width, max/min/mean height and required top
## and bottom widths for the user provided dam(s). The required amount of fill is 
## then estimated and returned in cubic yards.
##
## NOTE:  This tool requires an Advanced license for ArcGIS Desktop!

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
    f.write("Executing \"Estimate Pool From Contours\" tool\n")
    f.write("User Name: " + getpass.getuser()+ "\n")
    f.write("Date Executed: " + time.ctime())
    f.write("ArcGIS Version: " + str(arcpy.GetInstallInfo()['Version']) + "\n")
    f.write("User Parameters:\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tInput Contours: " + InputContours)
    f.write("\tInput Dem: " + DEM_aoi + "\n")    
    
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
    #--------------------------------------------------------------------- Check for ArcInfo License exit if not available
    if not arcpy.ProductInfo() == "ArcInfo":
        arcpy.AddError("\nThis tool requires an ArcInfo/Advanced license level for ArcGIS Desktop. Exiting...\n")
        sys.exit()
        
    # Check out Spatial Analyst License        
    if arcpy.CheckExtension("Spatial") == "Available":
        arcpy.CheckOutExtension("Spatial")
    else:
        arcpy.AddError("\nSpatial Analyst Extension not enabled. Please enable Spatial Analyst from the Tools/Extensions menu. Exiting...\n")
        sys.exit()

    arcpy.SetProgressorLabel("Setting Variables")
    #------------------------------------------------------------------------  Input Parameters
    InputContours = arcpy.GetParameterAsText(0)
    dam = arcpy.GetParameterAsText(1)
    #outputPoolName = arcpy.GetParameterAsText(2)
    #outputDamName = arcpy.GetParametersAsText(3)

    # ------------------------------------------------------------------------ Define Variables
    InputContours = arcpy.Describe(InputContours).CatalogPath

    # Exit if Contour layer not created from NRCS Engineering tools
    if InputContours.find('.gdb') > 0 and InputContours.find("_Contours") > 0:
        watershedGDB_path = InputContours[:InputContours.find('.')+4]
    else:
        arcpy.AddError("Input contours layer was not generated using the \"NRCS Engineering Tools\". Exiting...\n")
        sys.exit()

    watershedGDB_name = os.path.basename(watershedGDB_path)
    watershedFD = watershedGDB_path + os.sep + "Layers"
    userWorkspace = os.path.dirname(watershedGDB_path)
    projectName = arcpy.ValidateTableName(os.path.basename(userWorkspace).replace(" ","_"))

    # Use the same DEM as the contours were created from
    DEM_aoi =  watershedGDB_path + os.sep + projectName + "_DEM"
    if not arcpy.Exists(DEM_aoi):
        arcpy.AddError(""+ os.path.basename(DEM_aoi) + " not found in same file geodatabase as " + os.path.basename(InputContours) + "...")
        arcpy.AddError("Run the \"Create Contours from AOI\" or Define Area of Interest tool and try again. Exiting...\n")
        sys.exit()

    # Must have Project AOI to retrieve Z Units and apply proper conversion factors
    projectAOI = watershedFD + os.sep + projectName + "_AOI"
    if not arcpy.Exists(projectAOI):
        arcpy.AddError(""+ os.path.basename(projectAOI) + " not found in same file geodatabase as " + os.path.basename(InputContours) + "...")
        arcpy.AddError("Run the \"Create Contours from AOI\" or Define Area of Interest tool and try again. Exiting...\n")
        sys.exit()

    # log inputs and settings to file
    textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.txt"
    logBasicSettings()

    #--------------------------------------------- Temporary Datasets
    contourLyr = "contLyr"
    contourLyr2 = "contLyr2"
    contourMask = watershedFD + os.sep + "contMask"
    contourmaskLyr = "contMaskLyr"                                                                                     
    buffer1 = watershedFD + os.sep + "buffer1"
    buffer2 = watershedFD + os.sep + "buffer2"
    buffer3 = watershedFD + os.sep + "buffer3"
    buffer4 = watershedFD + os.sep + "buffer4"
    buffer5 = watershedFD + os.sep + "buffer5"
    buffer6 = watershedFD + os.sep + "buffer6"
    buffer7 = watershedFD + os.sep + "buffer7"
    contourErase = watershedFD + os.sep + "contErase"
    extentMask = watershedFD + os.sep + "extMask"
    damTemp = watershedGDB_path + os.sep + "damTemp"
    outDamLyr = "damLyr"
    damStats = watershedGDB_path + os.sep + "damStats"
    DEMclip = watershedGDB_path + os.sep + "DEMclip"
    DEMminus = watershedGDB_path + os.sep + "DEMminus"
    DEMsn = watershedGDB_path + os.sep + "DEMsn"
    DEMsnu = watershedGDB_path + os.sep + "DEMsnu"
    volGrid = watershedGDB_path + os.sep + "volGrid"
    volume = watershedGDB_path + os.sep + "volume"
    ExtentRaster = watershedGDB_path + os.sep + "ExtRast"
    PoolRast1 = watershedGDB_path + os.sep + "PoolRast1"
    PoolRast2 = watershedGDB_path + os.sep + "PoolRast2"
    PoolMask = watershedGDB_path + os.sep + "poolMask"
    PoolPoly = watershedGDB_path + os.sep + "PoolPoly"

    # ----------------------------------------------------------------------------- Check Some Parameters
    # Exit if wathershed layer not a line
    if arcpy.Describe(InputContours).ShapeType != "Polyline" and arcpy.Describe(InputContours).ShapeType != "Line":
        AddMsgAndPrint("\n\nThe Contour layer is not a Polyline or Line layer. Exiting...",2)        
        sys.exit()

    # --------------------------------------------------------------------------Copy User input to Dam(n) file and add fields...
    if not arcpy.GetCount_management(dam) > 0:
        AddMsgAndPrint("\tNo Dam features were provided.",2)
        AddMsgAndPrint("\tPlease make sure to digitize or provide a reference layer for a dam. Exiting...\n",2)
        sys.exit()             
    
    #--------------------------------------------------------------------- Retrieve Spatial Reference and units from DEM
    desc = arcpy.Describe(DEM_aoi)
    sr = desc.SpatialReference
    #cellSize = int(desc.MeanCellWidth)
    cellSize = desc.MeanCellWidth
    cellArea = desc.MeanCellWidth * desc.MeanCellHeight
    units = sr.LinearUnitName
    
    # Raster Volume Conversions for acre-feet
    if units == "Meter":
        convFactor = 0.000810714
        units = "Meters"
        
    if units == "Foot":
        convFactor = 0.000022957
        units = "Feet"
        
    if units == "Foot_US":
        convFactor = 0.000022957
        units = "Feet"

    if units == "Feet":
        convFactor = 0.000022957
        units = "Feet"
        
    AddMsgAndPrint("\nGathering information about Input DEM: " + os.path.basename(DEM_aoi) + "\n",0)    

    # Coordinate System must be a Projected type in order to continue.
    # XY & Z Units will determine Zfactor for Elevation and Volume Conversions.
    
    if sr.Type == "Projected":              
        AddMsgAndPrint("\tProjection Name: " + sr.Name,0)
        AddMsgAndPrint("\tXY Linear Units: " + units,0)
        AddMsgAndPrint("\tCell Size: " + str(desc.MeanCellWidth) + " x " + str(desc.MeanCellHeight) + " " + units,0)

    else:
        AddMsgAndPrint("\n\n\t" + os.path.basename(DEM_aoi) + " is no in a Projected Coordinate System. Exiting...",2)
        sys.exit()

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
##    gp.SnapRaster = DEM_aoi
##    gp.OutputCoordinateSystem = sr
##    del desc, sr
    
    # ---------------------------------------------------------------------------------------------- Create FGDB, FeatureDataset
    # Boolean - Assume FGDB already exists
    FGDBexists = True
        
    # ----------------------------------------------------------------------------------------------- Clean old files if FGDB already existed.
    if FGDBexists:    
        gridsToRemove = (contourMask,buffer1,buffer2,buffer3,buffer4,buffer5,buffer6,buffer7,contourErase,extentMask,damStats,DEMclip,DEMminus,DEMsn,volGrid,volume,ExtentRaster,PoolRast1,PoolRast2,PoolPoly)
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
        
    # -------------------------------------------------------- Set Conversion Factor for Volume Calculations and Elevation Conversions
    # Retrieve Z Units from Project AOI
    if arcpy.Exists(projectAOI):
        rows = arcpy.SearchCursor(projectAOI)
        row = rows.next()
        zUnits = row.Z_UNITS
        del rows
        del row

##    # If z units were not entered assume they are the same as xy
##    if not len(zUnits) > 0:
##        zUnits = units
        
    # Elevation Conversions
    # contFactor is for converting contours in feet to the zUnits values
    # Zfactor is for converting the zUnits to values to feet
    if zUnits == "Meters":
        contFactor = 0.3048         #feet to meters
        Zfactor = 3.280839896       #meters to feet
        
    elif zUnits == "Centimeters":    
        contFactor = 30.48          #feet to centimeters
        Zfactor = 0.03280839896     #centimeters to feet
        
    elif zUnits == "Feet":
        contFactor = 1              #feet to feet
        Zfactor = 1                 #feet to feet
        
    elif zUnits == "Inches":
        contFactor = 12             #feet to inches
        Zfactor = 0.0833333         #inches to feet


    arcpy.CopyFeatures_management(dam, damTemp)
    arcpy.AddField_management(damTemp, "ID", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    arcpy.AddField_management(damTemp, "MaxElev", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    arcpy.AddField_management(damTemp, "MinElev", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    arcpy.AddField_management(damTemp, "MeanElev", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    arcpy.AddField_management(damTemp, "LengthFt", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    arcpy.AddField_management(damTemp, "TopWidth", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    arcpy.AddField_management(damTemp, "BotWidth", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

    rows = arcpy.UpdateCursor(damTemp)
    row = rows.next()
    
    while row:
        row.ID = row.OBJECTID
        if units == "Feet":
            row.LengthFt = str(round(row.SHAPE_Length,1))
        else:
            row.LengthFt = str(round(row.SHAPE_Length * 3.280839896,1))
        rows.updateRow(row)
        row = rows.next()
        
    del row
    del rows

    # ------------------------------------------------------------------------ Select Contours by dam Location & copy
    AddMsgAndPrint("\nSelecting intersected contours...",0)
    
    arcpy.MakeFeatureLayer_management(InputContours, contourLyr)
    arcpy.SelectLayerByLocation_management(contourLyr, "INTERSECT", damTemp, "", "NEW_SELECTION")
    arcpy.CopyFeatures_management(contourLyr, contourMask)
    arcpy.SelectLayerByAttribute_management(contourLyr, "CLEAR_SELECTION")
        
    # ------------------------------------------------------------------------ Buffer and erase to break contours at dam and select closed contours
    # (This is the part requiring arcInfo -- Erase and Right/Left buffers...the right comes later...)
    arcpy.Buffer_analysis(damTemp, buffer1, "1 Feet", "FULL", "FLAT", "NONE", "")
    arcpy.Erase_analysis(contourMask, buffer1, contourErase, "")
    
    arcpy.Buffer_analysis(damTemp, buffer2, "1.5 Feet", "LEFT", "FLAT", "NONE", "")
    arcpy.Buffer_analysis(damTemp, buffer3, "3 Feet", "LEFT", "FLAT", "NONE", "")
    
    arcpy.Erase_analysis(buffer3, buffer1, buffer4, "")
    arcpy.Erase_analysis(buffer4, buffer2, buffer5, "")
 
    # Convert intersected contours to polygon mask
    arcpy.FeatureToPolygon_management(contourErase+";"+buffer2, extentMask, "", "ATTRIBUTES", "")

    # Check to make sure a polygon was created before proceeding
    if not arcpy.GetCount_management(extentMask) > 0:
        AddMsgAndPrint("\n\tThe intersection of the dam and contours did not create a polygon.",2)
        AddMsgAndPrint("\tPlease try again, making sure the intended pool is located ",2)
        AddMsgAndPrint("\tto the topographic left of the line(s) you provide. Exiting...\n",2)
        sys.exit()
    
    #Select Highest Contour that closed @ Polygon conversion.....
    arcpy.Clip_analysis(buffer5, extentMask, buffer6)

    if not arcpy.GetCount_management(buffer6) > 0:
        AddMsgAndPrint("\n\tThe intersection of the dam and contours did not create a polygon.",2)
        AddMsgAndPrint("\tPlease try again, making sure the intended pool is located ",2)
        AddMsgAndPrint("\tto the topographic left of the line(s) you provide. Exiting...\n",2)
        sys.exit()
    
    arcpy.SelectLayerByLocation_management(contourLyr, "INTERSECT", buffer6, "", "NEW_SELECTION")
    arcpy.MakeFeatureLayer_management(contourLyr, contourLyr2, "", "", "")
    
    inRows = arcpy.SearchCursor(contourLyr2, "", "", "CONTOUR", "CONTOUR" + " D")
    inRow = inRows.next()
    
    hiContour = inRow.CONTOUR
    # Assign the pool elevation in the actual units of the DEM
    poolElev = (hiContour * contFactor)
    
    del inRow
    del inRows
    
    AddMsgAndPrint("\n\tHighest closed contour is " + str(hiContour),0)
    
    # ------------------------------------------------------------------------------------------- Permanent Datasets!!
    
    outPool = watershedFD + os.sep + projectName + "_Pool_" + str(hiContour).replace(".","_")    
    
    # Must Have a unique name for pool -- project name and pool elev gets validated, but that doesn't ensure a unique name
    # Append a unique digit to pool if required
    x = 1
    while x > 0:
        if arcpy.Exists(outPool):
            outPool = watershedFD + os.sep + projectName + "_Pool"+ str(x) + "_" + str(hiContour).replace(".","_")
            x += 1
        else:
            x = 0
    del x

    # Set unique name for dam and copy to final output    
    outDam = outPool + str("_dam")
    arcpy.CopyFeatures_management(damTemp, outDam)
    arcpy.MakeFeatureLayer_management(outDam, outDamLyr)    

    # ---------------------------------------------------------------------- Dissolve and populate with plane elevation for raster processing
    AddMsgAndPrint("\nCreating Pool and Volume Grid...",0)
    arcpy.Dissolve_management(extentMask, PoolMask, "", "", "MULTI_PART", "DISSOLVE_LINES")
    arcpy.AddField_management(PoolMask, "DemElev", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

    # need to convert VB expression to Python for future integration to ArcGIS Pro
    expression = '"' + str(poolElev) + '"'
    #arcpy.CalculateField_management(PoolMask, "DemElev", "" + str(poolElev) + "", "VB", "")
    arcpy.CalculateField_management(PoolMask, "DemElev", expression, "PYTHON_9.3")
    
    # ---------------------------------------------------------------------- Convert to raster, clip DEM and create Pool polygon
    arcpy.MakeFeatureLayer_management(PoolMask, "pool_mask")
    arcpy.FeatureToRaster_conversion("pool_mask", "DemElev", ExtentRaster, cellSize)

    outMask = arcpy.sa.ExtractByMask(DEM_aoi, ExtentRaster)
    outMask.save(DEMclip)

    # User specified max elevation value must be within min-max range of elevation values in clipped dem
    demClipMaxElev = round(((float(arcpy.GetRasterProperties_management(DEMclip, "MAXIMUM").getOutput(0)))* Zfactor),1)
    demClipMinElev = round(((float(arcpy.GetRasterProperties_management(DEMclip, "MINIMUM").getOutput(0)))* Zfactor),1)

    # Check to make sure specified max elevation is within the range of elevation in clipped dem
    if not demClipMinElev < hiContour <= demClipMaxElev:
        
        AddMsgAndPrint("\n\tThe Pool Elevation Specified is not within the range",2)
        AddMsgAndPrint("\tof the corresponding area of your input DEM.",2)
        AddMsgAndPrint("\tPlease specify a value between " + str(demClipMinElev) + " and " + str(demClipMaxElev) + ". Exiting...",2)
        sys.exit()

    outMinus = arcpy.sa.Minus(ExtentRaster, DEMclip)
    outMinus.save(DEMminus)

    outNull = arcpy.sa.SetNull(DEMminus,DEMminus, "Value <= 0")
    outNull.save(DEMsn)

    # DEMsn is now a depth raster expressed in the original vertical units. Convert it to depths units that match the xy units.
    if units == "Meters":
        #xy units are meters
        if zUnits == "Inches":
            factor = 0.0254
        elif zUnits == "Centimeters":
            factor = 0.01
        elif zUnits == "Feet":
            factor = 0.3048
        else:
            #zUnits are assumed to be same as units
            factor = 1
    else:
        #xy units are feet
        if zUnits == "Inches":
            factor = 0.0833333
        elif zUnits == "Centimeters":
            factor = 0.03280839896
        elif zUnits == "Meters":
            factor = 3.280839896
        else:
            #zUnits are assumed to be same as units
            factor = 1

    outConv = arcpy.sa.Times(DEMsn, factor)
    outConv.save(DEMsnu)
    
    outTimes = arcpy.sa.Times(DEMsnu, 0)
    outTimes.save(PoolRast1)

    outInt = arcpy.sa.Int(PoolRast1)
    outInt.save(PoolRast2)
    
    arcpy.RasterToPolygon_conversion(PoolRast2, PoolPoly, "NO_SIMPLIFY", "VALUE")
        
    # Dissolve results and add fields
    arcpy.Dissolve_management(PoolPoly, outPool, "", "", "MULTI_PART", "DISSOLVE_LINES")
    arcpy.AddField_management(outPool, "ID", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    arcpy.AddField_management(outPool, "DemElev", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    arcpy.AddField_management(outPool, "PoolElev", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    arcpy.AddField_management(outPool, "PoolAcres", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    arcpy.AddField_management(outPool, "RasterVol", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    arcpy.AddField_management(outPool, "AcreFt", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    
    # ---------------------------------------------------------------------- Calculate Area, Raster Elevation and Pool Elevation
    rows = arcpy.UpdateCursor(outPool)
    row = rows.next()
    while row:
        row.ID = row.OBJECTID
        row.DemElev = str(poolElev)
        row.PoolElev = str(hiContour)
        if units == "Meters":
            row.PoolAcres = str(round(row.Shape_Area / 4046.86,1))
        else:
            row.PoolAcres = str(round(row.Shape_Area / 43560,1))
        rows.updateRow(row)
        
        AddMsgAndPrint("\n\tCalculating pool area and volume",0)

        volTimes = arcpy.sa.Times(DEMsnu, cellArea)
        volTimes.save(volGrid)
        
        outZonal = arcpy.sa.ZonalStatistics(outPool, "ID", volGrid, "SUM")
        outZonal.save(volume)
        
        # ---------------------------------------------------------------------- Get results and populate remaining fields
        row.RasterVol = str(round(float(arcpy.GetRasterProperties_management(volume, "MAXIMUM").getOutput(0)),1))
        row.AcreFt = str(round(float(row.RasterVol * convFactor),1))
        AddMsgAndPrint("\n\t\tPool Elevation: " + str(row.PoolElev) + " Feet",0)
        AddMsgAndPrint("\t\tPool Area: " + str(row.PoolAcres) + " Acres",0)
        AddMsgAndPrint("\t\tPool volume: " + str(row.RasterVol) + " Cubic " + str(units),0)
        AddMsgAndPrint("\t\tPool volume: " + str(row.AcreFt) + " Acre Feet",0)
        rows.updateRow(row)
        row = rows.next()
        
    del row
    del rows

    # ------------------------------------------------------------------------ Retrieve attributes for dam and populate fields
    arcpy.Buffer_analysis(outDam, buffer7, "3 Meters", "RIGHT", "ROUND", "LIST", "ID")
    arcpy.AddField_management(buffer7, "ELEV", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")    
    arcpy.sa.ZonalStatisticsAsTable(buffer7, "ID", DEM_aoi, damStats, "NODATA", "ALL") 

    rows = arcpy.SearchCursor(damStats)
    row = rows.next()
    
    while row:
        # zonal stats doesnt generate "Value" with the 9.3 geoprocessor in 10
        ID = row.ID

        #previously row.value in 9.3 geoprocessor
        #ID = row.VALUE
            
        maxElev = row.MAX
        minElev = row.MIN
        meanElev = row.MEAN
        
        maxFt = round(float(maxElev * Zfactor),1)
        minFt = round(float(minElev * Zfactor),1)
        meanFt = round(float(meanElev * Zfactor),1)
        
        AddMsgAndPrint("\n\tCalculating properties of embankment " + str(ID),0)
        AddMsgAndPrint("\n\t\tMax Elevation: " + str(maxFt) + " Feet",0)
        AddMsgAndPrint("\t\tMin Elevation: " + str(minFt) + " Feet",0)
        AddMsgAndPrint("\t\tMean Elevation: " + str(meanFt) + " Feet",0)
        
        query = "\"ID\" =  " + str(ID)
        arcpy.SelectLayerByAttribute_management(outDamLyr, "NEW_SELECTION", query)

        damHeight = int(maxFt - minFt)
        AddMsgAndPrint("\t\tMax Height: " + str(damHeight) + " Feet",0)

        whereclause = "ID = " + str(ID)
        damRows = arcpy.UpdateCursor(outDam,whereclause)
        damRow = damRows.next()
        while damRow:
            damLength = damRow.LengthFt
            damRow.LengthFt = round(damLength,1)
            damRow.MaxElev = maxFt
            damRow.MinElev = minFt
            damRow.MeanElev = meanFt

            AddMsgAndPrint("\t\tTotal Length: " + str(damRow.LengthFt) + " Feet",0)            
            
            # Assign Top and Bottom width from practice standards
            AddMsgAndPrint("\n\tCalculating suggested top / bottom widths (Based on 3:1 Slope)",0)
            
            if damHeight < 10:
                topWidth = 6
                
            elif damHeight >= 10 and damHeight < 15:
                topWidth = 8
                
            elif damHeight >= 15 and damHeight < 20:
                topWidth = 10
                
            elif damHeight >= 20 and damHeight < 25:
                topWidth = 12
                
            elif damHeight >= 25 and damHeight < 35:
                topWidth = 14
                
            elif damHeight >= 35:
                topWidth = 15

            bottomWidth = round(float(topWidth + 2 * (damHeight * 3)),0) # (bw + 2 * ss * depth) -- Assumes a 3:1 Side slope
            
            damRow.TopWidth = topWidth
            damRow.BotWidth = bottomWidth
            
            AddMsgAndPrint("\n\t\tSuggested Top Width: " + str(damRow.TopWidth) + " Feet",0)
            AddMsgAndPrint("\t\tSuggested Bottom Width: " + str(damRow.BotWidth) + " Feet",0)
            
            damRows.updateRow(damRow)
            damRow = damRows.next()
            
        row = rows.next()
        
        del ID
        del maxElev
        del minElev
        del meanElev
        del maxFt
        del minFt
        del meanFt
        del whereclause
        del damRows
        del damRow
        del damHeight
        del topWidth
        del bottomWidth

    del rows
    del row
    
    # ------------------------------------------------------------------------------------------------ Delete Intermediate Data            
    datasetsToRemove = (damTemp,buffer1,buffer2,buffer3,buffer4,buffer5,buffer6,buffer7,contourErase,contourMask,extentMask,ExtentRaster,PoolRast1,PoolRast2,PoolPoly,PoolMask,DEMclip,DEMminus,DEMsn,DEMsnu,volGrid,volume,outDamLyr,damStats)

    x = 0
    for dataset in datasetsToRemove:
        if arcpy.Exists(dataset):
            if x < 1:
                AddMsgAndPrint("\nDeleting intermediate data...",0)
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
    
    # ---------------------------------------------------------------------- Prepare to Add to Arcmap
    arcpy.SetParameterAsText(2, outPool)
    arcpy.SetParameterAsText(3, outDam)

    AddMsgAndPrint("\nAdding Layers to ArcMap",0)
    AddMsgAndPrint("\n",0)

    # ----------------------------------------------------------------------  Housekeeping
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

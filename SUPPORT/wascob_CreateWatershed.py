
from utils import AddMsgAndPrint

def logBasicSettings():
    import getpass, time
    f = open(textFilePath,'a+')
    f.write("\n################################################################################################################\n")
    f.write("Executing \"Wascob Create Watershed\" tool\n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write("ArcGIS Version: " + str(arcpy.GetInstallInfo()['Version']) + "\n")
    f.write("User Parameters:\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tStreams: " + streamsPath + "\n")
    if int(arcpy.GetCount_management(outlet).getOutput(0)) > 0:
        f.write("\tReference Lines Digitized: " + str(arcpy.GetCount_management(outlet)) + "\n")
    else:
        f.write("\tReference Lines Digitized: 0\n")
    f.write("\tWatershed Name: " + watershedOut + "\n")


import arcpy, sys, os, string, traceback, re
from arcpy.sa import *

try:
    streams = arcpy.GetParameterAsText(0)
    outlet = arcpy.GetParameterAsText(1)
    userWtshdName = "Watershed"

    # Check out Spatial Analyst License
    if arcpy.CheckExtension("spatial") == "Available":
        arcpy.CheckOutExtension("spatial")
    else:
        arcpy.AddError("Spatial Analyst Extension not enabled. Please enable Spatial analyst from the Tools/Extensions menu\n",2)
        exit()

    arcpy.env.parallelProcessingFactor = "75%"
    arcpy.env.overwriteOutput = True
    arcpy.env.geographicTransformations = "WGS_1984_(ITRF00)_To_NAD_1983"
    arcpy.env.resamplingMethod = "BILINEAR"
    arcpy.env.pyramid = "PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP"

    streamsPath = arcpy.da.Describe(streams)['catalogPath']

    if streamsPath.find('.gdb') > 0 and streamsPath.find('_Streams') > 0:
        watershedGDB_path = streamsPath[:streamsPath.find(".gdb")+4]
    else:
        arcpy.AddError("\n\n" + streams + " is an invalid Stream Network project layer")
        arcpy.AddError("Please run the Create Stream Network tool.\n\n")
        exit()

    userWorkspace = os.path.dirname(watershedGDB_path)
    watershedGDB_name = os.path.basename(watershedGDB_path)
    watershedFD = watershedGDB_path + os.sep + "Layers"
    projectName = arcpy.ValidateTableName(os.path.basename(userWorkspace).replace(" ","_"))
    projectAOI = watershedFD + os.sep + projectName + "_AOI"
    aoiName = os.path.basename(projectAOI)

    watershed = watershedFD + os.sep + (arcpy.ValidateTableName(userWtshdName, watershedFD))
    FlowAccum = watershedGDB_path + os.sep + "flowAccumulation"
    FlowDir = watershedGDB_path + os.sep + "flowDirection"
    DEM_aoi = watershedGDB_path + os.sep + projectName + "_Raw_DEM"
    DEMsmooth = watershedGDB_path + os.sep + projectName  + "_DEMsmooth"
    ProjectDEM = watershedGDB_path + os.sep + projectName + "_Project_DEM"
    outletFC = watershedFD + os.sep + "ReferenceLine"

    outletStats = watershedGDB_path + os.sep + "outletStats"
    slopeStats = watershedGDB_path + os.sep + "slopeStats"

    watershedOut = "" + os.path.basename(watershed) + ""
    outletOut = "" + os.path.basename(outletFC) + ""

    textFilePath = userWorkspace + os.sep + projectName + "_EngTools.txt"
    logBasicSettings()

    AddMsgAndPrint("\nChecking input outlets data")
    # Make sure the FGDB and streams exists from step 1 and 2
    if not arcpy.Exists(watershedGDB_path) or not arcpy.Exists(streamsPath):
        AddMsgAndPrint("\tThe \"Streams\" Feature Class or the File Geodatabase from Step 1 was not found!",2)
        AddMsgAndPrint("\tPlease run the Define AOI and the Create Stream Network tools in the WASCOB toolset.",2)
        AddMsgAndPrint("\tExiting...",2)
        exit()

    # Must have one pour points manually digitized
    if not int(arcpy.GetCount_management(outlet).getOutput(0)) > 0:
        AddMsgAndPrint("\n\nAt least one Pour Point must be used! None Detected. Exiting\n",2)
        exit()

    # Project DEM must be present to proceed
    if not arcpy.Exists(ProjectDEM):
        AddMsgAndPrint("\tProject DEM was not found in " + watershedGDB_path,2)
        AddMsgAndPrint("\tPlease run the Define AOI and the Create Stream Network tools from the WASCOB toolset.",2)
        AddMsgAndPrint("\tExiting...",2)
        exit()

    # Flow Accumulation grid must be present to proceed
    if not arcpy.Exists(FlowAccum):
        AddMsgAndPrint("\tFlow Accumulation Grid was not found in " + watershedGDB_path,2)
        AddMsgAndPrint("Run Tool#2: \"Create Stream Network\" Again!  Exiting.....\n",2)
        exit()

    # Flow Direction grid must be present to proceed
    if not arcpy.Exists(FlowDir):
        AddMsgAndPrint("\tFlow Direction Grid was not found in " + watershedGDB_path,2)
        AddMsgAndPrint("Run Tool#2: \"Create Stream Network\" Again!  Exiting.....\n",2)
        exit()

    # ----------------------------------------------------------------------------------------------- Create New Outlet
    # -------------------------------------------- Features reside on hard disk;
    #                                              No heads up digitizing was used.
    if (os.path.dirname(arcpy.da.Describe(outlet)['catalogPath'])).find("memory") < 0:
        # if paths between outlet and outletFC are NOT the same
        if not arcpy.da.Describe(outlet)['catalogPath'] == outletFC:
            # delete the outlet feature class; new one will be created
            if arcpy.Exists(outletFC):
                arcpy.Delete_management(outletFC)
                arcpy.Clip_analysis(outlet,projectAOI,outletFC)
                AddMsgAndPrint("\nSuccessfully Recreated " + str(outletOut) + " feature class from existing layer")

            else:
                arcpy.Clip_analysis(outlet,projectAOI,outletFC)
                AddMsgAndPrint("\nSuccessfully Created " + str(outletOut) + " feature class from existing layer")

        # paths are the same therefore input IS pour point
        else:
            AddMsgAndPrint("\nUsing Existing " + str(outletOut) + " feature class")
    # -------------------------------------------- Features reside in Memory;
    #                                              heads up digitizing was used.
    else:
        if arcpy.Exists(outletFC):
            arcpy.Delete_management(outletFC)
            arcpy.Clip_analysis(outlet,projectAOI,outletFC)
            AddMsgAndPrint("\nSuccessfully Recreated " + str(outletOut) + " feature class from digitizing")

        else:
            arcpy.Clip_analysis(outlet,projectAOI,outletFC)
            AddMsgAndPrint("\nSuccessfully Created " + str(outletOut) + " feature class from digitizing")

    if arcpy.Describe(outletFC).ShapeType != "Polyline" and arcpy.Describe(outletFC).ShapeType != "Line":
        AddMsgAndPrint("\n\nYour Outlet must be a Line or Polyline layer!.....Exiting!",2)
        exit()

    numOfOutletsWithinAOI = int(arcpy.GetCount_management(outletFC).getOutput(0))
    if numOfOutletsWithinAOI < 1:
        AddMsgAndPrint("\nThere were no outlets digitized within " + aoiName + "....EXITING!",2)
        arcpy.Delete_management(outletFC)
        exit()

    try:
        aprx = arcpy.mp.ArcGISProject("CURRENT")

        for maps in aprx.listMaps():
            for lyr in maps.listLayers():
                if lyr.name in (watershedOut,outletOut):
                    maps.removeLayer(lyr)
                    AddMsgAndPrint("\nRemoving " + lyr.name + " from your ArcPro session ")
    except:
        pass

    demDesc = arcpy.da.Describe(ProjectDEM)
    demName = demDesc['name']
    demPath = demDesc['catalogPath']
    demCellSize = demDesc['meanCellWidth']
    demFormat = demDesc['format']
    demSR = demDesc['spatialReference']
    demCoordType = demSR.type
    linearUnits = demSR.linearUnitName

    if linearUnits == "Meter":
        linearUnits = "Meters"
    elif linearUnits == "Foot":
        linearUnits = "Feet"
    elif linearUnits == "Foot_US":
        linearUnits = "Feet"

    arcpy.env.extent = "MAXOF"
    arcpy.env.cellSize = demCellSize
    arcpy.env.snapRaster = demPath
    arcpy.env.outputCoordinateSystem = demSR
    arcpy.env.workspace = watershedGDB_path

    # Add Attribute Embankement(s) and calc
    if len(arcpy.ListFields(outletFC,"Subbasin")) < 1:
        arcpy.SetProgressorLabel("Adding Subbasin Field to ReferenceLine")
        arcpy.AddField_management(outletFC, "Subbasin", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    if len(arcpy.ListFields(outletFC,"MaxElev")) < 1:
        arcpy.SetProgressorLabel("Adding MaxElev Field to ReferenceLine")
        arcpy.AddField_management(outletFC, "MaxElev", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    if len(arcpy.ListFields(outletFC,"MinElev")) < 1:
        arcpy.SetProgressorLabel("Adding MinElev Field to ReferenceLine")
        arcpy.AddField_management(outletFC, "MinElev", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    if len(arcpy.ListFields(outletFC,"MeanElev")) < 1:
        arcpy.SetProgressorLabel("Adding MeanElev Field to ReferenceLine")
        arcpy.AddField_management(outletFC, "MeanElev", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    if len(arcpy.ListFields(outletFC,"LengthFt")) < 1:
        arcpy.SetProgressorLabel("Adding LengthFt Field to ReferenceLine")
        arcpy.AddField_management(outletFC, "LengthFt", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

    # Populate Subbasin Field and Calculate embankment length
    arcpy.SetProgressorLabel("Updating Subbasin Field")
    objectIDfld = "!" + arcpy.da.Describe(outletFC)['OIDFieldName'] + "!"
    arcpy.CalculateField_management(outletFC,"Subbasin",objectIDfld, "PYTHON3")

    arcpy.SetProgressorLabel("Updating LengthFt Field")
    arcpy.CalculateField_management(outletFC, "LengthFt","!shape.length@feet!", "PYTHON3")

    # Buffer outlet features by  raster cell size
    bufferDist = "" + str(demCellSize * 2) + " " + str(linearUnits) + ""
    arcpy.SetProgressorLabel("Buffering ReferenceLine by " + str(bufferDist) + " " + linearUnits)
    outletBuffer = arcpy.CreateScratchName("outletBuffer",data_type="FeatureClass",workspace="in_memory")
    arcpy.Buffer_analysis(outletFC, outletBuffer, bufferDist, "FULL", "ROUND", "LIST", "Subbasin")

    # Get Reference Line Elevation Properties (Uses ProjectDEM, which is vertical feet by 1/10ths)
    arcpy.SetProgressorLabel("Calculating Reference Line Attributes")
    AddMsgAndPrint("\nCalculating Reference Line Attributes",0)
    ZonalStatisticsAsTable(outletBuffer, "Subbasin", ProjectDEM, outletStats, "DATA")

    # Update the outlet FC with the zonal stats
    with arcpy.da.UpdateCursor(outletFC,['Subbasin','MinElev','MaxElev','MeanElev']) as cursor:
        for row in cursor:
            subBasinNumber = row[0]
            expression = (u'{} = ' + str(subBasinNumber)).format(arcpy.AddFieldDelimiters(outletStats, "Subbasin"))
            stats = [(row[0],row[1],row[2]) for row in arcpy.da.SearchCursor(outletStats,["MIN","MAX","MEAN"],where_clause=expression)][0]
            row[1] = stats[0] # Min Elev
            row[2] = stats[1] # Max Elev
            row[3] = stats[2] # Mean Elev
            cursor.updateRow(row)

    arcpy.Delete_management(outletStats)

    # Convert bufferd outlet to raster
    arcpy.SetProgressorLabel("Converting Buffered Reference Line to Raster")
    pourPointGrid = arcpy.CreateScratchName("PourPoint",data_type="RasterDataset",workspace="in_memory")
    arcpy.PolygonToRaster_conversion(outletBuffer,"Subbasin",pourPointGrid,"MAXIMUM_AREA","NONE",demCellSize)

    # Create Watershed Raster using the raster pour point
    arcpy.SetProgressorLabel("Delineating Watersheds")
    AddMsgAndPrint("\nDelineating Watershed(s)")
    watershedGrid = Watershed(FlowDir,pourPointGrid,"VALUE")

    # Convert results to simplified polygon
    arcpy.SetProgressorLabel("Converting Watershed to Polygon")
    watershedTemp = arcpy.CreateScratchName("watershedTemp",data_type="FeatureClass",workspace="in_memory")
    arcpy.RasterToPolygon_conversion(watershedGrid,watershedTemp,"SIMPLIFY","VALUE")

    # Dissolve watershedTemp by GRIDCODE or grid_code
    arcpy.SetProgressorLabel("Dissolving Polygon Watershed")
    arcpy.Dissolve_management(watershedTemp, watershed, "GRIDCODE", "", "MULTI_PART", "DISSOLVE_LINES")
    AddMsgAndPrint("\n\tSuccessfully Created " + str(int(arcpy.GetCount_management(watershed).getOutput(0))) + " Watershed(s) from " + str(outletOut),0)

    # Add Subbasin Field in watershed and calculate it to be the same as GRIDCODE
    arcpy.SetProgressorLabel("Adding Subbasin Field to Watershed")
    arcpy.AddField_management(watershed, "Subbasin", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED")

    arcpy.CalculateField_management(watershed, "Subbasin", "!GRIDCODE!", "PYTHON3")
    arcpy.DeleteField_management(watershed, "GRIDCODE")

    # Add Acres Field in watershed and calculate them and notify the user
    arcpy.SetProgressorLabel("Adding Acres Field to Watershed")
    arcpy.AddField_management(watershed, "Acres", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")
    arcpy.CalculateField_management(watershed, "Acres", "!shape.area@acres!", "PYTHON3")

    arcpy.SetProgressorLabel("Adding Avg_Slope Field to Watershed")
    arcpy.AddField_management(watershed, "Avg_Slope", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")

    # Calculate Average Slope
    if linearUnits == "Feet":
        zFactor = 1
    if linearUnits == "Meters":
        zFactor = 0.3048

    AddMsgAndPrint("\nCalculating average slope using a z-factor of " + str(zFactor),1)

    if arcpy.Exists(DEMsmooth):
        arcpy.Delete_management(DEMsmooth)

    arcpy.env.mask = watershed

    # Run Focal Statistics on the DEM_aoi to remove exteraneous values
    arcpy.SetProgressorLabel("Recreating " + projectName  + "_DEMsmooth")
    outFocalStats = FocalStatistics(ProjectDEM, "RECTANGLE 3 3 CELL","MEAN","DATA")
    outFocalStats.save(DEMsmooth)

    arcpy.SetProgressorLabel("Creating Slope layer using a z-factor of " + str(zFactor))
    slopeGrid = Slope(outFocalStats, "PERCENT_RISE", zFactor)
    ZonalStatisticsAsTable(watershed, "Subbasin", slopeGrid, slopeStats, "DATA")

    AddMsgAndPrint("\n\tSuccessfully Calculated Average Slope")

    AddMsgAndPrint("\nCreate Watershed Results:")
    AddMsgAndPrint("\tUser Watershed: " + str(watershedOut))

    arcpy.SetProgressorLabel("Updating watershed fields")
    with arcpy.da.UpdateCursor(watershed,['Subbasin','Avg_Slope','Acres','SHAPE@AREA']) as cursor:
        for row in cursor:
            subBasinNumber = row[0]
            expression = (u'{} = ' + str(subBasinNumber)).format(arcpy.AddFieldDelimiters(slopeStats, "Subbasin"))
            avgSlope = [row[0] for row in arcpy.da.SearchCursor(slopeStats,["MEAN"],where_clause=expression)][0]
            row[1] = avgSlope
            cursor.updateRow(row)

            # Inform the user of Watershed Acres, area and avg. slope
            AddMsgAndPrint("\n\tSubbasin: " + str(subBasinNumber))
            AddMsgAndPrint("\t\tAcres: " + str(round(row[2],2)))
            AddMsgAndPrint("\t\tArea: " + str(round(row[3],2)) + " Sq. " + linearUnits)
            AddMsgAndPrint("\t\tAvg. Slope: " + str(round(avgSlope,2)))
            if row[2] > 40:
                AddMsgAndPrint("\t\tSubbasin " + str(row[0]) + " is greater than the 40 acre 638 standard.",1)
                AddMsgAndPrint("\t\tConsider re-delineating to split basins or move upstream.",1)

    arcpy.Delete_management(slopeStats)

    arcpy.Compact_management(watershedGDB_path)
    AddMsgAndPrint("\nCompacted FGDB: " + os.path.basename(watershedGDB_path))

    arcpy.SetParameterAsText(2, outletFC)
    arcpy.SetParameterAsText(3, watershed)

except:
    print_exception()

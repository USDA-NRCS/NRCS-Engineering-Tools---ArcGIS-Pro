from getpass import getuser
from os import path
from sys import argv, exit
from time import ctime

from arcpy import AddFieldDelimiters, CheckExtension, CheckOutExtension, Describe, env, Exists, GetInstallInfo, GetMessages, \
    GetParameter, GetParameterAsText, ListFields, SetParameterAsText, SetProgressorLabel
from arcpy.analysis import Buffer, Clip
from arcpy.cartography import SmoothLine
from arcpy.conversion import PolygonToRaster, RasterToPolygon
from arcpy.da import SearchCursor, UpdateCursor
from arcpy.management import AddField, AssignDomainToField, CalculateField, Compact, CreateFeatureclass, Delete, DeleteField, \
    Dissolve, GetCount, TableToDomain
from arcpy.mp import ArcGISProject
from arcpy.sa import Con, FlowLength, GreaterThan, Minus, Plus, Slope, StreamLink, StreamToFeature, Watershed, ZonalStatistics, \
    ZonalStatisticsAsTable

from utils import AddMsgAndPrint, deleteESRIAddedFields, emptyScratchGDB, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, streams, outlets, watershed_name):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: WASCOB Create Watershed\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tStreams Layer: {streams}\n")
        f.write(f"\tOutlets Layer: {outlets}\n")
        f.write(f"\tWatershed Name: {watershed_name}\n")


### Initial Tool Validation ###
try:
    aprx = ArcGISProject('CURRENT')
    map = aprx.listMaps('Engineering')[0]
except:
    AddMsgAndPrint('\nThis tool must be run from an ArcGIS Pro project template distributed with the Engineering Tools. Exiting!', 2)
    exit()

if CheckExtension('Spatial') == 'Available':
    CheckOutExtension('Spatial')
else:
    AddMsgAndPrint('\nSpatial Analyst Extension not enabled. Please enable Spatial Analyst from Project, Licensing, Configure licensing options. Exiting...', 2)
    exit()

### Input Parameters ###
streams = GetParameterAsText(0)
outlets = GetParameterAsText(1)
userWtshdName = "Watershed"
# watershed_name = GetParameterAsText(2).replace(' ','_') + '_WASCOB'

try:
    env.parallelProcessingFactor = "75%"
    env.overwriteOutput = True
    env.geographicTransformations = "WGS_1984_(ITRF00)_To_NAD_1983"
    env.resamplingMethod = "BILINEAR"
    env.pyramid = "PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP"

    streamsPath = Describe(streams)['catalogPath']

    if streamsPath.find('.gdb') > 0 and streamsPath.find('_Streams') > 0:
        watershedGDB_path = streamsPath[:streamsPath.find(".gdb")+4]
    else:
        AddError("\n\n" + streams + " is an invalid Stream Network project layer")
        AddError("Please run the Create Stream Network tool.\n\n")
        exit()

    userWorkspace = path.dirname(watershedGDB_path)
    watershedGDB_name = path.basename(watershedGDB_path)
    watershedFD = watershedGDB_path + sep + "Layers"
    projectName = ValidateTableName(path.basename(userWorkspace).replace(" ","_"))
    projectAOI = watershedFD + sep + projectName + "_AOI"
    aoiName = path.basename(projectAOI)

    watershed = watershedFD + sep + (ValidateTableName(userWtshdName, watershedFD))
    FlowAccum = watershedGDB_path + sep + "flowAccumulation"
    FlowDir = watershedGDB_path + sep + "flowDirection"
    DEM_aoi = watershedGDB_path + sep + projectName + "_Raw_DEM"
    DEMsmooth = watershedGDB_path + sep + projectName  + "_DEMsmooth"
    ProjectDEM = watershedGDB_path + sep + projectName + "_Project_DEM"
    outletFC = watershedFD + sep + "ReferenceLine"

    outletStats = watershedGDB_path + sep + "outletStats"
    slopeStats = watershedGDB_path + sep + "slopeStats"

    watershedOut = "" + path.basename(watershed) + ""
    outletOut = "" + path.basename(outletFC) + ""

    textFilePath = userWorkspace + sep + projectName + "_EngTools.txt"
    logBasicSettings()

    AddMsgAndPrint("\nChecking input outlets data")
    # Make sure the FGDB and streams exists from step 1 and 2
    if not Exists(watershedGDB_path) or not Exists(streamsPath):
        AddMsgAndPrint("\tThe \"Streams\" Feature Class or the File Geodatabase from Step 1 was not found!",2)
        AddMsgAndPrint("\tPlease run the Define AOI and the Create Stream Network tools in the WASCOB toolset.",2)
        AddMsgAndPrint("\tExiting...",2)
        exit()

    # Must have one pour points manually digitized
    if not int(GetCount(outlets).getOutput(0)) > 0:
        AddMsgAndPrint("\n\nAt least one Pour Point must be used! None Detected. Exiting\n",2)
        exit()

    # Project DEM must be present to proceed
    if not Exists(ProjectDEM):
        AddMsgAndPrint("\tProject DEM was not found in " + watershedGDB_path,2)
        AddMsgAndPrint("\tPlease run the Define AOI and the Create Stream Network tools from the WASCOB toolset.",2)
        AddMsgAndPrint("\tExiting...",2)
        exit()

    # Flow Accumulation grid must be present to proceed
    if not Exists(FlowAccum):
        AddMsgAndPrint("\tFlow Accumulation Grid was not found in " + watershedGDB_path,2)
        AddMsgAndPrint("Run Tool#2: \"Create Stream Network\" Again!  Exiting.....\n",2)
        exit()

    # Flow Direction grid must be present to proceed
    if not Exists(FlowDir):
        AddMsgAndPrint("\tFlow Direction Grid was not found in " + watershedGDB_path,2)
        AddMsgAndPrint("Run Tool#2: \"Create Stream Network\" Again!  Exiting.....\n",2)
        exit()

    # ----------------------------------------------------------------------------------------------- Create New Outlet
    # -------------------------------------------- Features reside on hard disk;
    #                                              No heads up digitizing was used.
    if (path.dirname(Describe(outlets)['catalogPath'])).find("memory") < 0:
        # if paths between outlet and outletFC are NOT the same
        if not Describe(outlets)['catalogPath'] == outletFC:
            # delete the outlet feature class; new one will be created
            if Exists(outletFC):
                Delete(outletFC)
                Clip(outlets,projectAOI,outletFC)
                AddMsgAndPrint("\nSuccessfully Recreated " + str(outletOut) + " feature class from existing layer")

            else:
                Clip(outlets,projectAOI,outletFC)
                AddMsgAndPrint("\nSuccessfully Created " + str(outletOut) + " feature class from existing layer")

        # paths are the same therefore input IS pour point
        else:
            AddMsgAndPrint("\nUsing Existing " + str(outletOut) + " feature class")
    # -------------------------------------------- Features reside in Memory;
    #                                              heads up digitizing was used.
    else:
        if Exists(outletFC):
            Delete(outletFC)
            Clip(outlets,projectAOI,outletFC)
            AddMsgAndPrint("\nSuccessfully Recreated " + str(outletOut) + " feature class from digitizing")

        else:
            Clip(outlets,projectAOI,outletFC)
            AddMsgAndPrint("\nSuccessfully Created " + str(outletOut) + " feature class from digitizing")

    if Describe(outletFC).ShapeType != "Polyline" and Describe(outletFC).ShapeType != "Line":
        AddMsgAndPrint("\n\nYour Outlet must be a Line or Polyline layer!.....Exiting!",2)
        exit()

    numOfOutletsWithinAOI = int(GetCount(outletFC).getOutput(0))
    if numOfOutletsWithinAOI < 1:
        AddMsgAndPrint("\nThere were no outlets digitized within " + aoiName + "....EXITING!",2)
        Delete(outletFC)
        exit()

    try:
        aprx = ArcGISProject("CURRENT")

        for maps in aprx.listMaps():
            for lyr in maps.listLayers():
                if lyr.name in (watershedOut,outletOut):
                    maps.removeLayer(lyr)
                    AddMsgAndPrint("\nRemoving " + lyr.name + " from your ArcPro session ")
    except:
        pass

    demDesc = Describe(ProjectDEM)
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

    env.extent = "MAXOF"
    env.cellSize = demCellSize
    env.snapRaster = demPath
    env.outputCoordinateSystem = demSR
    env.workspace = watershedGDB_path

    # Add Attribute Embankement(s) and calc
    if len(ListFields(outletFC,"Subbasin")) < 1:
        SetProgressorLabel("Adding Subbasin Field to ReferenceLine")
        AddField(outletFC, "Subbasin", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    if len(ListFields(outletFC,"MaxElev")) < 1:
        SetProgressorLabel("Adding MaxElev Field to ReferenceLine")
        AddField(outletFC, "MaxElev", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    if len(ListFields(outletFC,"MinElev")) < 1:
        SetProgressorLabel("Adding MinElev Field to ReferenceLine")
        AddField(outletFC, "MinElev", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    if len(ListFields(outletFC,"MeanElev")) < 1:
        SetProgressorLabel("Adding MeanElev Field to ReferenceLine")
        AddField(outletFC, "MeanElev", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    if len(ListFields(outletFC,"LengthFt")) < 1:
        SetProgressorLabel("Adding LengthFt Field to ReferenceLine")
        AddField(outletFC, "LengthFt", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

    # Populate Subbasin Field and Calculate embankment length
    SetProgressorLabel("Updating Subbasin Field")
    objectIDfld = "!" + Describe(outletFC)['OIDFieldName'] + "!"
    CalculateField(outletFC,"Subbasin",objectIDfld, "PYTHON3")

    SetProgressorLabel("Updating LengthFt Field")
    CalculateField(outletFC, "LengthFt","!shape.length@feet!", "PYTHON3")

    # Buffer outlet features by  raster cell size
    bufferDist = "" + str(demCellSize * 2) + " " + str(linearUnits) + ""
    SetProgressorLabel("Buffering ReferenceLine by " + str(bufferDist) + " " + linearUnits)
    outletBuffer = CreateScratchName("outletBuffer",data_type="FeatureClass",workspace="in_memory")
    Buffer(outletFC, outletBuffer, bufferDist, "FULL", "ROUND", "LIST", "Subbasin")

    # Get Reference Line Elevation Properties (Uses ProjectDEM, which is vertical feet by 1/10ths)
    SetProgressorLabel("Calculating Reference Line Attributes")
    AddMsgAndPrint("\nCalculating Reference Line Attributes",0)
    ZonalStatisticsAsTable(outletBuffer, "Subbasin", ProjectDEM, outletStats, "DATA")

    # Update the outlet FC with the zonal stats
    with UpdateCursor(outletFC,['Subbasin','MinElev','MaxElev','MeanElev']) as cursor:
        for row in cursor:
            subBasinNumber = row[0]
            expression = (u'{} = ' + str(subBasinNumber)).format(AddFieldDelimiters(outletStats, "Subbasin"))
            stats = [(row[0],row[1],row[2]) for row in SearchCursor(outletStats,["MIN","MAX","MEAN"],where_clause=expression)][0]
            row[1] = stats[0] # Min Elev
            row[2] = stats[1] # Max Elev
            row[3] = stats[2] # Mean Elev
            cursor.updateRow(row)

    Delete(outletStats)

    # Convert bufferd outlet to raster
    SetProgressorLabel("Converting Buffered Reference Line to Raster")
    pourPointGrid = CreateScratchName("PourPoint",data_type="RasterDataset",workspace="in_memory")
    PolygonToRaster_conversion(outletBuffer,"Subbasin",pourPointGrid,"MAXIMUM_AREA","NONE",demCellSize)

    # Create Watershed Raster using the raster pour point
    SetProgressorLabel("Delineating Watersheds")
    AddMsgAndPrint("\nDelineating Watershed(s)")
    watershedGrid = Watershed(FlowDir,pourPointGrid,"VALUE")

    # Convert results to simplified polygon
    SetProgressorLabel("Converting Watershed to Polygon")
    watershedTemp = CreateScratchName("watershedTemp",data_type="FeatureClass",workspace="in_memory")
    RasterToPolygon_conversion(watershedGrid,watershedTemp,"SIMPLIFY","VALUE")

    # Dissolve watershedTemp by GRIDCODE or grid_code
    SetProgressorLabel("Dissolving Polygon Watershed")
    Dissolve(watershedTemp, watershed, "GRIDCODE", "", "MULTI_PART", "DISSOLVE_LINES")
    AddMsgAndPrint("\n\tSuccessfully Created " + str(int(GetCount(watershed).getOutput(0))) + " Watershed(s) from " + str(outletOut),0)

    # Add Subbasin Field in watershed and calculate it to be the same as GRIDCODE
    SetProgressorLabel("Adding Subbasin Field to Watershed")
    AddField(watershed, "Subbasin", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED")

    CalculateField(watershed, "Subbasin", "!GRIDCODE!", "PYTHON3")
    DeleteField(watershed, "GRIDCODE")

    # Add Acres Field in watershed and calculate them and notify the user
    SetProgressorLabel("Adding Acres Field to Watershed")
    AddField(watershed, "Acres", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")
    CalculateField(watershed, "Acres", "!shape.area@acres!", "PYTHON3")

    SetProgressorLabel("Adding Avg_Slope Field to Watershed")
    AddField(watershed, "Avg_Slope", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")

    # Calculate Average Slope
    if linearUnits == "Feet":
        zFactor = 1
    if linearUnits == "Meters":
        zFactor = 0.3048

    AddMsgAndPrint("\nCalculating average slope using a z-factor of " + str(zFactor),1)

    if Exists(DEMsmooth):
        Delete(DEMsmooth)

    env.mask = watershed

    # Run Focal Statistics on the DEM_aoi to remove exteraneous values
    SetProgressorLabel("Recreating " + projectName  + "_DEMsmooth")
    outFocalStats = FocalStatistics(ProjectDEM, "RECTANGLE 3 3 CELL","MEAN","DATA")
    outFocalStats.save(DEMsmooth)

    SetProgressorLabel("Creating Slope layer using a z-factor of " + str(zFactor))
    slopeGrid = Slope(outFocalStats, "PERCENT_RISE", zFactor)
    ZonalStatisticsAsTable(watershed, "Subbasin", slopeGrid, slopeStats, "DATA")

    AddMsgAndPrint("\n\tSuccessfully Calculated Average Slope")

    AddMsgAndPrint("\nCreate Watershed Results:")
    AddMsgAndPrint("\tUser Watershed: " + str(watershedOut))

    SetProgressorLabel("Updating watershed fields")
    with UpdateCursor(watershed,['Subbasin','Avg_Slope','Acres','SHAPE@AREA']) as cursor:
        for row in cursor:
            subBasinNumber = row[0]
            expression = (u'{} = ' + str(subBasinNumber)).format(AddFieldDelimiters(slopeStats, "Subbasin"))
            avgSlope = [row[0] for row in SearchCursor(slopeStats,["MEAN"],where_clause=expression)][0]
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

    Delete(slopeStats)

    Compact(watershedGDB_path)
    AddMsgAndPrint("\nCompacted FGDB: " + path.basename(watershedGDB_path))

    SetParameterAsText(2, outletFC)
    SetParameterAsText(3, watershed)

except:
    print_exception()

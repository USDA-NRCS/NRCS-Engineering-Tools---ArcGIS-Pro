from getpass import getuser
from os import path
from sys import argv, exit
from time import ctime

from arcpy import CheckExtension, CheckOutExtension, Describe, env, Exists, GetInstallInfo, GetParameterAsText, \
    SetParameterAsText, SetProgressorLabel
from arcpy.analysis import Clip
from arcpy.conversion import RasterToPolygon
from arcpy.management import AddField, AddXY, Append, CalculateField, CreateFeatureclass, Compact, CopyFeatures, \
    DeleteFeatures, FeatureVerticesToPoints, GetCount, MakeFeatureLayer, SelectLayerByAttribute
from arcpy.mp import ArcGISProject
from arcpy.sa import ExtractByMask, Int, SetNull, Times

from utils import AddMsgAndPrint, errorMsg


def logBasicSettings(log_file_path):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: \n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\t: {}\n")


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

try:
    inWatershed = GetParameterAsText(0)
    Subbasin = GetParameterAsText(1)
    DesignElev = GetParameterAsText(2)
    IntakeElev = GetParameterAsText(3)
    IntakeLocation = GetParameterAsText(4)

    env.overwriteOutput = True
    env.parallelProcessingFactor = "75%"
    env.geographicTransformations = "WGS_1984_(ITRF00)_To_NAD_1983"
    env.resamplingMethod = "BILINEAR"
    env.pyramid = "PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP"

    watershed_path = Describe(inWatershed).CatalogPath
    watershedGDB_path = watershed_path[:watershed_path .find(".gdb")+4]
    watershedGDB_name = path.basename(watershedGDB_path)
    watershedFD_path = watershedGDB_path + sep + "Layers"
    userWorkspace = path.dirname(watershedGDB_path)
    wsName = path.basename(inWatershed)
    stakeoutPoints = watershedFD_path + sep + "stakeoutPoints"
    ProjectDEM = watershedGDB_path + sep + path.basename(userWorkspace).replace(" ","_") + "_Project_DEM"
    stakeoutPoints = "stakeoutPoints"
    ReferenceLine = "ReferenceLine"
    RefLineLyr = "ReferenceLineLyr"
    stakeoutPointsLyr ="stakeoutPointsLyr"
    pointsSelection = "pointsSelection"
    refLineSelection = "refLineSelection"
    textFilePath = userWorkspace + sep + path.basename(userWorkspace).replace(" ","_") + "_EngTools.txt"
    logBasicSettings()

    AddMsgAndPrint("\nChecking inputs and workspace...")
    if not Exists(ProjectDEM):
        AddMsgAndPrint("\tMissing Project_DEM from FGDB. Can not perform raster analysis.",2)
        AddMsgAndPrint("\tProject_DEM must be in the same geodatabase as your input watershed.",2)
        AddMsgAndPrint("\tCheck your the source of your provided watershed. Exiting...",2)
        exit()

    if not Exists(ReferenceLine):
        AddMsgAndPrint("\tReference Line not found in table of contents or in the workspace of your input watershed",2)
        AddMsgAndPrint("\tDouble check your inputs and workspace. Exiting...",2)
        exit()

    if int(GetCount(IntakeLocation).getOutput(0)) > 1:
        AddMsgAndPrint("\tYou provided more than one inlet location",2)
        AddMsgAndPrint("\tEach subbasin must be completed individually,",2)
        AddMsgAndPrint("\twith one intake provided each time you run this tool.",2)
        AddMsgAndPrint("\tTry again with only one intake loacation. Exiting...",2)
        exit()

    if int(GetCount(IntakeLocation).getOutput(0)) < 1:
        AddMsgAndPrint("\tYou did not provide a point for your intake loaction",2)
        AddMsgAndPrint("\tYou must create a point at the proposed inlet location by using",2)
        AddMsgAndPrint("\tthe Add Features tool in the Design Height tool dialog box. Exiting...",2)
        exit()

    if not Exists(stakeoutPoints):
        CreateFeatureclass(watershedFD_path, "stakeoutPoints", "POINT", "", "DISABLED", "DISABLED", "", "", "0", "0", "0")
        AddField(stakeoutPoints, "ID", "LONG")
        AddField(stakeoutPoints, "Subbasin", "LONG")
        AddField(stakeoutPoints, "Elev", "DOUBLE")
        AddField(stakeoutPoints, "Notes", "TEXT", field_length=50)

    # Select reference line for specified Subbasin
    MakeFeatureLayer(ReferenceLine, RefLineLyr)
    exp = "\"Subbasin\" = " + str(Subbasin) + ""
    SelectLayerByAttribute(RefLineLyr, "NEW_SELECTION", exp)
    MakeFeatureLayer(RefLineLyr, refLineSelection)

    if not int(GetCount(refLineSelection).getOutput(0)) > 0:
        # Exit if no corresponding subbasin id found in reference line
        AddMsgAndPrint("\tNo reference line features were found for subbasin " + str(Subbasin),2)
        AddMsgAndPrint("\tDouble check your inputs and specify a different subbasin ID. Exiting...",2)
        exit()

    refTemp = CreateScratchName("refTemp",data_type="FeatureClass",workspace="in_memory")
    CopyFeatures(refLineSelection, refTemp)
    SelectLayerByAttribute(RefLineLyr, "CLEAR_SELECTION", "")

    # Select any existing Reference points for specified basin and delete
    MakeFeatureLayer(stakeoutPoints, stakeoutPointsLyr)
    SelectLayerByAttribute(stakeoutPointsLyr, "NEW_SELECTION", exp)
    MakeFeatureLayer(stakeoutPointsLyr, pointsSelection)
    if int(GetCount(pointsSelection).getOutput(0)) > 0:
        DeleteFeatures(pointsSelection)
    SelectLayerByAttribute(stakeoutPointsLyr, "CLEAR_SELECTION")

    # Create Intake from user input and append to Stakeout Points
    AddMsgAndPrint("\nCreating Intake Reference Point")
    intake = CreateScratchName("intake",data_type="FeatureClass",workspace="in_memory")
    CopyFeatures(IntakeLocation, intake)
    AddField(intake, "ID", "LONG")
    AddField(intake, "Subbasin", "LONG")
    AddField(intake, "Elev", "DOUBLE")
    AddField(intake, "Notes", "TEXT", field_length=50)

    CalculateField(intake, "Id", "" + str(Subbasin)+ "", "PYTHON3")
    CalculateField(intake, "Subbasin", "" + str(Subbasin)+ "", "PYTHON3")
    CalculateField(intake, "Elev", "" + str(IntakeElev)+ "", "PYTHON3")
    CalculateField(intake, "Notes", "\"Intake\"", "PYTHON3")
    AddMsgAndPrint("\tSuccessfully created intake for subbasin " + str(Subbasin) + " at " + str(IntakeElev) + " feet")

    AddMsgAndPrint("\tAppending results to Stakeout Points...")
    Append(intake, stakeoutPoints, "NO_TEST", "", "")

    # Use DEM to determine intersection of Reference Line and Plane @ Design Elevation
    AddMsgAndPrint("\nCalculating Pool Extent")
    SelectLayerByAttribute(inWatershed, "NEW_SELECTION", exp)
    WSmask = CreateScratchName("WSmask",data_type="FeatureClass",workspace="in_memory")
    CopyFeatures(inWatershed, WSmask)
    SelectLayerByAttribute(inWatershed, "CLEAR_SELECTION")

    DA_Dem = ExtractByMask(ProjectDEM, WSmask)
    DA_sn = SetNull(DA_Dem, DA_Dem, "VALUE > " + str(DesignElev))
    DAx0 = Times(DA_sn, 0)
    DAint = Int(DAx0)

    DA_snPoly = CreateScratchName("DA_snPoly",data_type="FeatureClass",workspace="in_memory")
    RasterToPolygon(DAint, DA_snPoly, "NO_SIMPLIFY", "VALUE")

    AddMsgAndPrint("\nCreating Embankment Reference Points")
    refTempClip = CreateScratchName("refTempClip",data_type="FeatureClass",workspace="in_memory")
    Clip(refTemp, DA_snPoly, refTempClip)

    refPoints = CreateScratchName("refPoints",data_type="FeatureClass",workspace="in_memory")
    FeatureVerticesToPoints(refTempClip, refPoints, "BOTH_ENDS")
    AddMsgAndPrint("\tSuccessfully created " + str(int(GetCount(refPoints).getOutput(0))) + " reference points at " + str(DesignElev) + " feet")

    AddField(refPoints, "Id", "LONG")
    CalculateField(refPoints, "Id", "" + str(Subbasin)+ "", "PYTHON3")

    AddField(refPoints, "Elev", "DOUBLE")
    CalculateField(refPoints, "Elev", "" + str(DesignElev)+ "", "PYTHON3")

    AddField(refPoints, "Notes", "TEXT", field_length=50)
    CalculateField(refPoints, "Notes", "\"Embankment\"", "PYTHON3")

    AddMsgAndPrint("\tAppending Results to Stakeout Points...")
    Append(refPoints, stakeoutPoints, "NO_TEST")

    AddMsgAndPrint("\nAdding XY Coordinates to Stakeout Points")
    AddXY(stakeoutPoints)

    Compact(watershedGDB_path)

    SetParameterAsText(5, stakeoutPoints)

except:
    errorMsg()

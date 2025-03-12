from getpass import getuser
from os import path
from sys import argv, exit
from time import ctime

from arcpy import Describe, env, Exists, GetInstallInfo, GetParameterAsText, ListFields, SetParameterAsText, SetProgressorLabel
from arcpy.analysis import Intersect, Statistics
from arcpy.da import SearchCursor, UpdateCursor
from arcpy.management import AddField, AddJoin, AlterField, CalculateField, Compact, Delete, DeleteField, Dissolve, GetCount, \
    MakeFeatureLayer, RemoveJoin, SelectLayerByAttribute
from arcpy.mp import ArcGISProject

from utils import AddMsgAndPrint, emptyScratchGDB, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, input_watershed):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Calculate Runoff Curve Number\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tWatershed Layer: {input_watershed}\n")


### Initial Tool Validation ###
try:
    aprx = ArcGISProject('CURRENT')
    map = aprx.listMaps('Engineering')[0]
except:
    AddMsgAndPrint('\nThis tool must be run from an ArcGIS Pro project template distributed with the Engineering Tools. Exiting!', 2)
    exit()

### Input Parameters ###
input_watershed = GetParameterAsText(0)

### Locate Project GDB ###
watershed_path = Describe(input_watershed).catalogPath
if 'EngPro.gdb' in watershed_path:
    project_gdb = watershed_path[:watershed_path.find('.gdb')+4]
else:
    AddMsgAndPrint('\nThe selected Watershed layer is not from an Engineering Tools project or is not compatible with this version of the toolbox. Exiting...', 2)
    exit()

### Set Paths and Variables ###
support_dir = path.dirname(argv[0])
support_gdb = path.join(support_dir, 'Support.gdb')
scratch_gdb = path.join(support_dir, 'Scratch.gdb')
project_workspace = path.dirname(project_gdb)
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")
project_fd = path.join(project_gdb, 'Layers')
watershed_name = path.basename(watershed_path)
land_use_path = path.join(project_fd, f"{watershed_name}_Land_Use")
soils_path = path.join(project_fd, f"{watershed_name}_Soils")
output_rcn_name = f"{watershed_name}_RCN"
output_rcn_path = path.join(project_fd, output_rcn_name)
hydro_groups_lookup_table = path.join(support_gdb, 'HYD_GRP_Lookup')
tr_55_rcn_lookup_table = path.join(support_gdb, 'TR_55_RCN_Lookup')
watershed_landuse_soils_temp = path.join(scratch_gdb, 'watershed_landuse_soils')
rcn_stats_temp = path.join(scratch_gdb, 'rcn_stats')

### Validate Required Datasets Exist ###
if '_Land_Use' in input_watershed or '_Soils' in input_watershed:
    AddMsgAndPrint('\nInput layer appears to be either a Land Use or Soils layer, not the Watershed layer. Exiting...', 2)
    exit()
if not len(ListFields(input_watershed, 'Subbasin')) > 0:
    AddMsgAndPrint('\nSubbasin field was not found in input Watershed layer. Please run Prepare Soil and Land Use Layers tool before running this tool. Exiting...', 2)
    exit()
if not Exists(land_use_path):
    AddMsgAndPrint('\nLand Use layer not found for input Watershed layer. Please run Prepare Soil and Land Use Layers tool and attribute the resulting Land Use layer before running this tool. Exiting...', 2)
    exit()
if not Exists(soils_path):
    AddMsgAndPrint('\nSoils layer not found for input Watershed layer. Please run Prepare Soil and Land Use Layers tool before running this tool. Exiting...', 2)
    exit()
if not Exists(hydro_groups_lookup_table):
    AddMsgAndPrint('\HYD_GRP_Lookup table was not found in Support.gdb. Exiting...', 2)
    exit()
if not Exists(tr_55_rcn_lookup_table):
    AddMsgAndPrint('\TR_55_RCN_Lookup table was not found in Support.gdb. Exiting...', 2)
    exit()

### ESRI Environment Settings ###
env.overwriteOutput = True
env.parallelProcessingFactor = '75%'

try:
    removeMapLayers(map, [output_rcn_name])
    logBasicSettings(log_file_path, input_watershed)

    # Check for Null Values in Landuse Field
    AddMsgAndPrint("\nChecking Values in landuse layer...")

    # Landuse Field MUST be populated.  It is acceptable to have Condition field unpopulated.
    query = "\"LANDUSE\" LIKE '%Select%' OR \"LANDUSE\" Is Null"
    nullFeatures = [row[0] for row in SearchCursor(land_use_path, ["LANDUSE"], where_clause=query)]

    if len(nullFeatures) > 0:
        AddMsgAndPrint("\n\tThere are " + str(len(nullFeatures)) + " NULL or un-populated values in the LANDUSE or CONDITION Field of your landuse layer.",2)
        AddMsgAndPrint("\tMake sure all rows are attributed in an edit session, save your edits, stop editing and re-run this tool.",2)
        exit()

    # Check for Combined Classes in Soils Layer...
    AddMsgAndPrint("\nChecking Values in soils layer...")

    query = "\"HYDGROUP\" LIKE '%/%' OR \"HYDGROUP\" Is Null"
    combClasses = [row[0] for row in SearchCursor(soils_path, ["HYDGROUP"], where_clause=query)]

    if len(combClasses) > 0:
        AddMsgAndPrint("\n\tThere are " + str(len(combClasses)) + " Combined or un-populated classes in the HYDGROUP Field of your watershed soils layer.",2)
        AddMsgAndPrint("\tYou will need to make sure all rows are attributed with a single class in an edit session,",2)
        AddMsgAndPrint("\tsave your edits, stop editing and re-run this tool.\n",2)
        exit()

    # Intersect Soils, Landuse and Subbasins.
    if not len(ListFields(input_watershed, "RCN")) > 0:
        AddField(input_watershed, "RCN", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED")

    if not len(ListFields(input_watershed, "Acres")) > 0:
        AddField(input_watershed, "Acres", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")

    CalculateField(input_watershed, "Acres", "!shape.area@ACRES!", "PYTHON3")

    Intersect([input_watershed, land_use_path, soils_path], watershed_landuse_soils_temp, "NO_FID", "", "INPUT")

    AddField(watershed_landuse_soils_temp, "LUDESC", "TEXT", "255", "", "", "", "NULLABLE", "NON_REQUIRED")
    AddField(watershed_landuse_soils_temp, "LU_CODE", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")
    AddField(watershed_landuse_soils_temp, "HYDROL_ID", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")
    AddField(watershed_landuse_soils_temp, "HYD_CODE", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")
    AddField(watershed_landuse_soils_temp, "RCN_ACRES", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")
    AddField(watershed_landuse_soils_temp, "WGTRCN", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")
    AddField(watershed_landuse_soils_temp, "IDENT", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED")

    AddMsgAndPrint("\nSuccessfully intersected Hydrologic Groups, Landuse, and Subbasin Boundaries")

    # Perform Checks on Landuse and Condition Attributes
    # Make all edits to feature layer; delete intersect fc.
    watershed_landuse_soils_temp_lyr = 'watershed_landuse_soils_temp_lyr'
    MakeFeatureLayer(watershed_landuse_soils_temp, watershed_landuse_soils_temp_lyr)

    AddMsgAndPrint("\nChecking Landuse and Condition Values in intersected data")
    assumptions = 0

    # Check #1: Set the condition to the following landuses to NULL
    query = "\"LANDUSE\" = 'Fallow Bare Soil' OR \"LANDUSE\" = 'Farmstead' OR \"LANDUSE\" LIKE 'Roads%' OR \"LANDUSE\" LIKE 'Paved%' OR \"LANDUSE\" LIKE '%Districts%' OR \"LANDUSE\" LIKE 'Newly Graded%' OR \"LANDUSE\" LIKE 'Surface Water%' OR \"LANDUSE\" LIKE 'Wetland%'"
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, "NEW_SELECTION", query)
    count = int(GetCount(watershed_landuse_soils_temp_lyr).getOutput(0))

    if count > 0:
        CalculateField(watershed_landuse_soils_temp_lyr, "CONDITION", "\"\"", "PYTHON3",)

    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, "CLEAR_SELECTION")

    # Check #2: Convert All 'N/A' Conditions to 'Good'
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, "NEW_SELECTION", "\"CONDITION\" = 'N/A'")
    count = int(GetCount(watershed_landuse_soils_temp_lyr).getOutput(0))

    if count > 0:
        AddMsgAndPrint("\n\tThere were " + str(count) + " Landuse polygons with CONDITION 'N/A' that require a condition of Poor, Fair, or Good.",1)
        AddMsgAndPrint("\tCondition for these areas will be assumed to be 'Good'.")
        CalculateField(watershed_landuse_soils_temp_lyr, "CONDITION", '"Good"', "PYTHON3")
        assumptions = assumptions + 1

    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, "CLEAR_SELECTION")

    # Check #3: "Open Space Grass Cover 50 to 75 percent" should have a condition of "Fair"
    query = "\"LANDUSE\" = 'Open Space Grass Cover 50 to 75 percent' AND \"CONDITION\" <> 'Fair'"
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, "NEW_SELECTION", query)
    count = int(GetCount(watershed_landuse_soils_temp_lyr).getOutput(0))

    if count > 0:
        AddMsgAndPrint("\n\tThere were " + str(count) + " 'Open Space Grass Cover 50 to 75 percent' polygons with a condition other than fair.",1)
        AddMsgAndPrint("\tA condition of fair will be assigned to these polygons.",1)
        CalculateField(watershed_landuse_soils_temp_lyr, "CONDITION", '"Fair"', "PYTHON3")
        assumptions = assumptions + 1

    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, "CLEAR_SELECTION")

    # Check #4: "Open Space Grass Cover greater than 75 percent" should have a condition of "Good"
    query = "\"LANDUSE\" = 'Open Space Grass Cover greater than 75 percent' AND \"CONDITION\" <> 'Good'"
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, "NEW_SELECTION", query)
    count = int(GetCount(watershed_landuse_soils_temp_lyr).getOutput(0))

    if count > 0:
        AddMsgAndPrint("\n\tThere were " + str(count) + " 'Open Space Grass Cover greater than 75 percent' polygons with a condition other than Good. Greater than 75 percent cover assumes a condition of 'Good'..\n",1)
        AddMsgAndPrint("\tA condition of Good will be assigned to these polygons.\n",1)
        CalculateField(watershed_landuse_soils_temp_lyr, "CONDITION", '"Good"', "PYTHON3")
        assumptions = assumptions + 1

    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, "CLEAR_SELECTION")

    # Check #5: "Open Space, Grass Cover less than 50 percent" should have a condition of "Poor"
    query = "\"LANDUSE\" = 'Open Space, Grass Cover less than 50 percent' AND  \"CONDITION\" <> 'Poor'"
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, "NEW_SELECTION", query)
    count = int(GetCount(watershed_landuse_soils_temp_lyr).getOutput(0))

    if count > 0:
        AddMsgAndPrint("\n\n\tThere were " + str(count) + " 'Open Space, Grass Cover less than 50 percent' polygons with a condition other than Poor. Less than 50 percent cover assumes a condition of 'Poor'..\n",1)
        AddMsgAndPrint("\tA condition of Poor will be assigned to these polygons.\n",1)
        CalculateField(watershed_landuse_soils_temp_lyr, "CONDITION", '"Poor"', "PYTHON3")
        assumptions = assumptions + 1

    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, "CLEAR_SELECTION")

    # Check #6: "Meadow or Continuous Grass Not Grazed Generally Hayed" should have a condition of "Good"
    query = "\"LANDUSE\" = 'Meadow or Continuous Grass Not Grazed Generally Hayed' AND  \"CONDITION\" <> 'Good'"
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, "NEW_SELECTION", query)
    count = int(GetCount(watershed_landuse_soils_temp_lyr).getOutput(0))

    if count > 0:
        AddMsgAndPrint("\n\n\tThere were " + str(count) + " 'Meadow or Continuous Grass Not Grazed Generally Hayed' polygons with a condition other than Good.",1)
        AddMsgAndPrint("\tA condition of Good will be assigned to these polygons.\n",1)
        CalculateField(watershed_landuse_soils_temp_lyr, "CONDITION", '"Good"', "PYTHON3")
        assumptions = assumptions + 1

    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, "CLEAR_SELECTION")

    # Check #7: "Woods Grazed Not Burned Some forest Litter" should have a condition of "Fair"
    query = "\"LANDUSE\" = 'Woods Grazed Not Burned Some forest Litter' AND \"CONDITION\" <> 'Fair'"
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, "NEW_SELECTION", query)
    count = int(GetCount(watershed_landuse_soils_temp_lyr).getOutput(0))

    if count > 0:
        AddMsgAndPrint("\n\n\tThere were " + str(count) + " 'Woods Grazed Not Burned Some forest Litter' polygons with a condition other than fair.",1)
        AddMsgAndPrint("\tA condition of fair will be assigned to these polygons.\n",1)
        CalculateField(watershed_landuse_soils_temp_lyr, "CONDITION", '"Fair"', "PYTHON3")
        assumptions = assumptions + 1

    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, "CLEAR_SELECTION")

    # Check #8: "Woods Not Grazed Adequate litter and brush" should have a condition of "Good"
    query = "\"LANDUSE\" = 'Woods Not Grazed Adequate litter and brush' AND  \"CONDITION\" <> 'Good'"
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, "NEW_SELECTION", query)
    count = int(GetCount(watershed_landuse_soils_temp_lyr).getOutput(0))

    if count > 0:
        AddMsgAndPrint("\n\n\tThere were " + str(count) + " 'Woods Not Grazed Adequate litter and brush' polygons with a condition other than Good.",1)
        AddMsgAndPrint("\tA condition of Good will be assigned to these polygons.\n",1)
        CalculateField(watershed_landuse_soils_temp_lyr, "CONDITION", '"Good"', "PYTHON3")
        assumptions = assumptions + 1

    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, "CLEAR_SELECTION")

    # Check #9: "Woods Heavily Grazed or Burned" should have a condition of "Poor"
    query = "\"LANDUSE\" = 'Woods Heavily Grazed or Burned' AND  \"CONDITION\" <> 'Poor'"
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, "NEW_SELECTION", query)
    count = int(GetCount(watershed_landuse_soils_temp_lyr).getOutput(0))

    if count > 0:
        AddMsgAndPrint("\n\tThere were " + str(count) + " 'Woods Heavily Grazed or Burned' polygons with a condition other than Poor.",1)
        AddMsgAndPrint("\tA condition of Poor will be assigned to these polygons.\n",1)
        CalculateField(watershed_landuse_soils_temp_lyr, "CONDITION", '"Poor"', "PYTHON3")
        assumptions = assumptions + 1

    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, "CLEAR_SELECTION")

    # Check #10: Fallow crops, Row crops, Small Grains or closed seed should have a condition of 'Good' or 'Poor' - default to Good
    query = "\"LANDUSE\" LIKE 'Fallow Crop%' AND \"CONDITION\" = 'Fair' OR \"LANDUSE\" LIKE 'Row Crops%' AND \"CONDITION\" = 'Fair' OR \"LANDUSE\" LIKE 'Small Grain%' AND \"CONDITION\" = 'Fair' OR \"LANDUSE\" LIKE 'Close Seeded%' AND \"CONDITION\" = 'Fair'"
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, "NEW_SELECTION", query)
    count = int(GetCount(watershed_landuse_soils_temp_lyr).getOutput(0))

    if count > 0:
        AddMsgAndPrint("\n\tThere were " + str(count) + " Cropland related polygons with a 'Fair' condition listed. This Landuse assumes a condition of 'Good' or 'Poor'..\n",1)
        AddMsgAndPrint("\tA condition of Good will be assumed and assigned to these polygons.\n",1)
        CalculateField(watershed_landuse_soils_temp_lyr, "CONDITION", '"Good"', "PYTHON3")
        assumptions = assumptions + 1

    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, "CLEAR_SELECTION")

    if assumptions == 0:
        AddMsgAndPrint("\n\tAll populated correctly!",0)

    # Join LU Descriptions and assign codes for RCN Lookup
    # Select Landuse categories that arent assigned a condition (these dont need to be concatenated)
    query = "\"CONDITION\" = ''"
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, "NEW_SELECTION", query)
    count = int(GetCount(watershed_landuse_soils_temp_lyr).getOutput(0))

    if count > 0:
        CalculateField(watershed_landuse_soils_temp_lyr, "LUDESC", "!LANDUSE!", "PYTHON3")

    # Concatenate Landuse and Condition fields together
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, "SWITCH_SELECTION", "")
    CalculateField(watershed_landuse_soils_temp_lyr, "LUDESC", "!LANDUSE!" + "' '" +  "!CONDITION!", "PYTHON3")
    SelectLayerByAttribute(watershed_landuse_soils_temp_lyr, "CLEAR_SELECTION")

    # Join Layer and TR_55_RCN_Lookup table to get LUCODE
    # Had to create inJoinFld variable b/c createscratchanme appends a number at the end of the name
    AddJoin(watershed_landuse_soils_temp_lyr, "LUDESC", tr_55_rcn_lookup_table, "LandUseDes", "KEEP_ALL")
    inJoinFld = ''.join((path.basename(watershed_landuse_soils_temp),'.LU_CODE'))
    CalculateField(watershed_landuse_soils_temp_lyr, inJoinFld, "!TR_55_RCN_Lookup.LU_CODE!", "PYTHON3")
    RemoveJoin(watershed_landuse_soils_temp_lyr, "TR_55_RCN_Lookup")
    AddMsgAndPrint("\nSuccesfully Joined to TR_55_RCN Lookup table to assign Land Use Codes")

    # Join Layer and HYD_GRP_Lookup table to get HYDCODE
    AddJoin(watershed_landuse_soils_temp_lyr, "HYDGROUP", hydro_groups_lookup_table, "HYDGRP", "KEEP_ALL")
    inJoinFld = ''.join((path.basename(watershed_landuse_soils_temp),'.HYDROL_ID'))
    CalculateField(watershed_landuse_soils_temp_lyr, inJoinFld, "!HYD_GRP_Lookup.HYDCODE!", "PYTHON3")
    RemoveJoin(watershed_landuse_soils_temp_lyr, "HYD_GRP_Lookup")
    AddMsgAndPrint("\nSuccesfully Joined to HYD_GRP_Lookup table to assign Hydro Codes")

    # Join and Populate RCN Values
    # Concatenate LU Code and Hydrol ID to create HYD_CODE for RCN Lookup
    exp = "''.join([str(int(!LU_CODE!)),str(int(!HYDROL_ID!))])"
    CalculateField(watershed_landuse_soils_temp_lyr, "HYD_CODE", exp,"PYTHON3")

    # Join Layer and TR_55_RCN_Lookup to get RCN value
    AddJoin(watershed_landuse_soils_temp_lyr, "HYD_CODE", tr_55_rcn_lookup_table, "HYD_CODE", "KEEP_ALL")
    inJoinFld = ''.join((path.basename(watershed_landuse_soils_temp),'.RCN'))
    CalculateField(watershed_landuse_soils_temp_lyr, inJoinFld, "!TR_55_RCN_Lookup.RCN!", "PYTHON3")
    RemoveJoin(watershed_landuse_soils_temp_lyr, "TR_55_RCN_Lookup")
    AddMsgAndPrint("\nSuccesfully Joined to TR_55_RCN Lookup table to assign Curve Numbers for Unique Combinations")

    # Calculate Weighted RCN For Each Subbasin
    # Update acres for each new polygon
    CalculateField(watershed_landuse_soils_temp_lyr, "RCN_ACRES", "!shape.area@ACRES!", "PYTHON3")

    # Get weighted acres
    CalculateField(watershed_landuse_soils_temp_lyr, "WGTRCN", "(!RCN_ACRES! / !ACRES!) * !RCN!", "PYTHON3")

    Statistics(watershed_landuse_soils_temp_lyr, rcn_stats_temp, "WGTRCN SUM", "Subbasin")
    AddMsgAndPrint("\nSuccessfully Calculated Weighted Runoff Curve Number for each SubBasin")

    # Put the results in Watershed Attribute Table
    with UpdateCursor(input_watershed, ['Subbasin','RCN']) as cursor:
        for row in cursor:

            # Get the RCN Value from rcn_stats table by subbasin number
            subBasinNumber = row[0]

            # subbasin values should not be NULL
            if subBasinNumber is None or len(str(subBasinNumber)) < 1:
                AddMsgAndPrint("\n\tSubbasin record is NULL in " + watershed_name, 2)
                continue

            expression = (f"Subbasin = {str(subBasinNumber)}")
            rcnValue = [row[0] for row in SearchCursor(rcn_stats_temp, ["SUM_WGTRCN"], where_clause=expression)][0]

            # Update the inWatershed subbasin RCN value
            row[1] = rcnValue
            cursor.updateRow(row)

            AddMsgAndPrint("\n\tSubbasin ID: " + str(subBasinNumber))
            AddMsgAndPrint("\t\tWeighted Average RCN Value: " + str(round(rcnValue,0)))

    # Create fresh new RCN Layer
    AddMsgAndPrint("\nAdding unique identifier to each subbasin's soil and landuse combinations")

    exp = "''.join([str(int(!HYD_CODE!)),str(int(!Subbasin!))])"
    CalculateField(watershed_landuse_soils_temp_lyr, "IDENT", exp, "PYTHON3")

    # Dissolve the intersected layer by Subbasin and Hyd_code to produce rcn layer
    statFields = [['IDENT','FIRST'],['LANDUSE','FIRST'],['CONDITION','FIRST'],['HYDGROUP','FIRST'],['RCN','FIRST'],['Acres','FIRST']]
    Dissolve(watershed_landuse_soils_temp_lyr, output_rcn_path, ["Subbasin","HYD_CODE"], statFields, "MULTI_PART", "DISSOLVE_LINES")

    # Remove 'FIRST' from the field name and update alias as well
    for fld in [f.name for f in ListFields(output_rcn_path)]:
        if fld.startswith('FIRST'):
            AlterField(output_rcn_path, fld, fld[6:], fld[6:])

    # Update Acres
    CalculateField(output_rcn_path, "Acres", "!shape.area@ACRES!", "PYTHON3")

    # Remove Unnecessary fields
    DeleteField(output_rcn_path, ['IDENT','HYD_CODE'])

    ### Add Output to Map ###
    SetParameterAsText(1, output_rcn_path)

    ### Compact Project GDB ###
    try:
        SetProgressorLabel('Compacting project geodatabase...')
        AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
        Compact(project_gdb)
    except:
        pass

    AddMsgAndPrint('\nCalculate Runoff Curve Number completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Calculate Runoff Curve Number'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Calculate Runoff Curve Number'), 2)

finally:
    emptyScratchGDB(scratch_gdb)

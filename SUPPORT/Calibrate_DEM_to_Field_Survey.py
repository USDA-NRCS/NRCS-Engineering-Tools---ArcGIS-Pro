from getpass import getuser
from os import path
from sys import argv, exit
from time import ctime
from arcpy import CheckExtension, CheckOutExtension, Describe, env, Exists, GetInstallInfo, GetParameter, GetParameterAsText, ListFields, SetProgressorLabel
from arcpy.da import SearchCursor, UpdateCursor
from arcpy.management import AddField, CalculateField, Compact, CopyFeatures, Delete, GetCount
from arcpy.mp import ArcGISProject
from arcpy.sa import Plus, ZonalStatisticsAsTable
from utils import AddMsgAndPrint, emptyScratchGDB, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, project_dem, project_vertical_units, input_points, input_field, input_elevation_units, input_value):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Calibrate DEM to Field Survey\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tProject DEM: {project_dem}\n")
        f.write(f"\tProject DEM Vertical Units: {project_vertical_units}\n")
        f.write(f"\tInput Survey Points: {input_points if input_points else 'None'}\n")
        f.write(f"\tSurvey Elevation Field: {input_field if input_field else 'None'}\n")
        f.write(f"\tInput Elevation Units: {input_elevation_units if input_elevation_units else 'Not specified'}\n")
        f.write(f"\tManual Adjustment Value: {input_value if input_value not in [None, ''] else 'None'}\n")


# expanded logging so unit inputs and manual adjustments are traceable.
def getOptionalParameterAsText(parameter_index):
    try:
        return GetParameterAsText(parameter_index)
    except:
        return ''


# unit normalization/conversion helpers so survey/manual inputs can be matched to DEM Z-units.
def normalizeVerticalUnits(unit_name):

    if not unit_name:
        return ''

    unit_lookup = {
        'Meter': 'Meters',
        'Meters': 'Meters',
        'Foot': 'International Feet',
        'Feet': 'International Feet',
        'International Foot': 'International Feet',
        'International Feet': 'International Feet',
        'Foot_US': 'US Survey Feet',
        'US Survey Foot': 'US Survey Feet',
        'US Survey Feet': 'US Survey Feet'
    }
    return unit_lookup.get(unit_name, unit_name)


def getVerticalConversionFactor(input_units, output_units):
    input_units = normalizeVerticalUnits(input_units)
    output_units = normalizeVerticalUnits(output_units)

    conversion_lookup = {
        'Meters': {
            'Meters': 1,
            'International Feet': 3.280839895,
            'US Survey Feet': 3.2808333333
        },
        'International Feet': {
            'Meters': 0.3048,
            'International Feet': 1,
            'US Survey Feet': 0.999998
        },
        'US Survey Feet': {
            'Meters': 0.3048006096,
            'International Feet': 1.000002,
            'US Survey Feet': 1
        }
    }

    try:
        return conversion_lookup[input_units][output_units]
    except:
        return None


def getProjectVerticalUnits(project_units_table_path):
    if not Exists(project_units_table_path):
        return ''

    field_names = [field.name for field in ListFields(project_units_table_path)]
    if 'OUTPUT_Z_UNITS' not in field_names:
        return ''

    with SearchCursor(project_units_table_path, ['OUTPUT_Z_UNITS']) as cursor:
        for row in cursor:
            return normalizeVerticalUnits(row[0])

    return ''


def addFieldIfMissing(dataset, field_name, field_type):
    existing_fields = [field.name.upper() for field in ListFields(dataset)]
    if field_name.upper() not in existing_fields:
        AddField(dataset, field_name, field_type)


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
project_dem = GetParameterAsText(0)
input_points = GetParameterAsText(1)  
input_field = GetParameterAsText(2)
input_value = GetParameter(3)
# added explicit input elevation units parameter for unit-aware calibration.
input_elevation_units = normalizeVerticalUnits(getOptionalParameterAsText(4))

if input_value in [None, '']:
    input_value = 0

### Locate Project GDB ###
project_dem_path = Describe(project_dem).CatalogPath
if 'EngPro.gdb' in project_dem_path and 'DEM' in project_dem_path:
    project_gdb = project_dem_path[:project_dem_path.find('.gdb')+4]
else:
    AddMsgAndPrint('\nThe selected DEM is not from an Engineering Tools project or is not compatible with this version of the toolbox. Exiting...', 2)
    exit()

### Set Paths and Variables ###
support_dir = path.dirname(argv[0])
scratch_gdb = path.join(support_dir, 'Scratch.gdb')
project_workspace = path.dirname(project_gdb)
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")
project_fd = path.join(project_gdb, 'Layers')
survey_points = path.join(project_fd, 'DEM_Calibration_Points')
adjusted_dem_name = f"{project_name}_DEM_adjusted"
adjusted_dem_path = path.join(project_gdb, adjusted_dem_name)
project_units_table_name = f"{project_name}_Project_Units"
project_units_table_path = path.join(project_gdb, project_units_table_name)
temp_points = r"memory\temp_points"
temp_stats = r"memory\temp_stats"
elevation_adjustment = 0
adjustment_tolerance = 0.1

# calibration now reads project DEM Z-units from the project settings table.
project_vertical_units = getProjectVerticalUnits(project_units_table_path)

if project_vertical_units == '':
    AddMsgAndPrint('\nThe project unit settings table is missing or does not contain output DEM vertical units. Please run Create DEM with the current toolbox before calibrating the DEM. Exiting...', 2)
    exit()

### ESRI Environment Settings ###
dem_desc = Describe(project_dem_path)
dem_cell_size = dem_desc.meanCellWidth
env.cellSize = dem_cell_size
env.snapRaster = project_dem_path
env.outputCoordinateSystem = dem_desc.spatialReference
env.resamplingMethod = 'BILINEAR'
env.pyramid = 'PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP'
env.parallelProcessingFactor = '75%'
env.extent = 'MINOF'
env.overwriteOutput = True

try:
    removeMapLayers(map, [adjusted_dem_name])
    logBasicSettings(log_file_path, project_dem, project_vertical_units, input_points, input_field, input_elevation_units, input_value)

    ### Survey Points Layer Provided ###
    # survey-point workflow now validates/converts elevations into project DEM Z-units.
    if input_points and int(GetCount(input_points).getOutput(0)) > 0:

        if input_elevation_units == '':
            AddMsgAndPrint(f"\nInput survey elevation units were not specified. Survey elevations must be provided in known units so they can be converted to the project DEM vertical units ({project_vertical_units}). Exiting...", 2, log_file_path)
            exit()

        survey_to_dem_factor = getVerticalConversionFactor(input_elevation_units, project_vertical_units)
        if survey_to_dem_factor is None:
            AddMsgAndPrint(f"\nUnable to convert survey elevations from {input_elevation_units} to {project_vertical_units}. Exiting...", 2, log_file_path)
            exit()

        SetProgressorLabel('Processing survey points...')
        AddMsgAndPrint('\nProcessing survey points...', log_file_path=log_file_path)
        AddMsgAndPrint(f"\tProject DEM vertical units: {project_vertical_units}", log_file_path=log_file_path)
        if input_elevation_units == project_vertical_units:
            AddMsgAndPrint(f"\tSurvey elevations already match project DEM vertical units: {project_vertical_units}", log_file_path=log_file_path)
        else:
            AddMsgAndPrint(f"\tConverting survey elevations from {input_elevation_units} to {project_vertical_units}", log_file_path=log_file_path)

        elevation_difference = 0
        processed_points = 0
        number_of_points = int(GetCount(input_points).getOutput(0))

        CopyFeatures(input_points, temp_points)
        # Create the field only if it does not already exist, and save the converted survey elevations so they can be reviewed later.
        addFieldIfMissing(temp_points, 'POINTID', 'LONG')

        addFieldIfMissing(temp_points, 'SURVEY_ELEV', 'DOUBLE')
        addFieldIfMissing(temp_points, 'DEM_ELEV', 'DOUBLE')
        addFieldIfMissing(temp_points, 'DIFF', 'DOUBLE')
        CalculateField(temp_points, 'POINTID', '!OBJECTID!', 'PYTHON3')

        # Use Zonal Statistics to get elevations at point locations from DEM
        ZonalStatisticsAsTable(temp_points, 'POINTID', project_dem, temp_stats, 'DATA')

        with SearchCursor(temp_stats, ['POINTID', 'MEAN']) as s_cur:
            for s_row in s_cur:
                point_id = s_row[0]
                dem_elevation = s_row[1]

                if dem_elevation is None:
                    AddMsgAndPrint(f"\nUnable to retrieve a DEM elevation for calibration point OBJECTID {point_id}. Please verify all survey points fall within the DEM extent and valid data area. Exiting...", 2, log_file_path)
                    exit()

                with UpdateCursor(temp_points, ['SURVEY_ELEV', 'DEM_ELEV', 'DIFF', input_field], f"POINTID={point_id}") as u_cur:
                    for u_row in u_cur:
                        if u_row[3] is None:
                            AddMsgAndPrint(f"\nOne or more survey points contains a null value in the selected field: {input_field}. Exiting...", 2, log_file_path)
                            exit()

                        converted_survey_elevation = round(u_row[3] * survey_to_dem_factor, 1)
                        dem_elevation_rounded = round(dem_elevation, 1)
                        elevation_difference_at_point = round(converted_survey_elevation - dem_elevation_rounded, 1)

                        u_row[0] = converted_survey_elevation
                        u_row[1] = dem_elevation_rounded
                        u_row[2] = elevation_difference_at_point
                        u_cur.updateRow(u_row)

                        elevation_difference += elevation_difference_at_point
                        processed_points += 1

        if processed_points != number_of_points:
            AddMsgAndPrint('\nOne or more survey points did not receive a DEM elevation. Please verify all survey points fall within the DEM extent and valid data area. Exiting...', 2, log_file_path)
            exit()

        elevation_adjustment = round(elevation_difference / processed_points, 1)
        CopyFeatures(temp_points, survey_points)

    ### Adjustment Value Provided ###
    # manual adjustment path now also requires known units and converts to DEM Z-units.
    elif input_value != 0:

        if input_elevation_units == '':
            AddMsgAndPrint(f"\nInput adjustment units were not specified. The manual adjustment value must be provided in known units so it can be converted to the project DEM vertical units ({project_vertical_units}). Exiting...", 2, log_file_path)
            exit()

        adjustment_to_dem_factor = getVerticalConversionFactor(input_elevation_units, project_vertical_units)
        if adjustment_to_dem_factor is None:
            AddMsgAndPrint(f"\nUnable to convert the manual adjustment value from {input_elevation_units} to {project_vertical_units}. Exiting...", 2, log_file_path)
            exit()

        elevation_adjustment = round(float(input_value) * adjustment_to_dem_factor, 1)
        if input_elevation_units == project_vertical_units:
            AddMsgAndPrint(f"\nManual adjustment units match project DEM vertical units: {project_vertical_units}", log_file_path=log_file_path)
        else:
            AddMsgAndPrint(f"\nConverted manual adjustment from {input_elevation_units} to {project_vertical_units}", log_file_path=log_file_path)

    else:
        AddMsgAndPrint('\nInput survey points layer has no features or adjustment value not specified. Exiting...', 2, log_file_path)
        exit()

    ### Adjust and Finalize DEM ###
    # tolerance check is now symmetric (+/-) and reported in the project vertical units.
    if abs(elevation_adjustment) < adjustment_tolerance:

        AddMsgAndPrint(f"\nComputed elevation adjustment is less than {adjustment_tolerance} {project_vertical_units}. DEM will not be adjusted. Exiting...", 2, log_file_path)
        exit()
    else:
        SetProgressorLabel(f"\nAdjusting DEM elevation by {elevation_adjustment} {project_vertical_units}...")
        AddMsgAndPrint(f"\nAdjusting DEM elevation by {elevation_adjustment} {project_vertical_units}...", log_file_path=log_file_path)
        dem_plus = Plus(project_dem, elevation_adjustment)
        dem_plus.save(adjusted_dem_path)

    ### Add Output DEM to Map and Symbolize ###
    SetProgressorLabel('Adding adjusted DEM to map...')
    AddMsgAndPrint('\nAdding adjusted DEM to map...', log_file_path=log_file_path)
    map.addDataFromPath(adjusted_dem_path)
    dem_layer = map.listLayers(adjusted_dem_name)[0]
    sym = dem_layer.symbology
    sym.colorizer.resamplingType = 'Bilinear' #NOTE: Pro does not seem to honor this
    sym.colorizer.stretchType = 'StandardDeviation'
    sym.colorizer.standardDeviation = 2.5
    sym.colorizer.colorRamp = aprx.listColorRamps('Elevation #1')[0]
    dem_layer.symbology = sym

    ### Update Layer Order in TOC ###
    project_dem_name = f"{project_name}_DEM"
    try:
        if map.listLayers(project_dem_name)[0]:
            map.moveLayer(map.listLayers(project_dem_name)[0], dem_layer, 'BEFORE')
    except:
        pass

    ### Compact Project GDB ###
    try:
        SetProgressorLabel('Compacting project geodatabase...')
        AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
        Compact(project_gdb)
    except:
        pass

    AddMsgAndPrint('\nCalibrate DEM to Field Survey completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Calibrate DEM to Field Survey'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Calibrate DEM to Field Survey'), 2)

finally:
    try:
        Delete(temp_points)
    except:
        pass
    try:
        Delete(temp_stats)
    except:
        pass
    emptyScratchGDB(scratch_gdb)

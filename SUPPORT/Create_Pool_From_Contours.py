from getpass import getuser
from os import path
from sys import argv, exit
from time import ctime

from arcpy import CheckExtension, CheckOutExtension, Describe, env, Exists, GetInstallInfo, GetParameterAsText, \
    SetParameterAsText, SetProgressorLabel
from arcpy.analysis import Buffer, Clip, Erase
from arcpy.conversion import RasterToPolygon
from arcpy.da import SearchCursor, UpdateCursor
from arcpy.ddd import SurfaceVolume
from arcpy.management import AddField, CalculateField, Compact, CopyFeatures, Delete, Dissolve, GetCount, FeatureToPolygon, \
    MakeFeatureLayer, SelectLayerByAttribute, SelectLayerByLocation
from arcpy.mp import ArcGISProject
from arcpy.sa import ExtractByMask, Int, SetNull, Times, ZonalStatisticsAsTable

from utils import AddMsgAndPrint, deleteESRIAddedFields, emptyScratchGDB, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, project_contours):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Create Pool from Contours\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tProject Contours: {project_contours}\n")


### Initial Tool Validation ###
try:
    aprx = ArcGISProject('CURRENT')
    map = aprx.listMaps('Engineering')[0]
except:
    AddMsgAndPrint('\nThis tool must be run from an ArcGIS Pro project template distributed with the Engineering Tools. Exiting...', 2)
    exit()

if CheckExtension('Spatial') == 'Available':
    CheckOutExtension('Spatial')
else:
    AddMsgAndPrint('\nSpatial Analyst Extension not enabled. Please enable Spatial Analyst from Project, Licensing, Configure licensing options. Exiting...', 2)
    exit()
if CheckExtension('3d') == 'Available':
    CheckOutExtension('3d')
else:
    AddMsgAndPrint('\n3D Analyst Extension not enabled. Please enable 3D Analyst from Project, Licensing, Configure licensing options. Exiting...', 2)
    exit()

### Input Parameters ###
project_contours = GetParameterAsText(0)
input_dam = GetParameterAsText(1)
output_pool_name = GetParameterAsText(2).replace(' ','_')

### Locate Project GDB and Validate Input Dam ###
project_contours_path = Describe(project_contours).CatalogPath
if 'EngPro.gdb' in project_contours_path and 'Contour' in project_contours_path:
    project_gdb = project_contours_path[:project_contours_path.find('.gdb')+4]
else:
    AddMsgAndPrint('\nThe selected layer does not appear to be the project Contours or is not compatible with this version of the toolbox. Exiting...', 2)
    exit()

### Validate Input Dam ###
if int(GetCount(input_dam).getOutput(0)) != 1:
    AddMsgAndPrint('\nA single input line feature is required. Digitize a single line, or if using an existing dams layer, ensure one line is selected. Exiting...', 2)
    exit()

### Set Paths and Variables ###
support_dir = path.dirname(argv[0])
scratch_gdb = path.join(support_dir, 'Scratch.gdb')
project_workspace = path.dirname(project_gdb)
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")
project_fd = path.join(project_gdb, 'Layers')
project_dem = path.join(project_gdb, f"{project_name}_DEM")

### Locate Project DEM ###
if not Exists(project_dem):
    AddMsgAndPrint('\nCould not locate the project DEM in the project workspace. Exiting...', 2)
    exit()
dem_desc = Describe(project_dem)
dem_cell_size = dem_desc.meanCellWidth
dem_cell_area = dem_desc.meanCellWidth * dem_desc.meanCellHeight

### Intermediate Datasets ###
dams_lyr = 'Dams_Lyr'
contour_lyr = 'Contour_Lyr'
contour_lyr2 = 'Contour_Lyr2'
contour_mask = path.join(scratch_gdb, 'Contour_Mask')
contour_erase = path.join(scratch_gdb, 'Contour_Erase')
buffer1 = path.join(scratch_gdb, 'Buffer1')
buffer2 = path.join(scratch_gdb, 'Buffer2')
buffer3 = path.join(scratch_gdb, 'Buffer3')
buffer4 = path.join(scratch_gdb, 'Buffer4')
buffer5 = path.join(scratch_gdb, 'Buffer5')
buffer6 = path.join(scratch_gdb, 'Buffer6')
buffer7 = path.join(scratch_gdb, 'Buffer7')
extent_mask = path.join(scratch_gdb, 'Extent_Mask')
dams_temp = path.join(scratch_gdb, 'Dams_Temp')
dams_stats = path.join(scratch_gdb, 'Dams_Stats')
pool_mask = path.join(scratch_gdb, 'Pool_Mask')
volume = path.join(scratch_gdb, 'Volume')
temp_pool = path.join(scratch_gdb, 'Temp_Pool')

### ESRI Environment Settings ###
env.overwriteOutput = True
env.resamplingMethod = 'BILINEAR'
env.pyramid = 'PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP'
env.parallelProcessingFactor = '75%'

### Conversion Factors - Linear Units of DEM Meters ###
to_acres = 4046.8564224
to_square_feet = 0.092903
to_acre_foot = 1233.48184
to_cubic_meters = 1
to_cubic_feet = 35.3147

try:
    logBasicSettings(log_file_path, project_contours)

    SetProgressorLabel('Selecting contours by dam...')
    AddMsgAndPrint('\nSelecting contours by dam...', log_file_path=log_file_path)

    # Copy User input to temp dam layer and add fields
    CopyFeatures(input_dam, dams_temp)
    AddField(dams_temp, 'ID', 'LONG')
    AddField(dams_temp, 'MaxElev', 'DOUBLE')
    AddField(dams_temp, 'MinElev', 'DOUBLE')
    AddField(dams_temp, 'MeanElev', 'DOUBLE')
    AddField(dams_temp, 'LengthFt', 'DOUBLE')
    AddField(dams_temp, 'TopWidth', 'DOUBLE')
    AddField(dams_temp, 'BotWidth', 'DOUBLE')

    CalculateField(dams_temp, 'ID', '!OBJECTID!', 'PYTHON3')
    CalculateField(dams_temp, 'LengthFt', "!shape!.getLength('PLANAR', 'FeetInt')", 'PYTHON3')

    # Select Contours by dam Location & copy
    MakeFeatureLayer(project_contours_path, contour_lyr)
    SelectLayerByLocation(contour_lyr, 'INTERSECT', dams_temp, '', 'NEW_SELECTION')
    CopyFeatures(contour_lyr, contour_mask)
    SelectLayerByAttribute(contour_lyr, 'CLEAR_SELECTION')

    # Buffer and erase to break contours at dam and select closed contours
    Buffer(dams_temp, buffer1, '1 Feet', 'FULL', 'FLAT', 'NONE')
    Erase(contour_mask, buffer1, contour_erase)

    Buffer(dams_temp, buffer2, '1.5 Feet', 'LEFT', 'FLAT', 'NONE')
    Buffer(dams_temp, buffer3, '3 Feet', 'LEFT', 'FLAT', 'NONE')

    Erase(buffer3, buffer1, buffer4)
    Erase(buffer4, buffer2, buffer5)

    SetProgressorLabel('Determining highest closed contour...')
    AddMsgAndPrint('\nDetermining highest closed contour...', log_file_path=log_file_path)

    # Convert intersected contours to polygon mask
    FeatureToPolygon(f"{contour_erase};{buffer2}", extent_mask)

    # Check to make sure a polygon was created before proceeding
    if not int(GetCount(extent_mask).getOutput(0)) > 0:
        AddMsgAndPrint('\nThe intersection of the dam and contours did not create a polygon. Make sure the intended pool is located to the topographic left of the line(s) you provide. Exiting...', 2, log_file_path)
        exit()

    # Select highest contour that closed @ Polygon conversion
    Clip(buffer5, extent_mask, buffer6)

    if not int(GetCount(buffer6).getOutput(0)) > 0:
        AddMsgAndPrint('\nThe intersection of the dam and contours did not create a polygon. Make sure the intended pool is located to the topographic left of the line(s) you provide. Exiting...', 2, log_file_path)
        exit()

    SelectLayerByLocation(contour_lyr, 'INTERSECT', buffer6, '', 'NEW_SELECTION')
    MakeFeatureLayer(contour_lyr, contour_lyr2)

    hi_contour = 0
    with SearchCursor(contour_lyr2, ['Contour']) as cursor:
        for row in cursor:
            if row[0] > hi_contour: hi_contour = row[0]

    AddMsgAndPrint(f"\nHighest closed contour is {hi_contour} ft...", log_file_path=log_file_path)

    # Output Datasets
    if not output_pool_name:
        output_pool_name = f"{project_name}_Pool_{str(hi_contour).replace('.','_dot_')}"
    output_pool_path = path.join(project_fd, output_pool_name)
    output_dams_name = f"{output_pool_name}_Dam"
    output_dams_path = path.join(project_fd, output_dams_name)
    storage_table_temp = path.join(project_workspace, f"{output_pool_name}_StorageCSV.txt")

    removeMapLayers(map, [output_pool_name, output_dams_name])

    CopyFeatures(dams_temp, output_dams_path)
    MakeFeatureLayer(output_dams_path, dams_lyr)

    SetProgressorLabel('Calculating pool volume...')
    AddMsgAndPrint('\nCalculating pool volume...', log_file_path=log_file_path)

    # Dissolve and populate with plane elevation for raster processing
    Dissolve(extent_mask, pool_mask)
    temp_dem = ExtractByMask(project_dem, pool_mask)

    # Convert DEM elevation units to meters for processing
    temp_dem_meters = Times(temp_dem, 0.3048)
    pool_elevation_meters = hi_contour * 0.3048

    # Delete text file from SurfaceVolume if exists to avoid duplicated/extra rows from multiple runs
    if Exists(storage_table_temp):
        Delete(storage_table_temp)

    SurfaceVolume(temp_dem_meters, storage_table_temp, 'BELOW', pool_elevation_meters, '1')

    # Create new raster of only values below an elevation value by nullifying cells above the desired elevation value
    above_elevation = SetNull(temp_dem_meters, temp_dem_meters, f"Value > {pool_elevation_meters}")

    # Multiply every pixel by 0 and convert to integer for vectorizing
    zeros = Times(above_elevation, 0)
    zero_int = Int(zeros)

    # Convert to polygon and dissolve
    RasterToPolygon(zero_int, temp_pool, 'NO_SIMPLIFY', 'VALUE')
    Dissolve(temp_pool, output_pool_path)

    AddField(output_pool_path, 'ELEV_FEET', 'DOUBLE')
    AddField(output_pool_path, 'DEM_ELEV', 'DOUBLE')
    AddField(output_pool_path, 'POOL_ACRES', 'DOUBLE')
    AddField(output_pool_path, 'POOL_SQFT', 'DOUBLE')
    AddField(output_pool_path, 'ACRE_FOOT', 'DOUBLE')
    AddField(output_pool_path, 'CUBIC_FEET', 'DOUBLE')
    AddField(output_pool_path, 'CUBIC_METERS', 'DOUBLE')

    # Open surface volume text file
    with open(storage_table_temp) as file:
        lines = file.readlines()

    area2D = float(lines[len(lines)-1].split(',')[4])
    volume = float(lines[len(lines)-1].split(',')[6])

    elevation_feet = round(pool_elevation_meters*3.28084, 1)
    area_acres = round(area2D / to_acres, 1)
    area_sqft = round(area2D / to_square_feet, 1)
    volume_acre_foot = round(volume / to_acre_foot, 1)
    volume_cubic_meters = round(volume * to_cubic_meters, 1)
    volume_cubic_feet = round(volume * to_cubic_feet, 1)

    CalculateField(output_pool_path, 'ELEV_FEET', elevation_feet, 'PYTHON3')
    CalculateField(output_pool_path, 'DEM_ELEV', pool_elevation_meters, 'PYTHON3')
    CalculateField(output_pool_path, 'POOL_ACRES', area_acres, 'PYTHON3')
    CalculateField(output_pool_path, 'POOL_SQFT', area_sqft, 'PYTHON3')
    CalculateField(output_pool_path, 'ACRE_FOOT', volume_acre_foot, 'PYTHON3')
    CalculateField(output_pool_path, 'CUBIC_METERS', volume_cubic_meters, 'PYTHON3')
    CalculateField(output_pool_path, 'CUBIC_FEET', volume_cubic_feet, 'PYTHON3')

    AddMsgAndPrint(f"\n\tCreated {output_pool_path}:")
    AddMsgAndPrint(f"\t\tElevation {elevation_feet*3.28084} Feet")
    AddMsgAndPrint(f"\t\tArea: {area_sqft} Square Feet")
    AddMsgAndPrint(f"\t\tArea: {area_acres} Acres")
    AddMsgAndPrint(f"\t\tVolume: {volume_acre_foot} Acre Feet")
    AddMsgAndPrint(f"\t\tVolume: {volume_cubic_meters} Cubic Meters")
    AddMsgAndPrint(f"\t\tVolume: {volume_cubic_feet} Cubic Feet")

    ### Clean Up Temp Datasets ###
    if Exists(storage_table_temp):
        Delete(storage_table_temp)
    if Exists(temp_dem):
        Delete(temp_dem)

    # Retrieve attributes for dam and populate fields
    SetProgressorLabel('Calculating dam info...')
    AddMsgAndPrint('\nCalculating dam info...', log_file_path=log_file_path)
    Buffer(output_dams_path, buffer7, '3 Meters', 'RIGHT', 'ROUND', 'LIST', 'ID')
    ZonalStatisticsAsTable(buffer7, 'ID', project_dem, dams_stats, 'NODATA', 'ALL')

    with SearchCursor(dams_stats, ['MIN','MAX','MEAN']) as s_cursor:
        for s_row in s_cursor:
            minElev = s_row[0]
            maxElev = s_row[1]
            meanElev = s_row[2]
            maxFt = round(float(maxElev),1)
            minFt = round(float(minElev),1)
            meanFt = round(float(meanElev),1)

            AddMsgAndPrint(f"\n\tCalculating properties of embankment {id}")
            AddMsgAndPrint(f"\n\t\tMax Elevation: {maxFt} Feet")
            AddMsgAndPrint(f"\t\tMin Elevation: {minFt} Feet")
            AddMsgAndPrint(f"\t\tMean Elevation: {meanFt} Feet")

            damHeight = int(maxFt-minFt)
            AddMsgAndPrint(f"\t\tMax Height: {damHeight} Feet")

            with UpdateCursor(output_dams_path, ['LengthFt','MaxElev','MinElev','MeanElev','TopWidth','BotWidth']) as u_cursor:
                for u_row in u_cursor:
                    damLength = u_row[0]
                    u_row[0] = round(damLength,1)
                    u_row[1] = maxFt
                    u_row[2] = minFt
                    u_row[3] = meanFt

                    AddMsgAndPrint(f"\t\tTotal Length: {u_row[0]} Feet")

                    # Assign Top and Bottom width from practice standards
                    AddMsgAndPrint('\nCalculating suggested top / bottom widths (Based on 3:1 Slope)...', log_file_path=log_file_path)

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

                    bottomWidth = round(float(topWidth + 2 * (damHeight * 3))) # (bw + 2 * ss * depth) -- Assumes a 3:1 Side slope

                    u_row[4] = topWidth
                    u_row[5] = bottomWidth

                    AddMsgAndPrint(f"\n\t\tSuggested Top Width: {u_row[4]} Feet")
                    AddMsgAndPrint(f"\t\tSuggested Bottom Width: {u_row[5]} Feet")
                    u_cursor.updateRow(u_row)

    ### Delete Fields Added if Digitized ###
    deleteESRIAddedFields(output_dams_path)

    ### Add Output to Map ###
    SetParameterAsText(3, output_pool_path)
    SetParameterAsText(4, output_dams_path)

    ### Remove Digitized Layer (if present) ###
    for lyr in map.listLayers():
        if lyr.supports("NAME"):
            if 'Create Pool from Contours' in lyr.name:
                map.removeLayer(lyr)

    ### Compact Project GDB ###
    try:
        SetProgressorLabel('Compacting project geodatabase...')
        AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
        Compact(project_gdb)
    except:
        pass

    AddMsgAndPrint('\nCreate Pool from Contours completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Create Pool from Contours'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Create Pool from Contours'), 2)

finally:
    emptyScratchGDB(scratch_gdb)

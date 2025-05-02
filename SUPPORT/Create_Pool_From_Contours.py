from getpass import getuser
from os import path
from sys import argv, exit
from time import ctime

from arcpy import CheckExtension, CheckOutExtension, Describe, env, Exists, GetInstallInfo, GetParameterAsText, SetParameterAsText, SetProgressorLabel
from arcpy.analysis import Buffer, Clip, Erase
from arcpy.conversion import FeatureToRaster, RasterToPolygon
from arcpy.da import SearchCursor, UpdateCursor
from arcpy.management import AddField, CalculateField, Compact, CopyFeatures, Dissolve, GetCount, GetRasterProperties, FeatureToPolygon, \
    MakeFeatureLayer, SelectLayerByAttribute, SelectLayerByLocation
from arcpy.mp import ArcGISProject
from arcpy.sa import ExtractByMask, Int, Minus, SetNull, Times, ZonalStatistics, ZonalStatisticsAsTable

from utils import AddMsgAndPrint, emptyScratchGDB, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, project_contours):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Calculate State Storage\n')
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
    AddMsgAndPrint('\nThis tool must be run from an ArcGIS Pro project template distributed with the Engineering Tools. Exiting!', 2)
    exit()

if CheckExtension('Spatial') == 'Available':
    CheckOutExtension('Spatial')
else:
    AddMsgAndPrint('\nSpatial Analyst Extension not enabled. Please enable Spatial Analyst from Project, Licensing, Configure licensing options. Exiting...', 2)
    exit()

### Input Parameters ###
project_contours = GetParameterAsText(0)
input_dam = GetParameterAsText(1)

### Locate Project GDB and Validate Input Dam ###
project_contours_path = Describe(project_contours).CatalogPath
if 'EngPro.gdb' in project_contours_path and 'Contour' in project_contours_path:
    project_gdb = project_contours_path[:project_contours_path.find('.gdb')+4]
else:
    AddMsgAndPrint('\nThe selected contours layer is not from an Engineering Tools project or is not compatible with this version of the toolbox. Exiting...', 2)
    exit()

#TODO: Do we also need to validate for only 1 feature?
if not int(GetCount(input_dam).getOutput(0)) > 0:
    AddMsgAndPrint('\nAt least one dam feature is required. Exiting...', 2)
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
dem_clip = path.join(scratch_gdb, 'DEM_Clip')
dem_minus = path.join(scratch_gdb, 'DEM_Minus')
dem_set_null = path.join(scratch_gdb, 'DEM_SetNull')
dem_set_null_u = path.join(scratch_gdb, 'DEM_SetNull_u') #TODO: ??
extent_raster = path.join(scratch_gdb, 'Extent_Raster')
pool_raster1 = path.join(scratch_gdb, 'Pool_Raster1')
pool_raster2 = path.join(scratch_gdb, 'Pool_Raster2')
pool_mask = path.join(scratch_gdb, 'Pool_Mask')
pool_polygon = path.join(scratch_gdb, 'Pool_Polygon')
volume_grid = path.join(scratch_gdb, 'Volume_Grid')
volume = path.join(scratch_gdb, 'Volume')

### ESRI Environment Settings ###
env.overwriteOutput = True
env.resamplingMethod = 'BILINEAR'
env.pyramid = 'PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP'
env.parallelProcessingFactor = '75%'

try:
    logBasicSettings(log_file_path, project_contours)

    # Copy User input to temp dam layer and add fields...
    CopyFeatures(input_dam, dams_temp)
    AddField(dams_temp, 'ID', 'LONG')
    AddField(dams_temp, 'MaxElev', 'DOUBLE')
    AddField(dams_temp, 'MinElev', 'DOUBLE')
    AddField(dams_temp, 'MeanElev', 'DOUBLE')
    AddField(dams_temp, 'LengthFt', 'DOUBLE')
    AddField(dams_temp, 'TopWidth', 'DOUBLE')
    AddField(dams_temp, 'BotWidth', 'DOUBLE')

    # Raster Volume Conversions for acre-feet
    #NOTE: DEM always in WGS84 UTM, xy meters, elevation feet
    # if units == 'Meter':
    convFactor = 0.000810714
    units = 'Meters'

    # Elevation Conversions
    # contFactor is for converting contours in feet to the zUnits values
    # Zfactor is for converting the zUnits to values to feet
    # elif zUnits == 'Feet':
    contFactor = 1              #feet to feet
    Zfactor = 1                 #feet to feet

    #TODO: Don't think this is necessary? could use CalculateField and !shape!.getLength()
    CalculateField(dams_temp, 'ID', '!OBJECTID!', 'PYTHON3')
    CalculateField(dams_temp, 'LengthFt', "!shape!.getLength('PLANAR', 'FeetInt')", 'PYTHON3')
    # with UpdateCursor(dams_temp) as cursor:
    #     for row in cursor:
    #         row.ID = row.OBJECTID
    #         if units == 'Feet':
    #             row.LengthFt = str(round(row.SHAPE_Length,1))
    #         else:
    #             row.LengthFt = str(round(row.SHAPE_Length * 3.280839896,1))
    #         cursor.updateRow(row)

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

    # SelectLayerByLocation(contour_lyr, 'INTERSECT', buffer6, '', 'NEW_SELECTION')
    # MakeFeatureLayer(contour_lyr, contour_lyr2)

    # with SearchCursor(contour_lyr2, '', '', 'CONTOUR', 'CONTOUR' + ' D') as cursor:
    #     row = cursor.next()
    #     hi_contour = row.CONTOUR

    # # Assign the pool elevation in the actual units of the DEM
    # poolElev = (hi_contour * contFactor)

    # AddMsgAndPrint(f"\nHighest closed contour is {hi_contour}")

    # # Permanent Datasets
    # output_pool_name = f"{project_name}_Pool_{hi_contour.replace('.','_dot_')}"
    # output_pool_path = path.join(project_fd, output_pool_name)

    # # Set unique name for dam and copy to final output
    # output_dams_name = f"{output_pool_name}_Dams"
    # output_dams_path = path.join(project_fd, output_dams_name)

    # removeMapLayers(map, [output_pool_name, output_dams_name])

    # CopyFeatures(dams_temp, output_dams_path)
    # MakeFeatureLayer(output_dams_path, dams_lyr)

    # # Dissolve and populate with plane elevation for raster processing
    # AddMsgAndPrint('\nCreating Pool and Volume Grid...')
    # Dissolve(extent_mask, pool_mask, '', '', 'MULTI_PART', 'DISSOLVE_LINES')
    # AddField(pool_mask, 'DemElev', 'DOUBLE')
    # CalculateField(pool_mask, 'DemElev', poolElev, 'PYTHON3')

    # # Convert to raster, clip DEM and create Pool polygon
    # MakeFeatureLayer(pool_mask, 'pool_mask')
    # FeatureToRaster('pool_mask', 'DemElev', extent_raster, dem_cell_size)

    # outMask = ExtractByMask(project_dem, extent_raster)
    # outMask.save(dem_clip)

    # # User specified max elevation value must be within min-max range of elevation values in clipped dem
    # demClipMaxElev = round(((float(GetRasterProperties(dem_clip, 'MAXIMUM').getOutput(0)))* Zfactor),1)
    # demClipMinElev = round(((float(GetRasterProperties(dem_clip, 'MINIMUM').getOutput(0)))* Zfactor),1)

    # # Check to make sure specified max elevation is within the range of elevation in clipped dem
    # if not demClipMinElev < hi_contour <= demClipMaxElev:
    #     AddMsgAndPrint('\n\tThe Pool Elevation Specified is not within the range', 2)
    #     AddMsgAndPrint('\tof the corresponding area of your input DEM.', 2)
    #     AddMsgAndPrint('\tPlease specify a value between ' + str(demClipMinElev) + ' and ' + str(demClipMaxElev) + '. Exiting...', 2)
    #     exit()

    # outMinus = Minus(extent_raster, dem_clip)
    # outMinus.save(dem_minus)

    # outNull = SetNull(dem_minus, dem_minus, 'Value <= 0')
    # outNull.save(dem_set_null)

    # # DEMsn is now a depth raster expressed in the original vertical units. Convert it to depths units that match the xy units.
    # # if units == 'Meters':
    # #     elif zUnits == 'Feet':
    # factor = 0.3048

    # outConv = Times(dem_set_null, factor)
    # outConv.save(dem_set_null_u)

    # outTimes = Times(dem_set_null_u, 0)
    # outTimes.save(pool_raster1)

    # outInt = Int(pool_raster1)
    # outInt.save(pool_raster2)

    # RasterToPolygon(pool_raster2, pool_polygon, 'NO_SIMPLIFY', 'VALUE')

    # # Dissolve results and add fields
    # Dissolve(pool_polygon, output_pool_path, '', '', 'MULTI_PART', 'DISSOLVE_LINES')
    # AddField(output_pool_path, 'ID', 'LONG')
    # AddField(output_pool_path, 'DemElev', 'DOUBLE')
    # AddField(output_pool_path, 'PoolElev', 'DOUBLE')
    # AddField(output_pool_path, 'PoolAcres', 'DOUBLE')
    # AddField(output_pool_path, 'RasterVol', 'DOUBLE')
    # AddField(output_pool_path, 'AcreFt', 'DOUBLE')

    # # Calculate Area, Raster Elevation and Pool Elevation
    # with UpdateCursor(output_pool_path) as cursor:
    #     for row in cursor:
    #         row.ID = row.OBJECTID
    #         row.DemElev = str(poolElev)
    #         row.PoolElev = str(hi_contour)
    #         if units == 'Meters':
    #             row.PoolAcres = str(round(row.Shape_Area / 4046.86,1))
    #         else:
    #             row.PoolAcres = str(round(row.Shape_Area / 43560,1))
    #         cursor.updateRow(row)

    #         AddMsgAndPrint('\nCalculating pool area and volume')

    #         volTimes = Times(dem_set_null_u, dem_cell_area)
    #         volTimes.save(volume_grid)

    #         outZonal = ZonalStatistics(output_pool_path, 'ID', volume_grid, 'SUM')
    #         outZonal.save(volume)

    #         # Get results and populate remaining fields
    #         row.RasterVol = str(round(float(GetRasterProperties(volume, 'MAXIMUM').getOutput(0)),1))
    #         row.AcreFt = str(round(float(row.RasterVol * convFactor),1))
    #         AddMsgAndPrint('\n\t\tPool Elevation: ' + str(row.PoolElev) + ' Feet')
    #         AddMsgAndPrint('\t\tPool Area: ' + str(row.PoolAcres) + ' Acres')
    #         AddMsgAndPrint('\t\tPool volume: ' + str(row.RasterVol) + ' Cubic ' + str(units))
    #         AddMsgAndPrint('\t\tPool volume: ' + str(row.AcreFt) + ' Acre Feet')
    #         cursor.updateRow(row)

    # # Retrieve attributes for dam and populate fields
    # Buffer(output_dams_path, buffer7, '3 Meters', 'RIGHT', 'ROUND', 'LIST', 'ID')
    # AddField(buffer7, 'ELEV', 'DOUBLE')
    # ZonalStatisticsAsTable(buffer7, 'ID', project_dem, dams_stats, 'NODATA', 'ALL')

    # with SearchCursor(dams_stats) as s_cursor:
    #     for s_row in s_cursor:
    #         # zonal stats doesnt generate 'Value' with the 9.3 geoprocessor in 10
    #         id = s_row.ID

    #         maxElev = s_row.MAX
    #         minElev = s_row.MIN
    #         meanElev = s_row.MEAN

    #         maxFt = round(float(maxElev * Zfactor),1)
    #         minFt = round(float(minElev * Zfactor),1)
    #         meanFt = round(float(meanElev * Zfactor),1)

    #         AddMsgAndPrint('\n\tCalculating properties of embankment ' + str(id))
    #         AddMsgAndPrint('\n\t\tMax Elevation: ' + str(maxFt) + ' Feet')
    #         AddMsgAndPrint('\t\tMin Elevation: ' + str(minFt) + ' Feet')
    #         AddMsgAndPrint('\t\tMean Elevation: ' + str(meanFt) + ' Feet')

    #         query = f"ID = {id}"
    #         SelectLayerByAttribute(dams_lyr, 'NEW_SELECTION', query)

    #         damHeight = int(maxFt - minFt)
    #         AddMsgAndPrint('\t\tMax Height: ' + str(damHeight) + ' Feet')

    #         whereclause = f"ID = {id}"
    #         with UpdateCursor(output_dams_path, whereclause) as u_cursor:
    #             for u_row in u_cursor:
    #                 damLength = u_row.LengthFt
    #                 u_row.LengthFt = round(damLength,1)
    #                 u_row.MaxElev = maxFt
    #                 u_row.MinElev = minFt
    #                 u_row.MeanElev = meanFt

    #                 AddMsgAndPrint('\t\tTotal Length: ' + str(u_row.LengthFt) + ' Feet')

    #                 # Assign Top and Bottom width from practice standards
    #                 AddMsgAndPrint('\nCalculating suggested top / bottom widths (Based on 3:1 Slope)')

    #                 if damHeight < 10:
    #                     topWidth = 6
    #                 elif damHeight >= 10 and damHeight < 15:
    #                     topWidth = 8
    #                 elif damHeight >= 15 and damHeight < 20:
    #                     topWidth = 10
    #                 elif damHeight >= 20 and damHeight < 25:
    #                     topWidth = 12
    #                 elif damHeight >= 25 and damHeight < 35:
    #                     topWidth = 14
    #                 elif damHeight >= 35:
    #                     topWidth = 15

    #                 bottomWidth = round(float(topWidth + 2 * (damHeight * 3))) # (bw + 2 * ss * depth) -- Assumes a 3:1 Side slope

    #                 u_row.TopWidth = topWidth
    #                 u_row.BotWidth = bottomWidth

    #                 AddMsgAndPrint('\n\t\tSuggested Top Width: ' + str(u_row.TopWidth) + ' Feet')
    #                 AddMsgAndPrint('\t\tSuggested Bottom Width: ' + str(u_row.BotWidth) + ' Feet')
    #                 u_cursor.updateRow(u_row)

    # ### Add Output to Map ###
    # SetParameterAsText(2, output_pool_path)
    # SetParameterAsText(3, output_dams_path)

    # ### Compact Project GDB ###
    # try:
    #     SetProgressorLabel('Compacting project geodatabase...')
    #     AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
    #     Compact(project_gdb)
    # except:
    #     pass

    AddMsgAndPrint('\nCreate Pool from Contours completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Create Pool from Contours'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Create Pool from Contours'), 2)

# finally:
#     emptyScratchGDB(scratch_gdb)

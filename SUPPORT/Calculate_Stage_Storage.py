from getpass import getuser
from os import path
from sys import argv, exit
from time import ctime

from arcpy import AlterAliasName, Describe, CheckExtension, CheckOutExtension, env, Exists, GetInstallInfo, GetParameterAsText, \
    GetParameter, ListFeatureClasses, SetParameterAsText, SetProgressorLabel
from arcpy.conversion import RasterToPolygon
from arcpy.ddd import SurfaceVolume
from arcpy.management import AddField, CalculateField, Compact, CopyRows, Delete, Dissolve, GetCount, GetRasterProperties, Merge
from arcpy.mp import ArcGISProject, Table
from arcpy.sa import ExtractByMask, Int, SetNull, Times

from utils import AddMsgAndPrint, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, project_dem, input_pool, max_elevation, increment, create_pools_layer):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Calculate State Storage\n')
        f.write(f"Pro Version: {GetInstallInfo()['Version']}\n")
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tProject DEM: {project_dem}\n")
        f.write(f"\tInput Pool Polygon: {input_pool}\n")
        f.write(f"\tMaximum Elevation: {max_elevation} Feet\n")
        f.write(f"\tAnalysis Increment: {increment} Feet\n")
        f.write(f"\tCreate Pool Polygons: {'Yes' if create_pools_layer else 'No'}\n")


def createPool(elevationValue, storageTxtFile):
    try:
        global convToFeetFactor,acreConversion,ftConversion,convToAcreFootFactor

        fcName =  ("Pool_" + str(round((elevationValue * convToFeetFactor),1))).replace(".","_")
        poolExit = path.join(project_fd, fcName)

        # Create new raster of only values below an elevation value by nullifying
        # cells above the desired elevation value.
        conStatement = "Value > " + str(elevationValue)
        valuesAboveElev = SetNull(tempDEM, tempDEM, conStatement)

        # Multiply every pixel by 0 and convert to integer for vectorizing
        zeroValues = Times(valuesAboveElev, 0)
        zeroInt = Int(zeroValues)

        # Convert to polygon and dissolve
        RasterToPolygon(zeroInt, temp_pool, 'NO_SIMPLIFY', 'VALUE')
        Dissolve(temp_pool, poolExit)

        AddField(poolExit, 'ELEV_FEET', 'DOUBLE')
        AddField(poolExit, 'DEM_ELEV', 'DOUBLE')
        AddField(poolExit, 'POOL_ACRES', 'DOUBLE')
        AddField(poolExit, 'POOL_SQFT', 'DOUBLE')
        AddField(poolExit, 'ACRE_FOOT', 'DOUBLE')
        AddField(poolExit, 'CUBIC_FEET', 'DOUBLE')
        AddField(poolExit, 'CUBIC_METERS', 'DOUBLE')

        # open storageCSV file and read the last line which should represent the last pool
        with open(storageTxtFile) as file:
            lines = file.readlines()

        area2D = float(lines[len(lines)-1].split(',')[4])
        volume = float(lines[len(lines)-1].split(',')[6])

        elevFeetCalc = round(elevationValue * convToFeetFactor,1)
        poolAcresCalc = round(area2D / acreConversion,1)
        poolSqftCalc = round(area2D / ftConversion,1)
        acreFootCalc = round(volume / convToAcreFootFactor,1)
        cubicMeterCalc = round(volume * convToCubicMeterFactor,1)
        cubicFeetCalc = round(volume * convToCubicFeetFactor,1)

        CalculateField(poolExit, 'ELEV_FEET', elevFeetCalc, 'PYTHON3')
        CalculateField(poolExit, 'DEM_ELEV', elevationValue, 'PYTHON3')
        CalculateField(poolExit, 'POOL_ACRES', poolAcresCalc, 'PYTHON3')
        CalculateField(poolExit, 'POOL_SQFT', poolSqftCalc, 'PYTHON3')
        CalculateField(poolExit, 'ACRE_FOOT', acreFootCalc, 'PYTHON3')
        CalculateField(poolExit, 'CUBIC_METERS', cubicMeterCalc, 'PYTHON3')
        CalculateField(poolExit, 'CUBIC_FEET', cubicFeetCalc, 'PYTHON3')

        AddMsgAndPrint("\n\tCreated " + fcName + ":")
        AddMsgAndPrint("\t\tElevation " + str(elevFeetCalc) + " Ft")
        AddMsgAndPrint("\t\tArea:   " + str(poolSqftCalc) + " Sq.Feet")
        AddMsgAndPrint("\t\tArea:   " + str(poolAcresCalc) + " Acres")
        AddMsgAndPrint("\t\tVolume: " + str(acreFootCalc) + " Ac. Foot")
        AddMsgAndPrint("\t\tVolume: " + str(cubicMeterCalc) + " Cubic Meters")
        AddMsgAndPrint("\t\tVolume: " + str(cubicFeetCalc) + " Cubic Feet")

        return True

    except:
        AddMsgAndPrint("\nFailed to Create Pool Polygon for elevation value: " + str(elevationValue),1)
        return False


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
if CheckExtension('3d') == 'Available':
    CheckOutExtension('3d')
else:
    AddMsgAndPrint('\n3D Analyst Extension not enabled. Please enable 3D Analyst from Project, Licensing, Configure licensing options. Exiting...', 2)
    exit()

### Input Parameters ###
project_dem = GetParameterAsText(0)
input_pool = GetParameterAsText(1)
max_elevation = float(GetParameterAsText(2))
increment = float(GetParameterAsText(3))
create_pools_layer = GetParameter(4)

### Locate Project GDB ###
project_dem_path = Describe(project_dem).CatalogPath
if 'EngPro.gdb' in project_dem_path and 'DEM' in project_dem_path:
    project_gdb = project_dem_path[:project_dem_path.find('.gdb')+4]
else:
    AddMsgAndPrint('\nThe selected DEM is not from an Engineering Tools project or is not compatible with this version of the toolbox. Exiting...', 2)
    exit()

### Validate Input Pool Count ###
if int(GetCount(input_pool).getOutput(0)) > 1:
    AddMsgAndPrint('\nThe input pool must be a single polygon feature. If using the project Watershed layer, select a single Subbasin. If using a different layer, dissolve it to create a single polygon, or select a single polygon and try again. Exiting...', 2)
    exit()

### Set Paths and Variables ###
support_dir = path.dirname(argv[0])
scratch_gdb = path.join(support_dir, 'Scratch.gdb')
project_workspace = path.dirname(project_gdb)
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")
project_fd = path.join(project_gdb, 'Layers')
input_pool_name = path.splitext(path.basename(input_pool))[0]
output_pool_name = f"{input_pool_name}_All_Pools"
output_pool_path = path.join(project_fd, output_pool_name)
storage_table_path = path.join(project_gdb, f"{input_pool_name}_StorageTable")
storage_table_csv = path.join(project_workspace, f"{input_pool_name}_Storage")
storage_table_temp = path.join(project_workspace, f"{input_pool_name}_StorageCSV.txt")
storage_table_view_name = 'Stage_Storage_Table'
temp_pool = path.join(scratch_gdb, 'Temp_Pool')

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

#TODO: Add this validation as Range in parameters
# # Exit if Elevation value is less than 1
# if maxElev < 1:
#     AddMsgAndPrint("\n\nMaximum Elevation Value must be greater than 0.....Exiting\n",2)
#     exit()

# # Exit if elevation increment is not greater than 0
# if userIncrement < 0.5:
#     AddMsgAndPrint("\n\nAnalysis Increment Value must be greater than or equal to 0.5.....Exiting\n",2)
#     exit()

# lookup dictionary to convert XY units to area.  Key = XY unit of DEM; Value = conversion factor to sq.meters
acreConversionDict = {'Meters':4046.8564224,'Meter':4046.8564224,'Foot':43560,'Foot_US':43560,'Feet':43560, 'Centimeter':40470000,'Inch':6273000}
ftConversionDict = {'Meters':0.092903,'Meter':0.092903,'Foot':1,'Foot_US':1,'Feet':1}
conversionToAcreFootDict = {'Meters':1233.48184,'Meter':1233.48184,'Foot':43560,'Foot_US':43560,'Feet':43560}  # to acre Foot
conversionToFtFactorDict = {'Meters':3.280839896,'Meter':3.280839896,'Foot':1,'Foot_US':1,'Feet':1, 'Centimeter':0.0328084, 'Centimeters':0.0328084, 'Inches':0.0833333, 'Inch':0.0833333}
conversionToCubicMetersDict = {'Meters':1,'Meter':1,'Foot':0.0283168,'Foot_US':0.0283168,'Feet':0.0283168}
conversionToCubicFeetDict = {'Meters':35.3147,'Meter':35.3147,'Foot':1,'Foot_US':1,'Feet':1}

# Assign Z-factor based on XY and Z units of DEM
# the following represents a matrix of possible z-Factors
# using different combination of xy and z units
# ----------------------------------------------------
#                      Z - Units
#                       Meter    Foot     Centimeter     Inch
#          Meter         1	    0.3048	    0.01	    0.0254
#  XY      Foot        3.28084	  1	      0.0328084	    0.083333
# Units    Centimeter   100	    30.48	     1	         2.54
#          Inch        39.3701	  12       0.393701	      1
# ---------------------------------------------------

unitLookUpDict = {'Meter':0,'Meters':0,'Foot':1,'Foot_US':1,'Feet':1,'Centimeter':2,'Centimeters':2,'Inch':3,'Inches':3}
zFactorList = [[1,0.304800609601219,0.01,0.0254],
                [3.28084,1,0.0328084,0.083333],
                [100,30.4800609601219,1.0,2.54],
                [39.3701,12,0.393701,1.0]]

acreConversion = acreConversionDict.get(linearUnits)
ftConversion = ftConversionDict.get(linearUnits)
convToAcreFootFactor = conversionToAcreFootDict.get(linearUnits)
convToCubicMeterFactor = conversionToCubicMetersDict.get(linearUnits)
convToCubicFeetFactor = conversionToCubicFeetDict.get(linearUnits)

# if zUnits were left blank than assume Z-values are the same as XY units.
if not len(zUnits) > 0:
    zUnits = linearUnits

AddMsgAndPrint("\nGathering information about DEM: " + path.basename(inputDEM))


# This will be used to convert elevation values to Feet.
zFactor = zFactorList[unitLookUpDict.get(zUnits)][unitLookUpDict.get('Feet')]
convToFeetFactor = conversionToFtFactorDict.get(zUnits)

AddMsgAndPrint("\tProjection Name: " + demSR.name)
AddMsgAndPrint("\tXY Linear Units: " + linearUnits)
AddMsgAndPrint("\tElevation Values (Z): " + zUnits)
AddMsgAndPrint("\tCell Size: " + str(demCellSize) + " x " + str(demCellSize) + " " + linearUnits)


try:
    removeMapLayers(map, [output_pool_name, storage_table_view_name])
    logBasicSettings(log_file_path, project_dem, input_pool, max_elevation, increment, create_pools_layer)

    # ClipDEM to User's Pool or Watershed
    tempDEM = ExtractByMask(project_dem, input_pool)

    # User specified max elevation value must be within min-max elevation range of clipped dem
    demTempMaxElev = round(float(GetRasterProperties(tempDEM, "MAXIMUM").getOutput(0)))
    demTempMinElev = round(float(GetRasterProperties(tempDEM, "MINIMUM").getOutput(0)))

    # convert max elev value and increment(FT) to match the native Z-units of input DEM
    maxElevConverted = max_elevation * zFactor
    # increment = userIncrement * zFactor #NOTE: increment in feet, DEM elevation units feet

    # if maxElevConverted is not within elevation range exit.
    if not demTempMinElev < maxElevConverted <= demTempMaxElev:

        AddMsgAndPrint("\nThe Max Elevation value specified is not within the elevation range of your watershed-pool area",2)
        AddMsgAndPrint("Elevation Range of your watershed-pool polygon is:",2)
        AddMsgAndPrint("\tMaximum Elevation: " + str(demTempMaxElev) + " " + zUnits + " ---- " + str(round(float(demTempMaxElev*convToFeetFactor),1)) + " Feet")
        AddMsgAndPrint("\tMinimum Elevation: " + str(demTempMinElev) + " " + zUnits + " ---- " + str(round(float(demTempMinElev*convToFeetFactor),1)) + " Feet")
        AddMsgAndPrint("Please enter an elevation value within this range.....Exiting!\n\n",2)
        exit()

    else:
        AddMsgAndPrint("\nSuccessfully clipped DEM to " + path.basename(inPool))

    # Set Elevations to calculate volume and surface area
    try:
        i = 1
        while maxElevConverted > demTempMinElev:

            if i == 1:
                AddMsgAndPrint("\nDeriving Surface Volume for elevation values between " + str(round(demTempMinElev * convToFeetFactor,1)) + " and " + str(maxElev) + " FT every " + str(userIncrement) + " FT")
                numOfPoolsToCreate = str(int(round((maxElevConverted - demTempMinElev)/increment)))
                AddMsgAndPrint(numOfPoolsToCreate + " Pool Feature Classes will be created")
                i += 1

            SurfaceVolume(tempDEM, storage_table_temp, "BELOW", maxElevConverted, "1")

            if create_pools_layer:
                if not createPool(maxElevConverted, storage_table_temp):
                    AddMsgAndPrint("\nFailed To Create Pool at elevation: " + str(maxElevConverted),2)
                    exit()

            maxElevConverted = maxElevConverted - increment

    except:
        exit()

    Delete(tempDEM)

    # Convert StorageCSV to FGDB Table and populate fields.
    CopyRows(storage_table_temp, storage_table_path)
    AlterAliasName(storage_table_path, storage_table_view_name)

    AddField(storage_table_path, 'ELEV_FEET', 'DOUBLE', '5', '1')
    AddField(storage_table_path, 'DEM_ELEV', 'DOUBLE')
    AddField(storage_table_path, 'POOL_ACRES', 'DOUBLE')
    AddField(storage_table_path, 'POOL_SQFT', 'DOUBLE')
    AddField(storage_table_path, 'ACRE_FOOT', 'DOUBLE')
    AddField(storage_table_path, 'CUBIC_FEET', 'DOUBLE')
    AddField(storage_table_path, 'CUBIC_METERS', 'DOUBLE')

    demElevCalc = 'round(!Plane_Height!)'
    elevFeetCalc = 'round(!Plane_Height! *' + str(convToFeetFactor) + ',1)'
    poolAcresCalc = 'round(!Area_2D! /' + str(acreConversion) + ',1)'
    poolSqftCalc = 'round(!Area_2D! /' + str(ftConversion) + ',1)'
    acreFootCalc = 'round(!Volume! /' + str(convToAcreFootFactor) + ',1)'
    cubicMeterCalc = 'round(!Volume! *' + str(convToCubicMeterFactor) + ',1)'
    cubicFeetCalc = 'round(!Volume! *' + str(convToCubicFeetFactor) + ',1)'

    CalculateField(storage_table_path, 'DEM_ELEV', demElevCalc,  'PYTHON3')
    CalculateField(storage_table_path, 'ELEV_FEET', elevFeetCalc, 'PYTHON3')
    CalculateField(storage_table_path, 'POOL_ACRES', poolAcresCalc, 'PYTHON3')
    CalculateField(storage_table_path, 'POOL_SQFT', poolSqftCalc, 'PYTHON3')
    CalculateField(storage_table_path, 'ACRE_FOOT', acreFootCalc, 'PYTHON3')
    CalculateField(storage_table_path, 'CUBIC_METERS', cubicMeterCalc,  'PYTHON3')
    CalculateField(storage_table_path, 'CUBIC_FEET', cubicFeetCalc,  'PYTHON3')

    AddMsgAndPrint('\nSuccessfully Created ' + path.basename(storage_table_path))

    if Exists(storage_table_temp):
        Delete(storage_table_temp)

    # Merge all Pool Polygons together
    if create_pools_layer:
        poolFCs = ListFeatureClasses('Pool_*')
        Merge(poolFCs, output_pool_path)
        AddMsgAndPrint('\nSuccessfully Merged Pools into ' + path.basename(output_pool_path))
        SetParameterAsText(7, output_pool_path)

    tab = Table(storage_table_path)
    # TODO: use SetParameterAsText derived output instead?
    # # Add Storage Table to ArcGIS Pro Map
    # for maps in aprx.listMaps():
    #     for lyr in maps.listLayers():
    #         if lyr.name in (demName, Describe(input_pool).name):
    #             maps.addTable(tab)
    #             break

    ### Compact Project GDB ###
    try:
        SetProgressorLabel('Compacting project geodatabase...')
        AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
        Compact(project_gdb)
    except:
        pass

    AddMsgAndPrint('\nCCalculate Stage Storage completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Calculate Stage Storage'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Calculate Stage Storage'), 2)

# finally:
#     emptyScratchGDB(scratch_gdb)

from getpass import getuser
from os import path
from sys import exit
from time import ctime

from arcpy import CheckExtension, CheckOutExtension, Describe, env, Exists, GetInstallInfo, GetParameter, \
    GetParameterAsText, SetParameterAsText, ValidateTableName
from arcpy.da import InsertCursor, SearchCursor
from arcpy.ddd import AddSurfaceInformation
from arcpy.management import AddXY, CalculateField, Compact, CopyFeatures, CreateFeatureDataset, CreateFileGDB, DeleteField

from utils import AddMsgAndPrint, deleteScratchLayers, errorMsg


def logBasicSettings():    
    with open(textFilePath, 'a+') as f:
        f.write('\n##################################################################\n')
        f.write('Executing Change Point Coordinates Tool\n')
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write(f"ArcGIS Version: {str(GetInstallInfo()['Version'])}\n")    
        f.write('User Parameters:\n')
        f.write(f"\tWorkspace: {userWorkspace}\n")
        f.write(f"\tInput Dem: {Describe(inputDEM).CatalogPath}\n")
        f.write(f"\tElevation Z-units: {zUnits}\n")
        f.write(f"\tCoordinate System: {outCS}\n")


### ESRI Environment settings
env.overwriteOutput = True
env.geographicTransformations = 'WGS_1984_(ITRF00)_To_NAD_1983'
env.resamplingMethod = 'BILINEAR'
env.pyramid = 'PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP'

### Input Parameters
userWorkspace = GetParameterAsText(0)
inputPoints = GetParameterAsText(1)
inputDEM = GetParameterAsText(2)
zUnits = GetParameterAsText(3)
outCS = GetParameterAsText(4)
text = GetParameter(5)

try:
    # Check out 3D and SA licenses
    if CheckExtension('3D') == 'Available':
        CheckOutExtension('3D')
    else:
        AddMsgAndPrint('\n3D analyst extension is not enabled. Please enable 3D Analyst from the Tools/Extensions menu. Exiting...\n', 2)
        exit()

    # Directory Paths
    workspace_name = path.basename(userWorkspace).replace(' ','_')
    watershedGDB_name = f"{workspace_name}_EngTools.gdb"
    watershedGDB_path = path.join(userWorkspace, watershedGDB_name)
    watershedFD = path.join(watershedGDB_path, 'Layers')
    projectName = ValidateTableName(workspace_name)

    # record basic user inputs and settings to log file for future purposes
    textFilePath = path.join(userWorkspace, f"{workspace_name}_EngTools.txt")
    logBasicSettings()

    # Capture User environments
    tempCoordSys = env.outputCoordinateSystem

    # Set the following environments
    env.outputCoordinateSystem = outCS

    # Permanent Datasets
    outPoints = path.join(userWorkspace, f"{projectName}_XYZ_new_coordinates.shp") #NOTE: should these be shapefiles??
    outTxt = path.join(userWorkspace, f"{projectName}_XYZ_new_coordinates.txt")
    # Must Have a unique name for output -- Append a unique digit to output if required
    x = 1
    while x > 0:
        if Exists(outPoints):
            outPoints = path.join(userWorkspace, f"{projectName}_XYZ_new_coordinates{str(x)}.shp")
            outTxt = path.join(userWorkspace, f"{projectName}_XYZ_new_coordinates{str(x)}.txt")
            x += 1
        else:
            x = 0
    
    outPointsLyr = path.basename(outPoints)

    # Temp Datasets
    pointsProj = path.join(watershedGDB_path, 'pointsProj')

    # Check DEM Coordinate System and Linear Units
    AddMsgAndPrint(f"\nGathering information about DEM: {path.basename(inputDEM)}\n", textFilePath=textFilePath)
    desc = Describe(inputDEM)
    sr = desc.SpatialReference
    units = sr.LinearUnitName
    cellSize = desc.MeanCellWidth
    
    if units == 'Meter':
        units = 'Meters'
    elif units == 'Foot':
        units = 'Feet'
    elif units == 'Foot_US':
        units = 'Feet'

    # Coordinate System must be a Projected type in order to continue.
    # zUnits will determine Zfactor for the conversion of elevation values to feet.
    
    if sr.Type == 'Projected':
        if zUnits == 'Meters':
            Zfactor = 3.280839896       # 3.28 feet in a meter
        elif zUnits == 'Centimeters':   # 0.033 feet in a centimeter
            Zfactor = 0.03280839896
        elif zUnits == 'Inches':        # 0.083 feet in an inch
            Zfactor = 0.0833333
        # zUnits must be feet; no more choices       
        else:
            Zfactor = 1                 
        AddMsgAndPrint(f"\tProjection Name: {sr.Name}", textFilePath=textFilePath)
        AddMsgAndPrint(f"\tXY Linear Units: {units}", textFilePath=textFilePath)
        AddMsgAndPrint(f"\tElevation Values (Z): {zUnits}", textFilePath=textFilePath) 
        AddMsgAndPrint(f"\tCell Size: {str(desc.MeanCellWidth)} x {str(desc.MeanCellHeight)} {units}", textFilePath=textFilePath)
    else:
        AddMsgAndPrint(f"\n\n\t{path.basename(inputDEM)} is NOT in a projected Coordinate System. Exiting...", 2, textFilePath)
        exit()
                      
    # Create Watershed FGDB and feature dataset if it doesn't exist
    if not Exists(watershedGDB_path):
        CreateFileGDB(userWorkspace, watershedGDB_name)
        CreateFeatureDataset(watershedGDB_path, 'Layers', sr)
        AddMsgAndPrint(f"\nSuccessfully created File Geodatabase: {watershedGDB_name}", textFilePath=textFilePath)

    # if GDB already existed but feature dataset doesn't
    if not Exists(watershedFD):
        CreateFeatureDataset(watershedGDB_path, 'Layers', sr)

    # Copy Features will use the spatial reference of the geoprocessing environment that has been set
    # Transformation between WGS84 and NAD83 will default to WGS_1984_(ITRF00)_To_NAD_1983, per env settings
    # No other areas of transformation can be used - document this in help and manuals
    CopyFeatures(inputPoints, pointsProj)

    # Recalculate X,Y values in output table
    AddXY(pointsProj)
    
    # Update Elevation values in feet
    AddSurfaceInformation(pointsProj, inputDEM, 'Z', '', '', Zfactor)
    expression = 'round(!Z!,1)'
    CalculateField(pointsProj, 'POINT_Z', expression, 'PYTHON3')

    # Clean up extra fields
    DeleteField(pointsProj, 'POINT_M')
    DeleteField(pointsProj, 'Z')

    # Create final output
    CopyFeatures(pointsProj, outPoints)

    # Create Txt file if selected and write attributes of station points
    if text == True:
        AddMsgAndPrint('Creating Output text file:\n', textFilePath=textFilePath)
        AddMsgAndPrint(f"\t{str(outTxt)}\n", textFilePath=textFilePath)

        with open(outTxt, 'w') as t:
            t.write('ID, STATION, X, Y, Z')
        
        with SearchCursor(outPoints, '', '', 'STATION', 'STATION' + ' A') as rows:
            with InsertCursor(outTxt) as txtRows:
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

    # Restore environments
    env.outputCoordinateSystem = tempCoordSys

    # Add layer to map
    AddMsgAndPrint('Adding layer to map\n', textFilePath=textFilePath)
    SetParameterAsText(6, outPoints)

    # Delete Temp Layers 
    AddMsgAndPrint('Deleting temporary files...\n', textFilePath=textFilePath)
    deleteScratchLayers([pointsProj])

    try:
        Compact(watershedGDB_path)
        AddMsgAndPrint(f"\nSuccessfully Compacted FGDB: {path.basename(watershedGDB_path)}", textFilePath=textFilePath)    
    except:
        pass

    AddMsgAndPrint('Processing Complete!\n', textFilePath=textFilePath)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Change Point Coordinates'), 2, textFilePath)
    except:
        AddMsgAndPrint(errorMsg('Change Point Coordinates'), 2) 

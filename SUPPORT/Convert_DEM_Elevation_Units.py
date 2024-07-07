from getpass import getuser
from os import path
from sys import exit
from time import ctime

from arcpy import CheckExtension, CheckOutExtension, Describe, env, GetInstallInfo, GetParameter, GetParameterAsText
from arcpy.management import Compact, Delete, GetCount
from arcpy.sa import ExtractByMask, Times

from utils import AddMsgAndPrint, errorMsg


def logBasicSettings():
    with open(textFilePath, 'a+') as f:
        f.write('\n##################################################################\n')
        f.write('Executing Convert DEM Elevation Units Tool\n')
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write(f"ArcGIS Version: {str(GetInstallInfo()['Version'])}\n")    
        f.write('User Parameters:\n')
        f.write(f"\tWorkspace: {userWorkspace}\n")
        f.write("\tInput Dem: " + inputDEM + "\n")
        f.write("\tInput Elevation Z-units: " + zUnits + "\n")
        f.write("\tOutput Elevation Z-units: " + outzUnits + "\n")


### ESRI Environment settings
env.overwriteOutput = True
env.geographicTransformations = 'WGS_1984_(ITRF00)_To_NAD_1983'
env.resamplingMethod = 'BILINEAR'
env.pyramid = 'PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP'

### Input Parameters
inputDEM = GetParameterAsText(0)
zUnits = GetParameterAsText(1)
demClipped = GetParameter(2)
inMask = GetParameterAsText(3)
outzUnits = GetParameterAsText(4)
outputDEM = GetParameterAsText(5)

try:
    # Check out SA license or exit if not available
    if CheckExtension('Spatial') == 'Available':
        CheckOutExtension('Spatial')
    else:
        AddMsgAndPrint('\n\tSpatial Analyst Extension not enabled. Please enable Spatial Analyst from the Tools/Extensions menu. Exiting...\n', 2)
        exit()

    # Directory Paths
    userWorkspace = path.dirname(path.realpath(outputDEM))
    demName = path.splitext(path.basename(outputDEM))[0]
    DEMtemp = path.join(userWorkspace, 'DEMtemp')
    textFilePath = path.join(userWorkspace, f"{path.basename(userWorkspace).replace(' ','_')}_EngTools.txt")

    # record basic user inputs and settings to log file for future purposes
    logBasicSettings()

    # Check if Dem is Clipped was selected
    if demClipped == False:
        Clip = True
    else:
        Clip = False

    # Check if Mask was provided    
    if inMask:
        Mask = True
    else:
        Mask = False

    if Clip == False:
        if Mask == True:
            AddMsgAndPrint('\n\n"My DEM is Already clipped" was selected AND a mask was provided.', 2, textFilePath)
            AddMsgAndPrint('\nYou must choose one or the other. Select one option and try again. Exiting...\n', 2, textFilePath)
            exit()

    elif Clip == True:
        if Mask == False:
            AddMsgAndPrint('\n\n"My DEM is Already clipped" was not selected NOR was a mask provided.', 2, textFilePath)
            AddMsgAndPrint('\nYou must choose one or the other. Select one option and try again. Exiting...\n', 2, textFilePath)
            exit()

    # Capture Default Environments
    tempExtent = env.extent
    tempMask = env.mask
    tempSnapRaster = env.snapRaster
    tempCellSize = env.cellSize
    tempCoordSys = env.outputCoordinateSystem

    # Retrieve Spatial Reference and units from DEM
    desc = Describe(inputDEM)
    sr = desc.SpatialReference
    cellSize = desc.MeanCellWidth
    units = sr.LinearUnitName

    AddMsgAndPrint(f"\nGathering information about Input DEM: {path.basename(inputDEM)}\n")    

    # Coordinate System must be a Projected type in order to continue.
    # zUnits and outzUnits will determine conversion factor for the creation of a new DEM.
    # Conversion factors are now set for use with the Times function, as of 10/16/2019.

    if sr.Type == 'Projected':
        if zUnits == 'Meters':
            if outzUnits == 'Feet':
                convFactor = 3.280839896
            if outzUnits == 'Inches':
                convFactor = 39.3701
            if outzUnits == 'Centimeters':
                convFactor = 100
            if outzUnits == 'Meters':
                AddMsgAndPrint('\n\n\tSelected output Z-Units are the same as input Z-Units. Exiting...', 2, textFilePath)
                exit(0)
        elif zUnits == 'Centimeters':
            if outzUnits == 'Feet':
                convFactor = 0.03280839896
            if outzUnits == 'Inches':
                convFactor = 0.393701
            if outzUnits == 'Meters':
                convFactor = 0.01
            if outzUnits == 'Centimeters':
                AddMsgAndPrint('\n\n\tSelected output Z-Units are the same as input Z-Units. Exiting...', 2, textFilePath)
                exit(0)            
        elif zUnits == 'Feet':
            if outzUnits == 'Centimeters':
                convFactor = 30.48
            if outzUnits == 'Inches':
                convFactor = 12
            if outzUnits == 'Meters':
                convFactor = 0.3048
            if outzUnits == 'Feet':
                AddMsgAndPrint('\n\n\tSelected output Z-Units are the same as input Z-Units. Exiting...', 2, textFilePath)
                exit(0)
        elif zUnits == 'Inches':
            if outzUnits == 'Centimeters':
                convFactor = 2.54
            if outzUnits == 'Feet':
                convFactor = 0.0833333 
            if outzUnits == 'Meters':
                convFactor = 0.0254
            if outzUnits == 'Inches':
                AddMsgAndPrint('\n\n\tSelected output Z-Units are the same as input Z-Units. Exiting...', 2, textFilePath)
                exit(0)                
    else:
        AddMsgAndPrint(f"\n\n\t{path.basename(inputDEM)} is NOT in a projected Coordinate System. Exiting...", 2)
        exit(0)

    AddMsgAndPrint(f"\tInput Projection Name: {sr.Name}", textFilePath=textFilePath)
    AddMsgAndPrint(f"\tXY Linear Units: {units}")
    AddMsgAndPrint(f"\tCell Size: {str(desc.MeanCellWidth)} x {str(desc.MeanCellHeight)} {units}\n", textFilePath=textFilePath)
    AddMsgAndPrint(f"\tInput Elevation Values (Z): {zUnits}", textFilePath=textFilePath)
    AddMsgAndPrint(f"\tOuput Elevation Values (Z): {outzUnits}", textFilePath=textFilePath) 
    AddMsgAndPrint(f"\tConversion Factor: {str(float(convFactor))}", textFilePath=textFilePath)

    ### ESRI Environment settings
    env.extent = 'MINOF'
    env.cellSize = cellSize
    env.mask = ''
    env.snapRaster = ''
    env.outputCoordinateSystem = sr
    
    # Clip DEM to AOI if DEM not already clipped
    if Clip:
        clippedDEM = ExtractByMask(inputDEM, inMask)
        clippedDEM.save(DEMtemp)
        AddMsgAndPrint(f"\nSuccessully Clipped {path.basename(inputDEM)} to area of interest...", textFilePath=textFilePath)
        inputDEM = DEMtemp

    outTimes = Times(inputDEM, convFactor)
    outTimes.save(outputDEM)
    AddMsgAndPrint(f"\nSuccessfully converted {path.basename(inputDEM)} from {str(zUnits)} to {str(outzUnits)}\n", textFilePath=textFilePath)

    # Delete Optional Temp Output
    if Clip == True:
        AddMsgAndPrint('\nDeleting intermediate data...')
        try:
            Delete(DEMtemp)
        except:
            pass

    # Compact FGDB
    # try:
    #     Compact(watershedGDB_path) #NOTE: this gdb not defined
    #     AddMsgAndPrint(f"\nSuccessfully Compacted FGDB: {path.basename(watershedGDB_path)}")    
    # except:
    #     pass

    # Restore environment settings
    env.extent = tempExtent
    env.mask = tempMask
    env.snapRaster = tempSnapRaster
    env.outputCoordinateSystem = tempCoordSys

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Convert DEM Elevation Units'), 2, textFilePath)
    except:
        AddMsgAndPrint(errorMsg('Convert DEM Elevation Units'), 2) 

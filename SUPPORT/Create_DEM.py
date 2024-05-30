from getpass import getuser
from os import path
from sys import argv
from time import ctime

from arcpy import CheckExtension, CheckOutExtension, Describe, env, Exists, GetParameterAsText, ListDatasets, \
    SetParameterAsText, SetProgressorLabel
from arcpy.analysis import Buffer
from arcpy.management import Clip, Compact, CopyRaster, Delete, MosaicToNewRaster, Project, ProjectRaster
from arcpy.mp import ArcGISProject
from arcpy.da import Editor
from arcpy.sa import ExtractByMask

from utils import AddMsgAndPrint, deleteScratchLayers, errorMsg, removeMapLayers


def logBasicSettings(textFilePath, userWorkspace, inputDEMs, zUnits):
    with open(textFilePath,'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Create Site DEM\n')
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tWorkspace: {userWorkspace}\n")
        f.write(f"\tInput DEMs: {str(inputDEMs)}\n")
        if len (zUnits) > 0:
            f.write(f"\tElevation Z-units: {zUnits}\n")
        else:
            f.write('\tElevation Z-units: NOT SPECIFIED\n')


### Initial Tool Validation ###
try:
    aprx = ArcGISProject('CURRENT')
    map = aprx.listMaps()[0] #TODO: Map name??
except:
    AddMsgAndPrint('This tool must be run from an ArcGIS Pro project that was developed from the template distributed with this toolbox. Exiting!', 2)
    exit()

if CheckExtension('Spatial') == 'Available':
    CheckOutExtension('Spatial')
else:
    AddMsgAndPrint('Spatial Analyst Extension not enabled. Please enable Spatial Analyst from Project, Licensing, Configure licensing options. Exiting...', 2)
    exit()


### ESRI Environment Settings ###
env.overwriteOutput = True
env.resamplingMethod = 'BILINEAR'
env.pyramid = 'PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP'


### Input Parameters ###
projectAOI = GetParameterAsText(0)
demFormat = GetParameterAsText(1)
inputDEMs = GetParameterAsText(2).split(';')
DEMcount = len(inputDEMs)
nrcsService = GetParameterAsText(3)
externalService = GetParameterAsText(4)
sourceCellsize = GetParameterAsText(5)
zUnits = GetParameterAsText(6)
demSR = GetParameterAsText(7)
cluSR = GetParameterAsText(8)
transform = GetParameterAsText(9)


try:
    #### Set base path
    sourceCLU_path = Describe(projectAOI).CatalogPath
    # if sourceCLU_path.find('.gdb') > 0 and sourceCLU_path.find('Determinations') > 0 and sourceCLU_path.find('Site_CLU') > 0:
    basedataGDB_path = sourceCLU_path[:sourceCLU_path.find('.gdb')+4]
    # else:
    #     AddMsgAndPrint('\nSelected Site CLU layer is not from a Determinations project folder. Exiting...', 2)
    #     exit()


    #### Do not run if an unsaved edits exist in the target workspace
    # Pro opens an edit session when any edit has been made and stays open until edits are committed with Save Edits.
    # Check for uncommitted edits and exit if found, giving the user a message directing them to Save or Discard them.
    workspace = basedataGDB_path
    edit = Editor(workspace)
    if edit.isEditing:
        AddMsgAndPrint('\nYou have an active edit session. Please Save or Discard edits and run this tool again. Exiting...', 2)
        exit()


    #### Define Variables
    scratchGDB = path.join(path.dirname(argv[0]), 'Scratch.gdb')
    referenceLayers = path.join(path.dirname(path.dirname(argv[0])), 'Reference_Layers')
    basedataGDB_name = path.basename(basedataGDB_path)
    basedataFD_name = 'Layers'
    basedataFD = path.join(basedataGDB_path, basedataFD_name)
    userWorkspace = path.dirname(basedataGDB_path)
    projectName = path.basename(userWorkspace).replace(' ', '_')
    projectDEM = path.join(basedataGDB_path, 'Site_DEM')
    projectAOI_buffer = path.join(scratchGDB, 'AOI_Buffer')
    bufferDist = '500 Feet'
    wgs_AOI = path.join(scratchGDB, 'AOI_WGS84')
    WGS84_DEM = path.join(scratchGDB, 'WGS84_DEM')
    tempDEM = path.join(scratchGDB, 'tempDEM')


    # If NRCS Image Service selected, set path to lyrx file
    if '0.5m' in nrcsService:
        sourceService = path.join(referenceLayers, 'NRCS Bare Earth 0.5m.lyrx')
    elif '1m' in nrcsService:
        sourceService = path.join(referenceLayers, 'NRCS Bare Earth 1m.lyrx')
    elif '2m' in nrcsService:
        sourceService = path.join(referenceLayers, 'NRCS Bare Earth 2m.lyrx')
    elif '3m' in nrcsService:
        sourceService = path.join(referenceLayers, 'NRCS Bare Earth 3m.lyrx')
    elif externalService != '':
        sourceService = externalService

    # Temp layers list for cleanup at the start and at the end
    tempLayers = [projectAOI_buffer, wgs_AOI, WGS84_DEM, tempDEM]
    AddMsgAndPrint('Deleting Temp layers...')
    SetProgressorLabel('Deleting Temp layers...')
    deleteScratchLayers(tempLayers)


    #### Set up log file path and start logging
    textFilePath = path.join(userWorkspace, f"{projectName}_log.txt")
    logBasicSettings(textFilePath, userWorkspace, inputDEMs, zUnits)


    #### Create the projectAOI and projectAOI_B layers based on the choice selected by user input
    AddMsgAndPrint('\nBuffering selected extent...', textFilePath=textFilePath)
    SetProgressorLabel('Buffering selected extent...')
    Buffer(projectAOI, projectAOI_buffer, bufferDist, 'FULL', '', 'ALL', '')


    #### Remove existing project DEM and Hillshade if present in map
    AddMsgAndPrint('\nRemoving layers from project maps, if present...', textFilePath=textFilePath)
    SetProgressorLabel('Removing layers from project maps, if present...')
    removeMapLayers(map, ['Site_DEM'])


    #### Process the input DEMs
    AddMsgAndPrint('\nProcessing the input DEM(s)...', textFilePath=textFilePath)
    SetProgressorLabel('Processing the input DEM(s)...')

    # Extract and process the DEM if it's an image service
    if demFormat in ['NRCS Image Service', 'External Image Service']:
        if sourceCellsize == '':
            AddMsgAndPrint('\nAn output DEM cell size was not specified. Exiting...', 2, textFilePath)
            exit()
        else:
            AddMsgAndPrint('\nProjecting AOI to match input DEM...', textFilePath=textFilePath)
            SetProgressorLabel('Projecting AOI to match input DEM...')
            wgs_CS = demSR
            Project(projectAOI, wgs_AOI, wgs_CS)
            
            AddMsgAndPrint('\nDownloading DEM data...', textFilePath=textFilePath)
            SetProgressorLabel('Downloading DEM data...')
            aoi_ext = Describe(wgs_AOI).extent
            xMin = aoi_ext.XMin
            yMin = aoi_ext.YMin
            xMax = aoi_ext.XMax
            yMax = aoi_ext.YMax
            clip_ext = f"{str(xMin)} {str(yMin)} {str(xMax)} {str(yMax)}"
            Clip(sourceService, clip_ext, WGS84_DEM, '', '', '', 'NO_MAINTAIN_EXTENT')

            AddMsgAndPrint('\nProjecting downloaded DEM...', textFilePath=textFilePath)
            SetProgressorLabel('Projecting downloaded DEM...')
            ProjectRaster(WGS84_DEM, tempDEM, cluSR, 'BILINEAR', sourceCellsize)

    # Else, extract the local file DEMs
    else:
        # Manage spatial references
        env.outputCoordinateSystem = cluSR
        if transform != '':
            env.geographicTransformations = transform
        
        # Clip out the DEMs that were entered
        AddMsgAndPrint('\tExtracting input DEM(s)...', textFilePath=textFilePath)
        SetProgressorLabel('Extracting input DEM(s)...')
        x = 0
        DEMlist = []
        while x < DEMcount:
            raster = inputDEMs[x].replace("'", '')
            desc = Describe(raster)
            raster_path = desc.CatalogPath
            sr = desc.SpatialReference
            units = sr.LinearUnitName
            if units == 'Meter':
                units = 'Meters'
            elif units == 'Foot':
                units = 'Feet'
            elif units == 'Foot_US':
                units = 'Feet'
            else:
                AddMsgAndPrint('\nHorizontal units of one or more input DEMs do not appear to be feet or meters! Exiting...', 2, textFilePath)
                exit()
            outClip = f"{tempDEM}_{str(x)}"
            try:
                extractedDEM = ExtractByMask(raster_path, projectAOI)
                extractedDEM.save(outClip)
            except:
                AddMsgAndPrint('\nOne or more input DEMs may have a problem! Please verify that the input DEMs cover the tract area and try to run again. Exiting...', 2, textFilePath)
                exit()
            if x == 0:
                mosaicInputs = str(outClip)
            else:
                mosaicInputs = f"{mosaicInputs};{str(outClip)}"
            DEMlist.append(str(outClip))
            x += 1

        cellsize = 0
        # Determine largest cell size
        for raster in DEMlist:
            desc = Describe(raster)
            sr = desc.SpatialReference
            cellwidth = desc.MeanCellWidth
            if cellwidth > cellsize:
                cellsize = cellwidth

        # Merge the DEMs
        if DEMcount > 1:
            AddMsgAndPrint('\nMerging multiple input DEM(s)...', textFilePath=textFilePath)
            SetProgressorLabel('Merging multiple input DEM(s)...')
            MosaicToNewRaster(mosaicInputs, scratchGDB, 'tempDEM', '#', '32_BIT_FLOAT', cellsize, '1', 'MEAN', '#')

        # Else just convert the one input DEM to become the tempDEM
        else:
            AddMsgAndPrint('\nOnly one input DEM detected. Carrying extract forward for final DEM processing...', textFilePath=textFilePath)
            firstDEM = DEMlist[0]
            CopyRaster(firstDEM, tempDEM)

        # Delete clippedDEM files
        AddMsgAndPrint('\nDeleting temp DEM file(s)...', textFilePath=textFilePath)
        SetProgressorLabel('Deleting temp DEM file(s)...')
        for raster in DEMlist:
            Delete(raster)

        
    # Gather info on the final temp DEM
    desc = Describe(tempDEM)
    sr = desc.SpatialReference
    # linear units should now be meters, since outputs were UTM zone specified
    units = sr.LinearUnitName

    if sr.Type == 'Projected':
        if zUnits == 'Meters':
            Zfactor = 1
        elif zUnits == 'Meter':
            Zfactor = 1
        elif zUnits == 'Feet':
            Zfactor = 0.3048
        elif zUnits == 'Inches':
            Zfactor = 0.0254
        elif zUnits == 'Centimeters':
            Zfactor = 0.01
        else:
            AddMsgAndPrint('\nZunits were not selected at runtime....Exiting!', 2, textFilePath)
            exit()

        AddMsgAndPrint(f"\tDEM Projection Name: {sr.Name}", textFilePath=textFilePath)
        AddMsgAndPrint(f"\tDEM XY Linear Units: {units}", textFilePath=textFilePath)
        AddMsgAndPrint(f"\tDEM Elevation Values (Z): {zUnits}", textFilePath=textFilePath)
        AddMsgAndPrint(f"\tZ-factor for Slope Modeling: {str(Zfactor)}", textFilePath=textFilePath)
        AddMsgAndPrint(f"\tDEM Cell Size: {str(desc.MeanCellWidth)} x {str(desc.MeanCellHeight)} {units}", textFilePath=textFilePath)

    else:
        AddMsgAndPrint(f"\n\t{path.basename(tempDEM)} is not in a projected Coordinate System! Exiting...", 2, textFilePath)
        exit()

    # Clip out the DEM with extended buffer for temp processing and standard buffer for final DEM display
    AddMsgAndPrint('\nCopying out final DEM...', textFilePath=textFilePath)
    SetProgressorLabel('Copying out final DEM...')
    CopyRaster(tempDEM, projectDEM)

    #### Delete temp data
    AddMsgAndPrint('\nDeleting temp data...', textFilePath=textFilePath)
    SetProgressorLabel('Deleting temp data...')
    deleteScratchLayers(tempLayers)

    #### Add layers to Pro Map
    AddMsgAndPrint('\nAdding layers to map...', textFilePath=textFilePath)
    SetProgressorLabel('Adding layers to map...')
    SetParameterAsText(10, projectDEM)


    #### Clean up
    # Look for and delete anything else that may remain in the installed SCRATCH.gdb
    startWorkspace = env.workspace
    env.workspace = scratchGDB
    dss = []
    for ds in ListDatasets('*'):
        dss.append(path.join(scratchGDB, ds))
    for ds in dss:
        if Exists(ds):
            try:
                Delete(ds)
            except:
                pass
    env.workspace = startWorkspace


    #### Compact FGDB
    try:
        AddMsgAndPrint('\nCompacting File Geodatabase...', textFilePath=textFilePath)
        SetProgressorLabel('Compacting File Geodatabase...')
        Compact(basedataGDB_path)
    except:
        pass

    AddMsgAndPrint('\nScript completed successfully', textFilePath=textFilePath)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Prepare Site DEM'), 2, textFilePath)
    except:
        AddMsgAndPrint(errorMsg('Prepare Site DEM'), 2)

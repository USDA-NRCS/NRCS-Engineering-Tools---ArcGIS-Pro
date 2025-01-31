from getpass import getuser
from os import path
from sys import argv
from time import ctime

from arcpy import CheckExtension, CheckOutExtension, Describe, env, GetParameterAsText, SetParameterAsText, SetProgressorLabel
from arcpy.analysis import Buffer
from arcpy.management import Clip, Compact, CopyRaster, Delete, MosaicToNewRaster, Project, ProjectRaster
from arcpy.mp import ArcGISProject
from arcpy.sa import ExtractByMask, Times

from utils import AddMsgAndPrint, emptyScratchGDB, errorMsg, removeMapLayers


def logBasicSettings(log_file_path, project_workspace, dem_format, input_z_units, input_dem_sr, output_sr, cell_size):
    with open (log_file_path, 'a+') as f:
        f.write('\n######################################################################\n')
        f.write('Executing Tool: Create DEM\n')
        f.write(f"User Name: {getuser()}\n")
        f.write(f"Date Executed: {ctime()}\n")
        f.write('User Parameters:\n')
        f.write(f"\tProject Workspace: {project_workspace}\n")
        f.write(f"\tDEM Format: {dem_format}\n")
        f.write(f"\tInput DEM Elevation Units: {input_z_units}\n")
        f.write(f"\tInput DEM Spatial Reference: {input_dem_sr}\n")
        f.write(f"\tOutput DEM Spatial Reference: {output_sr}\n")
        f.write(f"\tOutput DEM Cell Size: {cell_size}\n")


### Initial Tool Validation ###
try:
    aprx = ArcGISProject('CURRENT')
    map = aprx.listMaps('Engineering')[0]
except:
    AddMsgAndPrint('This tool must be run from an ArcGIS Pro project that was developed from the template distributed with this toolbox. Exiting!', 2)
    exit()

if CheckExtension('Spatial') == 'Available':
    CheckOutExtension('Spatial')
else:
    AddMsgAndPrint('Spatial Analyst Extension not enabled. Please enable Spatial Analyst from Project, Licensing, Configure licensing options. Exiting...', 2)
    exit()

### Input Parameters ###
project_aoi = GetParameterAsText(0)
dem_format = GetParameterAsText(1)
input_dems = GetParameterAsText(2).split(';')
nrcs_service = GetParameterAsText(3)
external_service = GetParameterAsText(4)
cell_size = GetParameterAsText(5)
input_z_units = GetParameterAsText(6)
input_dem_sr = GetParameterAsText(7)
output_sr = GetParameterAsText(8)
transformation = GetParameterAsText(9)

### Locate Project GDB ###
project_aoi_path = Describe(project_aoi).CatalogPath
if project_aoi_path.find('.gdb') > 0 and 'AOI' in project_aoi_path:
    project_gdb = project_aoi_path[:project_aoi_path.find('.gdb')+4]
else:
    AddMsgAndPrint('\nSelected AOI layer is not from an Engineering project workspace. Exiting...', 2)
    exit()

### Set Paths and Variables ###
support_dir = path.dirname(argv[0])
scratch_gdb = path.join(support_dir, 'Scratch.gdb')
project_workspace = path.dirname(project_gdb)
project_name = path.basename(project_workspace)
log_file_path = path.join(project_workspace, f"{project_name}_log.txt")
project_dem_name = f"{project_name}_DEM"
project_dem_path = path.join(project_gdb, project_dem_name)
buffer_aoi = path.join(project_gdb, 'Layers', 'Buffer_AOI')
wgs_AOI = path.join(scratch_gdb, 'AOI_WGS84')
wgs84_dem = path.join(scratch_gdb, 'WGS84_DEM')
temp_dem = path.join(scratch_gdb, 'tempDEM')

### ESRI Environment Settings ###
env.overwriteOutput = True
env.resamplingMethod = 'BILINEAR'
env.pyramid = 'PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP'
env.cellSize = cell_size #TODO: Is this sufficient for converting xy?

# If NRCS Image Service selected, set path to lyrx file
reference_layers = path.join(path.dirname(support_dir), 'Reference_Layers')
if '0.5m' in nrcs_service:
    sourceService = path.join(reference_layers, 'NRCS Bare Earth 0.5m.lyrx')
elif '1m' in nrcs_service:
    sourceService = path.join(reference_layers, 'NRCS Bare Earth 1m.lyrx')
elif '2m' in nrcs_service:
    sourceService = path.join(reference_layers, 'NRCS Bare Earth 2m.lyrx')
elif '3m' in nrcs_service:
    sourceService = path.join(reference_layers, 'NRCS Bare Earth 3m.lyrx')
elif external_service != '':
    sourceService = external_service

# Set z-factor for converting vertical units to International Feet
if input_z_units == 'Meters':
    z_factor = 3.28083989501
elif input_z_units == 'Centimeters':
    z_factor = 328.083989501
elif input_z_units == 'International Feet':
    z_factor = 1
elif input_z_units == 'International Inches':
    z_factor = 12
elif input_z_units == 'US Survey Feet':
    z_factor = 1.000002000
elif input_z_units == 'US Survey Inches':
    z_factor = 12.000002400

try:
    emptyScratchGDB(scratch_gdb)
    logBasicSettings(log_file_path, project_workspace, dem_format, input_z_units, input_dem_sr, output_sr, cell_size)

    #### Create the projectAOI and projectAOI_B layers based on the choice selected by user input
    AddMsgAndPrint('\nBuffering selected extent...', log_file_path=log_file_path)
    SetProgressorLabel('Buffering selected extent...')
    Buffer(project_aoi, buffer_aoi, '500 Feet', 'FULL', '', 'ALL', '')

    #### Remove existing project DEM and Hillshade if present in map
    AddMsgAndPrint('\nRemoving layers from project maps, if present...', log_file_path=log_file_path)
    SetProgressorLabel('Removing layers from project maps, if present...')
    removeMapLayers(map, [project_dem_name])

    #### Process the input DEMs
    AddMsgAndPrint('\nProcessing the input DEM(s)...', log_file_path=log_file_path)
    SetProgressorLabel('Processing the input DEM(s)...')

    # Extract and process the DEM if it's an image service
    if dem_format in ['NRCS Image Service', 'External Image Service']:
        if cell_size == '':
            AddMsgAndPrint('\nAn output DEM cell size was not specified. Exiting...', 2, log_file_path)
            exit()
        else:
            AddMsgAndPrint('\nProjecting AOI to match input DEM...', log_file_path=log_file_path)
            SetProgressorLabel('Projecting AOI to match input DEM...')
            wgs_CS = input_dem_sr
            Project(buffer_aoi, wgs_AOI, wgs_CS)
            
            AddMsgAndPrint('\nDownloading DEM data...', log_file_path=log_file_path)
            SetProgressorLabel('Downloading DEM data...')
            aoi_ext = Describe(wgs_AOI).extent
            xMin = aoi_ext.XMin
            yMin = aoi_ext.YMin
            xMax = aoi_ext.XMax
            yMax = aoi_ext.YMax
            clip_ext = f"{str(xMin)} {str(yMin)} {str(xMax)} {str(yMax)}"
            Clip(sourceService, clip_ext, wgs84_dem, '', '', '', 'NO_MAINTAIN_EXTENT')

            AddMsgAndPrint('\nProjecting downloaded DEM...', log_file_path=log_file_path)
            SetProgressorLabel('Projecting downloaded DEM...')
            ProjectRaster(wgs84_dem, temp_dem, output_sr, 'BILINEAR', cell_size)

    # Else, extract the local file DEMs
    else:
        dem_count = len(input_dems)
        # Manage spatial references
        env.outputCoordinateSystem = output_sr
        if transformation != '':
            env.geographicTransformations = transformation
        
        # Clip out the DEMs that were entered
        AddMsgAndPrint('\tExtracting input DEM(s)...', log_file_path=log_file_path)
        SetProgressorLabel('Extracting input DEM(s)...')
        x = 0
        DEMlist = []
        while x < dem_count:
            raster = input_dems[x].replace("'", '')
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
                AddMsgAndPrint('\nHorizontal units of one or more input DEMs do not appear to be feet or meters! Exiting...', 2, log_file_path)
                exit()
            out_clip = f"{temp_dem}_{str(x)}"
            try:
                extractedDEM = ExtractByMask(raster_path, buffer_aoi)
                extractedDEM.save(out_clip)
            except:
                AddMsgAndPrint('\nOne or more input DEMs may have a problem! Please verify that the input DEMs cover the tract area and try to run again. Exiting...', 2, log_file_path)
                exit()
            if x == 0:
                mosaicInputs = str(out_clip)
            else:
                mosaicInputs = f"{mosaicInputs};{str(out_clip)}"
            DEMlist.append(str(out_clip))
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
        if dem_count > 1:
            AddMsgAndPrint('\nMerging multiple input DEM(s)...', log_file_path=log_file_path)
            SetProgressorLabel('Merging multiple input DEM(s)...')
            MosaicToNewRaster(mosaicInputs, scratch_gdb, temp_dem, '#', '32_BIT_FLOAT', cellsize, '1', 'MEAN', '#')

        # Else just convert the one input DEM to become the tempDEM
        else:
            AddMsgAndPrint('\nOnly one input DEM detected. Carrying extract forward for final DEM processing...', log_file_path=log_file_path)
            CopyRaster(DEMlist[0], temp_dem)

        # Delete clippedDEM files
        AddMsgAndPrint('\nDeleting temp DEM file(s)...', log_file_path=log_file_path)
        SetProgressorLabel('Deleting temp DEM file(s)...')
        for raster in DEMlist:
            Delete(raster)

    # Gather info on the final temp DEM
    desc = Describe(temp_dem)
    sr = desc.SpatialReference
    units = sr.LinearUnitName

    if sr.Type == 'Projected':
        AddMsgAndPrint(f"\tDEM Projection Name: {sr.Name}", log_file_path=log_file_path)
        AddMsgAndPrint(f"\tDEM XY Linear Units: {units}", log_file_path=log_file_path)
        AddMsgAndPrint(f"\tDEM Cell Size: {str(desc.MeanCellWidth)} x {str(desc.MeanCellHeight)} {units}", log_file_path=log_file_path)
    else:
        AddMsgAndPrint(f"\n\t{path.basename(temp_dem)} is not in a projected Coordinate System! Exiting...", 2, log_file_path)
        exit()

    ### Convert DEM Values to International Feet ###
    AddMsgAndPrint('\nFinalizing DEM...', log_file_path=log_file_path)
    SetProgressorLabel('Finalizing DEM...')
    output_dem = Times(temp_dem, z_factor)
    output_dem.save(project_dem_path)

    ### Add Output DEM to Map ###
    AddMsgAndPrint('\nAdding DEM to map...', log_file_path=log_file_path)
    SetProgressorLabel('Adding DEM to map...')
    SetParameterAsText(10, project_dem_path)

    ### Compact Project GDB ###
    try:
        SetProgressorLabel('Compacting project geodatabase...')
        AddMsgAndPrint('\nCompacting project geodatabase...', log_file_path=log_file_path)
        Compact(project_gdb)
    except:
        pass

    AddMsgAndPrint('\nCreate DEM completed successfully', log_file_path=log_file_path)

except SystemExit:
    pass

except:
    try:
        AddMsgAndPrint(errorMsg('Create DEM'), 2, log_file_path)
    except:
        AddMsgAndPrint(errorMsg('Create DEM'), 2)

finally:
    emptyScratchGDB(scratch_gdb)

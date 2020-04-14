## Download_Image_Service_Elevation.py: Chris Morse, 4/18/2019
## Used to download a DEM from WGS84 web services

import arcpy, os, traceback

## ===============================================================================================================
## Error handling and messaging
def print_exception():
    tb = sys.exc_info()[2]
    l = traceback.format_tb(tb)
    l.reverse()
    tbinfo = "".join(l)
    arcpy.AddError("\n----------------------------------- ERROR Start -----------------------------------")
    arcpy.AddError("Traceback Info: \n" + tbinfo + "Error Info: \n    " +  str(sys.exc_type)+ ": " + str(sys.exc_value) + "")
    arcpy.AddError("------------------------------------- ERROR End -----------------------------------\n")

## =============================================== MAIN =======================================================

arcpy.env.overwriteOutput = True

try:

    # Must be run from ArcMap
    try:
        mxd = arcpy.mapping.MapDocument("CURRENT")
    except:
        arcpy.AddError("\nThis tool must be run from ArcMap. Exiting tool...\n")
        sys.exit()
    
    # Check out Spatial Analyst License
    if arcpy.CheckExtension("Spatial") == "Available":
        arcpy.CheckOutExtension("Spatial")
    else:
        arcpy.AddError("Spatial Analyst Extension not enabled. Please enable Spatial analyst from the Tools/Extensions menu. Exiting...\n")
        sys.exit()

    # Environment Settings
    arcpy.env.overwriteOutput = True
    arcpy.env.resamplingMethod = "BILINEAR"
    arcpy.env.pyramid = "PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP"
    arcpy.env.geographicTransformations = "WGS_1984_(ITRF00)_To_NAD_1983"

    # Acquire script input parameters
    arcpy.AddMessage("\nGetting Inputs...\n")
    userWorkspace = arcpy.GetParameterAsText(0)
    source_Service = arcpy.GetParameterAsText(1)
    raster_name = arcpy.GetParameterAsText(2)
    input_extent = arcpy.GetParameterAsText(3)
    target_pcs = arcpy.GetParameterAsText(4)
    target_Cellsize = arcpy.GetParameterAsText(5)

    # Define variables
    arcpy.AddMessage("\nSetting Variables...\n")
    projectName = arcpy.ValidateTableName(os.path.basename(userWorkspace).replace(" ","_"))
    watershedGDB_name = os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.gdb"
    watershedGDB_path = userWorkspace + os.sep + watershedGDB_name
    watershedFD = watershedGDB_path + os.sep + "Layers"
    raster_name = raster_name.replace(" ","_")
    WGS84_DEM = watershedGDB_path + os.sep + "WGS84_DEM"
    final_DEM = watershedGDB_path + os.sep + raster_name
    project_AOI = os.path.join(watershedGDB_path, 'input_AOI')
    wgs_AOI = os.path.join(watershedGDB_path, 'AOI_WGS84')

    # Exit if the AOI that was drawn has more than 1 digitized area
    if int(arcpy.GetCount_management(input_extent).getOutput(0)) > 1:
        arcpy.AddError("\nYou can only digitize 1 extent to be downloaded! Please try again. Exiting...")
        sys.exit()

    # Check that the optional target pcs is a projected coordinate system and not just a geographic coordinate system
    if target_pcs != '':
        sr = arcpy.SpatialReference()
        sr.loadFromString(target_pcs)
        if sr.type != "Projected":
            arcpy.AddError("\nSelected output coordinate system is not a projected coordinate system. Please try again. Exiting...")
            sys.exit()    
    
    # Re-project the AOI to WGS84 Geographic (EPSG WKID: 4326)
    arcpy.AddMessage("\nConverting input extent to WGS 1984...\n")
    wgs_CS = arcpy.SpatialReference(4326)
    if target_pcs != '':
        arcpy.Project_management(input_extent, project_AOI, target_pcs)
        arcpy.Project_management(project_AOI, wgs_AOI, wgs_CS)
    else:
        arcpy.Project_management(input_extent, wgs_AOI, wgs_CS)

    # Use the WGS 1984 AOI to clip/extract the DEM from the service
    arcpy.AddMessage("\nDownloading Data...\n")
    arcpy.SetProgressorLabel("Downloading Data. Please standby...")
    aoi_ext = arcpy.Describe(wgs_AOI).extent
    xMin = aoi_ext.XMin
    yMin = aoi_ext.YMin
    xMax = aoi_ext.XMax
    yMax = aoi_ext.YMax
    clip_ext = str(xMin) + " " + str(yMin) + " " + str(xMax) + " " + str(yMax)
    ##arcpy.Clip_management(source_Service, clip_ext, WGS84_DEM, input_extent, "", "ClippingGeometry", "NO_MAINTAIN_EXTENT")
    arcpy.Clip_management(source_Service, clip_ext, WGS84_DEM, wgs_AOI, "", "ClippingGeometry", "NO_MAINTAIN_EXTENT")

    # Project the WGS 1984 DEM to the coordinate system of the input extent OR override with the specified pcs
    # We use the factory code to get it
    arcpy.AddMessage("\nProjecting output data...\n")
    if target_pcs != '':
        final_CS = arcpy.Describe(project_AOI).spatialReference.factoryCode
    else:
        final_CS = arcpy.Describe(input_extent).spatialReference.factoryCode
        
    arcpy.ProjectRaster_management(WGS84_DEM, final_DEM, final_CS, "BILINEAR", target_Cellsize)


    # Clean up and add to map
    arcpy.AddMessage("\nCleaning up temp files and adding DEM to map...\n")
    arcpy.Delete_management(WGS84_DEM)
    arcpy.Delete_management(wgs_AOI)
    try:
        arcpy.Delete_management(project_AOI)
    except:
        pass
    

    arcpy.SetParameterAsText(6, final_DEM)

    arcpy.Compact_management(watershedGDB_path)
    arcpy.RefreshCatalog(watershedGDB_path)
    arcpy.AddMessage("\nDone!\n")

except SystemExit:
    pass

except KeyboardInterrupt:
    AddMsgAndPrint("Interruption requested....exiting")

except:
    print_exception()

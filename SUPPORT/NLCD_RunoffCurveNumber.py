
#---------------------------------------------------------------------------------------------------------
def print_exception():
    
    tb = sys.exc_info()[2]
    l = traceback.format_tb(tb)
    l.reverse()
    tbinfo = "".join(l)
    AddMsgAndPrint("\n----------ERROR Start-------------------\n",2)
    AddMsgAndPrint("Traceback Info: \n" + tbinfo + "Error Info: \n    " +  str(sys.exc_type)+ ": " + str(sys.exc_value) + "",2)
    AddMsgAndPrint("----------ERROR End-------------------- \n",2)

## ================================================================================================================    
def AddMsgAndPrint(msg, severity=0):
    # prints message to screen if run as a python script
    # Adds tool message to the geoprocessor
    # 
    # Split the message on \n first, so that if it's multiple lines, a GPMessage will be added for each line

    print msg
    
    try:

        f = open(textFilePath,'a+')
        f.write(msg + " \n")
        f.close

        del f

        if ArcGIS10:
            if not msg.find("\n") < 0 and msg.find("\n") < 4:
                gp.AddMessage(" ")        
        
        for string in msg.split('\n'):
            
            # Add a geoprocessing message (in case this is run as a tool)
            if severity == 0:
                gp.AddMessage(string)
                
            elif severity == 1:
                gp.AddWarning(string)
                
            elif severity == 2:
                AddMsgAndPrint("    ")
                gp.AddError(string)

        if ArcGIS10:
            if msg.find("\n") > 4:
                gp.AddMessage(" ")                
                
    except:
        pass

## ================================================================================================================
def logBasicSettings():    
    # record basic user inputs and settings to log file for future purposes

    import getpass, time

    f = open(textFilePath,'a+')
    f.write("\n################################################################################################################\n")
    f.write("Executing \"NLCD Runoff Curve Number\" Tool\n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write("ArcGIS Version: " + str(version) + "\n")
    f.write("User Parameters:\n")
    f.write("\tInput Watershed: " + inWatershed + "\n")
    f.write("\tInput NLCD Raster: " + inNLCD + "\n")
    f.write("\tInput Soils: " + inSoils + "\n")
    
    if createRCN:
        f.write("\tCreate RCN Grid: SELECTED\n")
        if len(snapRaster) > 0:
            f.write("\tRCN Grid Snap Raster: " + snapRaster + "\n")
            f.write("\tRCN Grid Cellsize: " + str(float(outCellSize)) + "\n")
            f.write("\tRCN Grid Coord Sys: " + str(outCoordSys) + "\n")
        else:
            f.write("\tRCN Grid Snap Raster: NOT SPECIFIED\n")
    else:
        f.write("\tCreate RCN Grid: NOT SELECTED\n")
    
    f.close
    del f

## ================================================================================================================
# Import system modules
import sys, os, string, traceback, arcgisscripting

# Create the Geoprocessor object
gp = arcgisscripting.create(9.3)
gp.OverWriteOutput = 1

# Used to determine ArcGIS version
d = gp.GetInstallInfo('desktop')

keys = d.keys()

for k in keys:

    if k == "Version":

        version = " \nArcGIS %s : %s" % (k, d[k])
        print version

        if version.find("10.") > 0:
            ArcGIS10 = True

        else:
            ArcGIS10 = False

        break 

del d, keys
   
if version < 9.3:
    AddMsgAndPrint("\nThis tool requires ArcGIS version 9.3 or Greater.....EXITING",2)
    sys.exit("")           


try:
    # Check out Spatial Analyst License        
    if gp.CheckExtension("spatial") == "Available":
        gp.CheckOutExtension("spatial")
    else:
        gp.AddError("Spatial Analyst Extension not enabled. Please enable Spatial analyst and try again.... ...EXITING")
        sys.exit("")
        
    # ---------------------------------------------------------------------- Input Parameters
    
    inWatershed = gp.GetParameterAsText(0)
    inNLCD = gp.GetParameterAsText(1)
    inSoils = gp.GetParameterAsText(2)
    inputField = gp.GetParameterAsText(3)
    curveNoGrid = gp.GetParameterAsText(4)
    snapRaster = gp.GetParameterAsText(5)

    # Check for RCN Grid choice...
    if curveNoGrid == "#" or curveNoGrid == "" or curveNoGrid == False or curveNoGrid == "false":
        createRCN = False

    else:
        createRCN = True
        
    # If snap raster provided assign output cell size from snapRaster
    if len(snapRaster) > 0:
        if gp.Exists(snapRaster):
            desc = gp.Describe(snapRaster)
            sr = desc.SpatialReference
            outCellSize = desc.MeanCellWidth
            outCoordSys = sr
            del desc, sr
        else:
            AddMsgAndPrint("\n\nSpecified Snap Raster Does not exist, please make another selection or verify the path...EXITING",2)
            sys.exit("")
        
    # --------------------------------------------------------------------------- Define Variables 
    inWatershed = gp.Describe(inWatershed).CatalogPath
    inSoils = gp.Describe(inSoils).CatalogPath
    
    if inWatershed.find('.gdb') > -1 or inWatershed.find('.mdb') > -1:

        # inWatershed was created using 'Create Watershed Tool'
        if inWatershed.find('_EngTools'):
            watershedGDB_path = inWatershed[:inWatershed.find('.') + 4]

        # inWatershed is a fc from a DB not created using 'Create Watershed Tool'
        else:
            watershedGDB_path = os.path.dirname(inWatershed[:inWatershed.find('.')+4]) + os.sep + os.path.basename(inWatershed).replace(" ","_") + "_EngTools.gdb"

    elif inWatershed.find('.shp')> -1:
        watershedGDB_path = os.path.dirname(inWatershed[:inWatershed.find('.')+4]) + os.sep + os.path.basename(inWatershed).replace(".shp","").replace(" ","_") + "_EngTools.gdb"

    else:
        AddMsgAndPrint("\n\nWatershed Polygon must either be a feature class or shapefile!.....Exiting",2)
        sys.exit()

    watershedFD = watershedGDB_path + os.sep + "Layers"
    watershedGDB_name = os.path.basename(watershedGDB_path)
    userWorkspace = os.path.dirname(watershedGDB_path)
    wsName = gp.ValidateTablename(os.path.splitext(os.path.basename(inWatershed))[0])

    # log File Path
    textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.txt"   
    
    # record basic user inputs and settings to log file for future purposes
    logBasicSettings()

    # ----------------------------------------------------------------------------- Datasets
    # --------------------------------------------------- Temporary Datasets
    
    LU_PLUS_SOILS = watershedGDB_path + os.sep + "LU_PLUS_SOILS"
    CULT_GRID = watershedGDB_path + os.sep + "CULT_GRID"
    CULT_POLY = watershedGDB_path + os.sep + "CULT_POLY"
    soilsLyr = "soilsLyr"
    SOILS_GRID = watershedGDB_path + os.sep + "SOILS"
    landuse = watershedGDB_path + os.sep + "NLCD"
    RCN_Stats = watershedGDB_path + os.sep + "RCN_Stats"
    RCN_Stats2 = watershedGDB_path + os.sep + "RCN_Stats2"
    
    # --------------------------------------------------- Permanent Datasets
    
    wsSoils = watershedFD + os.sep + wsName + "_Soils"
    watershed = watershedFD + os.sep + wsName
    RCN_GRID = watershedGDB_path + os.sep + wsName + "_RCN"
    RCN_TABLE = watershedGDB_path + os.sep + wsName + "_RCN_Summary_Table"
    
     # ----------------------------------------------------------- Lookup Tables
     
    NLCD_RCN_TABLE = os.path.join(os.path.dirname(sys.argv[0]), "Support.gdb" + os.sep + "NLCD_RCN_TABLE")
    
    # ----------------------------------------------------------------------------- Check Some Parameters
    # Exit if any are true
    if not int(gp.GetCount_management(inWatershed).getOutput(0)) > 0:
        AddMsgAndPrint("\n\nWatershed Layer is empty.....Exiting!",2)
        sys.exit()

    if int(gp.GetCount_management(inWatershed).getOutput(0)) > 1:
        AddMsgAndPrint("\n\nOnly ONE Watershed or Subbasin can be submitted!...",2)
        AddMsgAndPrint("Either dissolve " + os.path.basename(inWatershed) + " Layer, export an individual polygon, ",2)
        AddMsgAndPrint("make a single selection, or provide a different input...EXITING",2)
        sys.exit()
        
    if gp.Describe(inWatershed).ShapeType != "Polygon":
        AddMsgAndPrint("\n\nYour Watershed Layer must be a polygon layer!.....Exiting!",2)
        sys.exit()

    if gp.Describe(inSoils).ShapeType != "Polygon":
        AddMsgAndPrint("\n\nYour Soils Layer must be a polygon layer!.....Exiting!",2)
        sys.exit()

    if not len(gp.ListFields(inSoils,inputField)) > 0:
        AddMsgAndPrint("\nThe field specified for Hydro Groups does not exist in your soils data.. please specify another name and try again..EXITING",2)
        sys.exit("")

    if not len(gp.ListFields(inSoils,"MUNAME")) > 0:
        AddMsgAndPrint("\nMUNAME field does not exist in your soils data.. please correct and try again..EXITING",2)
        sys.exit("")

    if not gp.Exists(NLCD_RCN_TABLE):
        AddMsgAndPrint("\n\n\"NLCD_RCN_TABLE\" was not found! Make sure \"Support.gdb\" is located within the same location as this script",2)
        sys.exit("")

    # --------------------------------------------------------------------------- Create FGDB, FeatureDataset
    # Boolean - Assume FGDB already exists
    FGDBexists = True

    # Create Watershed FGDB and feature dataset if it doesn't exist      
    if not gp.exists(watershedGDB_path):
        desc = gp.Describe(inWatershed)
        sr = desc.SpatialReference

        gp.CreateFileGDB_management(userWorkspace, watershedGDB_name)
        gp.CreateFeatureDataset_management(watershedGDB_path, "Layers", sr)
        AddMsgAndPrint("\nSuccessfully created File Geodatabase: " + watershedGDB_name,1)
        FGDBexists = False
        del desc, sr

    # if GDB already existed but feature dataset doesn't
    if not gp.exists(watershedFD):
        desc = gp.Describe(inWatershed)
        sr = desc.SpatialReference
        gp.CreateFeatureDataset_management(watershedGDB_path, "Layers", sr)
        del desc, sr

    # --------------------------------------------------------------------------- Remove domains from fields if they exist
    # If Watershed Runoff Curve Number Tools were previously used on specified watershed, domain will remain on fields
    vectorLanduse = watershedFD + os.sep + wsName + "_Landuse"
    desc = gp.describe(watershedGDB_path)
    listOfDomains = []

    domains = desc.Domains

    for domain in domains:
        listOfDomains.append(domain)

    del desc, domains

    if "LandUse_Domain" in listOfDomains:
        try:
            gp.RemoveDomainFromField(vectorLanduse, "LANDUSE")
        except:
            pass
    if "Condition_Domain" in listOfDomains:
        try:
            gp.RemoveDomainFromField(vectorLanduse, "CONDITION")
        except:
            pass

    if "Hydro_Domain" in listOfDomains:
        try:
            gp.RemoveDomainFromField(wsSoils, "HYDGROUP")
        except:
            pass
        
    del listOfDomains    
    # ------------------------------------- Delete previous layers from ArcMap if they exist
    # ------------------------------- Map Layers
    rcnOut = "" + wsName + "_RCN"
    soilsOut = "" + wsName + "_Soils"
    landuseOut = "" + wsName + "_Landuse"
    
    layersToRemove = (rcnOut,soilsOut,landuseOut)

    x = 0
    for layer in layersToRemove:
        
        if gp.exists(layer):
            if x == 0:
                AddMsgAndPrint("\nRemoving previous layers from your ArcMap session " + watershedGDB_name ,1)
                x+=1
                
            try:
                gp.delete_management(layer)
                AddMsgAndPrint("\tRemoving " + layer + "",0)
            except:
                pass

    del x
    del layer
    del layersToRemove
    
    # -------------------------------------------------------------------------- Delete Previous Data if present 
    if FGDBexists:    

        layersToRemove = (wsSoils,landuse,vectorLanduse,LU_PLUS_SOILS,CULT_GRID,CULT_POLY,SOILS_GRID,RCN_GRID,RCN_Stats)

        x = 0        
        for layer in layersToRemove:

            if gp.exists(layer):

                # strictly for formatting
                if x == 0:
                    AddMsgAndPrint("\nRemoving old files from FGDB: " + watershedGDB_name ,1)
                    x += 1
                
                try:
                    gp.delete_management(layer)
                    AddMsgAndPrint("\tDeleting....." + os.path.basename(layer),0)
                except:
                    pass

        del x, layersToRemove
        del vectorLanduse

    # ----------------------------------------------------------------------------------------------- Create Watershed
    
    # if paths are not the same then assume AOI was manually digitized
    # or input is some from some other feature class/shapefile

    # True if watershed was not created from this Eng tools
    externalWshd = False
        
    if not gp.Describe(inWatershed).CatalogPath == watershed:       

        # delete the AOI feature class; new one will be created            
        if gp.exists(watershed):
            
            try:
                gp.delete_management(watershed)
                gp.CopyFeatures_management(inWatershed, watershed)
                AddMsgAndPrint("\nSuccessfully Overwrote existing Watershed",1)
            except:
                print_exception()
                gp.OverWriteOutput = 1
            
        else:
            gp.CopyFeatures_management(inWatershed, watershed)
            AddMsgAndPrint("\nSuccessfully Created Watershed " + os.path.basename(watershed) ,1)

        externalWshd = True

    # paths are the same therefore input IS projectAOI
    else:
        AddMsgAndPrint("\nUsing existing " + os.path.basename(watershed) + " feature class",1)

    if externalWshd:
        
        # Delete all fields in watershed layer except for obvious ones
        fields = gp.ListFields(watershed)

        for field in fields:

            fieldName = field.Name

            if fieldName.find("Shape") < 0 and fieldName.find("OBJECTID") < 0 and fieldName.find("Subbasin") < 0:
                gp.deletefield_management(watershed,fieldName)
                
            del fieldName

        del fields

        if not len(gp.ListFields(watershed,"Subbasin")) > 0:
            gp.AddField_management(watershed, "Subbasin", "SHORT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")        
            gp.CalculateField_management(watershed, "Subbasin","[OBJECTID]","VB", "")

        if not len(gp.ListFields(watershed,"Acres")) > 0:
            gp.AddField_management(watershed, "Acres", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
            gp.CalculateField_management(watershed, "Acres", "!shape.area@ACRES!", "PYTHON", "")

    # ------------------------------------------------------------------------------------------------ Prepare Landuse Raster(s)
    # ----------------------------------- Capture Default Environments
    
    tempExtent = gp.Extent
    tempMask = gp.mask
    tempSnapRaster = gp.SnapRaster
    tempCellSize = gp.CellSize
    tempCoordSys = gp.OutputCoordinateSystem

    # ----------------------------------- Describe input NLCD Properties
    
    desc = gp.Describe(inNLCD)
    sr = desc.SpatialReference

    units = sr.LinearUnitName
    cellSize = desc.MeanCellWidth

    
    # ----------------------------------- Set Environment Settings
    
    gp.Extent = "MINOF"
    gp.CellSize = cellSize
    gp.mask = ""
    gp.SnapRaster = ""
    
    if units == "Meter":
        units = "Meters"
        
    elif units == "Foot":
        units = "Feet"
    elif units == "Foot_US":
        units = "Feet"
      
    cellArea = cellSize ** 2
    
    del desc
    del sr

    # ---------------------------------------------------------------------- Clip NLCD to watershed boundary
    
    AddMsgAndPrint("\nClipping " + str(os.path.basename(inNLCD)) + " to " + str(wsName) + " boundary..",1)
    gp.ExtractByMask_sa(inNLCD, watershed, landuse)
    AddMsgAndPrint("\nSuccessully Clipped NLCD...",1)

    # Isolate Cultivated Cropland and export to poly for soils processing
    gp.Con_sa(landuse, landuse, CULT_GRID, "", "\"VALUE\" = 81 OR \"VALUE\" = 82 OR \"VALUE\" = 83 OR \"VALUE\" = 84 OR \"VALUE\" = 85")
    # Convert to Polygon for selecting
    gp.RasterToPolygon_conversion(CULT_GRID,CULT_POLY,"SIMPLIFY","VALUE")

    # -------------------------------------------------------------------------------------- Clip and Process Soils Data          
    # Clip the soils to the watershed
    gp.Clip_analysis(inSoils,watershed,wsSoils)
    AddMsgAndPrint("\nSuccessfully clipped " + str(os.path.basename(inSoils)) + " soils layer",1)

    # If Input field name other than ssurgo default, add and calc proper field
    if inputField.upper() != "HYDGROUP":
        gp.AddField_management(wsSoils, "HYDGROUP", "TEXT", "", "", "20", "", "NULLABLE", "NON_REQUIRED", "")
    gp.CalculateField_management(wsSoils, "HYDGROUP", "[" + str(inputField) + "]", "VB", "")

    # ADD HYD_CODE Field for lookup
    if len(gp.ListFields(wsSoils,"HYD_CODE")) < 1:
        gp.AddField_management(wsSoils, "HYD_CODE", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")    
    gp.MakeFeatureLayer_management(wsSoils, soilsLyr)
    
    # Process soils to remove nulls in Water, Pits, or urban mapunits
    AddMsgAndPrint("\n\tProcessing soils data...",1)

    # Select and assign "W" value to any water type map units 
    gp.SelectLayerByAttribute_management(soilsLyr, "NEW_SELECTION", "\"MUNAME\" LIKE '%Water%'")
    count = int(gp.GetCount_management(soilsLyr).getOutput(0))
    if count > 0:
        AddMsgAndPrint("\n\t\tSelecting and converting 'Water' Mapunits",0)
        gp.CalculateField_management(soilsLyr, "HYDGROUP", "\"W\"", "VB", "")
    del count
        
    # Select and assign "P" value to any pit-like map units  
    gp.SelectLayerByAttribute_management(soilsLyr, "NEW_SELECTION", "\"MUNAME\" LIKE '%Pit%'")
    count = int(gp.GetCount_management(soilsLyr).getOutput(0))
    if count > 0:
        AddMsgAndPrint("\t\tSelecting and converting 'Pits' Mapunits",0)
        gp.CalculateField_management(soilsLyr, "HYDGROUP", "\"P\"", "VB", "")
    del count

    # Assign a "D" value to any unpopulated Urban mapunits   
    gp.SelectLayerByAttribute_management(soilsLyr, "NEW_SELECTION", "\"MUNAME\" LIKE 'Urban%'")
    count = int(gp.GetCount_management(soilsLyr).getOutput(0))
    if count > 0:
        AddMsgAndPrint("\t\tSelecting and converting Urban Mapunits",0) 
        gp.CalculateField_management(soilsLyr, "HYDGROUP", "\"D\"", "VB", "")
    del count   
    
    # Select any Combined Hydro groups
    AddMsgAndPrint("\n\tChecking for combined hydrologic groups...",1)
    query = "\"HYDGROUP\" LIKE '%/%'"
    gp.SelectLayerByAttribute_management(soilsLyr, "NEW_SELECTION", query)
    del query
    count = int(gp.GetCount_management(soilsLyr).getOutput(0))
    if count > 0:
        AddMsgAndPrint("\n\tThere are " + str(count) + " soil map unit(s) with combined hydro groups",0)
        gp.MakeFeatureLayer_management(soilsLyr, "combinedLyr")
    
        # Select Combined Classes that intersect cultivated cropland
        gp.SelectLayerByLocation("combinedLyr", "intersect", CULT_POLY, 0, "new_selection")
        count2 = int(gp.GetCount_management("combinedLyr").getOutput(0))
        if count2 > 0:
            AddMsgAndPrint("\n\t\tSetting " + str(count2) + " combined group(s) on cultivated land to drained state",0)
            # Set selected polygons to drained state
            gp.CalculateField_management("combinedLyr", "HYDGROUP", "!HYDGROUP![0]", "PYTHON", "")
        del count2
        
        # Set remaining combined groups to natural state
        gp.SelectLayerByAttribute_management("combinedLyr", "SWITCH_SELECTION", "")
        count2 = int(gp.GetCount_management("combinedLyr").getOutput(0))
        if count2 > 0:
            AddMsgAndPrint("\tSetting "  + str(count2) + " non-cultivated combined group(s) to natural state",0)
            gp.CalculateField_management("combinedLyr", "HYDGROUP", "\"D\"", "VB", "")
        del count2
        
    del count
    
    # Set any possible remaing nulls to "W", which will assign a RCN of 99    
    query = "\"HYDGROUP\" Is Null"
    gp.SelectLayerByAttribute_management(soilsLyr, "NEW_SELECTION", query)
    count = int(gp.GetCount_management(soilsLyr).getOutput(0))
    del query
    if count > 0:
        AddMsgAndPrint("\n\tThere are " + str(count) + " null hydro group(s) remaining",0)
        AddMsgAndPrint("\t\tA RCN value of 99 will be applied to these areas",0)
        gp.CalculateField_management(soilsLyr, "HYDGROUP", "\"W\"", "VB", "")
    del count

    # Clear any remaining selections
    gp.SelectLayerByAttribute_management(soilsLyr, "CLEAR_SELECTION", "")    
    
    # Join NLCD Lookup table to populate HYD_CODE field
    gp.AddJoin_management(soilsLyr, "HYDGROUP", NLCD_RCN_TABLE, "Soil", "KEEP_ALL")
    gp.CalculateField_management(soilsLyr, "" + str(os.path.basename(wsSoils)) + ".HYD_CODE", "[NLCD_RCN_TABLE.ID]", "VB", "")
    gp.RemoveJoin_management(soilsLyr, "NLCD_RCN_TABLE")

    # ----------------------------------------------------------------------------------------------  Create Soils Raster
    # Set snap raster to clipped NLCD
    gp.SnapRaster = landuse

    # Convert soils to raster using preset cellsize
    AddMsgAndPrint("\nCreating Hydro Groups Raster",1)
    gp.PolygonToRaster_conversion(soilsLyr,"HYD_CODE",SOILS_GRID,"MAXIMUM_AREA","NONE","" + str(gp.CellSize) + "")

    # ----------------------------------------------------------------------------------------------- Create Curve Number Grid

    # Combine Landuse and Soils
    gp.Combine_sa(landuse + ";" + SOILS_GRID, LU_PLUS_SOILS)
    gp.BuildRasterAttributeTable_management(LU_PLUS_SOILS)

    # Add RCN field to raster attributes
    gp.AddField_management(LU_PLUS_SOILS, "HYD_CODE", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.CalculateField_management(LU_PLUS_SOILS, "HYD_CODE", "([NLCD] * 100) + [SOILS]", "VB", "")
    gp.AddField_management(LU_PLUS_SOILS, "LANDUSE", "TEXT", "", "", "255", "", "NULLABLE", "NON_REQUIRED", "")
    gp.AddField_management(LU_PLUS_SOILS, "HYD_GROUP", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.AddField_management(LU_PLUS_SOILS, "RCN", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.AddField_management(LU_PLUS_SOILS, "ACRES", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.AddField_management(LU_PLUS_SOILS, "WGT_RCN", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

    # Calculate area of each combined unit in acres
    if units == "Meters":
        gp.CalculateField_management(LU_PLUS_SOILS, "ACRES", "Round([COUNT] * (" + str(cellArea) + " / 4046.86),1)", "VB", "")
    elif units == "Feet":
        gp.CalculateField_management(LU_PLUS_SOILS, "ACRES", "Round([COUNT] * (" + str(cellArea) + " / 43560),1)", "VB", "")
    else:
        pass
    
    # Sum the count (equivalent to area) for each CN in watershed
    gp.Statistics_analysis(LU_PLUS_SOILS, RCN_Stats,"COUNT sum","")
    
    # Join NLCD Lookup table to retrieve RCN and desc values
    gp.MakeRasterLayer_management(LU_PLUS_SOILS, "LU_PLUS_SOILS_LYR")
    gp.AddJoin_management("LU_PLUS_SOILS_LYR", "HYD_CODE", NLCD_RCN_TABLE, "Join_", "KEEP_ALL")
    gp.CalculateField_management("LU_PLUS_SOILS_LYR", "VAT_LU_PLUS_SOILS.RCN", "[NLCD_RCN_TABLE.CN]", "VB", "")
    gp.CalculateField_management("LU_PLUS_SOILS_LYR", "VAT_LU_PLUS_SOILS.LANDUSE", "[NLCD_RCN_TABLE.NRCS_LANDUSE]", "VB", "")
    gp.CalculateField_management("LU_PLUS_SOILS_LYR", "VAT_LU_PLUS_SOILS.HYD_GROUP", "[NLCD_RCN_TABLE.Soil]", "VB", "")

    # -------------------------------------------------------------------------------- Weight Curve Number    
    # Retrieve the total area (Watershed Area)
    rows = gp.searchcursor(RCN_Stats)
    row = rows.next()
    wsArea = row.SUM_COUNT
    
    # Multiply CN by percent of area to weight
    gp.CalculateField_management(LU_PLUS_SOILS, "WGT_RCN", "[RCN] * ([COUNT] / " + str(float(wsArea)) + ")", "VB", "")
    
    # Sum the weights to create weighted RCN
    gp.Statistics_analysis(LU_PLUS_SOILS, RCN_Stats2,"WGT_RCN sum","")
    wgtrows = gp.searchcursor(RCN_Stats2)
    wgtrow = wgtrows.next()
    wgtRCN = wgtrow.SUM_WGT_RCN
    AddMsgAndPrint("\n\tWeighted Average Runoff Curve No. for " + str(wsName) + " is " + str(int(wgtRCN)),0)

    
    del wsArea
    del rows
    del row 
    del wgtrows
    del wgtrow
    
    # Export RCN Summary Table
    gp.CopyRows_management(LU_PLUS_SOILS, RCN_TABLE)
    
    # Delete un-necessary fields from summary table
    gp.DeleteField_management(RCN_TABLE, "VALUE;COUNT;SOILS;HYD_CODE;HYD_CODE;WGT_RCN")
    
    # ------------------------------------------------------------------ Pass results to user watershed
    
    AddMsgAndPrint("\nAdding RCN results to " + str(wsName) + "'s attributes",1)
    if not len(gp.ListFields(watershed,"RCN")) > 0:
        gp.AddField_management(watershed, "RCN", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.CalculateField_management(watershed, "RCN", "" + str(wgtRCN) + "", "VB", "")

    del wgtRCN
            
    # ------------------------------------------------------------------ Optional: Create Runoff Curve Number Grid
    

   
    if createRCN:
        AddMsgAndPrint("\nCreating Curve Number Raster...",1)
    
        # If user provided a snap raster, assign from input        
        if len(snapRaster) > 0:
            gp.SnapRaster = snapRaster
            gp.OutputCoordinateSystem = outCoordSys
            gp.CellSize = outCellSize
            del outCoordSys, outCellSize
        else:
            gp.SnapRaster = landuse
            gp.CellSize = cellSize
            
        # Convert Combined Raster to Curve Number grid
        gp.Lookup_sa(LU_PLUS_SOILS, "RCN", RCN_GRID)
        AddMsgAndPrint("\nSuccessfully Created Runoff Curve Number Grid",1)


    # ----------------------------------------------------- Delete Intermediate data
    layersToRemove = (LU_PLUS_SOILS,CULT_GRID,CULT_POLY,SOILS_GRID,RCN_Stats,RCN_Stats2,landuse)

    x = 0        
    for layer in layersToRemove:

        if gp.exists(layer):

            # strictly for formatting
            if x == 0:
                AddMsgAndPrint("\nDeleting intermediate data...",1)
                x += 1
            
            try:
                gp.delete_management(layer)
            except:
                pass

    del x, layersToRemove
    
    # ----------------------------------------------------------------------- Compact FGDB
    try:
        gp.compact_management(watershedGDB_path)
        AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path),1)    
    except:
        pass
    
    # ------------------------------------------------------------ Prepare to Add to Arcmap

    if externalWshd:
        gp.SetParameterAsText(6, watershed)
    if createRCN:
        gp.SetParameterAsText(7, RCN_GRID)
        
    gp.SetParameterAsText(8, RCN_TABLE)
    
    AddMsgAndPrint("\nAdding Output to ArcMap",1)
    
    gp.RefreshCatalog(watershedGDB_path)

    # Restore original environments
    gp.extent = tempExtent
    gp.mask = tempMask
    gp.SnapRaster = tempSnapRaster
    gp.CellSize = tempCellSize
    gp.OutputCoordinateSystem = tempCoordSys

    # ------------------------------------------------------------ Cleanup
    try:
        del gp
        del inWatershed
        del inNLCD
        del inSoils
        del inputField
        del watershedGDB_path
        del watershedFD
        del watershedGDB_name
        del userWorkspace
        del wsName
        del textFilePath
        del LU_PLUS_SOILS
        del CULT_GRID
        del CULT_POLY
        del soilsLyr
        del SOILS_GRID
        del RCN_Stats
        del RCN_Stats2    
        del wsSoils
        del landuse
        del watershed
        del RCN_GRID
        del NLCD_RCN_TABLE
        del externalWshd
        del FGDBexists
        del units
        del ArcGIS10
        del version
        del curveNoGrid
        del snapRaster
        del createRCN
        del tempExtent
        del tempMask
        del tempSnapRaster
        del tempCellSize
        del tempCoordSys
        del rcnOut
        del soilsOut  
    except:
        pass
    
except SystemExit:
    pass

except KeyboardInterrupt:
    AddMsgAndPrint("Interruption requested....exiting")

except:
    print_exception()    
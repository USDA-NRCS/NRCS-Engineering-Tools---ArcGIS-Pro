# Wascob_Attributes.py
#
## ================================================================================================================
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
                #gp.AddMessage("    ")
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
    f.write("Executing \"4. Wascob Watershed Attributes\" Tool\n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write("User Parameters:\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tInput Watershed: " + wsName + "\n")
    f.write("\tInput Soils: " + inSoils + "\n")

    if len(inCLU) > 0:
        f.write("\tInput CLU: " + inCLU + "\n")

    else:
        f.write("\tInput CLU: BLANK" + "\n")
        
    f.close
    del f

## ================================================================================================================
def splitThousands(someNumber):
# will determine where to put a thousands seperator if one is needed.
# Input is an integer.  Integer with or without thousands seperator is returned.

    import re

    try:
 
        return re.sub(r'(\d{3})(?=\d)', r'\1,', str(int(round(someNumber)))[::-1])[::-1]        
    
    except:
        print_exception()
        return someNumber    

## ================================================================================================================
# Import system modules
import sys, os, string, arcgisscripting, traceback, re, math

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

    # Check out SA license
    if gp.CheckExtension("spatial") == "Available":
        gp.CheckOutExtension("spatial")
    else:
        AddMsgAndPrint("\n\n\tSpatial Analyst Extension not enabled. Please enable Spatial analyst from the Tools/Extensions menu..EXITING\n",1)
        sys.exit("")
    # ---------------------------------------------------------------------------- Input Parameters

    inWatershed = gp.GetParameterAsText(0)
    inSoils = gp.GetParameterAsText(1)  
    inputField = gp.GetParameterAsText(2)
    inCLU = gp.GetParameterAsText(3)

    # Determine if CLU is present
    if len(str(inCLU)) > 0:
        inCLU = gp.Describe(inCLU).CatalogPath
        splitLU = True
    else:
        splitLU = False 
    
    # ---------------------------------------------------------------------------- Define Variables 
    watershed_path = gp.Describe(inWatershed).CatalogPath
    watershedGDB_path = watershed_path[:watershed_path .find(".gdb")+4]
    watershedGDB_name = os.path.basename(watershedGDB_path)
    watershedFD = watershedGDB_path + os.sep + "Layers"
    userWorkspace = os.path.dirname(watershedGDB_path)
    projectName = gp.ValidateTablename(os.path.basename(userWorkspace).replace(" ","_"))
    projectAOI = watershedFD + os.sep + projectName + "_AOI"
    projectAOI_path = arcpy.Describe(projectAOI).CatalogPath
    wsName = os.path.splitext(os.path.basename(inWatershed))[0]
    outputFolder = userWorkspace + os.sep + "gis_output"
    tables = outputFolder + os.sep + "tables"
    
    if not gp.Exists(outputFolder):
        gp.CreateFolder_management(userWorkspace, "gis_output")
    if not gp.Exists(tables):
        gp.CreateFolder_management(outputFolder, "tables")    

    ReferenceLine = "ReferenceLine"
    DEM_aoi = watershedGDB_path + os.sep + projectName + "_Raw_DEM"
    ProjectDEM = watershedGDB_path + os.sep + projectName + "_Project_DEM"
    DEMsmooth = watershedGDB_path + os.sep + "_DEMsmooth"

    # log File Path
    textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.txt"    
    # record basic user inputs and settings to log file for future purposes
    logBasicSettings()
    
    # -------------------------------------------------------------------------- Permanent Datasets
    wsSoils = watershedFD + os.sep + wsName + "_Soils"
    landuse = watershedFD + os.sep + wsName + "_Landuse"
    storageTable = tables + os.sep + "storage.dbf"
    embankmentTable = tables + os.sep + "embankments.dbf"
    
    # -------------------------------------------------------------------------- Temporary Datasets
    cluClip = watershedFD + os.sep + "cluClip"
    watershedDissolve = watershedGDB_path + os.sep + "watershedDissolve"
    wtshdDEMsmooth = watershedGDB_path + os.sep + "wtshdDEMsmooth"
    slopeGrid = watershedGDB_path + os.sep + "slopeGrid"
    slopeStats = watershedGDB_path + os.sep + "slopeStats"
    outletBuffer = watershedGDB_path + os.sep + "Layers" + os.sep + "outletBuffer"
    outletStats = watershedGDB_path + os.sep + "outletStats"
    subMask = watershedFD + os.sep + "subbasin_mask"
    subGrid = watershedGDB_path + os.sep + "subElev"   
    #storageTemp = tables + os.sep + "storageTemp"
    storageTemp = watershedGDB_path + os.sep + "storageTemp"
    
    # -------------------------------------------------------------------------- Tables
    TR_55_LU_Lookup = os.path.join(os.path.dirname(sys.argv[0]), "Support.gdb" + os.sep + "TR_55_LU_Lookup")
    Hydro_Groups_Lookup = os.path.join(os.path.dirname(sys.argv[0]), "Support.gdb" + os.sep + "HydroGroups")
    Condition_Lookup = os.path.join(os.path.dirname(sys.argv[0]), "Support.gdb" + os.sep + "ConditionTable")    
    storageTemplate = os.path.join(os.path.dirname(sys.argv[0]), "storage.dbf")    

    # ----------------------------------------------------------------------------- Check Some Parameters
    # Exit if any are true
    if not int(gp.GetCount_management(inWatershed).getOutput(0)) > 0:
        AddMsgAndPrint("\n\nWatershed Layer is empty.....Exiting!",2)
        sys.exit()
        
    if gp.Describe(inWatershed).ShapeType != "Polygon":
        AddMsgAndPrint("\n\nYour Watershed Layer must be a polygon layer!.....Exiting!",2)
        sys.exit()

    if gp.Describe(inSoils).ShapeType != "Polygon":
        AddMsgAndPrint("\n\nYour Soils Layer must be a polygon layer!.....Exiting!",2)
        sys.exit()

    if splitLU:
        if gp.Describe(inCLU).ShapeType != "Polygon":
            AddMsgAndPrint("\n\nYour CLU Layer must be a polygon layer!.....Exiting!",2)
            sys.exit()

    if not len(gp.ListFields(inSoils,inputField)) > 0:
        AddMsgAndPrint("\nThe field specified for Hydro Groups does not exist in your soils data.. please specify another name and try again..EXITING",2)
        sys.exit("")

    if not gp.Exists(TR_55_LU_Lookup):
        AddMsgAndPrint("\n\n\"TR_55_LU_Lookup\" was not found! Make sure \"Support.gdb\" is located within the same location as this script",2)
        sys.exit("")

    if not gp.Exists(Hydro_Groups_Lookup):
        AddMsgAndPrint("\n\n\"Hydro_Groups_Lookup\" was not found! Make sure \"Support.gdb\" is located within the same location as this script",2)
        sys.exit("")

    if not gp.Exists(Condition_Lookup):
        AddMsgAndPrint("\n\n\"Condition_Lookup\" was not found! Make sure \"Support.gdb\" is located within the same location as this script",2)
        sys.exit("")          

    # ------------------------------------- Remove domains from fields if they exist
    desc = gp.describe(watershedGDB_path)
    listOfDomains = []

    domains = desc.Domains

    for domain in domains:
        listOfDomains.append(domain)

    del desc, domains

    if "LandUse_Domain" in listOfDomains:
        try:
            gp.RemoveDomainFromField(landuse, "LANDUSE")
        except:
            pass
    if "Condition_Domain" in listOfDomains:
        try:
            gp.RemoveDomainFromField(landuse, "CONDITION")
        except:
            pass

    if "Hydro_Domain" in listOfDomains:
        try:
            gp.RemoveDomainFromField(wsSoils, "HYDGROUP")
        except:
            pass
        
    del listOfDomains

    # ------------------------------------------------------------------------------- Remove existing layers from ArcMap
    # ---------------------------------------------------- Feature Layers in Arcmap
    landuseOut = "Watershed_Landuse"
    soilsOut = "Watershed_Soils"
    
    layersToRemove = (landuseOut,soilsOut)

    x = 0
    for layer in layersToRemove:
        
        if gp.exists(layer):
            if x == 0:
                AddMsgAndPrint("",1)
                x+=1
                
            try:
                gp.delete_management(layer)
                AddMsgAndPrint("Removing previous" + layer + " from your ArcMap Session",1)
            except:
                pass

    del x, layer, layersToRemove

    # -------------------------------------------------------------------------- Delete Previous Data if present
    datasetsToRemove = (wsSoils,landuse,cluClip,wtshdDEMsmooth,slopeGrid,slopeStats,watershedDissolve,cluClip,storageTemp,subMask,subGrid,outletStats,outletBuffer)

    x = 0
    for dataset in datasetsToRemove:

        if gp.exists(dataset):

            if x < 1:
                AddMsgAndPrint("\nRemoving old datasets from FGDB: " + watershedGDB_name ,1)
                x += 1
                
            try:
                gp.delete_management(dataset)
                AddMsgAndPrint("\tDeleting....." + os.path.basename(dataset),0)
            except:
                pass
            
    del dataset
    del datasetsToRemove
    del x
    
    # ------------------------------------------------------------------ Update inWatershed Area in case of user edits
    wsUnits = gp.Describe(inWatershed).SpatialReference.LinearUnitName

    # Clear any selections 
    gp.SelectLayerByAttribute_management(inWatershed, "CLEAR_SELECTION", "")

    AddMsgAndPrint("\nUpdating drainage area(s)",1)
    
    if len(gp.ListFields(inWatershed, "Acres")) < 1:
        gp.AddField_management(inWatershed, "Acres", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        
    if wsUnits == "Meter":
        gp.CalculateField_management(inWatershed, "Acres", "[Shape_Area]/4046.86", "VB", "")
        units = "Meters"
        AddMsgAndPrint("\n\tSuccessfully Updated Drainage Area(s)",0)
        displayAreaInfo = True
    elif wsUnits == "Foot":
        gp.CalculateField_management(inWatershed, "Acres", "[Shape_Area]/43560", "VB", "")
        units = "Feet"
        AddMsgAndPrint("\n\tSuccessfully Updated Drainage Area(s)",0)
        displayAreaInfo = True
    elif wsUnits == "Foot_US":
        gp.CalculateField_management(inWatershed, "Acres", "[Shape_Area]/43560", "VB", "")
        units = "Feet"
        AddMsgAndPrint("\n\tSuccessfully Updated Drainage Area(s)",0)
        displayAreaInfo = True
    else:
        AddMsgAndPrint("\n\tinWatershed Linear Units UNKNOWN, unable to update Drainage Area(s)",0)
        displayAreaInfo = False
        
    # ------------------------------------------------------------------------ Get DEM Properties
##
##    if not gp.Exists(DEM_aoi):
##        
##        if gp.Exists("Project_DEM"):
##            # If Project DEM is Missing in GDB but present in TOC set to TOC lyr
##            DEM_aoi = "Project_DEM"      
##        else:
##            # Exit if not present either place and instruct user on remedy...
##            AddMsgAndPrint("\nMissing Project_DEM from FGDB. Can not perform raster analysis.",2)
##            AddMsgAndPrint("Project_DEM must be in the same geodatabase as your input watershed.",2)
##            AddMsgAndPrint("\nCheck your the source of your provided watershed.",2)
##            AddMsgAndPrint("and/or export ProjectDEM from the table of contents to",2)
##            AddMsgAndPrint("the geodatabase where your provided watershed resides",2)
##            AddMsgAndPrint("as "+ str(watershedGDB_path) + "/Project_DEM...EXITING",2)
##            sys.exit("")
        
    desc = gp.Describe(DEM_aoi)
    sr = desc.SpatialReference
    cellSize = desc.MeanCellWidth
    DEMunits = sr.LinearUnitName

    if DEMunits == "Meter":
        units = "Meters"
        Zfactor = 0.3048            # 0.3048 meters in a foot
        ftConversion = 0.092903     # 0.093 sq meters in 1 foot
        volConversion = 35.3147     # 31.3147 cubic ft in 1 cu Meter
        
    else:
        units = "Feet"
        Zfactor = 1                 # XY Units are the same as Z
        ftConversion = 1            # XY Units are the same as Z
        volConversion = 1           # XY Units are the same as Z

    # ----------------------------------------------------------------------- Capture Default Environments
    tempExtent = gp.Extent
    tempMask = gp.mask
    tempSnapRaster = gp.SnapRaster
    tempCellSize = gp.CellSize
    tempCoordSys = gp.OutputCoordinateSystem
    
    # ----------------------------------- Set Environment Settings
    gp.Extent = "MAXOF"
    gp.CellSize = cellSize
    gp.mask = ""
    gp.SnapRaster = ""
    gp.OutputCoordinateSystem = sr
    
    # ----------------------------------------------------------------------- Calculate Average Slope        
    calcAvgSlope = False
    AddMsgAndPrint("\nUpdating average slope",1)

        
    if gp.exists(DEMsmooth):
        
        gp.ExtractByMask_sa(DEMsmooth, inWatershed, wtshdDEMsmooth)
        gp.Slope_sa(wtshdDEMsmooth, slopeGrid, "PERCENT_RISE", Zfactor)
        gp.ZonalStatisticsAsTable_sa(inWatershed, "Subbasin", slopeGrid, slopeStats, "DATA")
        calcAvgSlope = True

        # Delete unwanted rasters
        gp.delete_management(DEMsmooth)
        gp.delete_management(wtshdDEMsmooth)
        gp.delete_management(slopeGrid)

    else:
        
        # Run Focal Statistics on the DEM_aoi for the purpose of generating smoothed interpretation of slope
        gp.focalstatistics_sa(DEM_aoi, DEMsmooth,"RECTANGLE 3 3 CELL","MEAN","DATA")

        gp.ExtractByMask_sa(DEMsmooth, inWatershed, wtshdDEMsmooth)
        gp.Slope_sa(wtshdDEMsmooth, slopeGrid, "PERCENT_RISE", Zfactor)
        gp.ZonalStatisticsAsTable_sa(inWatershed, "Subbasin", slopeGrid, slopeStats, "DATA")
        calcAvgSlope = True

        # Delete unwanted rasters
        gp.delete_management(DEMsmooth)
        gp.delete_management(wtshdDEMsmooth)
        gp.delete_management(slopeGrid)   

    # -------------------------------------------------------------------------------------- Update inWatershed FC with Average Slope
    if calcAvgSlope:
        
        # go through each zonal Stat record and pull out the Mean value
        rows = gp.searchcursor(slopeStats)
        row = rows.next()

        AddMsgAndPrint("\n\tSuccessfully updated Average Slope",0)

        while row:
            wtshdID = row.OBJECTID
            
            # zonal stats doesnt generate "Value" with the 9.3 geoprocessor in 10
            if len(gp.ListFields(slopeStats,"Value")) > 0:
                zonalValue = row.VALUE
            else:
                zonalValue = row.SUBBASIN
   
            zonalMeanValue = row.MEAN

            whereclause = "Subbasin = " + str(zonalValue)
            wtshdRows = gp.UpdateCursor(inWatershed,whereclause)
            wtshdRow = wtshdRows.next()           

            # Pass the Mean value from the zonalStat table to the watershed FC.
            while wtshdRow:
                wtshdRow.Avg_Slope = zonalMeanValue
                wtshdRows.UpdateRow(wtshdRow)

                # Inform the user of Watershed Acres, area and avg. slope
                if displayAreaInfo:
                    
                    # Inform the user of Watershed Acres, area and avg. slope                    
                    AddMsgAndPrint("\n\tSubbasin ID: " + str(wtshdRow.OBJECTID),1)
                    AddMsgAndPrint("\t\tAcres: " + str(splitThousands(round(wtshdRow.Acres,2))),0)
                    AddMsgAndPrint("\t\tArea: " + str(splitThousands(round(wtshdRow.Shape_Area,2))) + " Sq. " + units,0)
                    AddMsgAndPrint("\t\tAvg. Slope: " + str(round(zonalMeanValue,2)),0)


                else:
                    AddMsgAndPrint("\tWatershed ID: " + str(wtshdRow.OBJECTID) + " is " + str(zonalMeanValue),1)
                                   
                break

            row = rows.next()        

            del wtshdID
            del zonalValue
            del zonalMeanValue
            del whereclause
            del wtshdRows
            del wtshdRow

        del rows
        del row
        
        gp.delete_management(slopeStats)    
    # ------------------------------------------------------------------------ Update reference line / Perform storage calculations                          
    calcSurfaceVol = False

    if gp.Exists(ReferenceLine):
        calcSurfaceVol = True
        
    if not gp.Exists(ReferenceLine):
        if gp.Exists(watershedFD + os.sep + "ReferenceLine"):
            ReferenceLine = watershedFD + os.sep + "ReferenceLine"
            calcSurfaceVol = True
        else:
            AddMsgAndPrint("\nReference Line not found in table of contents or in the workspace of your input watershed,",2)
            AddMsgAndPrint("Unable to update attributed perform surface volume calculations.",2)
            AddMsgAndPrint("\nYou will have to either correct the workspace issue or manually derive",2)
            AddMsgAndPrint("surface / volume calculations for " + str(wsName),2)
            calcSurfaceVol = False
# -------------------------------------------------------------------------- Update Reference Line Attributes
    if calcSurfaceVol:
        AddMsgAndPrint("\nUpdating Reference Line Attributes...",1)
        gp.CalculateField_management(ReferenceLine, "LengthFt","!shape.length@FEET!", "PYTHON", "")

        # Calculations here seem to be the same. Why do we have a check at all if bufferSize is cellSize * 2 in all cases?
        # Was there supposed to be an exit if the DEM resolution was too large? Or a default buffersize in the absence of input information?
        # Buffer outlet features by  raster cell size - dissolving by Subbasin ID
        if units == "Meters":
            if cellSize < 3:
                bufferSize = cellSize * 2
        elif units == "Feet":
            if cellSize < 10:
                bufferSize = cellSize * 2

        # suggested add by Minnesota to account for DEMs of 3m or larger.
        else:
            bufferSize = cellSize * 2

        
        bufferDist = "" + str(bufferSize) + " " + str(units) + ""    
        gp.Buffer_analysis(ReferenceLine, outletBuffer, bufferDist, "FULL", "ROUND", "LIST", "Subbasin")
        del bufferSize, bufferDist

        # Get Reference Line Elevation Properties
        gp.ZonalStatisticsAsTable_sa(outletBuffer, "Subbasin", ProjectDEM, outletStats, "DATA")
        
        rows = gp.searchcursor(outletStats)
        row = rows.next()

        while row:
            wtshdID = row.OBJECTID

            # zonal stats doesnt generate "Value" with the 9.3 geoprocessor
            if len(gp.ListFields(outletStats,"Value")) > 0:
                zonalValue = row.VALUE
            else:
                zonalValue = row.SUBBASIN

            zonalMaxValue = row.MAX   
            zonalMeanValue = row.MEAN
            zonalMinValue = row.MIN

            whereclause = "Subbasin = " + str(zonalValue)
            refRows = gp.UpdateCursor(ReferenceLine,whereclause)
            refRow = refRows.next()           

            # Pass the elevation Data to Reference Line FC.
            while refRow:
                refRow.MaxElev = zonalMaxValue
                refRow.MinElev = zonalMinValue
                refRow.MeanElev = round(zonalMeanValue,1)
                refRows.UpdateRow(refRow)
                
                break

            row = rows.next()        

            del wtshdID
            del zonalValue
            del zonalMeanValue
            del zonalMaxValue
            del zonalMinValue
            del whereclause
            del refRows
            del refRow

        del rows
        del row

        AddMsgAndPrint("\n\tSuccessfully updated Reference Line Attributes",0)
        gp.delete_management(outletStats)
        gp.delete_management(outletBuffer)

    
        # --------------------------------------------------------------------- Begin Subbasin Stage Storage Calcs
        
        AddMsgAndPrint("\nBeginning subbasin storage calculations...",1)
        gp.CopyRows_management(storageTemplate, storageTable, "")
        rows = gp.UpdateCursor(ReferenceLine)
        row = rows.Next()
        while row:
            value = row.Subbasin
            query = "Subbasin"+" = " +str(value)
            gp.SelectLayerByAttribute_management(inWatershed, "NEW_SELECTION", query)
            gp.CopyFeatures_management(inWatershed, subMask, "", "0", "0", "0")
            gp.ExtractByMask_sa(ProjectDEM, subMask, subGrid)
            AddMsgAndPrint("\n\tRetrieving Minumum Elevation for subbasin "+ str(value) + "\n",1)
            AddMsgAndPrint("\n",0)
            max = row.MaxElev
            MinElev = round(float(gp.GetRasterProperties_management(subGrid, "MINIMUM").getOutput(0)),1)
            totalElev = round(float(max - MinElev),1)
            roundElev = math.floor(totalElev)
            remainder = totalElev - roundElev
            
            Reference_Plane = "BELOW"
            plnHgt = MinElev + remainder
            outputText = tables + os.sep + "subbasin" + str(value) +".txt"

            f = open(outputText, "w")
            f.write("Dataset, Plane_heig, Reference, Z_Factor, Area_2D, Area_3D, Volume, Subbasin\n")
            f.close()
            
            while plnHgt <= max:
                Plane_Height = plnHgt
                AddMsgAndPrint("\tCalculating storage at elevation " + str(round(plnHgt,1)),0)
                gp.SurfaceVolume_3d(subGrid, outputText, Reference_Plane, Plane_Height, "1")
                plnHgt = 1 + plnHgt

            AddMsgAndPrint("\n\t\t\t\tConverting results..",1)
            gp.CopyRows_management(outputText, storageTemp, "")
            gp.CalculateField_management(storageTemp, "Subbasin", value, "VB", "")

            gp.Append_management(storageTemp, storageTable, "NO_TEST", "", "")
            gp.Delete_management(storageTemp)
            
            rows.UpdateRow(row)
            row = rows.next()
            
        del rows
        del max
        del MinElev
        del totalElev
        del roundElev
        del remainder
        del Reference_Plane
        del plnHgt
        del outputText
        
        gp.SelectLayerByAttribute_management(inWatershed, "CLEAR_SELECTION", "")

        # Convert area sq feet and volume to cu ft (as necessary)
        pool2dSqftCalc = "round([Area_2D] /" + str(ftConversion) + ",1)"
        pool3dSqftCalc = "round([Area_3D] /" + str(ftConversion) + ",1)"
        cuFootCalc = "round([Volume] *" + str(volConversion) + ",1)"
                
        gp.CalculateField_management(storageTable, "Subbasin", "\"Subbasin\" & [Subbasin]", "VB", "")
        gp.CalculateField_management(storageTable, "Area_2D", pool2dSqftCalc, "VB")
        gp.CalculateField_management(storageTable, "Area_3D", pool3dSqftCalc, "VB")
        gp.CalculateField_management(storageTable, "Volume", cuFootCalc, "VB")

        del pool2dSqftCalc
        del pool3dSqftCalc
        del cuFootCalc
        
        AddMsgAndPrint("\n\tSurface volume and area calculations completed",0)

        gp.Delete_management(subMask)
        gp.Delete_management(subGrid)
    # -------------------------------------------------------------------------- Process Soils and Landuse Data
    
    AddMsgAndPrint("\nProcessing Soils and Landuse for " + str(wsName) + "...",1)
    
    # -------------------------------------------------------------------------- Create Landuse Layer
    if splitLU:

        # Dissolve in case the watershed has multiple polygons        
        gp.Dissolve_management(inWatershed, watershedDissolve, "", "", "MULTI_PART", "DISSOLVE_LINES")

        # Clip the CLU layer to the dissolved watershed layer
        gp.Clip_analysis(inCLU, watershedDissolve, cluClip, "")
        AddMsgAndPrint("\n\tSuccessfully clipped the CLU to your Watershed Layer",0)

        # Union the CLU and dissolve watershed layer simply to fill in gaps
        gp.Union_analysis(cluClip +";" + watershedDissolve, landuse, "ONLY_FID", "", "GAPS")
        AddMsgAndPrint("\tSuccessfully filled in any CLU gaps and created Landuse Layer: " + os.path.basename(landuse),0)

        # Delete FID field
        fields = gp.ListFields(landuse,"FID*")

        for field in fields:
            gp.deletefield_management(landuse,field.Name)

        del fields

        gp.Delete_management(watershedDissolve)
        gp.Delete_management(cluClip)

    else:
        AddMsgAndPrint("\nNo CLU Layer Detected",1)

        gp.Dissolve_management(inWatershed, landuse, "", "", "MULTI_PART", "DISSOLVE_LINES")
        AddMsgAndPrint("\n\tSuccessfully created Watershed Landuse layer: " + os.path.basename(landuse),0)

    gp.AddField_management(landuse, "LANDUSE", "TEXT", "", "", "254", "", "NULLABLE", "NON_REQUIRED", "")
    gp.CalculateField_management(landuse, "LANDUSE", "\"- Select Land Use -\"", "VB", "")
    
    gp.AddField_management(landuse, "CONDITION", "TEXT", "", "", "25", "", "NULLABLE", "NON_REQUIRED", "")    
    gp.CalculateField_management(landuse, "CONDITION", "\"- Select Condition -\"", "VB", "")

    # ---------------------------------------------------------------------------------------------- Set up Domains
    desc = gp.describe(watershedGDB_path)
    listOfDomains = []

    domains = desc.Domains

    for domain in domains:
        listOfDomains.append(domain)

    del desc, domains

    if not "LandUse_Domain" in listOfDomains:
        gp.TableToDomain_management(TR_55_LU_Lookup, "LandUseDesc", "LandUseDesc", watershedGDB_path, "LandUse_Domain", "LandUse_Domain", "REPLACE")

    if not "Hydro_Domain" in listOfDomains:
        gp.TableToDomain_management(Hydro_Groups_Lookup, "HydrolGRP", "HydrolGRP", watershedGDB_path, "Hydro_Domain", "Hydro_Domain", "REPLACE")

    if not "Condition_Domain" in listOfDomains:
        gp.TableToDomain_management(Condition_Lookup, "CONDITION", "CONDITION", watershedGDB_path, "Condition_Domain", "Condition_Domain", "REPLACE")

    del listOfDomains

    # Assign Domain To Landuse Fields for User Edits...
    gp.AssignDomainToField_management(landuse, "LANDUSE", "LandUse_Domain", "")
    gp.AssignDomainToField_management(landuse, "CONDITION", "Condition_Domain", "")

    AddMsgAndPrint("\tSuccessfully added \"LANDUSE\" and \"CONDITION\" fields to Landuse Layer and associated Domains",0)

    # ---------------------------------------------------------------------------------------------------------------------------------- Work with soils
    
    # --------------------------------------------------------------------------------------- Clip Soils           
    # Clip the soils to the dissolved (and possibly unioned) watershed
    gp.Clip_analysis(inSoils,landuse,wsSoils)

    AddMsgAndPrint("\nSuccessfully clipped soils layer to Landuse layer and removed unnecessary fields",1)  
    
    # --------------------------------------------------------------------------------------- check the soils input Field to make
    # --------------------------------------------------------------------------------------- sure they are valid Hydrologic Group values
    AddMsgAndPrint("\nChecking Hydrologic Group Attributes in Soil Layer.....",1)
                   
    validHydroValues = ['A','B','C','D','A/D','B/D','C/D','W']
    valuesToConvert = ['A/D','B/D','C/D','W']
    
    rows = gp.searchcursor(wsSoils)
    row = rows.next()
    
    invalidHydValues = 0
    valuesToConvertCount = 0
    emptyValues = 0
    missingValues = 0
    
    while row:
        
        hydValue = str(row.GetValue(inputField))
        
        if len(hydValue) > 0:  # Not NULL Value
            
            if not hydValue in validHydroValues:
                invalidHydValues += 1
                AddMsgAndPrint("\t\t" + "\"" + hydValue + "\" is not a valid Hydrologic Group Attribute",0)
                
            if hydValue in valuesToConvert:
                valuesToConvertCount += 1
                #AddMsgAndPrint("\t" + "\"" + hydValue + "\" needs to be converted -------- " + str(valuesToConvertCount),1)

        else: # NULL Value
            emptyValues += 1
                            
        row = rows.next()
 
    del rows, row        

    # ------------------------------------------------------------------------------------------- Inform the user of Hydgroup Attributes
    if invalidHydValues > 0:
        AddMsgAndPrint("\t\tThere are " + str(invalidHydValues) + " invalid attributes found in your Soil's " + "\"" + inputField + "\"" + " Field",0)

    if valuesToConvertCount > 0:
        AddMsgAndPrint("\t\tThere are " + str(valuesToConvertCount) + " attributes that need to be converted to a single class i.e. \"B/D\" to \"B\"",0)

    if emptyValues > 0:
        AddMsgAndPrint("\t\tThere are " + str(emptyValues) + " NULL polygon(s) that need to be attributed with a Hydrologic Group",0)

    if emptyValues == int(gp.GetCount_management(inSoils).getOutput(0)):
        AddMsgAndPrint("\t\t" + "\"" + inputField + "\"" + "Field is blank.  It must be populated before using the 2nd tool!",0)
        missingValues = 1
    del validHydroValues, valuesToConvert, invalidHydValues

    # ------------------------------------------------------------------------------------------- Compare Input Field to SSURGO HydroGroup field name
    if inputField.upper() != "HYDGROUP":
        gp.AddField_management(wsSoils, "HYDGROUP", "TEXT", "", "", "20", "", "NULLABLE", "NON_REQUIRED", "")

        if missingValues == 0:
            gp.CalculateField_management(wsSoils, "HYDGROUP", "[" + str(inputField) + "]", "VB", "")

        else:
            AddMsgAndPrint("\n\tAdded " + "\"HYDGROUP\" to soils layer.  Please Populate the Hydrologic Group Values manually for this field",0)

    # Delete any field not in the following list
    fieldsToKeep = ["MUNAME","MUKEY","HYDGROUP","MUSYM","OBJECTID"]

    fields = gp.ListFields(wsSoils)

    for field in fields:
        
        fieldName = field.Name
        
        if not fieldName.upper() in fieldsToKeep and fieldName.find("Shape") < 0:
            gp.deletefield_management(wsSoils,fieldName)

    del fields, fieldsToKeep, missingValues

    gp.AssignDomainToField_management(wsSoils, "HYDGROUP", "Hydro_Domain", "")


    # ---------------------------------------------------------------------------------------------------------------------------- Compact FGDB
    try:
        gp.compact_management(watershedGDB_path)
        AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path),1)
    except:
        pass
    # --------------------------------------------------------------------------------------------------------------------------- Prepare to Add to Arcmap
    
    gp.SetParameterAsText(4, wsSoils)
    gp.SetParameterAsText(5, landuse)

    # Copy refernce line to embankment table
##    gp.SelectLayerByAttribute_management(ReferenceLine, "CLEAR_SELECTION", "")
    gp.CopyRows_management(ReferenceLine, embankmentTable, "")
    
    AddMsgAndPrint("\nAdding Layers to ArcMap",1)

    AddMsgAndPrint("\n\t=========================================================================",0)
    AddMsgAndPrint("\tBEFORE CALCULATING THE RUNOFF CURVE NUMBER FOR YOUR WATERSHED MAKE SURE TO",1)
    AddMsgAndPrint("\tATTRIBUTE THE \"LANDUSE\" AND \"CONDITION\" FIELDS IN " + os.path.basename(landuse) + " LAYER",1)
    
    if valuesToConvertCount > 0:
        AddMsgAndPrint("\tAND CONVERT THE " + str(valuesToConvertCount) + " COMBINED HYDROLOGIC GROUPS IN " + os.path.basename(wsSoils) + " LAYER",1)
        
    if emptyValues > 0:
        AddMsgAndPrint("\tAS WELL AS POPULATE VALUES FOR THE " + str(emptyValues) + " NULL POLYGONS IN " + os.path.basename(wsSoils) + " LAYER",1)
        
    AddMsgAndPrint("\t=========================================================================\n",0)
    
    import time
    time.sleep(3)

    del valuesToConvertCount, emptyValues    

    # -------------------------------------------------------------------------------- Clean Up
    gp.RefreshCatalog(watershedGDB_path)
    
    # Restore original environments
    gp.extent = tempExtent
    gp.mask = tempMask
    gp.SnapRaster = tempSnapRaster
    gp.CellSize = tempCellSize
    gp.OutputCoordinateSystem = tempCoordSys
    
    try:
        del inWatershed
        del inSoils
        del inputField
        del inCLU
        del splitLU
        del watershed_path
        del watershedGDB_path
        del watershedFD
        del userWorkspace
        del wsName
        del wsSoils
        del landuse
        del textFilePath
        del cluClip
        del landuseOut
        del soilsOut
        del TR_55_LU_Lookup
        del Hydro_Groups_Lookup
        del Condition_Lookup
        del ReferenceLine
        del DEM_aoi
        del DEMsmooth
        del outletBuffer
        del outletStats
        del subMask
        del subGrid
        del storageTemp
        del storageTemplate
        del desc
        del sr
        del DEMunits
        del Zfactor
        del slopeGrid
        del slopeStats
        del wsUnits
        del tables
        del calcSurfaceVol
        del embankmentTable
        del clipMask
        del soilLyrFile
        del landuseOutLyrFile
        del gp
        del tempExtent
        del tempMask
        del tempSnapRaster
        del tempCellSize
        del tempCoordSys
    except:
        pass
except SystemExit:
    pass

except KeyboardInterrupt:
    AddMsgAndPrint("Interruption requested....exiting")

except:
    print_exception()
    
    

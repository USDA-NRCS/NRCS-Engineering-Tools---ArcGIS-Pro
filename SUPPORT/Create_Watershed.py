# Create_Watershed.py
## ================================================================================================================ 
def print_exception():
    
    tb = sys.exc_info()[2]
    l = traceback.format_tb(tb)
    l.reverse()
    tbinfo = "".join(l)
    AddMsgAndPrint("\n----------------------------------- ERROR Start -----------------------------------",2)
    AddMsgAndPrint("Traceback Info:\n" + tbinfo + "Error Info:\n    " +  str(sys.exc_type)+ ": " + str(sys.exc_value) + "",2)
    AddMsgAndPrint("------------------------------------- ERROR End -----------------------------------\n",2)

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
    f.write("Executing \"3. Create Watershed\" for ArcGIS 9.3 and 10\n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write("ArcGIS Version: " + str(version) + "\n")
    f.write("User Parameters:\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tStreams: " + streamsPath + "\n")
    
    if int(gp.GetCount_management(outlet).getOutput(0)) > 0:
        f.write("\toutlet Digitized: " + str(gp.GetCount_management(outlet)) + "\n")
    else:
        f.write("\toutlet Digitized: 0\n")
    f.write("\tWatershed Name: " + watershedOut + "\n")
    if calcLHL:    
        f.write("\tCreate flow paths: SELECTED\n")
    else:
        f.write("\tCreate flow paths: NOT SELECTED\n")
        
    f.close
    del f

## ================================================================================================================
def determineOverlap(outletsLayer):
    # This function will compute a geometric intersection of the project_AOI boundary and the outlet
    # layer to determine overlap.

    try:
        # Make a layer from the project_AOI
        if gp.exists("AOI_lyr"):
            gp.delete_management("AOI_lyr")

        gp.MakeFeatureLayer(projectAOI,"AOI_lyr")

        if gp.exists("outletsTempLyr"):
            gp.delete_management("outletsTempLyr")

        gp.MakeFeatureLayer(outletsLayer,"outletsTempLyr")

        numOfOutlets = int((gp.GetCount_management(outletsLayer)).GetOutput(0))

        # Select all outlets that are completely within the AOI polygon
        gp.SelectLayerByLocation("outletsTempLyr", "completely_within", "AOI_lyr")
        numOfOutletsWithinAOI = int((gp.GetCount_management("outletsTempLyr")).GetOutput(0))

        # There are no outlets completely within AOI; may be some on the AOI boundary
        if numOfOutletsWithinAOI == 0:

            gp.SelectLayerByAttribute_management("outletsTempLyr", "CLEAR_SELECTION", "")
            gp.SelectLayerByLocation("outletsTempLyr", "crossed_by_the_outline_of", "AOI_lyr")

            # Check for outlets on the AOI boundary
            numOfIntersectedOutlets = int((gp.GetCount_management("outletsTempLyr")).GetOutput(0))

            # No outlets within AOI or intersecting AOI
            if numOfIntersectedOutlets == 0:

                AddMsgAndPrint("\tAll outlets are outside of your Area of Interest",2)
                AddMsgAndPrint("\tRedigitize your outlets so that they are within your Area of Interest\n",2)  
            
                gp.delete_management("AOI_lyr")
                gp.delete_management("outletsTempLyr")
                del numOfOutlets
                del numOfOutletsWithinAOI
                del numOfIntersectedOutlets
                
                return False

            # There are some outlets on AOI boundary but at least one outlet completely outside AOI
            else:

                # All outlets are intersecting the AOI boundary
                if numOfOutlets == numOfIntersectedOutlets:
                    
                    AddMsgAndPrint("\n\tAll Outlet(s) are intersecting the AOI Boundary",0)
                    AddMsgAndPrint("\tOutlets will be clipped to AOI",0)

                # Some outlets intersecting AOI and some completely outside.
                else:
                    
                    AddMsgAndPrint("\n\tThere is " + str(numOfOutlets - numOfOutletsWithinAOI) + " outlet(s) completely outside the AOI Boundary",0)
                    AddMsgAndPrint("\tOutlet(s) will be clipped to AOI",0)

                clippedOutlets = watershedGDB_path + os.sep + "Layers" + os.sep + projectName + "_clippedOutlets"
                gp.Clip_analysis(outletsLayer, projectAOI, clippedOutlets)

                gp.delete_management("AOI_lyr")
                gp.delete_management("outletsTempLyr")
                del numOfOutlets
                del numOfOutletsWithinAOI
                del numOfIntersectedOutlets

                gp.delete_management(outletFC)
                gp.rename(clippedOutlets,outletFC)

                AddMsgAndPrint("\n\t" + str(int(gp.GetCount_management(outletFC).getOutput(0))) + " Outlet(s) will be used to create watershed(s)",0) 
                
                return True
        
        # all outlets are completely within AOI; Ideal scenario
        elif numOfOutletsWithinAOI == numOfOutlets:

            AddMsgAndPrint("\n\t" + str(numOfOutlets) + " Outlet(s) will be used to create watershed(s)",0)            
            
            gp.delete_management("AOI_lyr")
            gp.delete_management("outletsTempLyr")
            del numOfOutlets
            del numOfOutletsWithinAOI            
            
            return True

        # combination of scenarios.  Would require multiple outlets to have been digitized. A
        # will be required.
        else:

            gp.SelectLayerByAttribute_management("outletsTempLyr", "CLEAR_SELECTION", "")
            gp.SelectLayerByLocation("outletsTempLyr", "crossed_by_the_outline_of", "AOI_lyr")

            numOfIntersectedOutlets = int((gp.GetCount_management("outletsTempLyr")).GetOutput(0))

            AddMsgAndPrint("\t" + str(numOfOutlets) + " Outlets digitized",0)            

            # there are some outlets crossing the AOI boundary and some within.
            if numOfIntersectedOutlets > 0 and numOfOutletsWithinAOI > 0:

                AddMsgAndPrint("\n\tThere is " + str(numOfIntersectedOutlets) + " outlet(s) intersecting the AOI Boundary",0)
                AddMsgAndPrint("\tOutlet(s) will be clipped to AOI",0)

            # there are some outlets outside the AOI boundary and some within.
            elif numOfIntersectedOutlets == 0 and numOfOutletsWithinAOI > 0:

                AddMsgAndPrint("\n\tThere is " + str(numOfOutlets - numOfOutletsWithinAOI) + " outlet(s) completely outside the AOI Boundary",0)
                AddMsgAndPrint("\tOutlet(s) will be clipped to AOI",0)             

            # All outlets are are intersecting the AOI boundary
            else:
                AddMsgAndPrint("\n\tOutlet(s) is intersecting the AOI Boundary and will be clipped to AOI",0)

            clippedOutlets = watershedGDB_path + os.sep + "Layers" + os.sep + projectName + "_clippedOutlets"
            gp.Clip_analysis(outletsLayer, projectAOI, clippedOutlets)

            gp.delete_management("AOI_lyr")
            gp.delete_management("outletsTempLyr")
            del numOfOutlets
            del numOfOutletsWithinAOI
            del numOfIntersectedOutlets            

            gp.delete_management(outletFC)
            gp.rename(clippedOutlets,outletFC)

            AddMsgAndPrint("\n\t" + str(int(gp.GetCount_management(outletFC).getOutput(0))) + " Outlet(s) will be used to create watershed(s)",0)            
            
            return True

    except:
        AddMsgAndPrint("\nFailed to determine overlap with " + projectAOI + ". (determineOverlap)",2)
        print_exception()
        return False

## ================================================================================================================
def splitThousands(someNumber):
# will determine where to put a thousands seperator if one is needed.
# Input is an integer.  Integer with or without thousands seperator is returned.

    try:
        return re.sub(r'(\d{3})(?=\d)', r'\1,', str(someNumber)[::-1])[::-1]
    except:
        print_exception()
        return someNumber

## ================================================================================================================
##                                      Main Body
## ================================================================================================================
# Import system modules
import sys, os, arcgisscripting, string, traceback, re

# Create the Geoprocessor object
gp = arcgisscripting.create(9.3)
gp.OverWriteOutput = 1

# Used to determine ArcGIS version
d = gp.GetInstallInfo('desktop')

keys = d.keys()

for k in keys:

    if k == "Version":

        version = "\nArcGIS %s : %s" % (k, d[k])
        print version

        if version.find("10.") > 0:
            ArcGIS10 = True

        else:
            ArcGIS10 = False

        break 

del d, keys
   
if version < 9.3:
    gp.AddError("\nThis tool requires ArcGIS version 9.3 or Greater.....EXITING",2)
    sys.exit("")


try:
    # Check out Spatial Analyst License        
    if gp.CheckExtension("spatial") == "Available":
        gp.CheckOutExtension("spatial")
    else:
        gp.AddError("Spatial Analyst Extension not enabled. Please enable Spatial analyst from the Tools/Extensions menu")
        sys.exit("")

    # Script Parameters
    streams = gp.getparameterastext(0)
    outlet = gp.getparameterastext(1)
    userWtshdName = gp.getparameterastext(2)
    createFlowPaths = gp.getparameterastext(3)
                   
    # Uncomment the following 4 lines to run from pythonWin
##    streams = r'C:\flex\flex_EngTools.gdb\Layers\Streams'
##    outlet = r'C:\flex\flex_EngTools.gdb\Layers\outlet'
##    userWtshdName = "testing10"
##    createFlowPaths = "true"

    if string.upper(createFlowPaths) <> "TRUE":
        calcLHL = False
    else:
        calcLHL = True
        
    # --------------------------------------------------------------------------------------------- Define Variables
    streamsPath = gp.Describe(streams).CatalogPath

    if streamsPath.find('.gdb') > 0 and streamsPath.find('_Streams') > 0:
        watershedGDB_path = streamsPath[:streamsPath.find(".gdb")+4]
    else:
        gp.AddError("\n\n" + streams + " is an invalid Stream Network Feature")
        gp.AddError("Run Watershed Delineation Tool #2. Create Stream Network\n\n")
        sys.exit("")
    
    userWorkspace = os.path.dirname(watershedGDB_path)
    watershedGDB_name = os.path.basename(watershedGDB_path)
    watershedFD = watershedGDB_path + os.sep + "Layers"
    projectName = gp.ValidateTablename(os.path.basename(userWorkspace).replace(" ","_"))
    projectAOI = watershedFD + os.sep + projectName + "_AOI"

    # --------------------------------------------------------------- Datasets
    # ------------------------------ Permanent Datasets
    watershed = watershedFD + os.sep + (gp.ValidateTablename(userWtshdName, watershedFD))
    FlowAccum = watershedGDB_path + os.sep + "flowAccumulation"
    FlowDir = watershedGDB_path + os.sep + "flowDirection"
    DEM_aoi = watershedGDB_path + os.sep + projectName + "_DEM"
    DEMsmooth = watershedGDB_path + os.sep + "DEMsmooth"

    # Must Have a unique name for watershed -- userWtshdName gets validated, but that doesn't ensure a unique name
    # Append a unique digit to watershed if required -- This means that a watershed with same name will NOT be
    # overwritten.
    x = 1
    while x > 0:
        if gp.exists(watershed):
            watershed = watershedFD + os.sep + (gp.ValidateTablename(userWtshdName, watershedFD)) + str(x)
            x += 1
        else:
            x = 0
    del x

    outletFC = watershedFD + os.sep + os.path.basename(watershed) + "_outlet"

    # ---------------------------------------------------------------------------------------------- Temporary Datasets
    outletBuffer = watershedGDB_path + os.sep + "Layers" + os.sep + "outletBuffer"
    pourPointGrid = watershedGDB_path + os.sep + "PourPoint"
    snapPourPoint = watershedGDB_path + os.sep + "snapPourPoint"
    watershedGrid = watershedGDB_path + os.sep + "watershedGrid"
    watershedTemp = watershedGDB_path + os.sep + "watershedTemp"
    watershedDissolve = watershedGDB_path + os.sep + "watershedDissolve"
    wtshdDEMsmooth = watershedGDB_path + os.sep + "wtshdDEMsmooth"
    slopeGrid = watershedGDB_path + os.sep + "slopeGrid"
    slopeStats = watershedGDB_path + os.sep + "slopeStats"
    
    # Features in Arcmap
    watershedOut = "" + os.path.basename(watershed) + ""
    outletOut = "" + os.path.basename(outletFC) + ""

    # -----------------------------------------------------------------------------------------------  Path of Log file
    textFilePath = userWorkspace + os.sep + projectName + "_EngTools.txt"

    # record basic user inputs and settings to log file for future purposes
    logBasicSettings()

    # ---------------------------------------------------------------------------------------------- Check some parameters
    # If validated name becomes different than userWtshdName notify the user        
    if os.path.basename(watershed) != userWtshdName:
        AddMsgAndPrint("\nUser Watershed name: " + str(userWtshdName) + " is invalid or already exists in project geodatabase.",1)
        AddMsgAndPrint("\tRenamed output watershed to " + str(watershedOut),0)
        
    # Make sure the FGDB and streams exists from step 1 and 2
    if not gp.exists(watershedGDB_path) or not gp.exists(streamsPath):
        AddMsgAndPrint("\nThe \"Streams\" Feature Class or the File Geodatabase from Step 1 was not found",2)
        AddMsgAndPrint("Rerun Step #1 and #2",2)
        sys.exit(0)

    # Must have one pour points manually digitized
    if not int(gp.GetCount_management(outlet).getOutput(0)) > 0:
        AddMsgAndPrint("\n\nAt least one Pour Point must be used! None Detected. Exiting\n",2)
        sys.exit(0)

    # Flow Accumulation grid must present to proceed
    if not gp.exists(FlowAccum):
        AddMsgAndPrint("\n\nFlow Accumulation Grid was not found in " + watershedGDB_path,2)
        AddMsgAndPrint("Run Tool#2: \"Create Stream Network\" Again!  Exiting.....\n",2)
        sys.exit(0)

    # Flow Direction grid must present to proceed
    if not gp.exists(FlowDir):
        AddMsgAndPrint("\n\nFlow Direction Grid was not found in " + watershedGDB_path,2)
        AddMsgAndPrint("Run Tool#2: \"Create Stream Network\" Again!  Exiting.....\n",2)
        sys.exit(0)

    # ---------------------------------------------------------------------------------------------- Delete old datasets
    datasetsToRemove = (outletBuffer,pourPointGrid,snapPourPoint,watershedGrid,watershedTemp,watershedDissolve,wtshdDEMsmooth,slopeGrid,slopeStats)

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
    
    # ----------------------------------------------------------------------------------------------- Create New Outlet
    # -------------------------------------------- Features reside on hard disk;
    #                                              No heads up digitizing was used.
    if (os.path.dirname(gp.Describe(outlet).CatalogPath)).find("memory") < 0:

        # if paths between outlet and outletFC are NOT the same
        if not gp.Describe(outlet).CatalogPath == outletFC:

            # delete the outlet feature class; new one will be created            
            if gp.exists(outletFC):
                gp.delete_management(outletFC)
                gp.CopyFeatures_management(outlet, outletFC)
                AddMsgAndPrint("\nSuccessfully Recreated " + str(outletOut) + " feature class from existing layer",1)                
                
            else:    
                gp.CopyFeatures_management(outlet, outletFC)
                AddMsgAndPrint("\nSuccessfully Created " + str(outletOut) + " feature class from existing layer",1)

        # paths are the same therefore input IS pour point
        else:
            AddMsgAndPrint("\nUsing Existing " + str(outletOut) + " feature class",1)

    # -------------------------------------------- Features reside in Memory;
    #                                              heads up digitizing was used.       
    else:

        if gp.exists(outletFC):
            gp.delete_management(outletFC)
            gp.CopyFeatures_management(outlet, outletFC)
            AddMsgAndPrint("\nSuccessfully Recreated " + str(outletOut) + " feature class from digitizing",1)

        else:
            gp.CopyFeatures_management(outlet, outletFC)
            AddMsgAndPrint("\nSuccessfully Created " + str(outletOut) + " feature class from digitizing",1)

    if gp.Describe(outletFC).ShapeType != "Polyline" and gp.Describe(outletFC).ShapeType != "Line":
        AddMsgAndPrint("\n\nYour Outlet must be a Line or Polyline layer!.....Exiting!",2)
        sys.exit()

    AddMsgAndPrint("\nChecking Placement of Outlet(s)....",1)
    if not determineOverlap(outletFC):
        gp.delete_management(outletFC)
        sys.exit()

    # ---------------------------------------------------------------------------------------------- Create Watershed
    # Capture Default Environments
    tempExtent = gp.Extent
    tempMask = gp.mask
    tempSnapRaster = gp.SnapRaster
    tempCellSize = gp.CellSize
    tempCoordSys = gp.OutputCoordinateSystem
    
    # ---------------------------------- Retrieve Raster Properties
    desc = gp.Describe(FlowDir)
    sr = desc.SpatialReference

    units = sr.LinearUnitName
    cellSize = desc.MeanCellWidth
    
    if units == "Meter":
        units = "Meters"
    elif units == "Foot":
        units = "Feet"
    elif units == "Foot_US":
        units = "Feet"
    # ----------------------------------- Set Environment Settings
    gp.Extent = "MAXOF"
    gp.CellSize = cellSize
    gp.mask = ""
    gp.SnapRaster = DEM_aoi
    gp.OutputCoordinateSystem = sr
    
    del desc
    del sr
        
    # --------------------------------------------------------------------- Convert outlet Line Feature to Raster Pour Point.

    # Add dummy field for buffer dissolve and raster conversion using OBJECTID (which becomes subbasin ID)
    gp.AddField_management(outletFC, "IDENT", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.CalculateField_management(outletFC, "IDENT", "[OBJECTID]", "VB", "")
    
    # Buffer outlet features by  raster cell size
    bufferDist = "" + str(cellSize) + " " + str(units) + ""    
    gp.Buffer_analysis(outletFC, outletBuffer, bufferDist, "FULL", "ROUND", "LIST", "IDENT")

    # Convert bufferd outlet to raster pour points    
    gp.MakeFeatureLayer(outletBuffer,"outletBufferLyr")
    gp.PolygonToRaster_conversion("outletBufferLyr","IDENT",pourPointGrid,"MAXIMUM_AREA","NONE",cellSize)

    # Delete intermediate data
    gp.Delete_management(outletBuffer)
    gp.Delete_management("outletBufferLyr")
    gp.DeleteField_management(outletFC, "IDENT")
    
    del bufferDist
    AddMsgAndPrint("\nDelineating Watershed(s)...",1)
    
    # ------------------------------------------------------------------ Create Watershed Raster using the raster pour point
    
    gp.Watershed_sa(FlowDir,pourPointGrid,watershedGrid,"VALUE")
    
    # ------------------------------------------------------------------- Convert results to simplified polygon
    if ArcGIS10:
        
        try:
            # --------------------------------------------- Convert to watershed grid to a polygon feature class
            
            gp.RasterToPolygon_conversion(watershedGrid,watershedTemp,"SIMPLIFY","VALUE")

        except:
            if gp.exists(watershedTemp):

                try:
                    gp.MakeFeatureLayer(watershedTemp,"wtshdTempLyr")
                except:
                    print_exception
            else:
                AddMsgAndPrint("\n" + gp.GetMessages(2),2)
                sys.exit()
                
        # -------------------------------------------------  Dissolve watershedTemp by GRIDCODE or grid_code
        if len(gp.ListFields(watershedTemp,"GRIDCODE")) > 0:
            gp.Dissolve_management(watershedTemp, watershedDissolve, "GRIDCODE", "", "MULTI_PART", "DISSOLVE_LINES")
        else:
            gp.Dissolve_management(watershedTemp, watershedDissolve, "grid_code", "", "MULTI_PART", "DISSOLVE_LINES")               

    # Do the following for ArcGIS 9.3
    else:                

        try:
            # Convert to watershed grid to a polygon feature class
            gp.RasterToPolygon_conversion(watershedGrid,watershedTemp,"SIMPLIFY","VALUE")

        except:
            if gp.exists(watershedTemp):
                
                if int(gp.GetCount_management(watershedTemp).getOutput(0)) > 0:
                    AddMsgAndPrint("",1)
                else:
                    AddMsgAndPrint("\n" + gp.GetMessages(2),2)
                    sys.exit()                
            else:
                AddMsgAndPrint("\n" + gp.GetMessages(2),2)
                sys.exit()

        # Dissolve watershedTemp by GRIDCODE or grid_code 
        if len(gp.ListFields(watershedTemp,"GRIDCODE")) > 0:
            gp.Dissolve_management(watershedTemp, watershedDissolve, "GRIDCODE", "", "MULTI_PART", "DISSOLVE_LINES")
        else:
            gp.Dissolve_management(watershedTemp, watershedDissolve, "grid_code", "", "MULTI_PART", "DISSOLVE_LINES")

        gp.delete_management(watershedTemp)


    # Copy Results to watershedFD
    gp.CopyFeatures_management(watershedDissolve, watershed)    
    AddMsgAndPrint("\n\tSuccessfully Created " + str(int(gp.GetCount_management(watershed).getOutput(0))) + " Watershed(s) from " + str(outletOut),0)

    # Delete unwanted datasets
    if gp.exists(watershedTemp):
        gp.delete_management(watershedTemp)
        
    gp.Delete_management(watershedDissolve)    
    gp.delete_management(pourPointGrid)
    gp.delete_management(watershedGrid)

    # -------------------------------------------------------------------------------------------------- Add and Calculate fields
    # Add Subbasin Field in watershed and calculate it to be the same as GRIDCODE
    gp.AddField_management(watershed, "Subbasin", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

    if len(gp.ListFields(watershed,"GRIDCODE")) > 0:
        gp.CalculateField_management(watershed, "Subbasin", "[GRIDCODE]", "VB", "")
        gp.DeleteField_management(watershed, "GRIDCODE")
        
    else:
        gp.CalculateField_management(watershed, "Subbasin", "[grid_code]", "VB", "")
        gp.DeleteField_management(watershed, "grid_code")
    
    # Add Acres Field in watershed and calculate them and notify the user
    displayAreaInfo = False

    if units == "Meters":
        gp.AddField_management(watershed, "Acres", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        gp.CalculateField_management(watershed, "Acres", "[Shape_Area]/4046.86", "VB", "")
        displayAreaInfo = True
        
    elif units == "Feet":
        gp.AddField_management(watershed, "Acres", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        gp.CalculateField_management(watershed, "Acres", "[Shape_Area]/43560", "VB", "")
        displayAreaInfo = True

    else:
        displayAreaInfo = False

    # ---------------------------------------------------------------------------- If user opts to calculate watershed flow paths
    if calcLHL:
        try:

            # ----------------------------------------- Temporary Datasets (Yes, there's a bunch)
            UP_GRID = watershedGDB_path + os.sep + "upgrid"
            DOWN_GRID = watershedGDB_path + os.sep + "downgrid"
            PLUS_GRID = watershedGDB_path + os.sep + "plusgrid"
            MAX_GRID = watershedGDB_path + os.sep + "maxgrid"
            MINUS_GRID = watershedGDB_path + os.sep + "minusgrid"
            LONGPATH = watershedGDB_path + os.sep + "longpath"
            LP_Extract = watershedGDB_path + os.sep + "lpExt"
            LongpathTemp = watershedGDB_path + os.sep + "lpTemp"
            LongpathTemp1 = watershedGDB_path + os.sep + "lpTemp1"
            LongpathTemp2 = watershedGDB_path + os.sep + "lpTemp2"
            LP_Smooth = watershedGDB_path + os.sep + "lpSmooth"
            
            # ------------------------------------------- Permanent Datasets (..and yes, it took 13 other ones to get here)
            Flow_Length = watershedFD + os.sep + os.path.basename(watershed) + "_FlowPaths"
            FlowLengthName = os.path.basename(Flow_Length)

            # ------------------------------------------- Derive Longest flow path for each subbasin
            # Create Longest Path Feature Class
            gp.CreateFeatureClass_management(watershedFD, FlowLengthName, "POLYLINE") 
            gp.AddField_management(Flow_Length, "Subbasin", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
            gp.AddField_management(Flow_Length, "Reach", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
            gp.AddField_management(Flow_Length, "Type", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
            gp.AddField_management(Flow_Length, "Length_ft", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

            AddMsgAndPrint("\nCalculating watershed flow path(s)...",1)
            
            # -------------------------------------------- Raster Flow Length Analysis
            # Set mask to watershed to limit calculations
            gp.mask = watershed
            
            # Calculate total upstream flow length on FlowDir grid
            gp.FlowLength_sa(FlowDir, UP_GRID, "UPSTREAM", "")
            
            # Calculate total downsteam flow length on FlowDir grid
            gp.FlowLength_sa(FlowDir, DOWN_GRID, "DOWNSTREAM", "")
            
            # Sum total upstream and downstream flow lengths
            gp.Plus_sa(UP_GRID, DOWN_GRID, PLUS_GRID)
            
            # Get Maximum downstream flow length in each subbasin
            gp.ZonalStatistics_sa(watershed, "Subbasin", DOWN_GRID, MAX_GRID, "MAXIMUM", "DATA")
            
            # Subtract tolerance from Maximum flow length -- where do you get tolerance from?
            gp.Minus_sa(MAX_GRID, "0.3", MINUS_GRID)
            
            # Extract cells with positive difference to isolate longest flow path(s)
            gp.GreaterThan_sa(PLUS_GRID, MINUS_GRID, LONGPATH)
            gp.Con_sa(LONGPATH, LONGPATH, LP_Extract, "", "\"VALUE\" = 1")

##            # -------------------------------------------- Convert to Polyline features
##            # Convert raster flow path to polyline (DOES NOT RUN IN ARCGIS 10.5.0 Base Install)
##            gp.RasterToPolyline_conversion(LP_Extract, LongpathTemp, "ZERO", "", "NO_SIMPLIFY", "VALUE")
##            
####################################################################################################################################
            # Try to use Stream to Feature process to convert the raster Con result to a line (DUE TO 10.5.0 BUG)
            LFP_StreamLink = watershedGDB_path + os.sep + "lfplink"
            gp.StreamLink_sa(LP_Extract, FlowDir, LFP_StreamLink)
            gp.StreamToFeature_sa(LFP_StreamLink, FlowDir, LongpathTemp, "NO_SIMPLIFY")
####################################################################################################################################
            
            # Smooth and Dissolve results
            gp.SmoothLine_management(LongpathTemp, LP_Smooth, "PAEK", "100 Feet", "FIXED_CLOSED_ENDPOINT", "NO_CHECK")

            # Intersect with watershed to get subbasin ID
            gp.Intersect_analysis(LP_Smooth + "; " + watershed, LongpathTemp1, "ALL", "", "INPUT")
            
            # Dissolve to create single lines for each subbasin
            gp.Dissolve_management(LongpathTemp1, LongpathTemp2, "Subbasin", "", "MULTI_PART", "DISSOLVE_LINES")
            
            # Add Fields / attributes & calculate length in feet
            gp.AddField_management(LongpathTemp2, "Reach", "SHORT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
            gp.CalculateField_management(LongpathTemp2, "Reach", "[OBJECTID]", "VB", "")
            gp.AddField_management(LongpathTemp2, "Type", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
            gp.CalculateField_management(LongpathTemp2, "Type", '"Natural Watercourse"', "VB", "")
            gp.AddField_management(LongpathTemp2, "Length_ft", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
            
            if units == "Meters":
                gp.CalculateField_management(LongpathTemp2, "Length_ft", "[shape_length] * 3.28084", "VB", "")
            else:
                gp.CalculateField_management(LongpathTemp2, "Length_ft", "[shape_length]", "VB", "")
                
            # Append Results to Flow Length FC
            gp.Append_management(LongpathTemp2, Flow_Length, "NO_TEST")

            # Delete Intermediate Data            
            datasetsToRemove = (UP_GRID,DOWN_GRID,PLUS_GRID,MAX_GRID,MINUS_GRID,LONGPATH,LP_Extract,LongpathTemp,LongpathTemp1,LongpathTemp2,LP_Smooth, LFP_StreamLink)

            x = 0
            for dataset in datasetsToRemove:

                if gp.exists(dataset):

                    if x < 1:
                        x += 1
                        
                    try:
                        gp.delete_management(dataset)
                    except:
                        pass
                    
            del dataset
            del datasetsToRemove
            del x
        
            # ---------------------------------------------------------------------------------------------- Set up Domains
            # Apply domains to watershed geodatabase and Flow Length fields to aid in user editing
            domainTables = True
            ID_Table = os.path.join(os.path.dirname(sys.argv[0]), "Support.gdb" + os.sep + "ID_TABLE")
            Reach_Table = os.path.join(os.path.dirname(sys.argv[0]), "Support.gdb" + os.sep + "REACH_TYPE")

            # If support tables not present skip domains -- user is on their own.
            if not gp.Exists(ID_Table):
                domainTables = False
                
            if not gp.Exists(Reach_Table):
                domainTables = False

            if domainTables:
                # describe present domains, estrablish and apply if needed
                desc = gp.describe(watershedGDB_path)
                listOfDomains = []

                domains = desc.Domains

                for domain in domains:
                    listOfDomains.append(domain)

                del desc, domains

                if not "Reach_Domain" in listOfDomains:
                    gp.TableToDomain_management(ID_Table, "IDENT", "ID_DESC", watershedGDB_path, "Reach_Domain", "Reach_Domain", "REPLACE")

                if not "Type_Domain" in listOfDomains:
                    gp.TableToDomain_management(Reach_Table, "TYPE", "TYPE", watershedGDB_path, "Type_Domain", "Type_Domain", "REPLACE")

                del listOfDomains
                del ID_Table
                del Reach_Table
                del domainTables

                # Assign domain to flow length fields for User Edits...
                gp.AssignDomainToField_management(Flow_Length, "Reach", "Reach_Domain", "")
                gp.AssignDomainToField_management(Flow_Length, "TYPE", "Type_Domain", "")

            #---------------------------------------------------------------------- Flow Path Calculations complete
            AddMsgAndPrint("\n\tSuccessfully extracted watershed flow path(s)",0)

            del UP_GRID
            del DOWN_GRID
            del PLUS_GRID
            del MAX_GRID
            del MINUS_GRID
            del LONGPATH
            del LP_Extract
            del LongpathTemp
            del LongpathTemp1
            del LongpathTemp2
            del LP_Smooth
            del FlowLengthName
            del LFP_StreamLink
            
        except:
            # If Calc LHL fails prompt user to delineate manually and continue...  ...capture error for reference
            AddMsgAndPrint("\nUnable to Calculate Flow Path(s) .. You will have to trace your stream network to create them manually.."+ gp.GetMessages(2),2)
            AddMsgAndPrint("\nContinuing....",1)
            
    # ----------------------------------------------------------------------------------------------- Calculate Average Slope
    calcAvgSlope = False

    # ----------------------------- Retrieve Z Units from AOI    
    if gp.exists(projectAOI):
        
        rows = gp.searchcursor(projectAOI)
        row = rows.next()
        zUnits = row.Z_UNITS
        
        del rows
        del row
        
        # Assign proper Z factor
        if zUnits == "Meters":
            
            if units == "Feet":
                Zfactor = 3.28084
            if units == "Meters":
                Zfactor = 1

        elif zUnits == "Feet":
            
            if units == "Feet":
                Zfactor = 1
            if units == "Meters":
                Zfactor = 0.3048                  
                
        elif zUnits == "Centimeters":
            
            if units == "Feet":
                Zfactor = 30.48
            if units == "Meters":
                Zfactor = 0.01

        # zUnits must be inches; no more choices                
        else:
            
            if units == "Feet":
                Zfactor = 12
            if units == "Meters":
                Zfactor = 39.3701
    else:
        Zfactor = 0 # trapped for below so if Project AOI not present slope isnt calculated
        
    # --------------------------------------------------------------------------------------------------------
    if Zfactor > 0:
        AddMsgAndPrint("\nCalculating average slope...",1)
        
        if gp.exists(DEMsmooth):
            
            # Use smoothed DEM to calculate slope to remove exteraneous values
            gp.AddField_management(watershed, "Avg_Slope", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

            gp.ExtractByMask_sa(DEMsmooth, watershed, wtshdDEMsmooth)
            gp.Slope_sa(wtshdDEMsmooth, slopeGrid, "PERCENT_RISE", Zfactor)
            gp.ZonalStatisticsAsTable_sa(watershed, "Subbasin", slopeGrid, slopeStats, "DATA")
            calcAvgSlope = True

            # Delete unwanted rasters
            gp.delete_management(DEMsmooth)
            gp.delete_management(wtshdDEMsmooth)
            gp.delete_management(slopeGrid)

        elif gp.exists(DEM_aoi):
           
            # Run Focal Statistics on the DEM_aoi to remove exteraneous values
            gp.focalstatistics_sa(DEM_aoi, DEMsmooth,"RECTANGLE 3 3 CELL","MEAN","DATA")

            gp.AddField_management(watershed, "Avg_Slope", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

            gp.ExtractByMask_sa(DEMsmooth, watershed, wtshdDEMsmooth)
            gp.Slope_sa(wtshdDEMsmooth, slopeGrid, "PERCENT_RISE", Zfactor)
            gp.ZonalStatisticsAsTable_sa(watershed, "Subbasin", slopeGrid, slopeStats, "DATA")
            calcAvgSlope = True

            # Delete unwanted rasters
            gp.delete_management(DEMsmooth)
            gp.delete_management(wtshdDEMsmooth)
            gp.delete_management(slopeGrid)   

        else:
            AddMsgAndPrint("\nMissing DEMsmooth or DEM_aoi from FGDB. Could not Calculate Average Slope",2)
            
    else:
        AddMsgAndPrint("\nMissing Project AOI from FGDB. Could not retrieve Z Factor to Calculate Average Slope",2)

    # -------------------------------------------------------------------------------------- Update Watershed FC with Average Slope
    if calcAvgSlope:
        
        # go through each zonal Stat record and pull out the Mean value
        rows = gp.searchcursor(slopeStats)
        row = rows.next()

        AddMsgAndPrint("\n\tSuccessfully Calculated Average Slope",0)

        AddMsgAndPrint("\nCreate Watershed Results:",1)
        AddMsgAndPrint("\n===================================================",0)
        AddMsgAndPrint("\tUser Watershed: " + str(watershedOut),0)
        
        while row:
            wtshdID = row.OBJECTID

            # zonal stats doesnt generate "Value" with the 9.3 geoprocessor
            if len(gp.ListFields(slopeStats,"Value")) > 0:
                zonalValue = row.VALUE
                
            else:
                zonalValue = row.SUBBASIN
                
            zonalMeanValue = row.MEAN

            whereclause = "Subbasin = " + str(zonalValue)
            wtshdRows = gp.UpdateCursor(watershed,whereclause)
            wtshdRow = wtshdRows.next()           

            # Pass the Mean value from the zonalStat table to the watershed FC.
            while wtshdRow:
                
                wtshdRow.Avg_Slope = zonalMeanValue
                wtshdRows.UpdateRow(wtshdRow)

                # Inform the user of Watershed Acres, area and avg. slope
                if displayAreaInfo:
                    
                    # Inform the user of Watershed Acres, area and avg. slope
                    AddMsgAndPrint("\n\tSubbasin: " + str(wtshdRow.OBJECTID),0)
                    AddMsgAndPrint("\t\tAcres: " + str(splitThousands(round(wtshdRow.Acres,2))),0)
                    AddMsgAndPrint("\t\tArea: " + str(splitThousands(round(wtshdRow.Shape_Area,2))) + " Sq. " + units,0)
                    AddMsgAndPrint("\t\tAvg. Slope: " + str(round(zonalMeanValue,2)),0)

                else:
                    AddMsgAndPrint("\tSubbasin " + str(wtshdRow.OBJECTID) + " Avg. Slope: " + str(zonalMeanValue) + "%",1)
                                   
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
        AddMsgAndPrint("\n===================================================",0)
        gp.delete_management(slopeStats)
        
    import time
    time.sleep(5)
    
    # ------------------------------------------------------------------------------------------------ Compact FGDB
    try:
        gp.compact_management(watershedGDB_path)
        AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path),1)    
    except:
        pass

    # ------------------------------------------------------------------------------------------------ Prepare to Add to Arcmap
    # Set paths for derived layers
    gp.SetParameterAsText(4, outletFC)
    gp.SetParameterAsText(5, watershed)
    
    if calcLHL:
        gp.SetParameterAsText(6, Flow_Length)
        del Flow_Length

    AddMsgAndPrint("\nAdding Layers to ArcMap",1)
    AddMsgAndPrint("\n",1)

    gp.RefreshCatalog(watershedGDB_path)

    # Restore original environments
    gp.extent = tempExtent
    gp.mask = tempMask
    gp.SnapRaster = tempSnapRaster
    gp.CellSize = tempCellSize
    gp.OutputCoordinateSystem = tempCoordSys

    try:
        del streams
        del outlet
        del userWtshdName
        del streamsPath
        del watershedGDB_path
        del userWorkspace
        del watershedGDB_name
        del outletFC
        del outletBuffer
        del watershed
        del FlowAccum
        del FlowDir
        del DEM_aoi
        del DEMsmooth
        del pourPointGrid
        del snapPourPoint
        del watershedGrid
        del watershedTemp
        del watershedDissolve
        del wtshdDEMsmooth
        del slopeGrid
        del slopeStats
        del watershedOut
        del outletOut
        del textFilePath
        del units
        del displayAreaInfo
        del calcAvgSlope
        del cellSize
        del gp
        del version
        del Zfactor
        del projectAOI
        del ArcGIS10
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

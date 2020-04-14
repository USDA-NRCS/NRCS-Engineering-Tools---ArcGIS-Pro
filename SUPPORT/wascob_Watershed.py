# wascob_Watershed.py
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
    f.write("Executing \"3. Wascob Create Watershed\" for ArcGIS 9.3 and 10\n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write("ArcGIS Version: " + str(version) + "\n")
    f.write("User Parameters:\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tStreams: " + streamsPath + "\n")
    
    if int(gp.GetCount_management(outlet).getOutput(0)) > 0:
        f.write("\tReference Lines Digitized: " + str(gp.GetCount_management(outlet)) + "\n")
    else:
        f.write("\tReference Lines Digitized: 0\n")
        
    f.write("\tWatershed Name: " + watershedOut + "\n")
        
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

                AddMsgAndPrint("\n\t" + str(int(gp.GetCount_management(outletFC).getOutput(0))) + " Reference Line(s) will be used to create watershed(s)",0)
                
                return True
        
        # all outlets are completely within AOI; Ideal scenario
        elif numOfOutletsWithinAOI == numOfOutlets:

            AddMsgAndPrint("\n\t" + str(numOfOutlets) + " Reference Line(s) will be used to create watershed(s)",0)            
            
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

            AddMsgAndPrint("\t" + str(numOfOutlets) + " Reference Line(s) digitized",0)            

            # there are some outlets crossing the AOI boundary and some within.
            if numOfIntersectedOutlets > 0 and numOfOutletsWithinAOI > 0:

                AddMsgAndPrint("\n\tThere is " + str(numOfIntersectedOutlets) + " Reference Line(s) intersecting the AOI Boundary",0)
                AddMsgAndPrint("\tOutlet(s) will be clipped to AOI",0)

            # there are some outlets outside the AOI boundary and some within.
            elif numOfIntersectedOutlets == 0 and numOfOutletsWithinAOI > 0:

                AddMsgAndPrint("\n\tThere is " + str(numOfOutlets - numOfOutletsWithinAOI) + " Reference Line(s) completely outside the AOI Boundary",0)
                AddMsgAndPrint("\tOutlet(s) will be clipped to AOI",0)             

            # All outlets are are intersecting the AOI boundary
            else:
                AddMsgAndPrint("\n\tAll Reference Line(s)  intersect the AOI Boundary and will be clipped to AOI",0)

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
    userWtshdName = "Watershed"
##    createFlowPaths = gp.getparameterastext(3)
                   
    # Uncomment the following 4 lines to run from pythonWin
##    streams = r'C:\flex\flex_EngTools.gdb\Layers\Streams'
##    outlet = r'C:\flex\flex_EngTools.gdb\Layers\outlet'
##    userWtshdName = "testing10"
##    createFlowPaths = "true"

##    if string.upper(createFlowPaths) <> "TRUE":
##        calcLHL = False
##    else:
##        calcLHL = True
        
    # --------------------------------------------------------------------------------------------- Define Variables
    streamsPath = gp.Describe(streams).CatalogPath

    if streamsPath.find('.gdb') > 0 and streamsPath.find('_Streams') > 0:
        watershedGDB_path = streamsPath[:streamsPath.find(".gdb")+4]
    else:
        gp.AddError("\n\n" + streams + " is an invalid Stream Network Feature")
        gp.AddError("Run Tool #2. Create Stream Network\n\n")
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
    DEM_aoi = watershedGDB_path + os.sep + projectName + "_Raw_DEM"
    DEMsmooth = watershedGDB_path + os.sep + "_DEMsmooth"
    ProjectDEM = watershedGDB_path + os.sep + projectName + "_Project_DEM"

##    # Must Have a unique name for watershed -- userWtshdName gets validated, but that doesn't ensure a unique name
##    # Append a unique digit to watershed if required -- This means that a watershed with same name will NOT be
##    # overwritten.
##    x = 1
##    while x > 0:
##        if gp.exists(watershed):
##            watershed = watershedFD + os.sep + (gp.ValidateTablename(userWtshdName, watershedFD)) + str(x)
##            x += 1
##        else:
##            x = 0
##    del x

    outletFC = watershedFD + os.sep + "ReferenceLine"

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
    # Wascob Additions
    outletStats = watershedGDB_path + os.sep + "outletStats"    
    # Features in Arcmap
    watershedOut = "" + os.path.basename(watershed) + ""
    outletOut = "" + os.path.basename(outletFC) + ""

    # -----------------------------------------------------------------------------------------------  Path of Log file
    textFilePath = userWorkspace + os.sep + projectName + "_EngTools.txt"

    # record basic user inputs and settings to log file for future purposes
    logBasicSettings()

    # ---------------------------------------------------------------------------------------------- Check some parameters
##    # If validated name becomes different than userWtshdName notify the user        
##    if os.path.basename(watershed) != userWtshdName:
##        AddMsgAndPrint("\nUser Watershed name: " + str(userWtshdName) + " is invalid or already exists in project geodatabase.",1)
##        AddMsgAndPrint("\tRenamed output watershed to " + str(watershedOut),0)
        
    # Make sure the FGDB and streams exists from step 1 and 2
    if not gp.exists(watershedGDB_path) or not gp.exists(streamsPath):
        AddMsgAndPrint("\nThe \"Streams\" Feature Class or the File Geodatabase from Step 1 was not found",2)
        AddMsgAndPrint("Rerun Step #1 and #2",2)
        sys.exit(0)

    # Must have one pour points manually digitized
    if not int(gp.GetCount_management(outlet).getOutput(0)) > 0:
        AddMsgAndPrint("\n\nAt least one Pour Point must be used! None Detected. Exiting\n",2)
        sys.exit(0)

    # Project DEM must present to proceed
    if not gp.exists(ProjectDEM):
        AddMsgAndPrint("\n\nProject DEM was not found in " + watershedGDB_path,2)
        AddMsgAndPrint("Run Tool#1: \"Define AOI\" and Tool #2: \"Create Stream Network\" Again!  Exiting.....\n",2)
        sys.exit(0)

    # Flow Accumulation grid must present to proceed
    if not gp.exists(FlowAccum):
        AddMsgAndPrint("\n\nFlow Accumulation Grid was not found in " + watershedGDB_path,2)
        AddMsgAndPrint("Run Tool  \"Create Stream Network\" Again!  Exiting.....\n",2)
        sys.exit(0)

    # Flow Direction grid must present to proceed
    if not gp.exists(FlowDir):
        AddMsgAndPrint("\n\nFlow Direction Grid was not found in " + watershedGDB_path,2)
        AddMsgAndPrint("Run Tool#2: \"Create Stream Network\" Again!  Exiting.....\n",2)
        sys.exit(0)




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
        AddMsgAndPrint("\n\nYour Reference Line must be a Line or Polyline layer!.....Exiting!",2)
        sys.exit()





    # ------------------------------------- Delete previous layers from ArcMap if they exist
    layersToRemove = (watershedOut,outletOut)

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
    
    # ---------------------------------------------------------------------------------------------- Delete old datasets
    # dropped outletFC from the remove list on 1/11/2018. It would cause problems with the Create New Outlet sequence
    datasetsToRemove = (watershed,outletBuffer,pourPointGrid,snapPourPoint,watershedGrid,watershedTemp,wtshdDEMsmooth,slopeGrid,slopeStats,outletStats)

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
    





    AddMsgAndPrint("\nChecking Placement of Reference Line(s)....",1)
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
    gp.SnapRaster = ""
    gp.OutputCoordinateSystem = sr
    
    del desc
    del sr

    # --------------------------------------------------------------------- Attribute Embankement(s)        
    # Add Attribute Fields to Reference Line(s)
    if len(gp.ListFields(outletFC,"Subbasin")) < 1:
        gp.AddField_management(outletFC, "Subbasin", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    if len(gp.ListFields(outletFC,"MaxElev")) < 1:
        gp.AddField_management(outletFC, "MaxElev", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    if len(gp.ListFields(outletFC,"MinElev")) < 1:
        gp.AddField_management(outletFC, "MinElev", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")    
    if len(gp.ListFields(outletFC,"MeanElev")) < 1:
        gp.AddField_management(outletFC, "MeanElev", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    if len(gp.ListFields(outletFC,"LengthFt")) < 1:
        gp.AddField_management(outletFC, "LengthFt", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

    # Populate Subbasin Field and Calculate embankment length       
    gp.CalculateField_management(outletFC, "Subbasin","[OBJECTID]", "VB", "")
    gp.CalculateField_management(outletFC, "LengthFt","!shape.length@FEET!", "PYTHON", "")
    
    # Buffer outlet features by  raster cell size - dissolving by Subbasin ID
    bufferSize = cellSize * 2
    bufferDist = "" + str(bufferSize) + " " + str(units) + ""    
    gp.Buffer_analysis(outletFC, outletBuffer, bufferDist, "FULL", "ROUND", "LIST", "Subbasin")
    del bufferSize, bufferDist

    # Get Reference Line Elevation Properties
    AddMsgAndPrint("\nCalculating Reference Line Attributes",1)
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
        refRows = gp.UpdateCursor(outletFC,whereclause)
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

    gp.delete_management(outletStats)

    # --------------------------------------------------------------------- Delineate Watershed(s) from Reference Lines
    # Convert buffered outlet Feature to Raster Pour Point.
    gp.MakeFeatureLayer(outletBuffer,"outletBufferLyr")
    gp.PolygonToRaster_conversion("outletBufferLyr","Subbasin",pourPointGrid,"MAXIMUM_AREA","NONE",cellSize)
    # Delete intermediate data
    gp.Delete_management(outletBuffer)
    gp.Delete_management("outletBufferLyr")
    
    # ------------------------------------------------------------------ Create Watershed Raster using the raster pour point
    AddMsgAndPrint("\nDelineating watershed(s)...",1)
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

    # ----------------------------------------------------------------------------------------------- Calculate Average Slope
    calcAvgSlope = False

    # Assign proper Z factor -- Z Units are ft, but XY units may difffer
    if units == "Meters":
        Zfactor = 0.3048            # 0.3048 meters in a foot
        
    elif units == "Feet":
        Zfactor = 1                 # XY Units are the same as Z

    else:
        Zfactor = 0 # trapped for below so if Project AOI not present slope isnt calculated
        
    # --------------------------------------------------------------------------------------------------------
    if Zfactor > 0:
        
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
           
            # Run Focal Statistics on the DEM_aoi for the purpose of generating smoothed results.
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
            AddMsgAndPrint("\nMissing DEMsmooth or Project_DEM from FGDB. Could not Calculate Average Slope",2)
            
    else:
        AddMsgAndPrint("\nCould not retrieve Z Factor to Calculate Average Slope",2)

    # -------------------------------------------------------------------------------------- Update Watershed FC with Average Slope
    if calcAvgSlope:
        
        # go through each zonal Stat record and pull out the Mean value
        rows = gp.searchcursor(slopeStats)
        row = rows.next()

        AddMsgAndPrint("\nSuccessfully Calculated Average Slope:",1)

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
                    if wtshdRow.Acres > 40:
                        AddMsgAndPrint("\t\tSubbasin " + str(wtshdRow.OBJECTID) + " is greater than the 40 acre 638 standard",1)
                        AddMsgAndPrint("\t\tConsider re-delineating to split basins or move upstream",1)

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
    gp.SetParameterAsText(2, outletFC)
    gp.SetParameterAsText(3, watershed)

    AddMsgAndPrint("\nAdding Layers to ArcMap",1)
    AddMsgAndPrint("\n",1)

    # --------------------------------------------------------------------------------------------------- Cleanup
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
        del DEMunits
        del projectAOI
        del ArcGIS10
        del tempExtent
        del tempMask
        del tempSnapRaster
        del tempCellSize
        del tempCoordSys
        del outletStats
    except:
        pass
    
except SystemExit:
    pass

except KeyboardInterrupt:
    AddMsgAndPrint("Interruption requested....exiting")

except:
    print_exception()

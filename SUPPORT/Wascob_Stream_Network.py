# Create_Stream_Network.py
## ================================================================================================================ 
def print_exception():
    
    tb = sys.exc_info()[2]
    l = traceback.format_tb(tb)
    l.reverse()
    tbinfo = "".join(l)
    AddMsgAndPrint("\n----------------------------------- ERROR Start -----------------------------------",2)
    AddMsgAndPrint("Traceback Info: \n" + tbinfo + "Error Info: \n    " +  str(sys.exc_type)+ ": " + str(sys.exc_value) + "",2)
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

        # Add a hard return if it calls for in the beginning
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
                gp.AddMessage("    ")
                gp.AddError(string)

        # Add a hard return if it calls for at the end
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
    f.write("Executing \"Wascob Create Stream Network\" Tool\n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write("ArcGIS Version: " + str(version) + "\n")
    f.write("User Parameters:\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tDem_AOI: " + DEM_aoi + "\n")

    if culvertsExist:
        
        if int(gp.GetCount_management(burnCulverts).getOutput(0)) > 1:
            f.write("\tCulverts Digitized: " + str(int(gp.GetCount_management(burnCulverts).getOutput(0))) + "\n")
        else:
            f.write("\tCulverts Digitized: 0\n")
            
    else:
        f.write("\tCulverts Digitized: 0\n")
        
    f.write("\tStream Threshold: " + str(streamThreshold) + "\n")
    
    f.close
    del f

## ================================================================================================================
def determineOverlap(culvertLayer):
    # This function will compute a geometric intersection of the project_AOI boundary and the culvert
    # layer to determine overlap.

    try:
        # Make a layer from the project_AOI
        if gp.exists("AOI_lyr"):
            gp.delete_management("AOI_lyr")

        gp.MakeFeatureLayer(projectAOI_path,"AOI_lyr")

        if gp.exists("culvertsTempLyr"):
            gp.delete_management("culvertsTempLyr")

        gp.MakeFeatureLayer(culvertLayer,"culvertsTempLyr")

        numOfCulverts = int((gp.GetCount_management(culvertLayer)).GetOutput(0))

        # Select all culverts that are completely within the AOI polygon
        gp.SelectLayerByLocation("culvertsTempLyr", "completely_within", "AOI_lyr")
        numOfCulvertsWithinAOI = int((gp.GetCount_management("culvertsTempLyr")).GetOutput(0))

        # There are no Culverts completely in AOI; may be some on the AOI boundary
        if numOfCulvertsWithinAOI == 0:

            gp.SelectLayerByAttribute_management("culvertsTempLyr", "CLEAR_SELECTION", "")
            gp.SelectLayerByLocation("culvertsTempLyr", "crossed_by_the_outline_of", "AOI_lyr")

            # Check for culverts on the AOI boundary
            numOfIntersectedCulverts = int((gp.GetCount_management("culvertsTempLyr")).GetOutput(0))

            # No culverts within AOI or intersecting AOI
            if numOfIntersectedCulverts == 0:

                AddMsgAndPrint("\tAll Culverts are outside of your Area of Interest",0)
                AddMsgAndPrint("\tNo culverts will be used to hydro enforce " + os.path.basename(DEM_aoi),0)                
            
                gp.delete_management("AOI_lyr")
                gp.delete_management("culvertsTempLyr")
                del numOfCulverts
                del numOfCulvertsWithinAOI
                del numOfIntersectedCulverts
                
                return False

            # There are some culverts on AOI boundary but at least one culvert completely outside AOI
            else:            

                # All Culverts are intersecting the AOI
                if numOfCulverts == numOfIntersectedCulverts:
                    
                    AddMsgAndPrint("\tAll Culvert(s) are intersecting the AOI Boundary",0)
                    AddMsgAndPrint("\tCulverts will be clipped to AOI",0)

                 # Some Culverts intersecting AOI and some completely outside.
                else:

                    AddMsgAndPrint("\t" + str(numOfCulverts) + " Culverts digitized",0)
                    AddMsgAndPrint("\n\tThere is " + str(numOfCulverts - numOfIntersectedCulverts) + " culvert(s) completely outside the AOI Boundary",0)
                    AddMsgAndPrint("\tCulverts will be clipped to AOI",0)

                clippedCulverts = watershedGDB_path + os.sep + "Layers" + os.sep + projectName + "_clippedCulverts"
                gp.Clip_analysis(culvertLayer, projectAOI_path, clippedCulverts)

                gp.delete_management("AOI_lyr")
                gp.delete_management("culvertsTempLyr")
                del numOfCulverts
                del numOfCulvertsWithinAOI
                del numOfIntersectedCulverts

                gp.delete_management(culverts)
                gp.rename(clippedCulverts,culverts)

                AddMsgAndPrint("\n\t" + str(int(gp.GetCount_management(culverts).getOutput(0))) + " Culvert(s) will be used to hydro enforce " + os.path.basename(DEM_aoi),0)
                
                return True
        
        # all culverts are completely within AOI; Ideal scenario
        elif numOfCulvertsWithinAOI == numOfCulverts:

            AddMsgAndPrint("\n\t" + str(numOfCulverts) + " Culvert(s) will be used to hydro enforce " + os.path.basename(DEM_aoi),0)            
            
            gp.delete_management("AOI_lyr")
            gp.delete_management("culvertsTempLyr")
            del numOfCulverts
            del numOfCulvertsWithinAOI            
            
            return True

        # combination of scenarios.  Would require multiple outlets to have been digitized. A
        # will be required.
        else:

            gp.SelectLayerByAttribute_management("culvertsTempLyr", "CLEAR_SELECTION", "")
            gp.SelectLayerByLocation("culvertsTempLyr", "crossed_by_the_outline_of", "AOI_lyr")

            numOfIntersectedCulverts = int((gp.GetCount_management("culvertsTempLyr")).GetOutput(0))            

            AddMsgAndPrint("\t" + str(numOfCulverts) + " Culverts digitized",0)

            # there are some culverts crossing the AOI boundary and some within.
            if numOfIntersectedCulverts > 0 and numOfCulvertsWithinAOI > 0:
                
                AddMsgAndPrint("\n\tThere is " + str(numOfIntersectedCulverts) + " culvert(s) intersecting the AOI Boundary",0)
                AddMsgAndPrint("\tCulverts will be clipped to AOI",0)

            # there are some culverts outside the AOI boundary and some within.
            elif numOfIntersectedCulverts == 0 and numOfCulvertsWithinAOI > 0:

                AddMsgAndPrint("\n\tThere is " + str(numOfCulverts - numOfCulvertsWithinAOI) + " culvert(s) completely outside the AOI Boundary",0)
                AddMsgAndPrint("\tCulverts(s) will be clipped to AOI",0)             

            # All outlets are are intersecting the AOI boundary
            else:
                AddMsgAndPrint("\n\tOutlet(s) is intersecting the AOI Boundary and will be clipped to AOI",0)                

            clippedCulverts = watershedGDB_path + os.sep + "Layers" + os.sep + projectName + "_clippedCulverts"
            gp.Clip_analysis(culvertLayer, projectAOI_path, clippedCulverts)

            gp.delete_management("AOI_lyr")
            gp.delete_management("culvertsTempLyr")
            del numOfCulverts
            del numOfCulvertsWithinAOI
            del numOfIntersectedCulverts            

            gp.delete_management(culverts)
            gp.rename(clippedCulverts,culverts)

            AddMsgAndPrint("\n\t" + str(int(gp.GetCount_management(culverts).getOutput(0))) + " Culvert(s) will be used to hydro enforce " + os.path.basename(DEM_aoi),0)            
            
            return True

    except:
        AddMsgAndPrint("\nFailed to determine overlap with " + projectAOI_path + ". (determineOverlap)",2)
        print_exception()
        AddMsgAndPrint("No culverts will be used to hydro enforce " + os.path.basename(DEM_aoi),2)
        return False
    
## ================================================================================================================
# Import system modules
import sys, os, arcgisscripting, traceback

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
    gp.AddError("\nThis tool requires ArcGIS version 9.3 or Greater.....EXITING")
    sys.exit(0)           

try:
    # Check out Spatial Analyst License        
    if gp.CheckExtension("spatial") == "Available":
        gp.CheckOutExtension("spatial")
        
    else:
        gp.AddError("Spatial Analyst Extension not enabled. Please enable Spatial analyst from the Tools/Extensions menu")
        sys.exit("")

    # Script Parameters
    AOI = gp.getparameterastext(0)
    burnCulverts = gp.getparameterastext(1)  
    streamThreshold = gp.getparameterastext(2)

    # Uncomment the following  3 lines to run from pythonWin
##    AOI = r'C:\flex\flex_EngTools.gdb\Layers\Project_AOI'
##    burnCulverts = ""
##    streamThreshold = 1

    # --------------------------------------------------------------------------------------------- Define Variables 
    projectAOI_path = gp.Describe(AOI).CatalogPath

    if projectAOI_path.find('.gdb') > 0 and projectAOI_path.find('_AOI') > 0:
        watershedGDB_path = projectAOI_path[:projectAOI_path.find('.gdb')+4]
    else:
        gp.AddError("\n\n" + AOI + " is an invalid project_AOI Feature")
        gp.AddError("Run Watershed Delineation Tool #1. Define Area of Interest\n\n")
        sys.exit("")
        
    watershedGDB_name = os.path.basename(watershedGDB_path)
    userWorkspace = os.path.dirname(watershedGDB_path)
    projectName = gp.ValidateTablename(os.path.basename(userWorkspace).replace(" ","_"))

    # --------------------------------------------------------------- Datasets
    # ------------------------------ Permanent Datasets
    culverts = watershedGDB_path + os.sep + "Layers" + os.sep + projectName + "_Culverts"
    streams = watershedGDB_path + os.sep + "Layers" + os.sep + projectName + "_Streams"
    DEM_aoi = watershedGDB_path + os.sep + projectName + "_Raw_DEM"
    hydroDEM = watershedGDB_path + os.sep + "hydroDEM"
    Fill_hydroDEM = watershedGDB_path + os.sep + "Fill_hydroDEM"
    FlowAccum = watershedGDB_path + os.sep + "flowAccumulation"
    FlowDir = watershedGDB_path + os.sep + "flowDirection"

    # ----------------------------- Temporary Datasets
    aggregatedDEM = watershedGDB_path + os.sep + "agrDEM"
    culvertsTemp = watershedGDB_path + os.sep + "Layers" + os.sep + "culvertsTemp"
    culvertBuffered = watershedGDB_path + os.sep + "Layers" + os.sep + "Culverts_Buffered"
    culvertRaster = watershedGDB_path + os.sep + "culvertRaster"
    conFlowAccum = watershedGDB_path + os.sep + "conFlowAccum"
    streamLink = watershedGDB_path + os.sep + "streamLink"

    # check if culverts exist.  This is only needed b/c the script may be executed manually
    if burnCulverts == "#" or burnCulverts == "" or burnCulverts == False or int(gp.GetCount_management(burnCulverts).getOutput(0)) < 1 or len(burnCulverts) < 1:
        culvertsExist = False
        
    else:
        culvertsExist = True

    # Path of Log file
    textFilePath = userWorkspace + os.sep + projectName + "_EngTools.txt"

    # record basic user inputs and settings to log file for future purposes
    logBasicSettings()

    # ---------------------------------------------------------------------------------------------------------------------- Check Parameters
    # Make sure the FGDB and DEM_aoi exists from step 1
    if not gp.exists(watershedGDB_path) or not gp.exists(DEM_aoi):
        AddMsgAndPrint("\nThe \"" + str(projectName) + "_Raw_DEM\" raster file or the File Geodatabase from Step 1 was not found",2)
        AddMsgAndPrint("Run Wascob Design Tool #1. Define Area of Interest",2)
        sys.exit(0)

    # ----------------------------------------------------------------------------------------------------------------------- Delete old datasets
        
    datasetsToRemove = (streams,Fill_hydroDEM,hydroDEM,FlowAccum,FlowDir,culvertsTemp,culvertBuffered,culvertRaster,conFlowAccum,streamLink,aggregatedDEM)

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
    # -------------------------------------------------------------------------------------------------------------------- Retrieve DEM Properties
    aggregate = False
    desc = gp.Describe(DEM_aoi)
    sr = desc.SpatialReference

    units = sr.LinearUnitName
    if units == "Meter":
        units = "Meters"
    elif units == "Foot":
        units = "Feet"
    elif units == "Foot_US":
        units = "Feet"
        
    cellSize = desc.MeanCellWidth
    if units == "Feet":
        if cellSize < 10:
            cellSize = 10
            aggregate = True
    if units == "Meters":
        if cellSize < 3:
            cellSize = 3
            aggregate = True

    # Capture Default Environments
    tempExtent = gp.Extent
    tempMask = gp.mask
    tempSnapRaster = gp.SnapRaster
    tempCellSize = gp.CellSize
    tempCoordSys = gp.OutputCoordinateSystem

    # ----------------------------------- Set Environment Settings
    gp.Extent = "MINOF"
    gp.CellSize = cellSize
    gp.mask = ""
    gp.SnapRaster = ""
    gp.OutputCoordinateSystem = sr
    
    del desc
    del sr
    
    # If Cellsize was less than 3 meter or 10 foot resolution create aggregated DEM...
    if aggregate:
        AddMsgAndPrint("\nResampling raster...",1)
        gp.Resample_management(DEM_aoi, aggregatedDEM, cellSize, "BILINEAR")
        DEM_aoi = aggregatedDEM        
    # ------------------------------------------------------------------------------------------------------------------------ Incorporate Culverts into DEM
    reuseCulverts = False
    # Culverts will be incorporated into the DEM_aoi if at least 1 culvert is provided.
    if culvertsExist:

        if int(gp.GetCount_management(burnCulverts).getOutput(0)) > 0:

            # if paths are not the same then assume culverts were manually digitized
            # or input is some from some other feature class/shapefile
            if not gp.Describe(burnCulverts).CatalogPath == culverts:

                # delete the culverts feature class; new one will be created   
                if gp.exists(culverts):
                    
                    try:
                        gp.delete_management(culverts)
                        gp.CopyFeatures_management(burnCulverts, culverts)
                        AddMsgAndPrint("\nSuccessfully Recreated \"Culverts\" feature class.",1)
                        
                    except:
                        print_exception()
                        gp.OverWriteOutput = 1

                else:
                    gp.CopyFeatures_management(burnCulverts, culverts)
                    AddMsgAndPrint("\nSuccessfully Created \"Culverts\" feature class",1)           

            # paths are the same therefore input was from within FGDB
            else:
                AddMsgAndPrint("\nUsing Existing \"Culverts\" feature class:",1)
                reuseCulverts = True

            # --------------------------------------------------------------------- determine overlap of culverts & AOI
            AddMsgAndPrint("\nChecking Placement of Culverts",1)
            proceed = False

            if determineOverlap(culverts):
                proceed = True

            # ------------------------------------------------------------------- Buffer Culverts
            if proceed:

                # determine linear units to set buffer value to the equivalent of 1 pixel
                if gp.Describe(DEM_aoi).SpatialReference.LinearUnitName == "Meter":
                    bufferSize = str(cellSize) + " Meters"
                    AddMsgAndPrint("\nBuffer size applied on Culverts: " + str(cellSize) + " Meter(s)",1)

                elif gp.Describe(DEM_aoi).SpatialReference.LinearUnitName == "Foot":
                    bufferSize = str(cellSize) + " Feet"
                    AddMsgAndPrint("\nBuffer size applied on Culverts: " + bufferSize,1)
                    
                elif gp.Describe(DEM_aoi).SpatialReference.LinearUnitName == "Foot_US":
                    bufferSize = str(cellSize) + " Feet"
                    AddMsgAndPrint("\nBuffer size applied on Culverts: " + bufferSize,1)
                    
                else:
                    bufferSize = str(cellSize) + " Unknown"
                    AddMsgAndPrint("\nBuffer size applied on Culverts: Equivalent of 1 pixel since linear units are unknown",0)
                    
                # Buffer the culverts to 1 pixel
                gp.Buffer_analysis(culverts, culvertBuffered, bufferSize, "FULL", "ROUND", "NONE", "")

                # Dummy field just to execute Zonal stats on each feature
                gp.AddField_management(culvertBuffered, "ZONE", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
                gp.CalculateField_management(culvertBuffered, "ZONE", "[OBJECTID]", "VB", "")

                gp.ZonalStatistics_sa(culvertBuffered, "ZONE", DEM_aoi, culvertRaster, "MINIMUM", "NODATA")
                AddMsgAndPrint("\nApplying the minimum Zonal DEM Value to the Culverts",1)

                # Elevation cells that overlap the culverts will get the minimum elevation value
                mosaicList = DEM_aoi + ";" + culvertRaster
                gp.MosaicToNewRaster_management(mosaicList, watershedGDB_path, "hydroDEM", "#", "32_BIT_FLOAT", cellSize, "1", "LAST", "#")
                AddMsgAndPrint("\nFusing Culverts and Raw DEM to create " + os.path.basename(hydroDEM),1)

                gp.Fill_sa(hydroDEM, Fill_hydroDEM)
                AddMsgAndPrint("\nSuccessfully filled sinks in " + os.path.basename(hydroDEM) + " to remove small imperfections",1)

                del bufferSize
                del mosaicList

                # Delete unwanted datasets
                gp.delete_management(culvertBuffered)
                gp.delete_management(culvertRaster)

            # No Culverts will be used due to no overlap or determining overlap error.
            else:
                cellSize = gp.Describe(DEM_aoi).MeanCellWidth
                gp.Fill_sa(DEM_aoi, Fill_hydroDEM)
                AddMsgAndPrint("\nSuccessfully filled sinks in " + os.path.basename(hydroDEM) + " to remove small imperfections",1)

            del proceed
            
        # No culverts were detected.
        else:
            AddMsgAndPrint("\nNo Culverts detected!",1)
            cellSize = gp.Describe(DEM_aoi).MeanCellWidth
            gp.Fill_sa(DEM_aoi, Fill_hydroDEM)
            AddMsgAndPrint("\nSuccessfully filled sinks in " + os.path.basename(DEM_aoi) + " to remove small imperfections",1)

    else:
        AddMsgAndPrint("\nNo Culverts detected!",1)
        cellSize = gp.Describe(DEM_aoi).MeanCellWidth
        gp.Fill_sa(DEM_aoi, Fill_hydroDEM)
        AddMsgAndPrint("\nSuccessfully filled sinks in " + os.path.basename(DEM_aoi) + " to remove small imperfections",1)            

    # ---------------------------------------------------------------------------------------------- Create Stream Network
    # Create Flow Direction Grid...
    gp.FlowDirection_sa(Fill_hydroDEM, FlowDir, "NORMAL", "")

    # Create Flow Accumulation Grid...
    gp.FlowAccumulation_sa(FlowDir, FlowAccum, "", "INTEGER")

    AddMsgAndPrint("\nSuccessfully created Flow Accumulation and Flow Direction",1)

    # stream link will be created using pixels that have a flow accumulation greater than the
    # user-specified acre threshold
    if streamThreshold > 0:

        # Calculating flow accumulation value for appropriate acre threshold
        if gp.Describe(DEM_aoi).SpatialReference.LinearUnitName == "Meter":
            acreThresholdVal = round((float(streamThreshold) * 4046.85642)/(cellSize*cellSize))
            conExpression = "Value >= " + str(acreThresholdVal)

        elif gp.Describe(DEM_aoi).SpatialReference.LinearUnitName == "Foot":
            acreThresholdVal = round((float(streamThreshold) * 43560)/(cellSize*cellSize))
            conExpression = "Value >= " + str(acreThresholdVal)
            
        elif gp.Describe(DEM_aoi).SpatialReference.LinearUnitName == "Foot_US":
            acreThresholdVal = round((float(streamThreshold) * 43560)/(cellSize*cellSize))
            conExpression = "Value >= " + str(acreThresholdVal)

        else:
            acreThresholdVal = round(float(streamThreshold)/(cellSize*cellSize))
            conExpression = "Value >= " + str(acreThresholdVal)

        # Select all cells that are greater than conExpression
        gp.Con_sa(FlowAccum, FlowAccum, conFlowAccum, "", conExpression)

        # Create Stream Link Works
        gp.StreamLink_sa(conFlowAccum, FlowDir, streamLink)
        del conExpression    

    # All values in flowAccum will be used to create sream link
    else:
        acreThresholdVal = 0
        gp.StreamLink_sa(FlowAccum, FlowDir, streamLink)

    # Converts a raster representing a linear network to features representing the linear network.
    # creates field grid_code
    gp.StreamToFeature_sa(streamLink, FlowDir, streams, "SIMPLIFY")
    AddMsgAndPrint("\nSuccessfully created stream linear network using a flow accumulation value >= " + str(acreThresholdVal),1)

    # ------------------------------------------------------------------------------------------------ Delete unwanted datasets
    gp.delete_management(Fill_hydroDEM)
    gp.delete_management(conFlowAccum)
    gp.delete_management(streamLink)

    # ------------------------------------------------------------------------------------------------ Compact FGDB
    try:
        gp.compact_management(watershedGDB_path)
        AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path),1)    
    except:
        pass

    # ------------------------------------------------------------------------------------------------ Prepare to Add to Arcmap    

    gp.SetParameterAsText(3, streams)
    
    if not reuseCulverts:
        gp.SetParameterAsText(4, culverts)
    
    AddMsgAndPrint("\nAdding Layers to ArcMap",1)
    AddMsgAndPrint("",1)

    # ------------------------------------------------------------------------------------------------ Clean up Time!
    gp.RefreshCatalog(watershedGDB_path)
    
    # Restore original environments
    gp.extent = tempExtent
    gp.mask = tempMask
    gp.SnapRaster = tempSnapRaster
    gp.CellSize = tempCellSize
    gp.OutputCoordinateSystem = tempCoordSys

    try:
        del AOI
        del burnCulverts
        del streamThreshold
        del projectAOI_path
        del watershedGDB_path
        del watershedGDB_name
        del userWorkspace
        del culverts
        del streams
        del DEM_aoi
        del hydroDEM
        del Fill_hydroDEM
        del FlowAccum
        del FlowDir
        del culvertBuffered
        del culvertRaster
        del conFlowAccum
        del streamLink
        del culvertsExist
        del textFilePath
        del cellSize
        del acreThresholdVal
        del projectName
        del version
        del reuseCulverts
        del ArcGIS10
        del tempExtent
        del tempMask
        del tempSnapRaster
        del tempCellSize
        del tempCoordSys
        del gp
    except:
        pass
    
except SystemExit:
    pass

except KeyboardInterrupt:
    AddMsgAndPrint("Interruption requested....exiting")

except:
    print_exception()    







        


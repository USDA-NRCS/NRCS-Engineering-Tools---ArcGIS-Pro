# ---------------------------------------------------------------------------
# designHeight.py
#
# Peter Mead USDA NRCS 
#
# Creates embankment points for stakeout, Allows user input of intake location.
# Appends results to "StakeoutPoints" Layer in Table of contents.
#
# ---------------------------------------------------------------------------
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
    f.write("Executing \"7. Wascob Design Height & Intake Location\" Tool\n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write("User Parameters:\n")
    f.write("\tInput Watershed: " + inWatershed + "\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tSelected Subbasin: " + Subbasin + "\n")
    f.write("\tDesign Elevation: " + DesignElev + "\n") 
    f.write("\tIntake Elevation: " + IntakeElev + "\n")    
        
    f.close
    del f   

## ================================================================================================================
# Import system modules
import sys, os, arcgisscripting, traceback, string

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
    if gp.CheckExtension("spatial") == "Available":gp.CheckOutExtension("spatial")
    else:
        gp.AddError("Spatial Analyst Extension not enabled. Please enable Spatial analyst from the Tools/Extensions menu")
        sys.exit("")
        
    # ---------------------------------------------- Input Parameters
    inWatershed = gp.GetParameterAsText(0)
    Subbasin = gp.GetParameterAsText(1)
    DesignElev = gp.GetParameterAsText(2)
    IntakeElev = gp.GetParameterAsText(3)
    IntakeLocation = gp.GetParameterAsText(4)

    # ---------------------------------------------------------------------------- Define Variables 
    watershed_path = gp.Describe(inWatershed).CatalogPath
    watershedGDB_path = watershed_path[:watershed_path .find(".gdb")+4]
    watershedGDB_name = os.path.basename(watershedGDB_path)
    watershedFD_path = watershedGDB_path + os.sep + "Layers"
    userWorkspace = os.path.dirname(watershedGDB_path)
    wsName = os.path.basename(inWatershed)
    
    # ---------------------------------------------------------------------------- Existing Datasets
    stakeoutPoints = watershedFD_path + os.sep + "stakeoutPoints"
    DEM_aoi = watershedGDB_path + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_Project_DEM"
    #DEM_aoi = watershedGDB_path + os.sep + "Project_DEM"


    # ------------- Layers in ArcMap
    stakeoutPoints = "stakeoutPoints"
    ReferenceLine = "ReferenceLine"

    # --------------------------------------------------------------------------- Temporary Datasets
    RefLineLyr = "ReferenceLineLyr"
    stakeoutPointsLyr ="stakeoutPointsLyr"
    pointsSelection = "pointsSelection"
    refLineSelection = "refLineSelection"
    refTemp = watershedFD_path + os.sep + "refTemp"
    intake = watershedFD_path + os.sep + "intake"
    refTempClip = watershedFD_path + os.sep + "refTemp_Clip"
    refPoints = watershedFD_path + os.sep + "refPoints"
    WSmask = watershedFD_path + os.sep + "WSmask"
    DA_Dem = watershedGDB_path + os.sep + "da_dem"
    DA_sn = watershedGDB_path + os.sep + "da_sn"
    DAint = watershedGDB_path + os.sep + "daint"
    DAx0 = watershedGDB_path + os.sep + "dax0"
    DA_snPoly = watershedGDB_path + os.sep + "DA_snPoly"

    # Path of Log file
    textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_WascobTools.txt"

    # record basic user inputs and settings to log file for future purposes
    logBasicSettings()
   
    # ---------------------------------------------------------------------------- Check inputs
    if not gp.Exists(DEM_aoi):
        AddMsgAndPrint("\nMissing Project_DEM from FGDB. Can not perform raster analysis.",2)
        AddMsgAndPrint("Project_DEM must be in the same geodatabase as your input watershed.",2)
        AddMsgAndPrint("\nCheck your the source of your provided watershed.",2)
        AddMsgAndPrint("and/or export ProjectDEM from the table of contents to",2)
        AddMsgAndPrint("the geodatabase where your provided watershed resides",2)
        AddMsgAndPrint("as <yourworkspace>_Wascob.gdb\Project_DEM...EXITING",2)
        sys.exit("")
            
    if not gp.Exists(ReferenceLine):
        AddMsgAndPrint("\nReference Line not found in table of contents or in the workspace of your input watershed",2)
        AddMsgAndPrint("\nDouble check your inputs and workspace....EXITING",2)
        sys.exit("")

    if not gp.Exists(stakeoutPoints):
        gp.CreateFeatureclass_management(watershedFD_path, "stakeoutPoints", "POINT", "", "DISABLED", "DISABLED", "", "", "0", "0", "0")
        gp.AddField_management(stakeoutPoints, "ID", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        gp.AddField_management(stakeoutPoints, "Subbasin", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        gp.AddField_management(stakeoutPoints, "Elev", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        gp.AddField_management(stakeoutPoints, "Notes", "TEXT", "", "", "50", "", "NULLABLE", "NON_REQUIRED", "")
            
    if int(gp.GetCount_management(IntakeLocation).getOutput(0)) > 1:
        # Exit if user input more than one intake
        AddMsgAndPrint("\nYou provided more than one inlet location",2)
        AddMsgAndPrint("Each subbasin must be completed individually,",2)
        AddMsgAndPrint("with one intake provided each time you run this tool.",2)
        AddMsgAndPrint("Try again with only one intake loacation....EXITING",2)
        sys.exit("")
        
    elif int(gp.GetCount_management(IntakeLocation).getOutput(0)) < 1:
        # Exit if no intake point was provided
        AddMsgAndPrint("\nYou did not provide a point for your intake loaction",2)
        AddMsgAndPrint("You must create a point at the proposed inlet location by using",2)
        AddMsgAndPrint("the Add Features tool in the Design Height tool dialog box...EXITING",2)
        sys.exit("")

    # ----------------------------------- Capture Default Environments
    tempExtent = gp.Extent
    tempMask = gp.mask
    tempSnapRaster = gp.SnapRaster
    tempCellSize = gp.CellSize
    tempCoordSys = gp.OutputCoordinateSystem
    
    # ---------------------------------- Retrieve Raster Properties
    desc = gp.Describe(DEM_aoi)
    sr = desc.SpatialReference
    cellSize = desc.MeanCellWidth
    
    # ----------------------------------- Set Environment Settings
    gp.Extent = "MINOF"
    gp.CellSize = cellSize
    gp.mask = ""
    gp.SnapRaster = ""
    gp.OutputCoordinateSystem = sr
    
    del desc, sr        
    
    # ----------------------------------------------------- Select reference line for specified Subbasin
    gp.MakeFeatureLayer_management(ReferenceLine, RefLineLyr)
    exp = "\"Subbasin\" = " + str(Subbasin) + ""
    AddMsgAndPrint("\nSelecting Reference Line for subbasin " + str(Subbasin),1)
    gp.SelectLayerByAttribute_management(RefLineLyr, "NEW_SELECTION", exp)
    gp.MakeFeatureLayer_management(RefLineLyr, refLineSelection)
    
    if not int(gp.GetCount_management(refLineSelection).getOutput(0)) > 0:
        # Exit if no corresponding subbasin id found in reference line
        AddMsgAndPrint("\nNo reference line features were found for subbasin " + str(Subbasin),2)
        AddMsgAndPrint("Double check your inputs and specify a different subbasin ID ..EXITING",2)
        sys.exit("")
        
    gp.CopyFeatures_management(refLineSelection, refTemp, "", "0", "0", "0")
    gp.SelectLayerByAttribute_management(RefLineLyr, "CLEAR_SELECTION", "")

    # Select any existing Reference points for specified basin and delete
    gp.MakeFeatureLayer_management(stakeoutPoints, stakeoutPointsLyr)
    gp.SelectLayerByAttribute_management(stakeoutPointsLyr, "NEW_SELECTION", exp)
    gp.MakeFeatureLayer_management(stakeoutPointsLyr, pointsSelection)
    if int(gp.GetCount_management(pointsSelection).getOutput(0)) > 0:
        gp.DeleteFeatures_management(pointsSelection)
    gp.SelectLayerByAttribute_management(stakeoutPointsLyr, "CLEAR_SELECTION", "")
    
    # Create Intake from user input and append to Stakeout Points
    AddMsgAndPrint("\nCreating Intake Reference Point...",1)
    gp.CopyFeatures_management(IntakeLocation, intake, "", "0", "0", "0")
    gp.CalculateField_management(intake, "Id", "" + str(Subbasin)+ "", "VB", "")
    gp.CalculateField_management(intake, "Subbasin", "" + str(Subbasin)+ "", "VB", "")
    gp.CalculateField_management(intake, "Elev", "" + str(IntakeElev)+ "", "VB", "")
    gp.CalculateField_management(intake, "Notes", "\"Intake\"", "VB", "")
    AddMsgAndPrint("\n\tSuccessfully created intake for subbasin " + str(Subbasin) + " at " + str(IntakeElev) + " feet",0)
    AddMsgAndPrint("\tAppending results to Stakeout Points",0)
    gp.Append_management(intake, stakeoutPoints, "NO_TEST", "", "")
    
    # Use DEM to determine intersection of Reference Line and Plane @ Design Elevation
    AddMsgAndPrint("\nCalculating Pool Extent...",1)
    gp.SelectLayerByAttribute_management(inWatershed, "NEW_SELECTION", exp)
    gp.CopyFeatures_management(inWatershed, WSmask, "", "0", "0", "0")
    gp.SelectLayerByAttribute_management(inWatershed, "CLEAR_SELECTION", "")
    gp.ExtractByMask_sa(DEM_aoi, WSmask, DA_Dem)
    gp.SetNull_sa(DA_Dem, DA_Dem, DA_sn, "VALUE > " + str(DesignElev))
    gp.Times_sa(DA_sn, "0", DAx0)
    gp.Int_sa(DAx0, DAint)
    gp.RasterToPolygon_conversion(DAint, DA_snPoly, "NO_SIMPLIFY", "VALUE")

    AddMsgAndPrint("\nCreating Embankment Reference Points...",1)
    gp.Clip_analysis(refTemp, DA_snPoly, refTempClip, "")
    gp.FeatureVerticesToPoints_management(refTempClip, refPoints, "BOTH_ENDS")
    AddMsgAndPrint("\n\tSuccessfully created " +  str(int(gp.GetCount_management(refPoints).getOutput(0))) + " reference points at " + str(DesignElev) + " feet",0)
    gp.AddField_management(refPoints, "Id", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.CalculateField_management(refPoints, "Id", "" + str(Subbasin)+ "", "VB", "")
    gp.AddField_management(refPoints, "Elev", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.CalculateField_management(refPoints, "Elev", "" + str(DesignElev)+ "", "VB", "")
    gp.AddField_management(refPoints, "Notes", "TEXT", "", "", "50", "", "NULLABLE", "NON_REQUIRED", "")
    gp.CalculateField_management(refPoints, "Notes", "\"Embankment\"", "VB", "")
    AddMsgAndPrint("\tAppending Results to Stakeout Points",0)
    gp.Append_management(refPoints, stakeoutPoints, "NO_TEST", "", "")

    # Add XY Coordinates to Stakeout Points
    AddMsgAndPrint("\nAdding XY Coordinates to Stakeout Points...",1)
    gp.AddXY_management(stakeoutPoints)

    # -------------------------------------------------------------- Delete Intermediate Files
    datasetsToRemove = (stakeoutPointsLyr,RefLineLyr,pointsSelection,refLineSelection,refTemp,intake,refTempClip,refPoints,WSmask,DA_Dem,DA_sn,DAint,DAx0,DA_snPoly)

    x = 0
    for dataset in datasetsToRemove:

        if gp.exists(dataset):

            if x < 1:
                AddMsgAndPrint("\nDeleting temporary data.." ,1)
                x += 1
                
            try:
                gp.delete_management(dataset)
            except:
                pass
            
    del dataset
    del datasetsToRemove
    del x
    
    # ------------------------------------------------------------------------------------------------ Compact FGDB
    try:
        gp.compact_management(watershedGDB_path)
        AddMsgAndPrint(" \nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path),1)
    except:
        pass

    # ------------------------------------------------------------------------------------------------ add to ArcMap
    AddMsgAndPrint("\nAdding Results to ArcMap",1)
    AddMsgAndPrint("\n",1)
    gp.SetParameterAsText(5, stakeoutPoints)

    
    AddMsgAndPrint("\nProcessing Finished!\n",1)

    # -------------------------------------------------------------- Cleanup

    gp.RefreshCatalog(watershedGDB_path)
    
    # Restore original environments
    gp.extent = tempExtent
    gp.mask = tempMask
    gp.SnapRaster = tempSnapRaster
    gp.CellSize = tempCellSize
    gp.OutputCoordinateSystem = tempCoordSys
    
    try:
        del inWatershed
        del Subbasin
        del DesignElev
        del IntakeElev
        del IntakeLocation
        del watershedGDB_path
        del watershedGDB_name
        del userWorkspace
        del watershed_path
        del watershedFD_path
        del wsName
        del DEM_aoi
        del ReferenceLine
        del stakeoutPoints
        del RefLineLyr
        del stakeoutPointsLyr
        del pointsSelection
        del refLineSelection
        del refTemp
        del intake
        del refTempClip
        del refPoints
        del WSmask
        del DA_Dem
        del DA_sn
        del DAint
        del DAx0
        del DA_snPoly
        del textFilePath
        del exp
        del ArcGIS10
        del version
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

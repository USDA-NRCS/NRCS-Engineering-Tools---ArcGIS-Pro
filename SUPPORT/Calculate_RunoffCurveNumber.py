
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
    f.write("Executing \"2.Calculate Runoff Curve Number\" Tool \n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write("ArcGIS Version: " + str(version) + "\n")
    f.write("User Parameters:\n")
    f.write("\tinWatershed: " + inWatershed + "\n")
    
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
    gp.AddError("\nThis tool requires ArcGIS version 9.3 or Greater.....EXITING")
    sys.exit("")          

try:
    # Script Parameters
    inWatershed = gp.GetParameterAsText(0)
    
    # Uncomment line below to run from pythonWin
##    inWatershed = r'C:\flex\flex_EngTools.gdb\Layers\testing10_Watershed'

    # ---------------------------------------------------------------------------- Define Variables
    # inWatershed can ONLY be a feature class
    watershed_path = gp.Describe(inWatershed).CatalogPath
    
    if watershed_path.find('.gdb') > 0:
        watershedGDB_path = watershed_path[:watershed_path.find('.gdb')+4]
        
    else:
        AddMsgAndPrint("\n\nWatershed Layer must be a File Geodatabase Feature Class!.....Exiting",2)
        AddMsgAndPrint("You must run \"Prepare Soils and Landuse\" tool first before running this tool\n",2)
        sys.exit()    

    watershedFD_path = watershedGDB_path + os.sep + "Layers"
    watershedGDB_name = os.path.basename(watershedGDB_path)
    userWorkspace = os.path.dirname(watershedGDB_path)
    wsName = os.path.basename(inWatershed)

    inLanduse = watershedFD_path + os.sep + wsName + "_Landuse"
    inSoils = watershedFD_path + os.sep + wsName + "_Soils"

    # -------------------------------------------------------------------------- Permanent Datasets
    rcn = watershedFD_path + os.sep + wsName + "_RCN"

    # log File Path
    textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.txt"

    # record basic user inputs and settings to log file for future purposes
    logBasicSettings()    

    # -------------------------------------------------------------------------- Temporary Datasets
    luLayer = "landuseLyr"
    soilsLyr = "soilsLyr"
    watershedLanduseInt = watershedFD_path + os.sep + "watershedLanduseInt"
    wtshdLanduseSoilsIntersect = watershedFD_path + os.sep + "wtshdLanduseSoilsIntersect"
    wtshdLanduseSoilsIntersect_Layer = "soils_lu_lyr"
    wtshdLanduseSoils_dissolve = watershedFD_path + os.sep + "wtshdLanduseSoils_dissolve"
    rcn_stats = watershedGDB_path + os.sep + "rcn_stats"
    rcnLayer = "rcnLayer"

    # ---------------------------------------------------- Map Layers   
    rcnOut = "" + str(wsName) + "_RCN"

    # -------------------------------------------------------------------------- Lookup Tables
    HYD_GRP_Lookup_Table = os.path.join(os.path.dirname(sys.argv[0]), "Support.gdb" + os.sep + "HYD_GRP_Lookup")
    TR_55_RCN_Lookup = os.path.join(os.path.dirname(sys.argv[0]), "Support.gdb" + os.sep + "TR_55_RCN_Lookup")

    # -------------------------------------------------------------------------- Check Soils / Landuse Inputs
    # Exit if input watershed is landuse or soils layer
    if inWatershed.find("_Landuse") > 0 or inWatershed.find("_Soils") > 0:
        AddMsgAndPrint("\nYou have mistakingly inputted your landuse or soils layer...Enter your watershed layer!",2)
        AddMsgAndPrint("Exiting",2)
        sys.exit("")
        
    # Exit if "Subbasin" field not found in watershed layer
    if not len(gp.ListFields(inWatershed,"Subbasin")) > 0:
        AddMsgAndPrint("\n\"Subbasin\" field was not found in " + os.path.basename(inWatershed) + "layer\n",2)
        AddMsgAndPrint("You must run \"Prepare Soils and Landuse\" tool first before running this tool\n",2)
        sys.exit("")

    # Exit if Soils fc not found in FD        
    if not gp.Exists(inSoils):
        AddMsgAndPrint("\nSoils data not found in " + str(watershedFD_path) + "\n",2)
        AddMsgAndPrint("You must run \"Prepare Soils and Landuse\" tool first before running this tool\n",2)
        sys.exit("")

    # Exit if landuse fc not found in FD
    if not gp.Exists(inLanduse):
        AddMsgAndPrint("\nLanduse data not present in " + str(watershedFD_path) +".\n",2)
        AddMsgAndPrint("You must run Step 1. -Prepare Soils and Landuse - first, and attribute the resulting Watershed Soils and Landuse Layers..EXITING.\n",2)
        sys.exit("")        

    # Exit if Hydro group lookup table is missing
    if not gp.Exists(HYD_GRP_Lookup_Table):
        AddMsgAndPrint("\n\"HYD_GRP_Lookup_Table\" was not found! Make sure \"Support.gdb\" is located within the same location as this script",2)
        sys.exit("")

    # Exit if TR 55 lookup table is missing
    if not gp.Exists(TR_55_RCN_Lookup):
        AddMsgAndPrint("\n\"TR_55_RCN_Lookup\" was not found! Make sure \"Support.gdb\" is located within the same location as this script",2)
        sys.exit("")

    # ---------------------------------------------------------------------------------------------- Check for RCN Grid:
    # If NLCD Curve Number tool was executed on specified watershed and a curve number grid was created, overwrite error
    # will result as rcn output feature class in feature dataset will have same name as existing FGDB raster. 
    rcnGrid = watershedGDB_path + os.sep + wsName + "_RCN"
    rcnGridLyr = "" + wsName + "_RCN"
    renameGrid = watershedGDB_path + os.sep + wsName + "_RCN_Grid"
    x = 1
    # Check for Watershed RCN Grid in TOC
    if gp.Exists(rcnGridLyr):
        # Remove if present
        gp.Delete_management(rcnGridLyr)
    # Check for RCN Grid in FGDB
    if gp.Exists(rcnGrid):
        while x > 0:
            # Make sure renameGrid has a unique name
            if gp.Exists(renameGrid):
                renameGrid = watershedGDB_path + os.sep + wsName + "_RCN_Grid" + str(x)
                x += 1
            else:
                x = 0
        # rename RCN Grid if present
        gp.rename(rcnGrid,renameGrid)
        AddMsgAndPrint("\nIt appears you have previously created a RCN Grid for " + wsName,1)
        AddMsgAndPrint("\n\t" + wsName+ "'s RCN Grid has been renamed to " + str(os.path.basename(renameGrid)),0)
        AddMsgAndPrint("\tto avoid any overwrite errors",0)

    del rcnGrid, renameGrid, rcnGridLyr, x
    gp.RefreshCatalog(watershedGDB_path)
    
    # ------------------------------------------------------------------------------------------------ Check for Null Values in Landuse Field
    AddMsgAndPrint("\nChecking Values in landuse layer...",1)
    gp.MakeFeatureLayer_management(inLanduse, luLayer, "", "", "")

    # Landuse Field MUST be populated.  It is acceptable to have Condition field unpopulated.
    query = "\"LANDUSE\" LIKE '%Select%' OR \"LANDUSE\" Is Null"
    gp.SelectLayerByAttribute_management(luLayer, "NEW_SELECTION", query)

    nullFeatures = int(gp.GetCount_management(luLayer).getOutput(0))
    
    if  nullFeatures > 0:
        AddMsgAndPrint("\n\tThere are " + str(nullFeatures) + " NULL or un-populated values in the LANDUSE or CONDITION Field of your landuse layer.",2)
        AddMsgAndPrint("\tMake sure all rows are attributed in an edit session, save your edits, stop editing and re-run this tool.",2)
        gp.Delete_management(luLayer)
        sys.exit("")

    gp.Delete_management(luLayer)
        
    del query, nullFeatures

    # ------------------------------------------------------------------------------------------------ Check for Combined Classes in Soils Layer...
    AddMsgAndPrint("\nChecking Values in soils layer...",1)
    gp.MakeFeatureLayer_management(inSoils, soilsLyr, "", "", "")

    query = "\"HYDGROUP\" LIKE '%/%' OR \"HYDGROUP\" Is Null"
    gp.SelectLayerByAttribute_management(soilsLyr, "NEW_SELECTION", query)
    
    combClasses = int(gp.GetCount_management(soilsLyr).getOutput(0))
    gp.SelectLayerByAttribute_management(soilsLyr, "CLEAR_SELECTION", "")

    if combClasses > 0:
        AddMsgAndPrint("\n\tThere are " + str(combClasses) + " Combined or un-populated classes in the HYDGROUP Field of your watershed soils layer.",2)
        AddMsgAndPrint("\tYou will need to make sure all rows are attributed with a single class in an edit session,",2)
        AddMsgAndPrint("\tsave your edits, stop editing and re-run this tool.\n",2)
        gp.Delete_management(soilsLyr)
        sys.exit("")

    gp.Delete_management(soilsLyr)

    del combClasses, query   

    # -------------------------------------------------------------------------- Delete Previous Map Layer if present
    if gp.Exists(rcnOut):
        AddMsgAndPrint("\nRemoving previous layers from your ArcMap session",1)
        AddMsgAndPrint("\tRemoving....." + str(wsName) + "_RCN",0)
        gp.Delete_management(rcnOut)

    # -------------------------------------------------------------------------- Delete Previous Data if present 
    datasetsToRemove = (rcn,watershedLanduseInt,wtshdLanduseSoilsIntersect_Layer,wtshdLanduseSoils_dissolve,rcn_stats,luLayer,soilsLyr,rcnLayer)

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

    # ------------------------------------------------------------------------------------------------ Intersect Soils, Landuse and Subbasins.
    if not len(gp.ListFields(inWatershed,"RCN")) > 0:
        gp.AddField_management(inWatershed, "RCN", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

    if not len(gp.ListFields(inWatershed,"Acres")) > 0:
        gp.AddField_management(inWatershed, "Acres", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        
    gp.CalculateField_management(inWatershed, "Acres", "!shape.area@ACRES!", "PYTHON", "")

    gp.Intersect_analysis(inWatershed + "; " + inLanduse, watershedLanduseInt, "NO_FID", "", "INPUT")
    gp.Intersect_analysis(watershedLanduseInt + "; " + inSoils, wtshdLanduseSoilsIntersect, "NO_FID", "", "INPUT")
        
    gp.AddField_management(wtshdLanduseSoilsIntersect, "LUDESC", "TEXT", "255", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.AddField_management(wtshdLanduseSoilsIntersect, "LU_CODE", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.AddField_management(wtshdLanduseSoilsIntersect, "HYDROL_ID", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.AddField_management(wtshdLanduseSoilsIntersect, "HYD_CODE", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.AddField_management(wtshdLanduseSoilsIntersect, "RCN_ACRES", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.AddField_management(wtshdLanduseSoilsIntersect, "WGTRCN", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.AddField_management(wtshdLanduseSoilsIntersect, "IDENT", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

    gp.Delete_management(watershedLanduseInt)

    AddMsgAndPrint("\nSuccessfully intersected Hydrologic Groups, Landuse, and Subbasin Boundaries",1)    
    
    # ------------------------------------------------------------------------------------------------ Perform Checks on Landuse and Condition Attributes
    # Make all edits to feature layer; delete intersect fc.
    gp.MakeFeatureLayer_management(wtshdLanduseSoilsIntersect, wtshdLanduseSoilsIntersect_Layer, "", "", "")
    
    AddMsgAndPrint("\nChecking Landuse and Condition Values in intersected data",1)
    assumptions = 0

    #+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Check #1: Set the condition to the following landuses to NULL
    query = "\"LANDUSE\" = 'Fallow Bare Soil' OR \"LANDUSE\" = 'Farmstead' OR \"LANDUSE\" LIKE 'Roads%' OR \"LANDUSE\" LIKE 'Paved%' OR \"LANDUSE\" LIKE '%Districts%' OR \"LANDUSE\" LIKE 'Newly Graded%' OR \"LANDUSE\" LIKE 'Surface Water%' OR \"LANDUSE\" LIKE 'Wetland%'"
    gp.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "NEW_SELECTION", query)
    count = int(gp.GetCount_management(wtshdLanduseSoilsIntersect_Layer).getOutput(0))

    if count > 0:    
        gp.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "CONDITION", "\"\"", "VB", "")
    
    gp.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "CLEAR_SELECTION", "")
    del query, count

    #+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Check #2: Convert All 'N/A' Conditions to 'Good'
    gp.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "NEW_SELECTION", "\"CONDITION\" = 'N/A'")                                        
    count = int(gp.GetCount_management(wtshdLanduseSoilsIntersect_Layer).getOutput(0))

    if count > 0:
        AddMsgAndPrint("\n\tThere were " + str(count) + " Landuse polygons with CONDITION 'N/A' that require a condition of Poor, Fair, or Good.",1)
        AddMsgAndPrint("\tCondition for these areas will be assumed to be 'Good'.",1)
        gp.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "CONDITION", '"Good"', "VB", "")
        assumptions = assumptions + 1

    gp.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "CLEAR_SELECTION", "")
    del count
    
    #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Check #3: "Open Space Grass Cover 50 to 75 percent" should have a condition of "Fair"
    query = "\"LANDUSE\" = 'Open Space Grass Cover 50 to 75 percent' AND \"CONDITION\" <> 'Fair'"
    gp.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "NEW_SELECTION", query)
    count = int(gp.GetCount_management(wtshdLanduseSoilsIntersect_Layer).getOutput(0))
    
    if count > 0:
        AddMsgAndPrint("\n\tThere were " + str(count) + " 'Open Space Grass Cover 50 to 75 percent' polygons with a condition other than fair.",1)
        AddMsgAndPrint("\tA condition of fair will be assigned to these polygons.",1)
        gp.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "CONDITION", '"Fair"', "VB", "")
        assumptions = assumptions + 1

    gp.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "CLEAR_SELECTION", "")
    del query, count
    
    #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Check #4: "Open Space Grass Cover greater than 75 percent" should have a condition of "Good"
    query = "\"LANDUSE\" = 'Open Space Grass Cover greater than 75 percent' AND \"CONDITION\" <> 'Good'"
    gp.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "NEW_SELECTION", query)
    count = int(gp.GetCount_management(wtshdLanduseSoilsIntersect_Layer).getOutput(0))
    
    if count > 0:
        AddMsgAndPrint("\n\tThere were " + str(count) + " 'Open Space Grass Cover greater than 75 percent' polygons with a condition other than Good. Greater than 75 percent cover assumes a condition of 'Good'..\n",1)
        AddMsgAndPrint("\tA condition of Good will be assigned to these polygons.\n",1)
        gp.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "CONDITION", '"Good"', "VB", "")
        assumptions = assumptions + 1

    gp.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "CLEAR_SELECTION", "")
    del query, count        

    #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Check #5: "Open Space, Grass Cover less than 50 percent" should have a condition of "Poor"
    query = "\"LANDUSE\" = 'Open Space, Grass Cover less than 50 percent' AND  \"CONDITION\" <> 'Poor'"
    gp.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "NEW_SELECTION", query)
    count = int(gp.GetCount_management(wtshdLanduseSoilsIntersect_Layer).getOutput(0))
    
    if count > 0:
        AddMsgAndPrint("\n\n\tThere were " + str(count) + " 'Open Space, Grass Cover less than 50 percent' polygons with a condition other than Poor. Less than 50 percent cover assumes a condition of 'Poor'..\n",1)
        AddMsgAndPrint("\tA condition of Poor will be assigned to these polygons.\n",1)
        gp.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "CONDITION", '"Poor"', "VB", "")
        assumptions = assumptions + 1

    gp.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "CLEAR_SELECTION", "")
    del query, count

    #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Check #6: "Meadow or Continuous Grass Not Grazed Generally Hayed" should have a condition of "Good"
    query = "\"LANDUSE\" = 'Meadow or Continuous Grass Not Grazed Generally Hayed' AND  \"CONDITION\" <> 'Good'"
    gp.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "NEW_SELECTION", query)
    count = int(gp.GetCount_management(wtshdLanduseSoilsIntersect_Layer).getOutput(0))
    
    if count > 0:
        AddMsgAndPrint("\n\n\tThere were " + str(count) + " 'Meadow or Continuous Grass Not Grazed Generally Hayed' polygons with a condition other than Good.",1)
        AddMsgAndPrint("\tA condition of Good will be assigned to these polygons.\n",1)
        gp.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "CONDITION", '"Good"', "VB", "")
        assumptions = assumptions + 1

    gp.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "CLEAR_SELECTION", "")
    del query, count

    #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Check #7: "Woods Grazed Not Burned Some forest Litter" should have a condition of "Fair"
    query = "\"LANDUSE\" = 'Woods Grazed Not Burned Some forest Litter' AND \"CONDITION\" <> 'Fair'"
    gp.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "NEW_SELECTION", query)
    count = int(gp.GetCount_management(wtshdLanduseSoilsIntersect_Layer).getOutput(0))
    
    if count > 0:
        AddMsgAndPrint("\n\n\tThere were " + str(count) + " 'Woods Grazed Not Burned Some forest Litter' polygons with a condition other than fair.",1)
        AddMsgAndPrint("\tA condition of fair will be assigned to these polygons.\n",1)
        gp.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "CONDITION", '"Fair"', "VB", "")
        assumptions = assumptions + 1

    gp.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "CLEAR_SELECTION", "")
    del query, count

    #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Check #8: "Woods Not Grazed Adequate litter and brush" should have a condition of "Good"
    query = "\"LANDUSE\" = 'Woods Not Grazed Adequate litter and brush' AND  \"CONDITION\" <> 'Good'"
    gp.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "NEW_SELECTION", query)
    count = int(gp.GetCount_management(wtshdLanduseSoilsIntersect_Layer).getOutput(0))
    
    if count > 0:
        AddMsgAndPrint("\n\n\tThere were " + str(count) + " 'Woods Not Grazed Adequate litter and brush' polygons with a condition other than Good.",1)
        AddMsgAndPrint("\tA condition of Good will be assigned to these polygons.\n",1)
        gp.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "CONDITION", '"Good"', "VB", "")
        assumptions = assumptions + 1

    gp.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "CLEAR_SELECTION", "")
    del query, count        

    #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Check #9: "Woods Heavily Grazed or Burned" should have a condition of "Poor"
    query = "\"LANDUSE\" = 'Woods Heavily Grazed or Burned' AND  \"CONDITION\" <> 'Poor'"
    gp.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "NEW_SELECTION", query)
    count = int(gp.GetCount_management(wtshdLanduseSoilsIntersect_Layer).getOutput(0))
    
    if count > 0:
        AddMsgAndPrint("\n\tThere were " + str(count) + " 'Woods Heavily Grazed or Burned' polygons with a condition other than Poor.",1)
        AddMsgAndPrint("\tA condition of Poor will be assigned to these polygons.\n",1)
        gp.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "CONDITION", '"Poor"', "VB", "")
        assumptions = assumptions + 1

    gp.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "CLEAR_SELECTION", "")
    del query, count          

    #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Check #10: Fallow crops, Row crops, Small Grains or closed seed should have a condition of 'Good' or 'Poor' - default to Good
    query = "\"LANDUSE\" LIKE 'Fallow Crop%' AND \"CONDITION\" = 'Fair' OR \"LANDUSE\" LIKE 'Row Crops%' AND \"CONDITION\" = 'Fair' OR \"LANDUSE\" LIKE 'Small Grain%' AND \"CONDITION\" = 'Fair' OR \"LANDUSE\" LIKE 'Close Seeded%' AND \"CONDITION\" = 'Fair'"
    gp.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "NEW_SELECTION", query)
    count = int(gp.GetCount_management(wtshdLanduseSoilsIntersect_Layer).getOutput(0))
    
    if count > 0:
        AddMsgAndPrint("\n\tThere were " + str(count) + " Cropland related polygons with a 'Fair' condition listed. This Landuse assumes a condition of 'Good' or 'Poor'..\n",1)
        AddMsgAndPrint("\tA condition of Good will be assumed and assigned to these polygons.\n",1)
        gp.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "CONDITION", '"Good"', "VB", "")
        assumptions = assumptions + 1
    
    gp.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "CLEAR_SELECTION", "")

    del query, count
    
    if assumptions == 0:
        AddMsgAndPrint("\n\tAll populated correctly!",0)

    # ------------------------------------------------------------------------------------------------ Join LU Descriptions and assign codes for RCN Lookup
    # Select Landuse categories that arent assigned a condition (these dont need to be concatenated)
    query = "\"CONDITION\" = ''"
    gp.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "NEW_SELECTION", query)
    count = int(gp.GetCount_management(wtshdLanduseSoilsIntersect_Layer).getOutput(0))
    
    if count > 0:
        gp.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "LUDESC", "!LANDUSE!", "PYTHON", "")

    # Concatenate Landuse and Condition fields together
    gp.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "SWITCH_SELECTION", "")
    gp.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "LUDESC", "!LANDUSE!" + "' '" +  "!CONDITION!", "PYTHON", "")  
    gp.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "CLEAR_SELECTION", "")

    del query, count
    
    # Join Layer and TR_55_RCN_Lookup table to get LUCODE
    gp.AddJoin_management(wtshdLanduseSoilsIntersect_Layer, "LUDESC", TR_55_RCN_Lookup, "LandUseDes", "KEEP_ALL")
    gp.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "wtshdLanduseSoilsIntersect.LU_CODE", "[TR_55_RCN_Lookup.LU_CODE]", "VB", "")
    gp.RemoveJoin_management(wtshdLanduseSoilsIntersect_Layer, "TR_55_RCN_Lookup")
    AddMsgAndPrint("\nSuccesfully Joined to TR_55_RCN Lookup table to assign Land Use Codes",1)

    # Join Layer and HYD_GRP_Lookup table to get HYDCODE
    gp.AddJoin_management(wtshdLanduseSoilsIntersect_Layer, "HYDGROUP", HYD_GRP_Lookup_Table, "HYDGRP", "KEEP_ALL")
    gp.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "wtshdLanduseSoilsIntersect.HYDROL_ID", "[HYD_GRP_Lookup.HYDCODE]", "VB", "")
    gp.RemoveJoin_management(wtshdLanduseSoilsIntersect_Layer, "HYD_GRP_Lookup")
    AddMsgAndPrint("\nSuccesfully Joined to HYD_GRP_Lookup table to assign Hydro Codes",1)

    # ------------------------------------------------------------------------------------------------ Join and Populate RCN Values        
    # Concatenate LU Code and Hydrol ID to create HYD_CODE for RCN Lookup
    gp.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "HYD_CODE", "[LU_CODE] & [HYDROL_ID]", "VB", "")

    # Join Layer and TR_55_RCN_Lookup to get RCN value
    gp.AddJoin_management(wtshdLanduseSoilsIntersect_Layer, "HYD_CODE", TR_55_RCN_Lookup, "HYD_CODE", "KEEP_ALL")
    gp.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "wtshdLanduseSoilsIntersect.RCN", "[TR_55_RCN_Lookup.RCN]", "VB", "")
    gp.RemoveJoin_management(wtshdLanduseSoilsIntersect_Layer, "TR_55_RCN_Lookup")
    AddMsgAndPrint("\nSuccesfully Joined to TR_55_RCN Lookup table to assign Curve Numbers for Unique Combinations",1)
    
    # ------------------------------------------------------------------------------------------------ Calculate Weighted RCN For Each Subbasin
    # Update acres for each new polygon
    gp.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "RCN_ACRES", "!shape.area@ACRES!", "PYTHON", "")

    # Get weighted acres
    gp.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "WGTRCN", "([RCN_ACRES] / [ACRES]) * [RCN]", "VB", "")

    gp.Statistics_analysis(wtshdLanduseSoilsIntersect_Layer, rcn_stats, "WGTRCN SUM", "Subbasin")
    AddMsgAndPrint("\nSuccessfully Calculated Weighted Runoff Curve Number for each SubBasin",1)

    # ------------------------------------------------------------------------------------------------ Put the results in Watershed Attribute Table
    #AddMsgAndPrint("\nUpdating RCN values on " + os.path.basename(inWatershed) + " layer",1)
    
    # go through each weighted record and pull out the Mean value
    rows = gp.searchcursor(rcn_stats)
    row = rows.next()

    while row:
        subbasinNum = row.Subbasin
        RCNvalue = row.SUM_WGTRCN

        wtshdRows = gp.UpdateCursor(inWatershed)
        wtshdRow = wtshdRows.next()

        while wtshdRow:
            watershedSubbasin = wtshdRow.Subbasin

            if watershedSubbasin == subbasinNum:
                wtshdRow.RCN = RCNvalue
                wtshdRows.UpdateRow(wtshdRow)

                AddMsgAndPrint("\n\tSubbasin ID: " + str(watershedSubbasin),0)
                AddMsgAndPrint("\t\tWeighted Average RCN Value: " + str(round(RCNvalue,0)),0)

                del watershedSubbasin
                break

            else:
                wtshdRow = wtshdRows.next()

        del subbasinNum, RCNvalue, wtshdRows, wtshdRow
        
        row = rows.next()

    del rows, row        

    # ------------------------------------------------------------------------------------------------ Create fresh new RCN Layer
    AddMsgAndPrint("\nAdding unique identifier to each subbasin's soil and landuse combinations",1)
    
    gp.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "IDENT", "[HYD_CODE] & [Subbasin]", "VB", "")
    
    gp.Dissolve_management(wtshdLanduseSoilsIntersect_Layer, wtshdLanduseSoils_dissolve, "Subbasin;HYD_CODE", "", "MULTI_PART", "DISSOLVE_LINES")
    
    gp.AddField_management(wtshdLanduseSoils_dissolve, "IDENT", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "") #done
    gp.AddField_management(wtshdLanduseSoils_dissolve, "SUB_BASIN", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "") #done
    gp.AddField_management(wtshdLanduseSoils_dissolve, "LANDUSE", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.AddField_management(wtshdLanduseSoils_dissolve, "CONDITION", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.AddField_management(wtshdLanduseSoils_dissolve, "HYDROLGROUP", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.AddField_management(wtshdLanduseSoils_dissolve, "RCN", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.AddField_management(wtshdLanduseSoils_dissolve, "ACRES", "DOUBLE", "5", "1", "", "", "NULLABLE", "NON_REQUIRED", "") #done

    gp.CalculateField_management(wtshdLanduseSoils_dissolve, "IDENT", "[HYD_CODE] & [Subbasin]", "VB", "")
    gp.CalculateField_management(wtshdLanduseSoils_dissolve, "ACRES", "!shape.area@ACRES!", "PYTHON", "")
    gp.CalculateField_management(wtshdLanduseSoils_dissolve, "SUB_BASIN", "[Subbasin]", "VB", "")

    # Just for the purpose of joining and transfering attributes    
    gp.MakeFeatureLayer_management(wtshdLanduseSoils_dissolve, rcnLayer, "", "", "")
    
    gp.AddJoin_management(rcnLayer, "IDENT", wtshdLanduseSoilsIntersect_Layer, "IDENT", "KEEP_ALL")

    gp.CalculateField_management(rcnLayer, "wtshdLanduseSoils_dissolve.LANDUSE", "[wtshdLanduseSoilsIntersect.LANDUSE]", "VB", "")
    gp.CalculateField_management(rcnLayer, "wtshdLanduseSoils_dissolve.CONDITION", "[wtshdLanduseSoilsIntersect.CONDITION]", "VB", "")
    gp.CalculateField_management(rcnLayer, "wtshdLanduseSoils_dissolve.HYDROLGROUP", "[wtshdLanduseSoilsIntersect.HYDGROUP]", "VB", "")
    gp.CalculateField_management(rcnLayer, "wtshdLanduseSoils_dissolve.RCN", "[wtshdLanduseSoilsIntersect.RCN]", "VB", "")

    gp.RemoveJoin_management(rcnLayer, "wtshdLanduseSoilsIntersect")
    gp.DeleteField_management(rcnLayer, "Subbasin;IDENT;HYD_CODE")

    # Create final RCN feature class
    gp.CopyFeatures(rcnLayer,rcn)

    gp.Delete_management(rcn_stats)
    gp.Delete_management(wtshdLanduseSoilsIntersect)
    gp.Delete_management(wtshdLanduseSoilsIntersect_Layer)
    gp.Delete_management(wtshdLanduseSoils_dissolve)
    gp.Delete_management(rcnLayer)

    AddMsgAndPrint("\nSuccessfully created RCN Layer: " + str(os.path.basename(rcn)),1)

    # ---------------------------------------------------------------------------------------------------------------------------- Compact FGDB
    try:
        gp.compact_management(watershedGDB_path)
        AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path),1)    
    except:
        pass

    # --------------------------------------------------------------------------------------------------------------------------- Prepare to Add to Arcmap

    gp.SetParameterAsText(1, rcn)    

    AddMsgAndPrint("\nAdding Layers to ArcMap",1)
    AddMsgAndPrint("\n",1)

    # ----------------------------------------------------------------------------------------------------- Cleanup
    gp.RefreshCatalog(watershedGDB_path)

    try:    
        del inWatershed
        del watershedGDB_path
        del watershedFD_path
        del watershedGDB_name
        del userWorkspace
        del wsName
        del inLanduse
        del inSoils
        del rcn
        del textFilePath
        del luLayer
        del soilsLyr
        del watershedLanduseInt
        del wtshdLanduseSoilsIntersect
        del wtshdLanduseSoilsIntersect_Layer
        del wtshdLanduseSoils_dissolve
        del rcn_stats
        del rcnLayer
        del HYD_GRP_Lookup_Table
        del TR_55_RCN_Lookup
        del ArcGIS10
    except:
        pass
    
except SystemExit:
    pass

except KeyboardInterrupt:
    AddMsgAndPrint("Interruption requested....exiting")

except:
    print_exception()

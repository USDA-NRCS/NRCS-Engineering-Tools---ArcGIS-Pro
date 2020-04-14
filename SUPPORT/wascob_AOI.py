# ===============================================================================================================
# ===============================================================================================================
#
#                 WASCOB_AOI.py for LiDAR Based Design of Water and Sediment Control Basins
#
#                 Author:   Originally Scripted by Peter Mead, MN USDA-NRCS with assistance 
#                           from Adolfo Diaz, WI NRCS. 
#
#                           Graciously updated and maintained by Peter Mead, under GeoGurus Group.
#
#                 Contact: peter.mead@geogurus.com
#
#                 Notes:
#                           Rescripted in arcpy 12/2013.
#
#                           3/2014 - removed of "Relative Survey" as default.
#                           Added option of creating "Relative Survey" or Using MSL elevations.
#
# ===============================================================================================================
# ===============================================================================================================
#
# Checks a user supplied workspace's file structure and creates 
# directories as necessary for 638 Tool Workflow.
#
# Determines input DEM's Native Resolution, Spatial Reference, and Elevation format to 
# apply proper conversion factors and projection where necessary throughout the workflow.
#  
# Clips a user supplied DEM to a User defined area of interest, Saving a clipped 
# "AOI DEM", Polygon Mask, and Hillshade of the Area of interest.
#
# Converts (if necessary) Clipped Input to Feet, and creates "Project DEM" --  with 
# elevations rounded to nearest 1/10th ft for the area of interest. Option to use MSL elevations
# or create " Relative Survey". Relative survey is useful when projects will be staked in
# field using a laser vs. msl when using a vrs system.
#
# The Project DEM is "smoothed" using focal mean within a 3 cell x 3 cell window, 
# and indexed contour lines are generated at the user defined interval.
#
# A "Depth Grid" is also created to show area of the DEM where water would theoretically 
# pool due to either legitimate sinks or "digital dams" existing in the raster data.
#
# All Derived Layers are added to the Current MXD's table of contents upon successful execution
#
# ===============================================================================================================
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

    print msg
    
    try:

        f = open(textFilePath,'a+')
        f.write(msg + " \n")
        f.close

        del f        
        
        for string in msg.split('\n'):
            
            # Add a geoprocessing message (in case this is run as a tool)
            if severity == 0:
                arcpy.AddMessage(string)
                
            elif severity == 1:
                arcpy.AddWarning(string)
                
            elif severity == 2:
                arcpy.AddMessage("    ")
                arcpy.AddError(string)
                
    except:
        pass

## ================================================================================================================
def logBasicSettings():    
    # record basic user inputs and settings to log file for future purposes

    import getpass, time

    f = open(textFilePath,'a+')
    f.write("\n################################################################################################################\n")
    f.write("Executing \"1.WASCOB: Define Area of Interest\" tool\n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write("User Parameters:\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tInput Dem: " + arcpy.Describe(inputDEM).CatalogPath + "\n")
    f.write("\tContour Interval: " + str(interval) + "\n")

    if len(zUnits) > 0:
        f.write("\tElevation Z-units: " + zUnits + "\n")

    else:
        f.write("\tElevation Z-units: BLANK" + "\n")
    
    f.close
    del f

## ================================================================================================================
def splitThousands(someNumber):
# will determine where to put a thousands seperator if one is needed.
# Input is an integer.  Integer with or without thousands seperator is returned.

    try:
        return re.sub(r'(\d{3})(?=\d)', r'\1,', str(someNumber)[::-1])[::-1]        

## --------------Use this code in case you want to preserve numbers after the decimal.  I decided to just round up
        # Number is a floating number        
        if str(someNumber).find("."):
            
            dropDecimals = int(someNumber)
            numberStr = str(someNumber)

            afterDecimal = str(numberStr[numberStr.find("."):numberStr.find(".")+2])
            beforeDecimalCommas = re.sub(r'(\d{3})(?=\d)', r'\1,', str(dropDecimals)[::-1])[::-1]

            return beforeDecimalCommas + afterDecimal

        # Number is a whole number    
        else:
            return int(re.sub(r'(\d{3})(?=\d)', r'\1,', str(someNumber)[::-1])[::-1])
    
    except:
        print_exception()
        return someNumber

## ================================================================================================================
# Import system modules
import sys, os, arcpy, string, traceback, re
arcpy.env.overwriteOutput = True

# ----------------------------------------------- Determine ArcGIS Install Version
d = arcpy.GetInstallInfo('desktop')

keys = d.keys()

for k in keys:

    if k == "Version":

        version = " \nArcGIS %s : %s" % (k, d[k])

        if version.find("10.0") > 0 or version.find("10.1") > 0:
            ArcGIS101 = True

        else:
            ArcGIS101 = False

        break 

del d, keys
## ---------------------------------------------------------------------------------

try:
    #--------------------------------------------------------------------- Check out SA license or exit if not available
    if arcpy.CheckExtension("spatial") == "Available":
        arcpy.CheckOutExtension("spatial")
    else:
        AddMsgAndPrint(" \nSpatial Analyst Extension not enabled. Please enable Spatial analyst from the Tools/Extensions menu\n",2)
        sys.exit("")
        
    # --------------------------------------------------------------------------------------------- Input Parameters
    # Comment following six lines to run from pythonWin
    userWorkspace = arcpy.GetParameterAsText(0)     # User Defined Workspace Folder
    inputDEM = arcpy.GetParameterAsText(1)          # Input DEM Raster
    zUnits = arcpy.GetParameterAsText(2)            # Elevation z units of input DEM
    AOI = arcpy.GetParameterAsText(3)               # AOI that was drawn
    interval = arcpy.GetParameterAsText(4)          # user defined contour interval           
    relSurvey = arcpy.GetParameterAsText(5)         # Optional - Create Relative Survey
        
##    # Uncomment following 6 lines to run from pythonWin
##    userWorkspace = "C:\Geogurus\Tools\NRCS_PROJECTS\GIS10_Support\Wascob_Update"    # User Defined Workspace Folder
##    inputDEM = r"C:\Geogurus\Geodata\elevation.gdb\dem01"     # Input DEM Raster
##    AOI = r"C:\Geogurus\Tools\NRCS_PROJECTS\GIS10_Support\Wascob_Update\Wascob_Update_Wascob.gdb\Layers\Wascob_Update_AOI"              # AOI that was drawn
##    interval = "1"         # user defined contour interval
##    zUnits = ""          # elevation z units of input DEM
##    relSurvey = "True"

    # If user selected relative survey, set boolean to create relative dem surface.
    if string.upper(relSurvey) <> "TRUE":
        relativeSurvey = False
    else:
        relativeSurvey = True
        
    # --------------------------------------------------------------------------------------------- Define Variables
    projectName = arcpy.ValidateTableName(os.path.basename(userWorkspace).replace(" ","_"))
    textFilePath = userWorkspace + os.sep + projectName + "_EngTools.txt"

    watershedGDB_name = os.path.basename(userWorkspace).replace(" ","_") + "_Wascob.gdb"  # replace spaces for new FGDB name
    watershedGDB_path = userWorkspace + os.sep + watershedGDB_name
    watershedFD = watershedGDB_path + os.sep + "Layers"

    # WASCOB Project Folders:
    Documents = userWorkspace + os.sep + "Documents"
    gis_output = userWorkspace + os.sep + "gis_output"    

    # ---------------------------------------------------------- Datasets
    # ------------------------------ Permanent Datasets
    projectAOI = watershedFD + os.sep + projectName + "_AOI"
    Contours = watershedFD + os.sep + projectName + "_Contours_" + str(interval.replace(".","_")) + "_ft"
    DEM_aoi = watershedGDB_path + os.sep + projectName + "_Raw_DEM"
    Hillshade = watershedGDB_path + os.sep + projectName + "_Hillshade"
    depthGrid = watershedGDB_path + os.sep + projectName + "_DepthGrid"

    projectDEM = watershedGDB_path + os.sep + projectName + "_Project_DEM"
    DEMsmooth = watershedGDB_path + os.sep + projectName + "_DEMsmooth"
    
    # ----------------------------- Temporary Datasets
    ContoursTemp = watershedFD + os.sep + "ContoursTemp"
    Fill_DEMaoi = watershedGDB_path + os.sep + "Fill_DEMaoi"
    FilMinus = watershedGDB_path + os.sep + "FilMinus"
    DEMft = watershedGDB_path + os.sep + "DEMft"
    MinDEM = watershedGDB_path + os.sep + "min"
    MinusDEM = watershedGDB_path + os.sep + "minus"
    TimesDEM = watershedGDB_path + os.sep + "times"
    intDEM = watershedGDB_path + os.sep + "DEMint"
    
    # record basic user inputs and settings to log file for future purposes
    logBasicSettings()

    # ---------------------------------------------------------------------------------------------- Count the number of features in AOI
    # Exit if AOI contains more than 1 digitized area.
    if int(arcpy.GetCount_management(AOI).getOutput(0)) > 1:
        AddMsgAndPrint(" \n\nYou can only digitize 1 Area of interest! Please Try Again.",2)
        sys.exit()

    # Exit if interval not set propertly
    try:
        float(interval)
    except:
        AddMsgAndPrint(" \nCountour Interval was invalid; Cannot Create Contours.......EXITING",2)
        sys.exit()
        
    # ---------------------------------------------------------------------------------------------- Check DEM Coordinate System and Linear Units

    desc = arcpy.Describe(inputDEM)
    sr = desc.SpatialReference
    cellSize = desc.MeanCellWidth

    units = sr.LinearUnitName

    if units == "Meter":
        units = "Meters"
    elif units == "Foot":
        units = "Feet"
    elif units == "Foot_US":
        units = "Feet"
    else:
        AddMsgAndPrint(" \nCould not determine linear units of DEM....Exiting!",2)
        sys.exit()

    # if zUnits were left blank than assume Z-values are the same as XY units.
    if not len(zUnits) > 0:
        zUnits = units

    AddMsgAndPrint(" \nGathering information about DEM: " + os.path.basename(inputDEM),1)    

    # Coordinate System must be a Projected type in order to continue.
    # zUnits will determine Zfactor for the creation of foot contours.
    # if XY units differ from Z units then a Zfactor must be calculated to adjust
    # the z units by multiplying by the Zfactor

    if sr.Type == "Projected":
        if zUnits == "Meters":
            Zfactor = 3.280839896       # 3.28 feet in a meter

        elif zUnits == "Centimeters":   # 0.033 feet in a centimeter
            Zfactor = 0.0328084

        elif zUnits == "Inches":        # 0.083 feet in an inch
            Zfactor = 0.0833333

        # z units and XY units are the same thus no conversion is required
        else:
            Zfactor = 1

        AddMsgAndPrint(" \tProjection Name: " + sr.Name,0)
        AddMsgAndPrint(" \tXY Linear Units: " + units,0)
        AddMsgAndPrint(" \tElevation Values (Z): " + zUnits,0) 
        AddMsgAndPrint(" \tCell Size: " + str(desc.MeanCellWidth) + " x " + str(desc.MeanCellHeight) + " " + units,0)

    else:
        AddMsgAndPrint(" \n\n\t" + os.path.basename(inputDEM) + " is NOT in a projected Coordinate System....EXITING",2)
        sys.exit()

    # ----------------------------- Capture User environments
    tempExtent = arcpy.env.extent
    tempMask = arcpy.env.mask
    tempSnapRaster = arcpy.env.snapRaster
    tempCellSize = arcpy.env.cellSize
    tempCoordSys = arcpy.env.outputCoordinateSystem
    
    # ----------------------------- Set the following environments
    arcpy.env.extent = "MINOF"
    arcpy.env.cellSize = cellSize
    arcpy.env.mask = ""
    arcpy.env.snapRaster = ""
    arcpy.env.outputCoordinateSystem = sr
    
    # ---------------------------------------------------------------------------------------------- Delete old datasets
    if arcpy.Exists(watershedGDB_path):

        datasetsToRemove = (DEM_aoi,Hillshade,depthGrid,DEMsmooth,ContoursTemp,Fill_DEMaoi,FilMinus,projectDEM,DEMft,intDEM)

        x = 0
        for dataset in datasetsToRemove:

            if arcpy.Exists(dataset):

                if x < 1:
                    AddMsgAndPrint(" \nRemoving old datasets from FGDB: " + watershedGDB_name ,1)
                    x += 1
                    
                try:
                    arcpy.Delete_management(dataset)
                    AddMsgAndPrint(" \tDeleting....." + os.path.basename(dataset),0)
                except:
                    pass
                
        del dataset
        del datasetsToRemove
        del x

        # If FGDB Exists but FD not present, create it.
        if not arcpy.Exists(watershedFD):
            arcpy.CreateFeatureDataset_management(watershedGDB_path, "Layers", sr)

    # Otherwise FGDB does not exist, create it.
    else:
        arcpy.CreateFileGDB_management(userWorkspace, watershedGDB_name)
        arcpy.CreateFeatureDataset_management(watershedGDB_path, "Layers", sr)
        AddMsgAndPrint(" \nSuccessfully created File Geodatabase: " + watershedGDB_name,1)
    
    # If Documents folder not present, create and copy required files to it
    if not arcpy.Exists(Documents):
        arcpy.CreateFolder_management(userWorkspace, "Documents")
        DocumentsFolder =  os.path.join(os.path.dirname(sys.argv[0]), "Documents")
        if arcpy.Exists(DocumentsFolder):
            arcpy.Copy_management(DocumentsFolder, Documents, "Folder")
        del DocumentsFolder
        
    # Create gis_output folder if not present 
    if not arcpy.Exists(gis_output):
        arcpy.CreateFolder_management(userWorkspace, "gis_output")

    # ----------------------------------------------------------------------------------------------- Create New AOI
    # if AOI path and  projectAOI path are not the same then assume AOI was manually digitized
    # or input is some from some other feature class/shapefile
    if not arcpy.Describe(AOI).CatalogPath == projectAOI:       

        # delete the existing projectAOI feature class and recreate it.
        if arcpy.Exists(projectAOI):
            
            try:
                arcpy.Delete_management(projectAOI)
                arcpy.CopyFeatures_management(AOI, projectAOI)
                AddMsgAndPrint(" \nSuccessfully Recreated \"" + str(projectName) + "_AOI\" feature class",1)
                
            except:
                print_exception()
                arcpy.OverWriteOutput = 1
            
        else:
            arcpy.CopyFeatures_management(AOI, projectAOI)
            AddMsgAndPrint(" \nSuccessfully Created \"" + str(projectName) + "_AOI\" feature class",1)

    # paths are the same therefore AOI is projectAOI
    else:
        AddMsgAndPrint(" \nUsing Existing \"" + str(projectName) + "_AOI\" feature class:",1)
      
    # -------------------------------------------------------------------------------------------- Exit if AOI was not a polygon 
    if arcpy.Describe(projectAOI).ShapeType != "Polygon":
        AddMsgAndPrint(" \n\nYour Area of Interest must be a polygon layer!.....Exiting!",2)
        sys.exit()
    # --------------------------------------------------------------------------------------------  Populate AOI with DEM Properties
    # Write input DEM name to AOI 
    if len(arcpy.ListFields(projectAOI,"INPUT_DEM")) < 1:
        arcpy.AddField_management(projectAOI, "INPUT_DEM", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        
    arcpy.CalculateField_management(projectAOI, "INPUT_DEM", "\"" + os.path.basename(inputDEM) +  "\"", "VB", "")
    
    # Write XY Units to AOI
    if len(arcpy.ListFields(projectAOI,"XY_UNITS")) < 1:
        arcpy.AddField_management(projectAOI, "XY_UNITS", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        
    arcpy.CalculateField_management(projectAOI, "XY_UNITS", "\"" + str(units) + "\"", "VB", "")
    
    # Write Z Units to AOI
    if len(arcpy.ListFields(projectAOI,"Z_UNITS")) < 1:
        arcpy.AddField_management(projectAOI, "Z_UNITS", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        
    arcpy.CalculateField_management(projectAOI, "Z_UNITS", "\"" + str(zUnits) + "\"", "VB", "")

    # Delete unwanted "Id" remanant field
    if len(arcpy.ListFields(projectAOI,"Id")) > 0:
        
        try:
            arcpy.DeleteField_management(projectAOI,"Id")
        except:
            pass

# Get the Shape Area to notify user of Area and Acres of AOI
    rows = arcpy.SearchCursor(projectAOI,"","","SHAPE_Area")   

    area = ""

    for row in rows:
        area = row.SHAPE_Area
        break

    del row
    del rows

    if area != 0:

        AddMsgAndPrint(" \tProject_AOI Area:  " + str(splitThousands(round(area,2))) + " Sq. " + units,0)

        if units == "Meters":
            acres = area/4046.86
            AddMsgAndPrint(" \tProject_AOI Acres: " + str(splitThousands(round(acres,2))) + " Acres",0)
            del acres

        elif units == "Feet":
            acres = area/43560
            AddMsgAndPrint(" \tProject_AOI Acres: " + str(splitThousands(round(acres,2))) + " Acres",0)
            del acres

        else:
            AddMsgAndPrint(" \tCould not calculate Acres",2)

    del area

    # ------------------------------------------------------------------------------------------------- Clip inputDEM
    AddMsgAndPrint(" \nClipping "+ os.path.basename(inputDEM) +" to " + os.path.basename(projectAOI) + "...",1)
    arcpy.gp.ExtractByMask_sa(inputDEM, AOI, DEM_aoi)
    AddMsgAndPrint(" \tSuccessully saved clipped dem as: " + os.path.basename(DEM_aoi),0)
     
    # --------------------------------------------------------------- Round Elevation Values to nearest 10th
    if not relativeSurvey:
        AddMsgAndPrint(" \nCreating Project DEM using Mean Sea Level Elevations...",1)
    else:
        AddMsgAndPrint(" \nCreating Project DEM using Relative Elevations (0 - Max Rise)...",1)
    
    # Convert to feet if necessary
    if not zUnits == "Feet":
        AddMsgAndPrint(" \tConverting elevations to feet",0)
        arcpy.gp.Times_sa(DEM_aoi, Zfactor, DEMft)
        AddMsgAndPrint(" \tSuccessfully converted elevations to feet",0)
        DEM_aoi = DEMft
        
    if relativeSurvey:
        AddMsgAndPrint(" \tDetermining realtive elevations...",0)
        # Get Minimum Elevation in AOI...
        AddMsgAndPrint(" \tRetrieving minimum elevation...",0)
        arcpy.gp.ZonalStatistics_sa(AOI, "OBJECTID", DEM_aoi, MinDEM, "MINIMUM", "DATA")
        # Subtract Minimum Elevation from all cells in AOI...
        AddMsgAndPrint(" \tDetermining maximum rise...",0)
        arcpy.gp.Minus_sa(DEM_aoi, MinDEM, MinusDEM)
        DEM_aoi = MinusDEM

    AddMsgAndPrint(" \tRounding to nearest 1/10th Ft..",0)

    # Multiply DEM by 10 for rounding...
    arcpy.gp.Times_sa(DEM_aoi, "10", TimesDEM)
    
    # Create integer raster and add 0.5..
    Expression1 = "Int(\""+str(TimesDEM)+"\" + 0.5)"
    arcpy.gp.RasterCalculator_sa(Expression1, intDEM)
    
    # Float to round back to nearest 1/10th foot.. 
    # ..this becomes "Project DEM", a raster surface in 1/10th Ft values
    Expression2 = "Float(\""+str(intDEM)+"\" * 0.1)"
    arcpy.gp.RasterCalculator_sa(Expression2, projectDEM)

    AddMsgAndPrint(" \tSuccessfully created Project DEM",0)

    # Delete intermediate rasters
    datasetsToRemove = (intDEM,DEMft,TimesDEM,MinDEM,MinusDEM)

    x = 0
    for dataset in datasetsToRemove:

        if arcpy.Exists(dataset):

            if x < 1:
                x += 1
                
            try:
                arcpy.Delete_management(dataset)
            except:
                pass
            
    del dataset
    del datasetsToRemove
    del x

    # ------------------------------------------------------------------------------------------------ Create Contours 
    AddMsgAndPrint(" \nCreating " + str(interval) + " foot Contour Lines...",1)
 
    # Run Focal Statistics on the Project DEM to generate smooth contours
    arcpy.gp.Focalstatistics_sa(projectDEM, DEMsmooth,"RECTANGLE 3 3 CELL","MEAN","DATA")

    # Create Contours from DEMsmooth if user-defined interval is greater than 0
    if interval > 0:
        arcpy.gp.Contour_sa(DEMsmooth, ContoursTemp, interval, "0", "1")
        
        AddMsgAndPrint(" \tSuccessfully Created Contours from " + os.path.basename(projectDEM),0)
        
        arcpy.AddField_management(ContoursTemp, "Index", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

        if arcpy.Exists("ContourLYR"):
            try:
                arcpy.Delete_management("ContourLYR")
            except:
                pass
            
        arcpy.MakeFeatureLayer_management(ContoursTemp,"ContourLYR","","","")

        # Every 5th contour will be indexed to 1
        AddMsgAndPrint(" \tIndexing every 5th Contour line...",0)
        expression = "MOD( \"CONTOUR\"," + str(float(interval) * 5) + ") = 0"
        
        arcpy.SelectLayerByAttribute_management("ContourLYR", "NEW_SELECTION", expression)
        indexValue = 1
        arcpy.CalculateField_management("ContourLYR", "Index", indexValue, "VB","")
        del indexValue

        # All othe contours will be indexed to 0
        arcpy.SelectLayerByAttribute_management("ContourLYR", "SWITCH_SELECTION", "")
        indexValue = 0
        arcpy.CalculateField_management("ContourLYR", "Index", indexValue, "VB","")
        del indexValue

        AddMsgAndPrint(" \tSuccessfully indexed Contour lines",0)
        
        # Clear selection and write all contours to a new feature class        
        arcpy.SelectLayerByAttribute_management("ContourLYR","CLEAR_SELECTION","")      
        arcpy.CopyFeatures_management("ContourLYR", Contours)

        # Delete unwanted datasets
        arcpy.Delete_management(ContoursTemp)
        arcpy.Delete_management("ContourLYR")
       
        del expression
        arcpy.Delete_management(DEMsmooth)
        
    else:
        AddMsgAndPrint(" \nContours will not be created since interval was set to 0",2)

    # ---------------------------------------------------------------------------------------------- Create Hillshade and Depth Grid
    # Process: Creating Hillshade from DEM_aoi
    AddMsgAndPrint(" \nCreating Hillshade for AOI...",1)
    DEM_aoi = watershedGDB_path + os.sep + projectName + "_Raw_DEM"
    arcpy.gp.HillShade_sa(DEM_aoi, Hillshade, "315", "45", "#", "1")
    AddMsgAndPrint(" \tSuccessfully Created Hillshade",0)
    
    AddMsgAndPrint(" \nFilling sinks to create depth grid...",1)
    try:
        # Fills sinks in DEM_aoi to create depth grid.
        arcpy.gp.Fill_sa(DEM_aoi, Fill_DEMaoi, "")
        AddMsgAndPrint(" \tSuccessfully filled sinks",0)
        fill = True

    except:
        fill = False
        arcpy.AddError(" \n\nFailed filling in the sinks on " + os.path.basename(DEM_aoi) + "\n")
        AddMsgAndPrint(" \tDepth Grid will not be created\n",2)
        AddMsgAndPrint(arcpy.GetMessages(2),2)

    if fill:
        AddMsgAndPrint(" \nCreating depth grid...",1)
        # DEM_aoi - Fill_DEMaoi = FilMinus
        arcpy.gp.Minus_sa(Fill_DEMaoi, DEM_aoi, FilMinus)

        # Create a Depth Grid; Any pixel where there is a difference write it out
        arcpy.gp.Con_sa(FilMinus, FilMinus, depthGrid, "", "VALUE > 0")

        # Delete unwanted rasters
        arcpy.Delete_management(Fill_DEMaoi)
        arcpy.Delete_management(FilMinus)
        
        AddMsgAndPrint(" \tSuccessfully Created a Depth Grid",0)
          
    # ------------------------------------------------------------------------------------------------ Prepare to Add to Arcmap
    AddMsgAndPrint(" \nAdding Layers to ArcMap",1)
    AddMsgAndPrint(" \t..Contours",0)
    arcpy.SetParameterAsText(6, Contours)
    AddMsgAndPrint(" \t..Area of Interest",0)
    arcpy.SetParameterAsText(7, projectAOI)
    AddMsgAndPrint(" \t..Project DEM",0)
    arcpy.SetParameterAsText(8, projectDEM)
    AddMsgAndPrint(" \t..Hillshade",0)
    arcpy.SetParameterAsText(9, Hillshade)
    AddMsgAndPrint(" \t..Depth Grid",0)
    arcpy.SetParameterAsText(10, depthGrid)
    arcpy.RefreshActiveView()

    # ------------------------------------------------------------------------------------------------ Clean up Time!
    AddMsgAndPrint(" \nInitiating cleanup...",1)
    
    # ------------------------------------------------------------------------------------------------ Compact FGDB
    try:
        AddMsgAndPrint(" \tCompacting FGDB: " + os.path.basename(watershedGDB_path) + "...",0)
        arcpy.Compact_management(watershedGDB_path)
    except:
        pass
    # ------------------------------------------------------------------------------------------------ Refresh Catalog
    AddMsgAndPrint(" \tRefreshing Catalog for: " + os.path.basename(watershedGDB_path) + "...",0)
    arcpy.RefreshCatalog(watershedGDB_path)

    # ------------------------------------------------------------------------------------------------ Restore User environments
    AddMsgAndPrint(" \tRestoring default environment settings...",0)    
    arcpy.env.extent = tempExtent
    arcpy.env.cellSize = tempCellSize
    arcpy.env.mask = tempMask
    arcpy.env.snapRaster = tempSnapRaster
    arcpy.env.outputCoordinateSystem = tempCoordSys

    AddMsgAndPrint(" \nProcessing Complete!",1)
    AddMsgAndPrint(" \n",1)
    
    try:
        del userWorkspace
        del inputDEM
        del AOI
        del interval
        del zUnits
        del textFilePath
        del watershedGDB_name
        del watershedGDB_path
        del watershedFD
        del projectAOI
        del Contours
        del DEM_aoi
        del DEMsmooth
        del Hillshade
        del depthGrid
        del ContoursTemp
        del Fill_DEMaoi
        del FilMinus
        del desc
        del sr
        del units
        del cellSize
        del Zfactor
        del fill
        del tempExtent
        del tempMask
        del tempSnapRaster
        del tempCellSize
        del tempCoordSys
        del ArcGIS101
        del version
        del projectDEM
        del DEMft
        del intDEM
        del documents
        del gis_output
        
    except:
        pass
    
except SystemExit:
    pass

except KeyboardInterrupt:
    AddMsgAndPrint("Interruption requested....exiting")

except:
    print_exception()

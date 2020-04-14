## ===============================================================================================================
# Define_AOI.py For LiDAR WASCOB Design
#
#
# This script has only been tested with ArcGIS 9.3.1 and ArcGIS 10.0
# 
## ===============================================================================================================
#
# Checks a user supplied workspace's file structure and creates 
# directories as necessary for Watershed Tool Workflow.
#
# Determines input DEM's Native Resolution, Spatial Reference, and Elevation format to 
# apply proper conversion factors and projection where necessary throughout the workflow.
#  
# Clips a user supplied DEM to a User defined area of interest, Saving a clipped 
# "AOI DEM", Polygon Mask, and Hillshade of the Area of interest.
#
# Converts (if necessary) Clipped Input to Feet, and creates "Project DEM" -- a "Relative Survey" with 
# elevations rounded to nearest 1/10th ft ranging from 0 (minimum) to X.X (maximum number of feet of rise) 
# within  the area of interest
#
# The Project DEM is "smoothed" using focal mean within a 3 cell x 3 cell window, 
# and indexed contour lines are generated at the user defined interval.
#
# A "Depth Grid" is also created to show area of the DEM where water would theoretically 
# pool due to either legitimate sinks or "digital dams" existing in the raster data.
#
# All Derived Layers are added to the Current MXD's table of contents upon successful execution

## ===============================================================================================================
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
                gp.AddMessage("    ")
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
    f.write("Executing \"1.WASCOB: Define Area of Interest\" tool\n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write("User Parameters:\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tInput Dem: " + gp.Describe(inputDEM).CatalogPath + "\n")
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
##        # Number is a floating number        
##        if str(someNumber).find("."):
##            
##            dropDecimals = int(someNumber)
##            numberStr = str(someNumber)
##
##            afterDecimal = str(numberStr[numberStr.find("."):numberStr.find(".")+2])
##            beforeDecimalCommas = re.sub(r'(\d{3})(?=\d)', r'\1,', str(dropDecimals)[::-1])[::-1]
##
##            return beforeDecimalCommas + afterDecimal
##
##        # Number is a whole number    
##        else:
##            return int(re.sub(r'(\d{3})(?=\d)', r'\1,', str(someNumber)[::-1])[::-1])
    
    except:
        print_exception()
        return someNumber

## ================================================================================================================
# Import system modules
import sys, os, arcgisscripting, traceback, re

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
        gp.AddError("Spatial Analyst Extension not enabled. Please enable Spatial analyst from the Tools/Extensions menu")
        sys.exit("")

    # --------------------------------------------------------------------------------------------- Input Parameters
    userWorkspace = gp.GetParameterAsText(0)
    inputDEM = gp.GetParameterAsText(1)         #DEM
    zUnits = gp.GetParameterAsText(2)           # elevation z units of input DEM
    AOI = gp.GetParameterAsText(3)              # AOI that was drawn
    interval = gp.GetParameterAsText(4)         # user defined contour interval


    # --------------------------------------------------------------------------------------------- Define Variables
    projectName = gp.ValidateTablename(os.path.basename(userWorkspace).replace(" ","_"))
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
    Contours = watershedFD + os.sep + projectName + "_Contours_" + str(interval.replace(".","_")) + "ft"
    DEM_aoi = watershedGDB_path + os.sep + projectName + "_DEM"
    Hillshade = watershedGDB_path + os.sep + projectName + "_Hillshade"
    depthGrid = watershedGDB_path + os.sep + projectName + "_DepthGrid"

    projectDEM = watershedGDB_path + os.sep + "Project_DEM"
    DEMsmooth = watershedGDB_path + os.sep + "DEMsmooth"
    
    # ----------------------------- Temporary Datasets
    ContoursTemp = watershedFD + os.sep + "ContoursTemp"
    Fill_DEMaoi = watershedGDB_path + os.sep + "Fill_DEMaoi"
    FilMinus = watershedGDB_path + os.sep + "FilMinus"
    DEMft = watershedGDB_path + os.sep + "DEMft"
    MinDEM = watershedGDB_path + os.sep + "min"
    MinusDEM = watershedGDB_path + os.sep + "minus"
    TimesDEM = watershedGDB_path + os.sep + "times"
    intDEM = watershedGDB_path + os.sep + "DEMtemp3"

    
    # record basic user inputs and settings to log file for future purposes
    logBasicSettings()

    # ---------------------------------------------------------------------------------------------- Count the number of features in AOI
    # Exit if AOI contains more than 1 digitized area.
    if int(gp.GetCount_management(AOI).getOutput(0)) > 1:
        AddMsgAndPrint("\n\nYou can only digitize 1 Area of interest! Please Try Again.",2)
        sys.exit()

    # Exit if interval not set propertly
    try:
        float(interval)
    except:
        AddMsgAndPrint("\nCountour Interval was invalid; Cannot Create Contours.......EXITING",2)
        sys.exit()        
        
    # ---------------------------------------------------------------------------------------------- Check DEM Coordinate System and Linear Units
    desc = gp.Describe(inputDEM)
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
        AddMsgAndPrint("\nCould not determine linear units of DEM....Exiting!",2)
        sys.exit()

    # if zUnits were left blank than assume Z-values are the same as XY units.
    if not len(zUnits) > 0:
        zUnits = units

    AddMsgAndPrint("\nGathering information about DEM: " + os.path.basename(inputDEM)+ ":",1)    

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

        AddMsgAndPrint("\tProjection Name: " + sr.Name,0)
        AddMsgAndPrint("\tXY Linear Units: " + units,0)
        AddMsgAndPrint("\tElevation Values (Z): " + zUnits,0) 
        AddMsgAndPrint("\tCell Size: " + str(desc.MeanCellWidth) + " x " + str(desc.MeanCellHeight) + " " + units,0)

    else:
        AddMsgAndPrint("\n\n\t" + os.path.basename(inputDEM) + " is NOT in a projected Coordinate System....EXITING",2)
        sys.exit()
        
    # ----------------------------- Capture User environments
    tempExtent = gp.Extent
    tempMask = gp.mask
    tempSnapRaster = gp.SnapRaster
    tempCellSize = gp.CellSize
    tempCoordSys = gp.OutputCoordinateSystem

    # ----------------------------- Set the following environments
    gp.Extent = "MINOF"
    gp.CellSize = cellSize
    gp.mask = ""
    gp.SnapRaster = ""
    gp.OutputCoordinateSystem = sr
    
    # ---------------------------------------------------------------------------------------------- Delete old datasets
    if gp.exists(watershedGDB_path):

        datasetsToRemove = (DEM_aoi,Hillshade,depthGrid,DEMsmooth,ContoursTemp,Fill_DEMaoi,FilMinus,projectDEM,DEMft,MinDEM,MinusDEM,TimesDEM,intDEM)

        x = 0
        for dataset in datasetsToRemove:

            if gp.exists(dataset):

                if x < 1:
                    AddMsgAndPrint("\nRemoving old datasets from FGDB: " + watershedGDB_name ,1)
                    x += 1
                    
                try:
                    gp.delete_management(dataset)
                    AddMsgAndPrint("\tDeleting....." + os.path.basename(dataset),1)
                except:
                    pass
                
        del dataset
        del datasetsToRemove
        del x

        if not gp.exists(watershedFD):
            gp.CreateFeatureDataset_management(watershedGDB_path, "Layers", sr)

    # FGDB does not exist, create it.
    else:
        gp.CreateFileGDB_management(userWorkspace, watershedGDB_name)
        gp.CreateFeatureDataset_management(watershedGDB_path, "Layers", sr)
        AddMsgAndPrint("\nSuccessfully created File Geodatabase: " + watershedGDB_name,1)
    
    # If Documents folder not present, create and copy required files to it
    if not gp.exists(Documents):
        gp.CreateFolder_management(userWorkspace, "Documents")
        DocumentsFolder =  os.path.join(os.path.dirname(sys.argv[0]), "Documents")
        if gp.Exists(DocumentsFolder):
            gp.Copy_management(DocumentsFolder, Documents, "Folder")
        del DocumentsFolder
        
    # Create gis_output folder if not present 
    if not gp.Exists(gis_output):
        gp.CreateFolder_management(userWorkspace, "gis_output")
        
    # ----------------------------------------------------------------------------------------------- Create New AOI
    # if AOI path and  projectAOI path are not the same then assume AOI was manually digitized
    # or input is some from some other feature class/shapefile
    if not gp.Describe(AOI).CatalogPath == projectAOI:       

        # delete the existing projectAOI feature class and recreate it.
        if gp.exists(projectAOI):
            
            try:
                gp.delete_management(projectAOI)
                gp.CopyFeatures_management(AOI, projectAOI)
                AddMsgAndPrint("\nSuccessfully Recreated \"" + str(projectName) + "_AOI\" feature class",1)
                
            except:
                print_exception()
                gp.OverWriteOutput = 1
            
        else:
            gp.CopyFeatures_management(AOI, projectAOI)
            AddMsgAndPrint("\nSuccessfully Created \"" + str(projectName) + "_AOI\" feature class",1)

    # paths are the same therefore AOI is projectAOI
    else:
        AddMsgAndPrint("\nUsing Existing \"" + str(projectName) + "_AOI\" feature class:",1)
      
    # -------------------------------------------------------------------------------------------- Exit if AOI was not a polygon 
    if gp.Describe(projectAOI).ShapeType != "Polygon":
        AddMsgAndPrint("\n\nYour Area of Interest must be a polygon layer!.....Exiting!",2)
        sys.exit()
    # --------------------------------------------------------------------------------------------  Populate AOI with DEM Properties
    # Write input DEM name to AOI 
    if len(gp.ListFields(projectAOI,"INPUT_DEM")) < 1:
        gp.AddField_management(projectAOI, "INPUT_DEM", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        
    gp.CalculateField_management(projectAOI, "INPUT_DEM", "\"" + os.path.basename(inputDEM) +  "\"", "VB", "")
    
    # Write XY Units to AOI
    if len(gp.ListFields(projectAOI,"XY_UNITS")) < 1:
        gp.AddField_management(projectAOI, "XY_UNITS", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        
    gp.CalculateField_management(projectAOI, "XY_UNITS", "\"" + str(units) + "\"", "VB", "")
    
    # Write Z Units to AOI
    if len(gp.ListFields(projectAOI,"Z_UNITS")) < 1:
        gp.AddField_management(projectAOI, "Z_UNITS", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        
    gp.CalculateField_management(projectAOI, "Z_UNITS", "\"" + str(zUnits) + "\"", "VB", "")

    # Delete unwanted "Id" remanant field
    if len(gp.ListFields(projectAOI,"Id")) > 0:
        
        try:
            gp.DeleteField_management(projectAOI,"Id")
        except:
            pass
        
    # Get the Shape Area to notify user of Area and Acres of AOI
    rows = gp.searchcursor(projectAOI,"","","SHAPE_Area")
    row = rows.next()    

    area = ""

    while row:
        area = row.SHAPE_Area
        break

    del rows
    del row

    if area != 0:

        AddMsgAndPrint("\tProject_AOI Area:  " + str(splitThousands(round(area,2))) + " Sq. " + units,0)

        if units == "Meters":
            acres = area/4046.86
            AddMsgAndPrint("\tProject_AOI Acres: " + str(splitThousands(round(acres,2))) + " Acres",0)
            del acres

        elif units == "Feet":
            acres = area/43560
            AddMsgAndPrint("\tProject_AOI Acres: " + str(splitThousands(round(acres,2))) + " Acres",0)
            del acres

        else:
            AddMsgAndPrint("\tCould not calculate Acres",2)

    del area

    # ------------------------------------------------------------------------------------------------- Clip inputDEM
    gp.ExtractByMask_sa(inputDEM, AOI, DEM_aoi)
    AddMsgAndPrint("\nSuccessully Clipped " + os.path.basename(inputDEM) + " using " + os.path.basename(projectAOI),1)

     
    # --------------------------------------------------------------- Round Elevation Values to create "Relative Survey"
    AddMsgAndPrint("\nRounding Elevation Values to create Project DEM",1)
    
    # Convert to feet if necessary
    if not zUnits == "Feet":
        AddMsgAndPrint("\n\tConverting elevations to feet",1)
        gp.Times_sa(DEM_aoi, Zfactor, DEMft)
        AddMsgAndPrint("\tSuccessfully converted elevations to feet",1)
        DEM_aoi = DEMft
        
    # Get Minimum Elevation in AOI...
    gp.ZonalStatistics_sa(AOI, "OBJECTID", DEM_aoi, MinDEM, "MINIMUM", "DATA")

    # Subtract Minimum Elevation from all cells in AOI...
    gp.Minus_sa(DEM_aoi, MinDEM, MinusDEM)

    # Multiply DEM by 10 for rounding...
    gp.Times_sa(MinusDEM, "10", TimesDEM)
    
    # Create Int and Float Rasters to create Project DEM with feet rounded to 10ths..
    Expression1 = "int(["+str(TimesDEM)+"] + 0.5)"
    gp.SingleOutputMapAlgebra_sa(Expression1, intDEM)
    
    Expression2 = "float(["+str(intDEM)+"] * 0.1)"
    gp.SingleOutputMapAlgebra_sa(Expression2, projectDEM)

    AddMsgAndPrint("\n\tSuccessfully rounded elevations",1)
    
    # Delete intermediate rasters
    datasetsToRemove = (MinDEM,MinusDEM,TimesDEM,intDEM,DEMft)

    x = 0
    for dataset in datasetsToRemove:

        if gp.exists(dataset):

            if x < 1:
                AddMsgAndPrint("\n\tDeleting Intermediate Data..",1)
                x += 1
                
            try:
                gp.delete_management(dataset)
            except:
                pass
            
    del dataset
    del datasetsToRemove
    del x
    # ------------------------------------------------------------------------------------------------ Creating Contours 
    AddMsgAndPrint("\nCreating Contour Lines...",1) 
    # Run Focal Statistics on the DEM_aoi for the purpose of generating smooth contours
    gp.focalstatistics_sa(projectDEM, DEMsmooth,"RECTANGLE 3 3 CELL","MEAN","DATA")

    # Create Contours from DEMsmooth if user-defined interval is greater than 0
    if interval > 0:
        gp.Contour_sa(DEMsmooth, ContoursTemp, interval, "0", "1")
        
        AddMsgAndPrint("\nSuccessfully Created " + str(interval) + " foot Contours from " + os.path.basename(projectDEM),1)
        
        gp.AddField_management(ContoursTemp, "Index", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

        if gp.exists("ContourLYR"):
            try:
                gp.delete_management("ContourLYR")
            except:
                pass
            
        gp.MakeFeatureLayer_management(ContoursTemp,"ContourLYR","","","")

        # Every 5th contour will be indexed to 1
        expression = "MOD( \"CONTOUR\"," + str(float(interval) * 5) + ") = 0"
        
        gp.SelectLayerByAttribute("ContourLYR", "NEW_SELECTION", expression)
        indexValue = 1
        gp.CalculateField_management("ContourLYR", "Index", indexValue, "VB","")
        del indexValue

        # All othe contours will be indexed to 0
        gp.SelectLayerByAttribute("ContourLYR", "SWITCH_SELECTION", "")
        indexValue = 0
        gp.CalculateField_management("ContourLYR", "Index", indexValue, "VB","")
        del indexValue

        # Clear selection and write all contours to a new feature class        
        gp.SelectLayerByAttribute("ContourLYR","CLEAR_SELECTION","")      
        gp.CopyFeatures_management("ContourLYR", Contours)

        # Delete unwanted datasets
        gp.delete_management(ContoursTemp)
        gp.delete_management("ContourLYR")
       
        del expression
        
    else:
        AddMsgAndPrint("\nCountours will not be created since interval was set to 0",2)

    # ---------------------------------------------------------------------------------------------- Create Hillshade and Depth Grid
    # Process: Creating Hillshade from DEM_aoi
    DEM_aoi = watershedGDB_path + os.sep + projectName + "_DEM"
    gp.HillShade_sa(DEM_aoi, Hillshade, "315", "45", "#", Zfactor)
    AddMsgAndPrint("\nSuccessfully Created Hillshade from " + os.path.basename(DEM_aoi),1)

    try:
        # Fills sinks in DEM_aoi to remove small imperfections in the data.
        gp.Fill_sa(DEM_aoi, Fill_DEMaoi, "")
        AddMsgAndPrint("\nSuccessfully filled sinks in " + os.path.basename(DEM_aoi) + " to create Depth Grid",1)
        fill = True

    except:
        fill = False
        gp.AddError("\n\nFailed filling in the sinks on " + os.path.basename(DEM_aoi) + "\n")
        AddMsgAndPrint("Depth Grid will not be created\n",2)
        AddMsgAndPrint(gp.GetMessages(2),2)

    if fill:
        # DEM_aoi - Fill_DEMaoi = FilMinus
        gp.Minus_sa(Fill_DEMaoi, DEM_aoi, FilMinus)

        # Create a Depth Grid; Any pixel where there is a difference write it out
        gp.Con_sa(FilMinus, FilMinus, depthGrid, "", "VALUE > 0")

        # Delete unwanted rasters
        gp.delete_management(Fill_DEMaoi)
        gp.delete_management(FilMinus)
        
        AddMsgAndPrint("\nSuccessfully Created a Depth Grid",1)
          

    # ------------------------------------------------------------------------------------------------ Prepare to Add to Arcmap

    gp.SetParameterAsText(5, Contours)
    gp.SetParameterAsText(6, projectAOI)
    gp.SetParameterAsText(7, projectDEM)
    gp.SetParameterAsText(8, Hillshade)
    gp.SetParameterAsText(9, depthGrid)


    AddMsgAndPrint("\nAdding Layers to ArcMap",1)
    AddMsgAndPrint("\n",1)
    
    # ------------------------------------------------------------------------------------------------ Compact FGDB
    try:
        gp.compact_management(watershedGDB_path)
        AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path),1)
    except:
        pass
    # ------------------------------------------------------------------------------------------------ Clean up Time!
    gp.RefreshCatalog(watershedGDB_path)

    # Restore User environments
    gp.extent = tempExtent
    gp.mask = tempMask
    gp.SnapRaster = tempSnapRaster
    gp.CellSize = tempCellSize
    gp.OutputCoordinateSystem = tempCoordSys
    
    try:
        del gp
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
        del ArcGIS10
        del version
        # WASCOB Additions
        del projectDEM
        del DEMft
        del MinDEM
        del MinusDEM
        del TimesDEM
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

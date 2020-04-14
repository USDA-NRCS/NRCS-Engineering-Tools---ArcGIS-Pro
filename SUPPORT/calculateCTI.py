#----------------------------------------------------------------------------
#
# calculateCTI.py
#
# Created by Peter Mead MN USDA NRCS
#
# Creates A Compound Topographic Index for an area of interest.
#
## ================================================================================================================ 
def print_exception():
    
    tb = sys.exc_info()[2]
    l = traceback.format_tb(tb)
    l.reverse()
    tbinfo = "".join(l)
    AddMsgAndPrint(" \n----------ERROR Start------------------- \n",2)
    AddMsgAndPrint("Traceback Info:  \n" + tbinfo + "Error Info:  \n    " +  str(sys.exc_type)+ ": " + str(sys.exc_value) + "",2)
    AddMsgAndPrint("----------ERROR End--------------------  \n",2)

## ================================================================================================================    
def AddMsgAndPrint(msg, severity=0):
    # prints message to screen if run as a python script
    # Adds tool message to the geoprocessor
    # 
    # Split the message on  \n first, so that if it's multiple lines, a GPMessage will be added for each line
    
    print msg
    
    try:

        f = open(textFilePath,'a+')
        f.write(msg + "  \n")
        f.close

        del f

        if ArcGIS10:
            if not msg.find("\n") < 0 and msg.find("\n") < 4:
                gp.AddMessage(" ")        
        
        for string in msg.split(' \n'):          
            
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
    f.write(" \n################################################################################################################ \n")
    f.write("Executing \"Compound Topographic Index\" Tool \n")
    f.write("User Name: " + getpass.getuser() + " \n")
    f.write("Date Executed: " + time.ctime() + " \n")
    f.write("ArcGIS Version: " + str(version) + "\n")
    f.write("User Parameters:\n")
    f.write(" \tWorkspace: " + userWorkspace + " \n")   
    f.write(" \tInput DEM: " + DEM_aoi + " \n")
    f.write(" \tInput Flow Accumulation Grid: " + FlowAccum + " \n")
    if len(zUnits) < 1:
        f.write(" \tInput Z Units: BLANK \n")
    else:
        f.write(" \tInput Z Units: " + str(zUnits) + " \n")
    if len(inWatershed) > 0:
        f.write(" \tClipping set to mask: " + inWatershed + " \n")
    else:
        f.write(" \tClipping: NOT SELECTED\n") 
        
    f.close
    del f

## ================================================================================================================
# Import system modules
import sys, os, arcgisscripting, string, traceback

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

    # -------------------------------------------------------------------------------------------- Input Parameters
    DEM_aoi = gp.getparameterastext(0)
    zUnits = gp.getparameterastext(1)
    inWatershed = gp.getparameterastext(2)
        
    if len(inWatershed) > 0:
        clip = True
    else:
        clip = False
        
    # --------------------------------------------------------------------- Define Variables
    
    DEMpath = gp.Describe(DEM_aoi).CatalogPath
    # AOI DEM must be from a engineering tools file geodatabase
    if not DEMpath.find('_EngTools.gdb') > -1:
        gp.AddError("\n\nInput AOI DEM is not in a \"xx_EngTools.gdb\" file geodatabase.")
        gp.AddError("\n\nYou must provide a DEM prepared with the Define Area of Interest Tool.... ....EXITING")
        sys.exit("")
        
    watershedGDB_path = DEMpath[:DEMpath.find(".gdb")+4]
    userWorkspace = os.path.dirname(watershedGDB_path)
    watershedGDB_name = os.path.basename(watershedGDB_path)
    projectName = gp.ValidateTablename(os.path.basename(userWorkspace).replace(" ","_"))

    # ---------------------------------- Datasets -------------------------------------------
    # -------------------------------------------------------------------- Temporary Datasets

    smoothDEM = watershedGDB_path + os.sep + "smoothDEM"
    ctiTemp = watershedGDB_path + os.sep + "ctiTemp"
    DEMclip = watershedGDB_path + os.sep + "DEMclip"
    FACclip = watershedGDB_path + os.sep + "FACclip"
    FDRclip = watershedGDB_path + os.sep + "FDRclip"
    
    
    # -------------------------------------------------------------------- Permanent Datasets
    
    Slope = watershedGDB_path + os.sep + projectName + "_Slope"    
    ctiOut = watershedGDB_path + os.sep + projectName + "_CTI"

    # -------------------------------------------------------------------- Required Existing Inputs
    
    FlowAccum = watershedGDB_path + os.sep + "flowAccumulation"

    # Path of Log file
    textFilePath = userWorkspace + os.sep + projectName + "_EngTools.txt"

    # record basic user inputs and settings to log file for future purposes
    logBasicSettings()

    # ------------------------------------------------------------------- Check some parameters
    # Flow Accum and Flow Dir must be in project gdb
    if not gp.Exists(FlowAccum):
        AddMsgAndPrint("\n\nFlow Accumulation grid not found in same directory as " + str(os.path.basename(DEM_aoi)) + " (" + watershedGDB_path + "/" + watershedGDB_name + ")",2)
        AddMsgAndPrint("\nYou Must run the \"Create Stream\" Network Tool to create Flow Direction/Accumulation Grids....EXITING\n",2)
        sys.exit("")
        
    #-------------------------------------------------------------------- Get Raster Properties
    
    AddMsgAndPrint("\nGathering information about " + os.path.basename(DEM_aoi)+ ":",1) 
    desc = gp.Describe(DEM_aoi)
    sr = desc.SpatialReference
    units = sr.LinearUnitName
    cellSize = desc.MeanCellWidth
    cellArea = cellSize * cellSize

    # Set Z Factor for slope calculations    
    if units == "Meter":
        units = units + "s"
        if not len(zUnits) > 0:
            zUnits = units
        if zUnits == "Meters":
            Zfactor = 1
        elif zUnits == "Feet":
            Zfactor = 0.3048
                        
    if units == "Foot":
        units = "Feet"
        if not len(zUnits) > 0:
            zUnits = units
        if zUnits == "Meters":
            Zfactor = 3.28084
        elif zUnits == "Feet":
            Zfactor = 1

    if units == "Foot_US":
        units = "Feet"
        if not len(zUnits) > 0:
            zUnits = units
        if zUnits == "Meters":
            Zfactor = 3.28084
        elif zUnits == "Feet":
            Zfactor = 1            
        
    # Print / Display DEM properties    

    AddMsgAndPrint("\n\tProjection Name: " + sr.Name,0)
    AddMsgAndPrint("\tXY Linear Units: " + units,0)
    AddMsgAndPrint("\tElevation Values (Z): " + zUnits,0) 
    AddMsgAndPrint("\tCell Size: " + str(desc.MeanCellWidth) + " x " + str(desc.MeanCellHeight) + " " + units,0)
       
    # -------------------------------------------------------------------------- Capture Default Environments
    
    tempExtent = gp.Extent
    tempMask = gp.mask
    tempSnapRaster = gp.SnapRaster
    tempCellSize = gp.CellSize
    tempCoordSys = gp.OutputCoordinateSystem

    # ----------------------------------- Set Environment Settings
    
    gp.Extent = "MINOF"
    gp.CellSize = cellSize
    gp.mask = ""
    gp.SnapRaster = DEM_aoi
    gp.OutputCoordinateSystem = sr
    
    del desc
    del sr     

    # ---------------------------------------------------------------------------- If user provided a mask clip inputs first.
    
    if clip:
        
        # Clip inputs to input Mask
        AddMsgAndPrint("\nClipping Grids to " + str(os.path.basename(inWatershed)) + "...",1) 
        gp.ExtractByMask_sa(DEM_aoi, inWatershed, DEMclip)
        AddMsgAndPrint("\tSuccessfully clipped " + str(os.path.basename(DEM_aoi)),0)  
        gp.ExtractByMask_sa(FlowAccum, inWatershed, FACclip)
        AddMsgAndPrint("\tSuccessfully clipped Flow Accumulation",0)
        
        # Reset paths to DEM and Flow Accum
        DEM_aoi = DEMclip
        FlowAccum = FACclip

    # --------------------------------------------------------------------------------- Calculate Slope Grid
    if not gp.Exists(Slope):
        AddMsgAndPrint("\nPreparing Slope Grid using a Z-Factor of " + str(Zfactor) + "",1)
        
        if not gp.Exists(smoothDEM):
            # Smooth the DEM to remove imperfections in drop
            AddMsgAndPrint("\n\tSmoothing the Raw DEM...",0)    
            gp.Focalstatistics_sa(DEM_aoi, smoothDEM,"RECTANGLE 3 3 CELL","MEAN","DATA")

        # Calculate percent slope with proper Z Factor    
        AddMsgAndPrint("\tCalculating percent slope...",0)
        gp.Slope_sa(smoothDEM, Slope, "PERCENT_RISE", Zfactor)
                       
    # --------------------------------------------------------------------------------- Create and Filter CTI
    
    # Calculate CTI
    AddMsgAndPrint("\nCalculating Compound Topographic Index...",1)
    gp.SingleOutputMapAlgebra_sa("Ln((\""+str(FlowAccum)+"\" + 0.001) / (\""+str(Slope)+"\" / 100 + 0.001))", ctiTemp)
    AddMsgAndPrint("\n\tFiltering index values...",0)

    # Set Values < 0 to null
    gp.SetNull(ctiTemp, ctiTemp, ctiOut, "\"VALUE\" <= 0")

    # --------------------------------------------------------------------------------- Delete intermediate data
                       
    datasetsToRemove = (smoothDEM,ctiTemp,DEMclip,FACclip)

    x = 0
    for dataset in datasetsToRemove:

        if gp.Exists(dataset):

            if x == 0:
                AddMsgAndPrint(" \nDeleting Temporary Data...",1)
                x += 1
                
            try:
                gp.Delete_management(dataset)
                
            except:
                pass
    del x, dataset, datasetsToRemove
    
    # ----------------------------------------------------------------------- Compact FGDB
    try:
        gp.compact_management(watershedGDB_path)
        AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path),1)    
    except:
        pass

    # ------------------------------------------------------------ Prepare to Add to Arcmap

    gp.SetParameterAsText(3, ctiOut)    

    #----------------------------------------------------------------------- Finished! 
    # Restore original environments
    gp.extent = tempExtent
    gp.mask = tempMask
    gp.SnapRaster = tempSnapRaster
    gp.CellSize = tempCellSize
    gp.OutputCoordinateSystem = tempCoordSys   

    AddMsgAndPrint("\nProcessing Completed!",1)
    AddMsgAndPrint("\n",0)
    
    #--------------------------------------------------------------------- Take care of Some HouseKeeping....
    
    gp.RefreshCatalog(watershedGDB_path)
    
    try:
        del inWatershed
        del DEM_aoi
        del zUnits
        del clip
        del DEMpath
        del watershedGDB_path
        del userWorkspace
        del watershedGDB_name
        del projectName
        del smoothDEM
        del ctiTemp
        del DEMclip
        del FACclip
        del Slope
        del ctiOut
        del FlowDir
        del FlowAccum
        del textFilePath
        del cellSize
        del cellArea
        del tempExtent
        del tempMask
        del tempSnapRaster
        del tempCellSize
        del tempCoordSys
        del units
        del Zfactor
        del gp
    except:
        pass


except SystemExit:
    pass

except KeyboardInterrupt:
    AddMsgAndPrint("Interruption requested....exiting")

except:
    print_exception()    

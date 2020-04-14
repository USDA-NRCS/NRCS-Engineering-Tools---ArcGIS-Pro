## convertDEM.py
##
## Created by Peter Mead, USDA NRCS, 2013
## Updated by Chris Morse, USDA NRCS, 2019
##
## Converts a DEM's elevation values from native Z-Units to User Specified Units
## Optionally allows user to clip DEM prior to conversion or supply a pre-clipped grid
##
# ---------------------------------------------------------------------------
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
    # Split the message on  \n first, so that if it's multiple lines, a GPMessage will be added for each line

    print(msg)
    
    try:
        f = open(textFilePath,'a+')
        f.write(msg + " \n")
        f.close
        del f
        
        if severity == 0:
            arcpy.AddMessage(msg)
        elif severity == 1:
            arcpy.AddWarning(msg)
        elif severity == 2:
            arcpy.AddError(msg)
            
    except:
        pass

## ================================================================================================================
def logBasicSettings():    
    # record basic user inputs and settings to log file for future purposes

    import getpass, time

    f = open(textFilePath,'a+')
    f.write("\n##################################################################\n")
    f.write("Executing \"Convert DEM Z-Units\" Tool" + "\n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write("ArcGIS Version: " + str(arcpy.GetInstallInfo()['Version']) + "\n")    
    f.write("User Parameters:\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tInput Dem: " + inputDEM + "\n")
    f.write("\tInput Elevation Z-units: " + zUnits + "\n")
    f.write("\tOutput Elevation Z-units: " + outzUnits + "\n")
    
    f.close
    del f

## ================================================================================================================
# Import system modules
import arcpy, sys, os, traceback

# Environment settings
arcpy.env.overwriteOutput = True
arcpy.env.geographicTransformations = "WGS_1984_(ITRF00)_To_NAD_1983"
arcpy.env.resamplingMethod = "BILINEAR"
arcpy.env.pyramid = "PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP"

### Version check
##version = str(arcpy.GetInstallInfo()['Version'])
##if version.find("10.") > 0:
##    ArcGIS10 = True
##else:
##    ArcGIS10 = False
#### Convert version string to a float value (needed for numeric comparison)
##versionFlt = float(version[0:4])
##if versionFlt < 10.5:
##    arcpy.AddError("\nThis tool requires ArcGIS version 10.5 or greater. Exiting...\n")
##    sys.exit()

# Main - wrap everything in a try statement
try:
    #--------------------------------------------------------------------- Check out SA license or exit if not available
    if arcpy.CheckExtension("spatial") == "Available":
        arcpy.CheckOutExtension("spatial")
    else:
        arcpy.AddError("\n\tSpatial Analyst Extension not enabled. Please enable Spatial Analyst from the Tools/Extensions menu. Exiting...\n")
        sys.exit()

    arcpy.SetProgressorLabel("Setting Variables")
    #--------------------------------------------------------------------- Input Parameters
    inputDEM = arcpy.GetParameterAsText(0)
    zUnits = arcpy.GetParameterAsText(1)
    demClipped = arcpy.GetParameter(2)
    inMask = arcpy.GetParameterAsText(3)
    outzUnits = arcpy.GetParameterAsText(4)
    outputDEM = arcpy.GetParameterAsText(5)

    #--------------------------------------------------------------------- Directory Paths
    userWorkspace = os.path.dirname(os.path.realpath(outputDEM))
    demName = os.path.splitext(os.path.basename(outputDEM))[0]
    DEMtemp = userWorkspace + os.sep + "DEMtemp"
    textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.txt"

    # record basic user inputs and settings to log file for future purposes
    logBasicSettings()
    
    #--------------------------------------------------------------------- Set Variables for Conversion    
    AddMsgAndPrint("\nRunning Convert DEM Z-Units tool...",0)
    # Check if Dem is Clipped was selected
    
    if demClipped == False:
        Clip = True
    else:
        Clip = False
   
    # Check if Mask was provided    
    if int(arcpy.GetCount_management(inMask).getOutput(0)) > 0:
        Mask = True
    else:
        Mask = False

    if Clip == False:
        if Mask == True:
            AddMsgAndPrint("\n\n\"My DEM is Already clipped\" was selected AND a mask was provided.",2)
            AddMsgAndPrint("\nYou must choose one or the other. Select one option and try again. Exiting...\n",2)
            sys.exit("")
            
    elif Clip == True:
        if Mask == False:
            AddMsgAndPrint("\n\n\"My DEM is Already clipped\" was not selected NOR was a mask provided.",2)
            AddMsgAndPrint("\nYou must choose one or the other. Select one option and try again. Exiting...\n",2)
            sys.exit("")
            
    # --------------------------------------------------------------------- Capture Default Environments
    tempExtent = arcpy.env.extent
    tempMask = arcpy.env.mask
    tempSnapRaster = arcpy.env.snapRaster
    tempCellSize = arcpy.env.cellSize
    tempCoordSys = arcpy.env.outputCoordinateSystem
    
    #--------------------------------------------------------------------- Retrieve Spatial Reference and units from DEM
    
    desc = arcpy.Describe(inputDEM)
    sr = desc.SpatialReference
    cellSize = desc.MeanCellWidth
    units = sr.LinearUnitName

    AddMsgAndPrint("\nGathering information about Input DEM: " + os.path.basename(inputDEM)+ ":\n",0)    

    # Coordinate System must be a Projected type in order to continue.
    # zUnits and outzUnits will determine conversion factor for the creation of a new DEM.
    # Conversion factors are now set for use with the Times function, as of 10/16/2019.
    
    if sr.Type == "Projected":
        if zUnits == "Meters":
            if outzUnits == "Feet":
                convFactor = 3.280839896
            if outzUnits == "Inches":
                convFactor = 39.3701
            if outzUnits == "Centimeters":
                convFactor = 100
            if outzUnits == "Meters":
                AddMsgAndPrint("\n\n\tSelected output Z-Units are the same as input Z-Units. Exiting...",2)
                sys.exit(0)
        elif zUnits == "Centimeters":
            if outzUnits == "Feet":
                convFactor = 0.03280839896
            if outzUnits == "Inches":
                convFactor = 0.393701
            if outzUnits == "Meters":
                convFactor = 0.01
            if outzUnits == "Centimeters":
                AddMsgAndPrint("\n\n\tSelected output Z-Units are the same as input Z-Units. Exiting...",2)
                sys.exit(0)            
        elif zUnits == "Feet":
            if outzUnits == "Centimeters":
                convFactor = 30.48
            if outzUnits == "Inches":
                convFactor = 12
            if outzUnits == "Meters":
                convFactor = 0.3048
            if outzUnits == "Feet":
                AddMsgAndPrint("\n\n\tSelected output Z-Units are the same as input Z-Units. Exiting...",2)
                sys.exit(0)
        elif zUnits == "Inches":
            if outzUnits == "Centimeters":
                convFactor = 2.54
            if outzUnits == "Feet":
                convFactor = 0.0833333 
            if outzUnits == "Meters":
                convFactor = 0.0254
            if outzUnits == "Inches":
                AddMsgAndPrint("\n\n\tSelected output Z-Units are the same as input Z-Units. Exiting...",2)
                sys.exit(0)                
    else:
        AddMsgAndPrint("\n\n\t" + os.path.basename(inputDEM) + " is NOT in a projected Coordinate System. Exiting...",2)
        sys.exit(0)

    AddMsgAndPrint("\tInput Projection Name: " + sr.Name,0)
    AddMsgAndPrint("\tXY Linear Units: " + units,0)
    AddMsgAndPrint("\tCell Size: " + str(desc.MeanCellWidth) + " x " + str(desc.MeanCellHeight) + " " + units + "\n",0)
    AddMsgAndPrint("\tInput Elevation Values (Z): " + zUnits,0)
    AddMsgAndPrint("\tOuput Elevation Values (Z): " + outzUnits,0) 
    AddMsgAndPrint("\tConversion Factor: " + str(float(convFactor)),0)

    # -------------------------------------------------------------------- Specify environments
    arcpy.env.extent = "MINOF"
    arcpy.env.cellSize = cellSize
    arcpy.env.mask = ""
    arcpy.env.snapRaster = ""
    arcpy.env.outputCoordinateSystem = sr
    
    # -------------------------------------------------------------------- Clip DEM to AOI if DEM not already clipped

    if Clip:
        clippedDEM = arcpy.sa.ExtractByMask(inputDEM, inMask)
        clippedDEM.save(DEMtemp)
        AddMsgAndPrint("\nSuccessully Clipped " + os.path.basename(inputDEM) + " to area of interest...",0)
        inputDEM = DEMtemp

##    # Change to Times. Update conversion factors (Done 10/16/2019)
##    gp.Divide_sa(inputDEM, convFactor, outputDEM)
##    AddMsgAndPrint("\nSuccessfully converted " + os.path.basename(inputDEM) + " from " + str(zUnits) + " to " + str(outzUnits) + "\n",1)

    outTimes = arcpy.sa.Times(inputDEM, convFactor)
    outTimes.save(outputDEM)
    AddMsgAndPrint("\nSuccessfully converted " + os.path.basename(inputDEM) + " from " + str(zUnits) + " to " + str(outzUnits) + "\n",0)
    
    # -------------------------------------------------------------------- Delete Optional Temp Output
    if Clip == True:
        AddMsgAndPrint("\nDeleting intermediate data...",0)
        try:
            arcpy.Delete_management(DEMtemp)
        except:
            pass
    # ------------------------------------------------------------------------------------------------ Compact FGDB
    try:
        arcpy.Compact_management(watershedGDB_path)
        AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path),0)    
    except:
        pass
    # ------------------------------------------------------------------------------------------------ FIN!
    AddMsgAndPrint("\nProcessing Complete!\n",0)
    
    # -------------------------------------------------------------------- Cleanup
    arcpy.RefreshCatalog(userWorkspace)

    # Restore environment settings
    arcpy.env.extent = tempExtent
    arcpy.env.mask = tempMask
    arcpy.env.snapRaster = tempSnapRaster
    arcpy.env.outputCoordinateSystem = tempCoordSys
   
# -----------------------------------------------------------------------------------------------------------------

except SystemExit:
    pass

except KeyboardInterrupt:
    AddMsgAndPrint("Interruption requested....exiting")

except:
    print_exception()   

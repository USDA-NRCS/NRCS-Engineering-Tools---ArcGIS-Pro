## Wascob_calibrateDEM.py for LiDAR-Based DEM Design of Water and Sediment Control Basins
##
## Author: Peter Mead, 2018
## Contact: peter.mead@geogurus.com
##
## Notes:
## Allows User input of Survey points or a decimal value to adjust a DEM up or down based on differences in Elevation
##
## Updated: Chris Morse, USDA NRCS, 2020

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
    # Split the message on  \n first, so that if it's multiple lines, a GPMessage will be added for each line

    print(msg)
    
    try:
        f = open(textFilePath,'a+')
        f.write(msg + " \n")
        f.close
        del f
    except:
        pass
    
    if severity == 0:
        arcpy.AddMessage(msg)
    elif severity == 1:
        arcpy.AddWarning(msg)
    elif severity == 2:
        arcpy.AddError(msg)

## ================================================================================================================
def logBasicSettings():    
    # record basic user inputs and settings to log file for future purposes

    import getpass, time

    f = open(textFilePath,'a+')
    f.write("\n################################################################################################################\n")
    f.write("Executing \"DEM Calibration Tool\"\n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write("User Parameters:\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tInput DEM: " + inputDEM + "\n")
    if len(str(inputPoints)) > 0:
        f.write("\tInput Survey Points: " + inputPoints + "\n")
    else:
        f.write("\tInput Adjustment Value: " + str(inputValue) + "\n")
    f.close
    del f

## ================================================================================================================
## ================================================================================================================
# Import system modules
import sys, os, arcpy, traceback
#import string

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
    # Check out Spatial Analyst License
    if arcpy.CheckExtension("Spatial") == "Available":
        arcpy.CheckOutExtension("Spatial")
    else:
        arcpy.AddError("\nSpatial Analyst Extension not enabled. Please enable Spatial Analyst from the Tools/Extensions menu. Exiting...\n")
        sys.exit()

    arcpy.SetProgressorLabel("Setting Variables")
    # ---------------------------------------------------------------------------- Input Parameters
    inputDEM = arcpy.GetParameterAsText(0)
    inputPoints = arcpy.GetParameterAsText(1)  
    inputField = arcpy.GetParameterAsText(2)
    #inputValue = float(arcpy.GetParameterAsText(3))
    inputValue = arcpy.GetParameter(3)

    watershed_path = arcpy.Describe(inputDEM).CatalogPath
   
    # Check source of input DEM, exit if not a WASCOB "Project DEM"
    if watershed_path.find('.gdb') > 0 and watershed_path.find('_DEM') > 0:
        watershedGDB_path = watershed_path[:watershed_path.find('.gdb')+4]
    else:
        arcpy.AddError(" \n\n" + inputDEM + " is an invalid Project DEM")
        arcpy.AddError(" \tPlease provide the \"Project_DEM\" produced by the step 1. \"Define Area of Interest\" tool. Exiting...\n\n")
        sys.exit()
        
    watershedGDB_name = os.path.basename(watershedGDB_path)
    watershedFD = watershedGDB_path + os.sep + "Layers"
    userWorkspace = os.path.dirname(watershedGDB_path)
    projectName = arcpy.ValidateTableName(os.path.basename(userWorkspace).replace(" ","_"))

    # Output Datasets 
    ProjectDEM = watershedGDB_path + os.sep + projectName + "_DEM"
    surveyPoints = watershedFD + os.sep + "calibration_points"

    # Temp Datasets
    backupDEM = watershedGDB_path + os.sep + "backupDEM"
    tempDEM = watershedGDB_path + os.sep + "tempDEM"
    tempPoints = watershedGDB_path + os.sep + "tempPoints"
    tempStats = watershedGDB_path + os.sep + "tempStats"

    # start log file
    textFilePath = userWorkspace + os.sep + projectName + "_EngTools.txt"
    logBasicSettings()

    # ----------------------------- Capture User environments
    tempExtent = arcpy.env.extent
    tempMask = arcpy.env.mask
    tempSnapRaster = arcpy.env.snapRaster
    tempCellSize = arcpy.env.cellSize
    tempCoordSys = arcpy.env.outputCoordinateSystem
    
    # ---------------------------------- Retrieve Raster Properties
    desc = arcpy.Describe(inputDEM)
    sr = desc.SpatialReference
    units = sr.LinearUnitName
    cellSize = desc.MeanCellWidth

    # ----------------------------- Set the following environments
    arcpy.env.extent = "MAXOF"
    arcpy.env.cellSize = cellSize
    arcpy.env.mask = ""
    arcpy.env.snapRaster = ""
    arcpy.env.outputCoordinateSystem = sr
        
    # ---------------------------------------------------------------------------- Main Block
    AddMsgAndPrint(" \nBeginning Calibration Process...",0)

    averageDifference = 0
    
    if not len(str(inputPoints)) > 0:
        averageDifference = inputValue
        
    else:
        AddMsgAndPrint(" \n\tCopying input survey points...",0)
        arcpy.CopyFeatures_management(inputPoints, tempPoints)
        AddMsgAndPrint(" \tBacking up " + str(inputDEM) + "...",0)
        arcpy.CopyRaster_management(inputDEM, backupDEM)

        # Retrieve Spot Elevations
        # Change VB Expressions to PYTHON_9.3
        AddMsgAndPrint(" \n\tCalculating differences in elevation...",0)
        arcpy.AddField_management(tempPoints, "POINTID", "LONG")
        #arcpy.CalculateField_management(tempPoints, "POINTID", "[OBJECTID]", "VB", "")
        arcpy.CalculateField_management(tempPoints, "POINTID", "!OBJECTID!", "PYTHON")
        arcpy.AddField_management(tempPoints, "SURV_ELEV", "DOUBLE")
        arcpy.AddField_management(tempPoints, "RAST_ELEV", "DOUBLE")
        arcpy.AddField_management(tempPoints, "DIFF", "DOUBLE")
        #arcpy.CalculateField_management(tempPoints, "SURV_ELEV", "[" + str(inputField) + "]", "VB", "")
        arcpy.CalculateField_management(tempPoints, "SURV_ELEV", "!" + str(inputField) + "!", "PYTHON")

        # Use Zonal Statistics to pull values from project DEM
        arcpy.sa.ZonalStatisticsAsTable(tempPoints, "POINTID", inputDEM, tempStats, "DATA")

        rows = arcpy.SearchCursor(tempStats)
        totalPoints = 0
        totalDifference = 0
        
        # Use search cursor on stats TABLE
        for row in rows:
            pointID = row.POINTID
            zonalValue = row.MEAN
            
            # Pass Values to survey points
            whereclause = "POINTID = " + str(pointID)
            pointRows = arcpy.UpdateCursor(tempPoints,whereclause)         

            # Pass the elevation Data to Reference Line FC.
            for pointRow in pointRows:
                survElev = pointRow.SURV_ELEV
                pointRow.RAST_ELEV = round(zonalValue,1)
                pointRow.DIFF = round(survElev - zonalValue,1)
                pointRows.updateRow(pointRow)
                totalDifference += pointRow.DIFF
                totalPoints += 1

                break      
             
            del pointID
            del zonalValue
            del survElev
            del whereclause
            del pointRow
            del pointRows
            
        del row
        del rows
        
        averageDifference = round(totalDifference / totalPoints,1)
        
        del totalDifference, totalPoints

        # Copy survey points to project FD    
        arcpy.CopyFeatures_management(tempPoints, surveyPoints)

    # ----------------------  Create New Adjusted Raster Surface
    AddMsgAndPrint( " \nAverage difference in surface elevation is " + str(averageDifference) + " feet...",0)
    if averageDifference == 0:
        AddMsgAndPrint(" \n No difference (greater than 0.1 foot) was detected.",2)
        AddMsgAndPrint(" \nYour DEM will not be adjusted. Exiting...",2)
        sys.exit()
    else:
        AddMsgAndPrint( " \nApplying " + str(averageDifference) + " Z-units adjustment to " + str(inputDEM) + "...",0)
        #arcpy.gp.Plus_sa(inputDEM, averageDifference, tempDEM)
        outPlus = arcpy.sa.Plus(inputDEM, averageDifference)
        outPlus.save(tempDEM)


##    # shouldn't this always be just the Plus function? If Average Difference is negative, subtracting a negative would actually be adding positive? See change above (else statement).
##    elif averageDifference > 0:
##        AddMsgAndPrint( " \nAdding " + str(averageDifference) + " Z-units to " + str(inputDEM) + "...",0)
##        #arcpy.gp.Plus_sa(inputDEM, averageDifference, tempDEM)
##        outPlus = arcpy.sa.Plus(inputDEM, averageDifference)
##        outPlus.save(tempDEM)
##    elif averageDifference < 0:
##        AddMsgAndPrint( " \nSubtracting " + str(averageDifference) + " Z-units from " + str(inputDEM) + "...",0)
##        #arcpy.gp.Minus_sa(inputDEM, averageDifference, tempDEM)
##        outMinus = arcpy.sa.Minus(inputDEM, averageDifference)
##        outMinus.save(tempDEM)

    proceed = False
    
    try:
        arcpy.CopyRaster_management(tempDEM, ProjectDEM)
        proceed = True

    except:
        AddMsgAndPrint(" \nUnable to re-create ProjectDEM. Restoring original...",2)
        arcpy.CopyRaster_management(backupDEM, ProjectDEM)
        AddMsgAndPrint(" \nAdjusted surface can be found at " + str(tempDEM) + ".",2)

    if proceed:
        datasetsToRemove = (tempDEM,backupDEM,tempPoints,tempStats)
    else:
        datasetsToRemove = (tempPoints,backupDEM,tempStats)

    x = 0
    for dataset in datasetsToRemove:
        if arcpy.Exists(dataset):
            if x < 1:
                AddMsgAndPrint(" \nDeleting temporary datasets..." ,0)
                x += 1
            try:
                arcpy.Delete_management(dataset)
                AddMsgAndPrint(" \tDeleting..." + os.path.basename(dataset),0)
            except:
                pass
            
    del dataset
    del datasetsToRemove
    del x
    del proceed
    del averageDifference

    arcpy.SetParameterAsText(4, ProjectDEM)
    
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


    AddMsgAndPrint(" \nProcessing Complete!",0)
    AddMsgAndPrint(" \n",0)
    
except SystemExit:
    pass

except KeyboardInterrupt:
    AddMsgAndPrint("Interruption requested....exiting")

except:
    print_exception()


# updateWatershedAttributes.py
## ================================================================================================================ 
def print_exception():
    
    tb = sys.exc_info()[2]
    l = traceback.format_tb(tb)
    l.reverse()
    tbinfo = "".join(l)
    AddMsgAndPrint("\n----------ERROR Start-------------------\n",2)
    AddMsgAndPrint("Traceback Info:\n" + tbinfo + "Error Info:\n    " +  str(sys.exc_type)+ ": " + str(sys.exc_value) + "",2)
    AddMsgAndPrint("----------ERROR End--------------------\n",2)

## ================================================================================================================    
def AddMsgAndPrint(msg, severity=0):
    # prints message to screen if run as a python script
    # Adds tool message to the geoprocessor
    # 
    # Split the message on\n first, so that if it's multiple lines, a GPMessage will be added for each line

    print msg
    
    try:

        f = open(textFilePath,'a+')
        f.write(msg + "\n")
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
    f.write("Executing \"4.Update Watershed Attributess\" Tool\n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write("ArcGIS Version: " + str(version) + "\n")
    f.write("User Parameters:\n")
    f.write("\tInput Watershed: " + watershed + "\n")
    
    f.close
    del f
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
# Import system modules
import sys, os, traceback, arcgisscripting, string, re

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
    # --------------------------------------------------------------------- Input Parameters
    watershed = gp.GetParameterAsText(0)

    # --------------------------------------------------------------------- Variables
    watershedPath = gp.Describe(watershed).CatalogPath
    watershedGDB_path = watershedPath[:watershedPath.find('.gdb')+4]
    watershedGDB_name = os.path.basename(watershedGDB_path)
    userWorkspace = os.path.dirname(watershedGDB_path)
    watershedFD = watershedGDB_path + os.sep + "Layers"
    wsName = os.path.basename(watershed)
    projectName = gp.ValidateTablename(os.path.basename(userWorkspace).replace(" ","_"))
    projectAOI = watershedFD + os.sep + projectName + "_AOI"
    Flow_Length = watershedFD + os.sep + wsName + "_FlowPaths"
    
    # log File Path
    textFilePath = userWorkspace + os.sep + projectName + "_EngTools.txt"   
    
    # record basic user inputs and settings to log file for future purposes
    logBasicSettings()
    
    if gp.Exists(Flow_Length):
        updateFlowLength = True
        
    else:
        updateFlowLength = False
        
    # --------------------------------------------------------------------- Permanent Datasets
    DEM_aoi = watershedGDB_path + os.sep + projectName + "_DEM"
    DEMsmooth = watershedGDB_path + os.sep + "DEMsmooth"

    # --------------------------------------------------------------------- Temporary Datasets
    wtshdDEMsmooth = watershedGDB_path + os.sep + "wtshdDEMsmooth"
    slopeGrid = watershedGDB_path + os.sep + "slopeGrid"
    slopeStats = watershedGDB_path + os.sep + "slopeStats"

    # --------------------------------------------------------------------- Get XY Units From inWatershed
    desc = gp.Describe(DEM_aoi)
    sr = desc.SpatialReference
    
    units = sr.LinearUnitName
    cellSize = desc.MeanCellWidth
    
    if units == "Meter":
        units = "Meters"
    elif units == "Foot":
        units = "Feet"
    elif units == "Foot_US":
        units = "Feet"
        
    # ------------------------------------ Capture default environments
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
    
    # ---------------------------------------------------------------------- Update Drainage Area(s)
    
    if units == "Meters":
        if len(gp.ListFields(watershed,"Acres")) < 1:
            gp.AddField_management(watershed, "Acres", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
            
        gp.CalculateField_management(watershed, "Acres", "[Shape_Area]/4046.86", "VB", "")
        displayAreaInfo = True
        AddMsgAndPrint("\nSuccessfully updated drainage area(s)",1)
        
    elif units == "Feet":
        if len(gp.ListFields(watershed,"Acres")) < 1:
            gp.AddField_management(watershed, "Acres", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
            
        gp.CalculateField_management(watershed, "Acres", "[Shape_Area]/43560", "VB", "")
        displayAreaInfo = True
        AddMsgAndPrint("\nSuccessfully updated drainage area(s)..",1)

    else:
        displayAreaInfo = False
        AddMsgAndPrint("\nUnable to update drainage acres..  ..You must manually calculate in " + str(wsName) + "'s attribute table",1)

    # ---------------------------------------------------------------------- Update Flow Path Length (if present)
    
    if updateFlowLength:
        
        if units == "Meters":

            if len(gp.ListFields(Flow_Length,"Length_ft")) < 1:
                gp.AddField_management(Flow_Length, "Length_ft", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
                
            gp.CalculateField_management(Flow_Length, "Length_ft", "[shape_length] * 3.28084", "VB", "")
            AddMsgAndPrint("\nSuccessfully updated flow path length(s)..",1)

        elif units == "Feet":

            if len(gp.ListFields(Flow_Length,"Length_ft")) < 1:
                gp.AddField_management(Flow_Length, "Length_ft", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

            gp.CalculateField_management(Flow_Length, "Length_ft", "[shape_length]", "VB", "")
            AddMsgAndPrint("\nSuccessfully updated flow path length(s)..",1)

        else:
            AddMsgAndPrint("\nUnable to update flow length(s)..  ..You must manually calculate in " + str(os.path.basename(Flow_Length)) + "'s attribute table",1)        
        
    # ----------------------------------------------------------------------- Update Average Slope
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
            AddMsgAndPrint("\nMissing DEMsmooth and DEM_aoi from " + watershedGDB_name + " FGDB. Could not Calculate Average Slope",2)
    else:
        AddMsgAndPrint("\nMissing Project AOI from " + watershedGDB_name + " FGDB. Could not retrieve Z Factor to Calculate Average Slope",2)

    # -------------------------------------------------------------------------------------- Update Watershed FC with Average Slope
    if calcAvgSlope:
        
        # go through each zonal Stat record and pull out the Mean value
        rows = gp.searchcursor(slopeStats)
        row = rows.next()

        AddMsgAndPrint("\nSuccessfully re-calculated average slope",1)

        AddMsgAndPrint("\n===================================================",0)
        AddMsgAndPrint("\tUser Watershed: " + str(wsName),0)
        
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
    time.sleep(3)
    
    # ------------------------------------------------------------------------------------------------ Compact FGDB
    try:
        gp.compact_management(watershedGDB_path)
        AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path),1)    
    except:
        pass

    # ------------------------------------------------------------------------------------------------ Cleanup
    # Restore original environments
    gp.extent = tempExtent
    gp.mask = tempMask
    gp.SnapRaster = tempSnapRaster
    gp.CellSize = tempCellSize
    gp.OutputCoordinateSystem = tempCoordSys
    
    try:    
        del gp
        del watershedGDB_path
        del watershedGDB_name
        del userWorkspace
        del watershedFD
        del wsName
        del projectName
        del projectAOI
        del Flow_Length
        del DEM_aoi
        del DEMsmooth
        del wtshdDEMsmooth
        del slopeGrid
        del slopeStats
        del units
        del cellSize
        del Zfactor
        del displayAreaInfo
        del calcAvgSlope
        del version
        del ArcGIS10
        del desc
        del sr
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

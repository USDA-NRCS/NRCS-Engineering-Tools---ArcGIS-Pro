# ---------------------------------------------------------------------------
# exportData.py
#
# Peter Mead USDA NRCS 
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
                AddMsgAndPrint("    ")
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
    f.write("Executing \"Wascob: Export Data\" Tool\n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write("User Parameters:\n")
    f.write("\tInput Watershed: " + inWatershed + "\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")   

    if len(outCoordsys) > 0:
        f.write("\tOutput Coord Sys: " + outCoordsys + "\n")
    else:
        f.write("\tOutput Coord Sys: BLANK\n") 
        
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
        
    # ---------------------------------------------- Input Parameters
    inWatershed = gp.GetParameterAsText(0)
    outCoordsys = gp.GetParameterAsText(1)

    # ---------------------------------------------------------------------------- Define Variables 
    watershed_path = gp.Describe(inWatershed).CatalogPath
    watershedGDB_path = watershed_path[:watershed_path .find(".gdb")+4]
    watershedFD_path = watershedGDB_path + os.sep + "Layers"
    userWorkspace = os.path.dirname(watershedGDB_path)
    outputFolder = userWorkspace + os.sep + "gis_output"

    # Path of Log file
    textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_WascobTools.txt"

    # record basic user inputs and settings to log file for future purposes
    logBasicSettings()
   
    # ----------------------------------- Inputs to be converted to shp
    stationPoints = watershedFD_path + os.sep + "StationPoints"
    tileLines = watershedFD_path + os.sep + "tileLines"
    stakeoutPoints = watershedFD_path + os.sep + "stakeoutPoints"
    referenceLines = watershedFD_path + os.sep + "ReferenceLine"

    # ----------------------------------- Possible Existing Feature Layers
    stations = "StationPoints"
    tile = "TileLines"
    refLine = "Reference Line"
    points = "StakeoutPoints"
    
    # ------------------------ If lyrs present, clear any possible selections
    if gp.Exists(stations):
        gp.SelectLayerByAttribute_management(stations, "CLEAR_SELECTION", "")
    if gp.Exists(tile):
        gp.SelectLayerByAttribute_management(tile, "CLEAR_SELECTION", "")
    if gp.Exists(refLine):
        gp.SelectLayerByAttribute_management(refLine, "CLEAR_SELECTION", "")
    if gp.Exists(points):
        gp.SelectLayerByAttribute_management(points, "CLEAR_SELECTION", "")        

    # ----------------------------------------------------- Shapefile Outputs
    stationsOut = outputFolder + os.sep + "StationPoints.shp"
    tileOut = outputFolder + os.sep + "TileLines.shp"
    pointsOut = outputFolder + os.sep + "StakeoutPoints.shp"
    linesOut = outputFolder + os.sep + "ReferenceLines.shp"
    

    # ---------------------------------- Set Parameters for Output Projection if necessary
    change = False
    if len(outCoordsys) > 0:
        change = True
        AddMsgAndPrint("\nSetting output coordinate system",1)
        tempCoordSys = gp.OutputCoordinateSystem
        gp.OutputCoordinateSystem = outCoordsys

    # ------------------------------------------------------------ Copy FC's to Shapefiles
    AddMsgAndPrint("\nCopying GPS layers to output Folder",1)
    if gp.Exists(stationPoints):
        gp.CopyFeatures_management(stationPoints, stationsOut)
    else:
        AddMsgAndPrint("\nUnable to find stationPoints in project workspace, copy failed.  Export them manually.",2)
    if gp.Exists(tileLines):
        gp.CopyFeatures_management(tileLines, tileOut)
    else:
        AddMsgAndPrint("\nUnable to find TileLines in project workspace, copy failed.  Export them manually.",2)
    if gp.Exists(stakeoutPoints):  
        gp.CopyFeatures_management(stakeoutPoints, pointsOut)
    else:
        AddMsgAndPrint("\nUnable to find stakeoutPoints in project workspace, copy failed.  Export them manually.",2)
    if gp.Exists(referenceLines):
        gp.CopyFeatures_management(referenceLines, linesOut)
    else:
        AddMsgAndPrint("\nUnable to find referenceLines in project workspace, copy failed.  Export them manually.",2)


    # --------------------------------------------------- Restore Environments if necessary
    if change:
        gp.OutputCoordinateSystem = tempCoordSys
    
    AddMsgAndPrint("\nProcessing Finished!\n",1)

    # -------------------------------------------------------------- Cleanup

    try:
        del inWatershed
        del watershedGDB_path
        del userWorkspace
        del watershed_path
        del watershedFD_path
        del outputFolder
        del textFilePath
        del stationPoints
        del tileLines
        del stakeoutPoints
        del referenceLines
        del stations
        del tile
        del refLine
        del points
        del stationsOut
        del tileOut
        del pointsOut
        del linesOut
    except:
        pass
        
except SystemExit:
    pass

except KeyboardInterrupt:
    AddMsgAndPrint("Interruption requested....exiting")

except:
    print_exception()

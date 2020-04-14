## ChangeProfileCoordinates.py
##
## Created by Chris Morse, USDA NRCS, 2014
## Updated by Chris Morse, USDA NRCS, 2019
##
## Converts existing Profile Points layer to new copy in a new coordinate system.
## Recomputes X,Y, and Z values for the table of the new layer.
## Includes option to create a new text file of the points table, per the normal Profile tool.

# ---------------------------------------------------------------------------
def print_exception():
    
    tb = sys.exc_info()[2]
    l = traceback.format_tb(tb)
    l.reverse()
    tbinfo = "".join(l)
    AddMsgAndPrint("----------ERROR Start-------------------",2)
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
    f.write("Executing \"Line to XYZ\" Tool" + "\n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write("ArcGIS Version: " + str(arcpy.GetInstallInfo()['Version']) + "\n")    
    f.write("User Parameters:\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tInput Dem: " + arcpy.Describe(inputDEM).CatalogPath + "\n")
#    f.write("\tInterval: " + str(interval) + "\n")
    f.write("\tElevation Z-units: " + zUnits + "\n")
    f.write("\tCoordinate System: " + outCS + "\n")
    
    f.close
    del f
    
## ================================================================================================================    
# Import system modules
import arcpy, sys, os, traceback
#import arcgisscripting, string

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
    # Check out 3D and SA licenses
    if arcpy.CheckExtension("3d") == "Available":
        arcpy.CheckOutExtension("3d")
    else:
        AddMsgAndPrint("\n3D analyst extension is not enabled. Please enable 3D Analyst from the Tools/Extensions menu. Exiting...\n",2)
        sys.exit()
    if arcpy.CheckExtension("spatial") == "Available":
        arcpy.CheckOutExtension("spatial")
    else:
        AddMsgAndPrint("\nSpatial Analyst Extension not enabled. Please enable Spatial Analyst from the Tools/Extensions menu. Exiting...\n",2)
        sys.exit()

    arcpy.SetProgressorLabel("Setting Variables")
    #----------------------------------------------------------------------------------------- Input Parameters
    userWorkspace = arcpy.GetParameterAsText(0)
    inputPoints = arcpy.GetParameterAsText(1)
    inputDEM = arcpy.GetParameterAsText(2)
    zUnits = arcpy.GetParameterAsText(3)
    outCS = arcpy.GetParameterAsText(4)
    text = arcpy.GetParameter(5)

    # --------------------------------------------------------------------- Directory Paths
    watershedGDB_name = os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.gdb"  # replace spaces for new FGDB name
    watershedGDB_path = userWorkspace + os.sep + watershedGDB_name
    watershedFD = watershedGDB_path + os.sep + "Layers"
    projectName = arcpy.ValidateTableName(os.path.basename(userWorkspace).replace(" ","_"))

    # record basic user inputs and settings to log file for future purposes
    textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.txt"
    logBasicSettings()

    # ----------------------------- Capture User environments
    tempCoordSys = arcpy.env.outputCoordinateSystem

    # ----------------------------- Set the following environments
    arcpy.env.outputCoordinateSystem = outCS

    # --------------------------------------------------------------------- Permanent Datasets
    outPoints = userWorkspace + os.sep + projectName + "_XYZ_new_coordinates.shp"
    outTxt = userWorkspace + os.sep + projectName + "_XYZ_new_coordinates.txt"
    # Must Have a unique name for output -- Append a unique digit to output if required
    x = 1
    while x > 0:
        if arcpy.Exists(outPoints):
            outPoints = userWorkspace + os.sep + projectName + "_XYZ_new_coordinates" + str(x) + ".shp"
            outTxt = userWorkspace + os.sep + projectName + "_XYZ_new_coordiantes" + str(x) + ".txt"
            x += 1
        else:
            x = 0
    del x
    
    outPointsLyr = "" + os.path.basename(outPoints) + ""

    # --------------------------------------------------------------------- Temp Datasets
    pointsProj = watershedGDB_path + os.sep + "pointsProj"    

    # --------------------------------------------------------------------- Check DEM Coordinate System and Linear Units
    AddMsgAndPrint("\nGathering information about DEM: " + os.path.basename(inputDEM)+ "\n",0)
    desc = arcpy.Describe(inputDEM)
    sr = desc.SpatialReference
    units = sr.LinearUnitName
    cellSize = desc.MeanCellWidth
    
    if units == "Meter":
        units = "Meters"
    elif units == "Foot":
        units = "Feet"
    elif units == "Foot_US":
        units = "Feet"
        
##    # if zUnits were left blank than assume Z-values are the same as XY units.
##    if not len(zUnits) > 0:
##        zUnits = units

    # Coordinate System must be a Projected type in order to continue.
    # zUnits will determine Zfactor for the conversion of elevation values to feet.
    
    if sr.Type == "Projected":
        if zUnits == "Meters":
            Zfactor = 3.280839896       # 3.28 feet in a meter
        elif zUnits == "Centimeters":   # 0.033 feet in a centimeter
            Zfactor = 0.03280839896
        elif zUnits == "Inches":        # 0.083 feet in an inch
            Zfactor = 0.0833333
        # zUnits must be feet; no more choices       
        else:
            Zfactor = 1                 

        AddMsgAndPrint("\tProjection Name: " + sr.Name,0)
        AddMsgAndPrint("\tXY Linear Units: " + units,0)
        AddMsgAndPrint("\tElevation Values (Z): " + zUnits,0) 
        AddMsgAndPrint("\tCell Size: " + str(desc.MeanCellWidth) + " x " + str(desc.MeanCellHeight) + " " + units,0)

    else:
        AddMsgAndPrint("\n\n\t" + os.path.basename(inputDEM) + " is NOT in a projected Coordinate System. Exiting...",2)
        sys.exit()

    # ------------------------------------------------------------------------ Create FGDB, FeatureDataset
    # Boolean - Assume FGDB already exists
    FGDBexists = True
                      
    # Create Watershed FGDB and feature dataset if it doesn't exist
    if not arcpy.Exists(watershedGDB_path):
        arcpy.CreateFileGDB_management(userWorkspace, watershedGDB_name)
        arcpy.CreateFeatureDataset_management(watershedGDB_path, "Layers", sr)
        AddMsgAndPrint("\nSuccessfully created File Geodatabase: " + watershedGDB_name,0)
        FGDBexists = False

    # if GDB already existed but feature dataset doesn't
    if not arcpy.Exists(watershedFD):
        arcpy.CreateFeatureDataset_management(watershedGDB_path, "Layers", sr)

    # Copy Features will use the spatial reference of the geoprocessing environment that has been set
    # Transformation between WGS84 and NAD83 will default to WGS_1984_(ITRF00)_To_NAD_1983, per env settings
    # No other areas of transformation can be used - document this in help and manuals
    arcpy.CopyFeatures_management(inputPoints, pointsProj)

    # ------------------------------------------------------------- Recalculate X,Y values in output table
    arcpy.AddXY_management(pointsProj)
    
    # --------------------------------------------------------------------- Update Elevation values in feet
    arcpy.AddSurfaceInformation_3d(pointsProj, inputDEM, "Z", "", "", Zfactor)
    expression = "round(!Z!,1)"
    arcpy.CalculateField_management(pointsProj, "POINT_Z", expression, "PYTHON_9.3")
    del expression

    # --------------------------------------------------------------------- Clean up extra fields
    arcpy.DeleteField_management(pointsProj, "POINT_M")
    arcpy.DeleteField_management(pointsProj, "Z")

    # ---------------------------------------------------------------------- Create final output
    # Copy Station Points
    arcpy.CopyFeatures_management(pointsProj, outPoints)

    # Create Txt file if selected and write attributes of station points
    if text == True:
        AddMsgAndPrint("Creating Output text file:\n",0)
        AddMsgAndPrint("\t" + str(outTxt) + "\n",0)

        t = open(outTxt, 'w')
        t.write("ID, STATION, X, Y, Z")
        t.close()
        
        rows = arcpy.SearchCursor(outPoints, "", "", "STATION", "STATION" + " A")

        txtRows = arcpy.InsertCursor(outTxt)
        row = rows.next()

        while row:
            newRow = txtRows.newRow()
            newRow.ID = row.ID
            newRow.STATION = row.STATION
            newRow.X = row.POINT_X
            newRow.Y = row.POINT_Y
            newRow.Z = row.POINT_Z
            txtRows.insertRow(newRow)

            row = rows.next()
        
        del txtRows
        del newRow
        del row
        del rows
        del t

    # Restore environments
    arcpy.env.outputCoordinateSystem = tempCoordSys

    # ---------------------------------------------------- Prepare to add to ArcMap

    AddMsgAndPrint("Adding Layer to ArcMap\n",0)
    arcpy.SetParameterAsText(6, outPoints)

    # ------------------------------------------------------------------- Delete Temp Layers
    layersToRemove = (pointsProj)    
    AddMsgAndPrint("Deleting temporary files...\n",0)
    x = 0
    for layer in layersToRemove:
        if arcpy.Exists(layer):
            if x == 0:
                AddMsgAndPrint("",0)
                x+=1
            try:
                arcpy.Delete_management(layer)
            except:
                pass
    del x
    del layer
    del layersToRemove
    
    # ---------------------------------------------------------------------------------------------------------------------------- Compact FGDB
    try:
        arcpy.Compact_management(watershedGDB_path)
        AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path),0)    
    except:
        pass
    # ---------------------------------------------------------------------------- FIN!
    AddMsgAndPrint("Processing Complete!\n",0)

    # ---------------------------------------------------------------------------- Cleanup
    arcpy.RefreshCatalog(watershedGDB_path)

except SystemExit:
    pass

except KeyboardInterrupt:
    AddMsgAndPrint("Interruption requested....exiting")

except:
    print_exception()            


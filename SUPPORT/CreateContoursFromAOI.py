# ==========================================================================================
# Name: Clip DEM to AOI
#
# Author: Peter Mead
# e-mail: pemead@co.becker.mn.us
#
# Author: Chris Morse
#         IN State GIS Coordinator
#         USDA - NRCS
# e-mail: chris.morse@usda.gov
# phone: 317.501.1578
#
# Author: Adolfo.Diaz
#         GIS Specialist
#         National Soil Survey Center
#         USDA - NRCS
# e-mail: adolfo.diaz@usda.gov
# phone: 608.662.4422 ext. 216

# Created by Peter Mead, Adolfo Diaz, USDA NRCS, 2013
# Updated by Chris Morse, USDA NRCS, 2019

# ==========================================================================================
# Updated  3/6/2020 - Adolfo Diaz
# - Updated and Tested for ArcGIS Pro 2.4.2 and python 3.6
# - Added Snap Raster environment

## ================================================================================================================
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
    f.write("Executing \"Create Contours By AOI\" Tool \n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write("ArcGIS Version: " + str(arcpy.GetInstallInfo()['Version']) + "\n")
    f.write("User Parameters:\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tInput Dem: " + inputDEM + "\n")
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
    except:
        print_exception()
        return someNumber

## ================================================================================================================
# Import system modules
import arcpy, sys, os, traceback, re
#import  arcgisscripting

# Environment settings
arcpy.env.overwriteOutput = True
arcpy.env.geographicTransformations = "WGS_1984_(ITRF00)_To_NAD_1983"
arcpy.env.resamplingMethod = "BILINEAR"
arcpy.env.pyramid = "PYRAMIDS -1 BILINEAR DEFAULT 75 NO_SKIP"
arcpy.env.parallelProcessingFactor = "75%"

# Main - wrap everything in a try statement
try:
    # Check out Spatial Analyst License
    if arcpy.CheckExtension("Spatial") == "Available":
        arcpy.CheckOutExtension("Spatial")
    else:
        arcpy.AddError("\nSpatial Analyst Extension not enabled. Please enable Spatial Analyst from the Tools/Extensions menu. Exiting...\n")
        sys.exit()

    arcpy.SetProgressorLabel("Setting Variables")
    # --------------------------------------------------------------------- Input Parameters
    userWorkspace = arcpy.GetParameterAsText(0)
    inputDEM = arcpy.GetParameterAsText(1)
    zUnits = arcpy.GetParameterAsText(2)
    AOI = arcpy.GetParameterAsText(3)
    interval = arcpy.GetParameterAsText(4)

    # --------------------------------------------------------------------------------------------- Define Variables
    projectName = arcpy.ValidateTableName(os.path.basename(userWorkspace).replace(" ","_"))
    watershedGDB_name = os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.gdb"  # replace spaces for new FGDB name
    watershedGDB_path = userWorkspace + os.sep + watershedGDB_name
    watershedFD = watershedGDB_path + os.sep + "Layers"

    # ---------------------------------------------------------- Datasets
    # ------------------------------ Permanent Datasets
    projectAOI = watershedFD + os.sep + projectName + "_AOI"
    Contours = watershedFD + os.sep + projectName + "_Contours_" + str(interval.replace(".","_")) + "ft"
    DEM_aoi = watershedGDB_path + os.sep + projectName + "_DEM"
    Hillshade = watershedGDB_path + os.sep + projectName + "_Hillshade"

    #------------------------------- Temp Layers
    ContoursTemp = watershedFD + os.sep + "ContoursTemp"
    DEMsmooth = watershedGDB_path + os.sep + "DEMsmooth_contoursByAOI"

    # ------------------------------- Map Layers
    aoiOut = "" + projectName + "_AOI"
    contoursOut = "" + projectName + "_Contours_" + str(interval) + "ft"
    hillshadeOut = "" + projectName + "_HillShade"

    # start log file
    textFilePath = userWorkspace + os.sep + projectName + "_EngTools.txt"
    logBasicSettings()

    # ---------------------------------------------------------------------------------------------- Validate Inputs
    arcpy.SetProgressorLabel("Validating Inputs")
    AddMsgAndPrint("\nValidating Inputs...",0)

    # Check interval value to be able to be set as a decimal point number
    try:
        float(interval)
    except:
        AddMsgAndPrint("\nCountour Interval was invalid. Cannot create contours. Exiting...",2)
        sys.exit()

    # Exit if AOI contains more than 1 digitized area.
    if int(arcpy.GetCount_management(AOI).getOutput(0)) > 1:
        AddMsgAndPrint("\n\nYou can only digitize 1 Area of interest or provide an AOI with one feature. Please try again. Exiting...",2)
        sys.exit()

    # --------------------------------------------------------------------- Gather DEM Info
    arcpy.SetProgressorLabel("Gathering information about input DEM file")
    AddMsgAndPrint("\nInformation about input DEM file " + os.path.basename(inputDEM)+ ":",0)

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
    elif units == "Feet":
        units = "Feet"

##    ## Remove this block because vertical units should be required to reduce chances of this tool producing improper results ##
##    # if zUnits were left blank than assume Z-values are the same as XY units.
##    if not len(zUnits) > 0:
##        zUnits = units

    # Coordinate System must be a Projected type in order to continue.
    # zUnits will determine Zfactor for the creation of contours in ft.
    # Contour tool has no dependency on the linear units of the DEM,
    # but we always want the contours to be created in feet so convert
    # any other zUnits type to feet with a Zfactor.
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
        AddMsgAndPrint("\n\n\t" + os.path.basename(inputDEM) + " is NOT in a Projected Coordinate System. Exiting...",2)
        sys.exit(0)

    # ------------------------------------- Delete previous layers from ArcMap if they exist
    if arcpy.Describe(AOI).CatalogPath == projectAOI:
        layersToRemove = (contoursOut,hillshadeOut)
    else:
        layersToRemove = (contoursOut,hillshadeOut,aoiOut)
    x = 0
    for layer in layersToRemove:
        if arcpy.Exists(layer):
            if x == 0:
                AddMsgAndPrint("\nRemoving previous layers from your ArcMap session ",0)
                x+=1
            try:
                arcpy.Delete_management(layer)
                AddMsgAndPrint("\tRemoving..." + layer + "",0)
            except:
                pass
    del x, layer, layersToRemove

    # ---------------------------------------------------------------------------------------------- Create FGDB, FeatureDataset
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

    # ----------------------------------------------------------------------------------------------- Clean old files if FGDB already existed.
    if FGDBexists:
        gridsToRemove = (DEM_aoi,DEMsmooth,Hillshade,Contours)
        x = 0
        for grid in gridsToRemove:
            if arcpy.Exists(grid):
                # strictly for formatting
                if x == 0:
                    AddMsgAndPrint("\nRemoving old files from FGDB: " + watershedGDB_name ,0)
                    x += 1
                try:
                    arcpy.Delete_management(grid)
                    AddMsgAndPrint("\tDeleting..." + os.path.basename(grid),0)
                except:
                    pass
        del x, grid, gridsToRemove

    # ----------------------------------------------------------------------------------------------- Create New AOI
    # if paths are not the same then assume AOI was manually digitized
    # or input is some from some other feature class/shapefile
    if not arcpy.Describe(AOI).CatalogPath == projectAOI:
        # delete the AOI feature class; new one will be created
        if arcpy.Exists(projectAOI):
            try:
                arcpy.Delete_management(projectAOI)
                arcpy.CopyFeatures_management(AOI, projectAOI)
                AddMsgAndPrint("\nSuccessfully Recreated Area of Interest",0)
            except:
                print_exception()
                arcpy.env.overwriteOutput = True
        else:
            arcpy.CopyFeatures_management(AOI, projectAOI)
            AddMsgAndPrint("\nSuccessfully Created Area of Interest:" + str(os.path.basename(projectAOI)),0)

    # paths are the same therefore input IS projectAOI
    else:
        AddMsgAndPrint("\nUsing existing \"" + str(projectName) + "_AOI\" feature class:",0)

    if arcpy.Describe(projectAOI).ShapeType != "Polygon":
        AddMsgAndPrint("\n\nYour Area of Interest must be a polygon layer. Exiting...",2)
        sys.exit()

    # --------------------------------------------------------------------------------------------  Add DEM Properties to AOI
    # Write input DEM name to AOI
    # Note: VB Expressions may need to be updated to Python to prepare for conversion to Pro
    if len(arcpy.ListFields(projectAOI,"INPUT_DEM")) < 1:
        arcpy.AddField_management(projectAOI, "INPUT_DEM", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

    expression = '"' + os.path.basename(inputDEM) + '"'
    arcpy.CalculateField_management(projectAOI, "INPUT_DEM", expression, "PYTHON3")

    # Write XY Units to AOI
    if len(arcpy.ListFields(projectAOI,"XY_UNITS")) < 1:
        arcpy.AddField_management(projectAOI, "XY_UNITS", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

    expression = '"' + str(units) + '"'
    arcpy.CalculateField_management(projectAOI, "XY_UNITS", expression, "PYTHON3")

    # Write Z Units to AOI
    if len(arcpy.ListFields(projectAOI,"Z_UNITS")) < 1:
        arcpy.AddField_management(projectAOI, "Z_UNITS", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

    expression = '"' + str(zUnits) + '"'
    arcpy.CalculateField_management(projectAOI, "Z_UNITS", expression, "PYTHON3")
    del expression

    #--------------------------------------------------------------------- Add Acre field
    if not len(arcpy.ListFields(projectAOI,"Acres")) > 0:
        arcpy.AddField_management(projectAOI, "Acres", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

    #--------------------------------------------------------------------- Calculate Acres
    expression = "!SHAPE.AREA@ACRES!"
    arcpy.CalculateField_management(projectAOI, "Acres", expression, "PYTHON3")

    with arcpy.da.SearchCursor(projectAOI, ['SHAPE@AREA','Acres']) as cursor:
        for row in cursor:
            AddMsgAndPrint("\n\tArea of Interest: " + str(os.path.basename(projectAOI)),0)
            AddMsgAndPrint("\t\tArea:  " + str(splitThousands(round(row[0],2))) + " Sq. " + units,0)
            AddMsgAndPrint("\t\tAcres: " + str(splitThousands(round(row[1],2))) + " Acres",0)
    del cursor

##    # Get the Shape Area to notify user of Area and Acres of AOI
##    rows = arcpy.SearchCursor(projectAOI)
##    row = rows.next()
##    area = ""
##    while row:
##        area = row.SHAPE_Area
##        acres = row.Acres
##        if area != 0:
##            AddMsgAndPrint("\n\tArea of Interest: " + str(os.path.basename(projectAOI)),0)
##            AddMsgAndPrint("\t\tArea:  " + str(splitThousands(round(area,2))) + " Sq. " + units,0)
##            AddMsgAndPrint("\t\tAcres: " + str(splitThousands(round(acres,2))) + " Acres",0)
##        else:
##            AddMsgAndPrint("\tCould not calculate Acres for AOI ID: " + str(row.OBJECTID),2)
##        del area
##        del acres
##        row = rows.next()
##    del rows
##    del row

    # ------------------------------------------------------------------------------------------------- Clip inputDEM
    maskedDEM = arcpy.sa.ExtractByMask(inputDEM, projectAOI)
    maskedDEM.save(DEM_aoi)
    AddMsgAndPrint("\nSuccessully Created " + os.path.basename(DEM_aoi) + " using " + os.path.basename(projectAOI),0)

    # ------------------------------------------------------------------------------------------------ Creating Contours
    # Run Focal Statistics on the DEM_aoi for the purpose of generating smooth contours
    outFocalStats = arcpy.sa.FocalStatistics(DEM_aoi, "RECTANGLE 3 3 CELL","MEAN","DATA")
    outFocalStats.save(DEMsmooth)
    AddMsgAndPrint("\nSuccessully Smoothed " + os.path.basename(DEM_aoi),0)

    arcpy.sa.Contour(DEMsmooth, ContoursTemp, interval, "0", Zfactor)
    AddMsgAndPrint("\nSuccessfully Created " + str(interval) + " foot Contours using a Z-factor of " + str(Zfactor),0)

    arcpy.AddField_management(ContoursTemp, "Index", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    if arcpy.Exists("ContourLYR"):
        try:
            arcpy.Delete_management("ContourLYR")
        except:
            pass

    arcpy.MakeFeatureLayer_management(ContoursTemp,"ContourLYR","","","")

    # Every 5th contour will be indexed to 1
    expression = "MOD( \"CONTOUR\"," + str(float(interval) * 5) + ") = 0"
    arcpy.SelectLayerByAttribute_management("ContourLYR", "NEW_SELECTION", expression)
    del expression

    indexValue = 1
    #arcpy.CalculateField_management("ContourLYR", "Index", indexValue, "VB","")
    arcpy.CalculateField_management("ContourLYR", "Index", indexValue, "PYTHON_9.3")
    del indexValue

    # All othe contours will be indexed to 0
    arcpy.SelectLayerByAttribute_management("ContourLYR", "SWITCH_SELECTION")
    indexValue = 0
    #arcpy.CalculateField_management("ContourLYR", "Index", indexValue, "VB","")
    arcpy.CalculateField_management("ContourLYR", "Index", indexValue, "PYTHON_9.3")
    del indexValue

    # Clear selection and write all contours to a new feature class
    arcpy.SelectLayerByAttribute_management("ContourLYR","CLEAR_SELECTION")
    arcpy.CopyFeatures_management("ContourLYR", Contours)

    # ---------------------------------------------------------------------------------------------- Create Hillshade and Depth Grid
    # Process: Creating Hillshade from DEM_aoi
    # This section needs a different Zfactor than just the contours conversion multiplier!
    # Update Zfactor for use with hillshade

    if zUnits == "Meters":
        if units == "Feet":
            Zfactor = 3.280839896
        if units == "Meters":
            Zfactor = 1
    elif zUnits == "Feet":
        if units == "Feet":
            Zfactor = 1
        if units == "Meters":
            Zfactor = 0.3048
    elif zUnits == "Centimeters":
        if units == "Feet":
            Zfactor = 0.03280839896
        if units == "Meters":
            Zfactor = 0.01
    elif zUnits == "Inches":
        if units == "Feet":
            Zfactor = 0.0833333
        if units == "Meters":
            Zfactor = 0.0254

    outHill = arcpy.sa.Hillshade(DEM_aoi, "315", "45", "#", Zfactor)
    outHill.save(Hillshade)
    AddMsgAndPrint("\nSuccessfully Created Hillshade from " + os.path.basename(DEM_aoi),0)

    # ---------------------------------------------------------------------------------------------- Delete Intermediate data
    datasetsToRemove = (DEMsmooth,ContoursTemp,"ContourLYR")
    x = 0
    for dataset in datasetsToRemove:
        if arcpy.Exists(dataset):
            # Strictly Formatting
            if x < 1:
                x += 1
            try:
                arcpy.Delete_management(dataset)
            except:
                pass
    del dataset
    del datasetsToRemove
    del x

    # ------------------------------------------------------------------------------------------------ Compact FGDB
    try:
        arcpy.Compact_management(watershedGDB_path)
        AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path),0)
    except:
        pass

    # ------------------------------------------------------------------------------------------------ Prepare to Add to Arcmap
    arcpy.SetParameterAsText(5, Contours)
    arcpy.SetParameterAsText(6, projectAOI)
    arcpy.SetParameterAsText(7, DEM_aoi)
    arcpy.SetParameterAsText(8, Hillshade)


    AddMsgAndPrint("\nAdding Layers to ArcMap",0)
    AddMsgAndPrint("\n",0)


except SystemExit:
    pass

except KeyboardInterrupt:
    AddMsgAndPrint("Interruption requested....exiting")

except:
    print_exception()


# ==========================================================================================
# Name: Create_Watershed.py
#
# Author: Peter Mead
# e-mail: pemead@co.becker.mn.us
#
# Author: Adolfo.Diaz
#         GIS Specialist
#         National Soil Survey Center
#         USDA - NRCS
# e-mail: adolfo.diaz@usda.gov
# phone: 608.662.4422 ext. 216
#
# Author: Chris Morse
#         IN State GIS Coordinator
#         USDA - NRCS
# e-mail: chris.morse@usda.gov
# phone: 317.501.1578
#
#
# Created by Peter Mead, Adolfo Diaz, USDA NRCS, 2013
# Updated by Chris Morse, USDA NRCS, 2019
#
# ==========================================================================================
# Updated  4/22/2020 - Adolfo Diaz
#
# - Updated and Tested for ArcGIS Pro 2.4.2 and python 3.6
# - All temporary raster layers such as Fill and Minus are stored in Memory and no longer
#   written to hard disk.
# - All describe functions use the arcpy.da.Describe functionality.
# - Removed determineOverlap() function since this can now be done using the extent
#   object to determine overalop of culverts within the AOI
# - All field calculation expressions are in PYTHON3 format.
# - Used acre conversiont dictionary and z-factor lookup table
# - All cursors were updated to arcpy.da
# - Updated AddMsgAndPrint to remove ArcGIS 10 boolean and gp function
# - Updated print_exception function.  Traceback functions slightly changed for Python 3.6.
# - Added Snap Raster environment
# - Added parallel processing factor environment
# - swithced from sys.exit() to exit()
# - All gp functions were translated to arcpy
# - Every function including main is in a try/except clause
# - Main code is wrapped in if __name__ == '__main__': even though script will never be
#   used as independent library.
# - Normal messages are no longer Warnings unnecessarily.

## ===============================================================================================================
def print_exception():

    try:

        exc_type, exc_value, exc_traceback = sys.exc_info()
        theMsg = "\t" + traceback.format_exception(exc_type, exc_value, exc_traceback)[1] + "\n\t" + traceback.format_exception(exc_type, exc_value, exc_traceback)[-1]

        if theMsg.find("exit") > -1:
            AddMsgAndPrint("\n\n")
            pass
        else:
            AddMsgAndPrint("\n----------------------------------- ERROR Start -----------------------------------",2)
            AddMsgAndPrint(theMsg,2)
            AddMsgAndPrint("------------------------------------- ERROR End -----------------------------------\n",2)

    except:
        AddMsgAndPrint("Unhandled error in print_exception method", 2)
        pass

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
    arcInfo = arcpy.GetInstallInfo()  # dict of ArcGIS Pro information

    f = open(textFilePath,'a+')
    f.write("\n################################################################################################################\n")
    f.write("Executing \"3. Create Watershed\" Tool")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write(arcInfo['ProductName'] + ": " + arcInfo['Version'] + "\n")
    f.write("User Parameters:\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tStreams: " + streamsPath + "\n")

    if int(arcpy.GetCount_management(outlet).getOutput(0)) > 0:
        f.write("\toutlet Digitized: " + str(arcpy.GetCount_management(outlet)) + "\n")
    else:
        f.write("\toutlet Digitized: 0\n")

    f.write("\tWatershed Name: " + watershedOut + "\n")

    if bCalcLHL:
        f.write("\tCreate flow paths: SELECTED\n")
    else:
        f.write("\tCreate flow paths: NOT SELECTED\n")

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
import arcpy, sys, os, string, traceback, re, time
from arcpy.sa import *
import arcpy.cartography as CA

if __name__ == '__main__':

    try:
        # Check out Spatial Analyst License
        if arcpy.CheckExtension("spatial") == "Available":
            arcpy.CheckOutExtension("spatial")
        else:
            arcpy.AddError("Spatial Analyst Extension not enabled. Please enable Spatial analyst from the Tools/Extensions menu\n",2)
            exit()

        # Script Parameters
        streams = arcpy.GetParameterAsText(0)
        outlet = arcpy.GetParameterAsText(1)
        userWtshdName = arcpy.GetParameterAsText(2)
        createFlowPaths = arcpy.GetParameterAsText(3)

        # Uncomment the following 4 lines to run from pythonWin
##        streams = r'E:\NRCS_Engineering_Tools_ArcPro\Testing\Testing_EngTools.gdb\Testing_Streams'
##        outlet = r'E:\python_scripts\NRCS_Engineering_Tools\ArcMap_Testing\ArcMap_Testing_EngTools.gdb\DiazWtshd1_outlet'
##        userWtshdName = "ProTest"
##        createFlowPaths = "true"

        # Set environmental variables
        arcpy.env.parallelProcessingFactor = "75%"
        arcpy.env.overwriteOutput = True

        if str(createFlowPaths).upper() == "TRUE":
            bCalcLHL = True
        else:
            bCalcLHL = False

        # --------------------------------------------------------------------------------------------- Define Variables
        streamsPath = arcpy.da.Describe(streams)['catalogPath']

        if streamsPath.find('.gdb') > 0 and streamsPath.find('_Streams') > 0:
            watershedGDB_path = streamsPath[:streamsPath.find(".gdb")+4]
        else:
            arcpy.AddError("\n\n" + streams + " is an invalid Stream Network Feature")
            arcpy.AddError("Run Watershed Delineation Tool #2. Create Stream Network\n\n")
            exit()

        userWorkspace = os.path.dirname(watershedGDB_path)
        watershedGDB_name = os.path.basename(watershedGDB_path)
        watershedFD = watershedGDB_path + os.sep + "Layers"
        projectName = arcpy.ValidateTableName(os.path.basename(userWorkspace).replace(" ","_"))
        projectAOI = watershedFD + os.sep + projectName + "_AOI"
        aoiName = os.path.basename(projectAOI)

        # --------------------------------------------------------------- Datasets
        # ------------------------------ Permanent Datasets
        watershed = watershedFD + os.sep + (arcpy.ValidateTableName(userWtshdName, watershedFD))
        FlowAccum = watershedGDB_path + os.sep + "flowAccumulation"
        FlowDir = watershedGDB_path + os.sep + "flowDirection"
        DEM_aoi = watershedGDB_path + os.sep + projectName + "_DEM"

        # Must Have a unique name for watershed -- userWtshdName gets validated, but that doesn't ensure a unique name
        # Append a unique digit to watershed if required -- This means that a watershed with same name will NOT be
        # overwritten.
        x = 1
        while x > 0:
            if arcpy.Exists(watershed):
                watershed = watershedFD + os.sep + (arcpy.ValidateTableName(userWtshdName, watershedFD)) + str(x)
                x += 1
            else:
                x = 0
        del x

        outletFC = watershedFD + os.sep + os.path.basename(watershed) + "_outlet"

        # Features in Arcmap
        watershedOut = "" + os.path.basename(watershed) + ""
        outletOut = "" + os.path.basename(outletFC) + ""

        # -----------------------------------------------------------------------------------------------  Path of Log file
        textFilePath = userWorkspace + os.sep + projectName + "_EngTools.txt"

        # record basic user inputs and settings to log file for future purposes
        logBasicSettings()

        # ---------------------------------------------------------------------------------------------- Check some parameters
        # If validated name becomes different than userWtshdName notify the user
        if os.path.basename(watershed) != userWtshdName:
            AddMsgAndPrint("\nUser Watershed name: " + str(userWtshdName) + " is invalid or already exists in project geodatabase.",1)
            AddMsgAndPrint("\tRenamed output watershed to " + str(watershedOut),1)

        # Make sure the FGDB and streams exists from step 1 and 2
        if not arcpy.Exists(watershedGDB_path) or not arcpy.Exists(streamsPath):
            AddMsgAndPrint("\nThe \"Streams\" Feature Class or the File Geodatabase from Step 1 was not found",2)
            AddMsgAndPrint("Re-run Step #1 and #2",2)
            exit()

        # Must have one pour points manually digitized
        if not int(arcpy.GetCount_management(outlet).getOutput(0)) > 0:
            AddMsgAndPrint("\n\nAt least one Pour Point must be used! None Detected. Exiting\n",2)
            exit()

        # Flow Accumulation grid must in FGDB
        if not arcpy.Exists(FlowAccum):
            AddMsgAndPrint("\n\nFlow Accumulation Grid was not found in " + watershedGDB_path,2)
            AddMsgAndPrint("Run Tool#2: \"Create Stream Network\" Again!  Exiting.....\n",2)
            exit()

        # Flow Direction grid must present to proceed
        if not arcpy.Exists(FlowDir):
            AddMsgAndPrint("\n\nFlow Direction Grid was not found in " + watershedGDB_path,2)
            AddMsgAndPrint("Run Tool#2: \"Create Stream Network\" Again!  Exiting.....\n",2)
            sys.exit(0)

        # ----------------------------------------------------------------------------------------------- Create New Outlet
        # -------------------------------------------- Features reside on hard disk;
        #                                              No heads up digitizing was used.
        if (os.path.dirname(arcpy.Describe(outlet).CatalogPath)).find("memory") < 0:

            # if paths between outlet and outletFC are NOT the same
            if not arcpy.Describe(outlet).CatalogPath == outletFC:

                # delete the outlet feature class; new one will be created
                if arcpy.Exists(outletFC):
                    arcpy.Delete_management(outletFC)
                    arcpy.CopyFeatures_management(outlet, outletFC)
                    AddMsgAndPrint("\nSuccessfully Recreated " + str(outletOut) + " feature class from existing layer")

                else:
                    arcpy.CopyFeatures_management(outlet, outletFC)
                    AddMsgAndPrint("\nSuccessfully Created " + str(outletOut) + " feature class from existing layer")

            # paths are the same therefore input IS pour point
            else:
                AddMsgAndPrint("\nUsing Existing " + str(outletOut) + " feature class")

        # -------------------------------------------- Features reside in Memory;
        #                                              heads up digitizing was used.
        else:

            if arcpy.Exists(outletFC):
                arcpy.Delete_management(outletFC)
                arcpy.Clip_analysis(outlet,projectAOI,outletFC)
                #arcpy.CopyFeatures_management(outlet, outletFC)
                AddMsgAndPrint("\nSuccessfully Recreated " + str(outletOut) + " feature class from digitizing")

            else:
                arcpy.Clip_analysis(outlet,projectAOI,outletFC)
                #arcpy.CopyFeatures_management(outlet, outletFC)
                AddMsgAndPrint("\nSuccessfully Created " + str(outletOut) + " feature class from digitizing")

        if arcpy.Describe(outletFC).ShapeType != "Polyline" and arcpy.Describe(outletFC).ShapeType != "Line":
            AddMsgAndPrint("\n\nYour Outlet must be a Line or Polyline layer!.....Exiting!",2)
            exit()

        AddMsgAndPrint("\nChecking Placement of Outlet(s)....")
        numOfOutletsWithinAOI = int(arcpy.GetCount_management(outletFC).getOutput(0))
        if numOfOutletsWithinAOI < 1:
            AddMsgAndPrint("\nThere were no outlets digitized within " + aoiName + "....EXITING!",2)
            arcpy.Delete_management(outletFC)
            exit()

        # ---------------------------------------------------------------------------------------------- Create Watershed
        # ---------------------------------- Retrieve DEM Properties
        demDesc = arcpy.da.Describe(DEM_aoi)
        demName = demDesc['name']
        demPath = demDesc['catalogPath']
        demCellSize = demDesc['meanCellWidth']
        demFormat = demDesc['format']
        demSR = demDesc['spatialReference']
        demCoordType = demSR.type
        linearUnits = demSR.linearUnitName

        if linearUnits == "Meter":
            linearUnits = "Meters"
        elif linearUnits == "Foot":
            linearUnits = "Feet"
        elif linearUnits == "Foot_US":
            linearUnits = "Feet"

        # ----------------------------------- Set Environment Settings
        arcpy.env.extent = "MAXOF"
        arcpy.env.cellSize = demCellSize
        arcpy.env.snapRaster = demPath
        arcpy.env.outputCoordinateSystem = demSR
        arcpy.env.workspace = watershedGDB_path

        # --------------------------------------------------------------------- Convert outlet Line Feature to Raster Pour Point.

        # Add dummy field for buffer dissolve and raster conversion using OBJECTID (which becomes subbasin ID)
        objectIDfld = "!" + arcpy.da.Describe(outletFC)['OIDFieldName'] + "!"
        arcpy.AddField_management(outletFC, "IDENT", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")
        arcpy.CalculateField_management(outletFC, "IDENT", objectIDfld, "PYTHON3")

        # Buffer outlet features by  raster cell size
        outletBuffer = "in_memory" + os.sep + os.path.basename(arcpy.CreateScratchName("outletBuffer",data_type="FeatureClass",workspace=watershedGDB_path))
        bufferDist = "" + str(demCellSize) + " " + str(linearUnits) + ""
        arcpy.Buffer_analysis(outletFC, outletBuffer, bufferDist, "FULL", "ROUND", "LIST", "IDENT")

        # Convert bufferd outlet to raster
        #arcpy.MakeFeatureLayer(outletBuffer,"outletBufferLyr")
        pourPointGrid = "in_memory" + os.sep + os.path.basename(arcpy.CreateScratchName("PourPoint",data_type="RasterDataset",workspace=watershedGDB_path))
        arcpy.PolygonToRaster_conversion(outletBuffer,"IDENT",pourPointGrid,"MAXIMUM_AREA","NONE",demCellSize)

        # Delete intermediate data
        arcpy.Delete_management(outletBuffer)
        arcpy.DeleteField_management(outletFC, "IDENT")

        # Create Watershed Raster using the raster pour point
        AddMsgAndPrint("\nDelineating Watershed(s)...")
        #watershedGrid = "in_memory" + os.sep + os.path.basename(arcpy.CreateScratchName("watershedGrid",data_type="RasterDataset",workspace=watershedGDB_path))
        watershedGrid = Watershed(FlowDir,pourPointGrid,"VALUE")

        # Convert results to simplified polygon
        watershedTemp = "in_memory" + os.sep + os.path.basename(arcpy.CreateScratchName("watershedTemp",data_type="FeatureClass",workspace=watershedGDB_path))
        arcpy.RasterToPolygon_conversion(watershedGrid,watershedTemp,"SIMPLIFY","VALUE")

        # Dissolve watershedTemp by GRIDCODE or grid_code
        arcpy.Dissolve_management(watershedTemp, watershed, "GRIDCODE", "", "MULTI_PART", "DISSOLVE_LINES")
        AddMsgAndPrint("\n\tSuccessfully Created " + str(int(arcpy.GetCount_management(watershed).getOutput(0))) + " Watershed(s) from " + str(outletOut),0)

        del pourPointGrid
        del watershedGrid

        # -------------------------------------------------------------------------------------------------- Add and Calculate fields
        # Add Subbasin Field in watershed and calculate it to be the same as GRIDCODE
        arcpy.AddField_management(watershed, "Subbasin", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED")

        arcpy.CalculateField_management(watershed, "Subbasin", "!GRIDCODE!", "PYTHON3")
        arcpy.DeleteField_management(watershed, "GRIDCODE")

        # Add Acres Field in watershed and calculate them and notify the user
        arcpy.AddField_management(watershed, "Acres", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")
        arcpy.CalculateField_management(watershed, "Acres", "!shape.area@acres!", "PYTHON3")

        # ---------------------------------------------------------------------------- If user opts to calculate watershed flow paths
        if bCalcLHL:
            try:

                # ------------------------------------------- Permanent Datasets (..and yes, it took 13 other ones to get here)
                Flow_Length = watershedFD + os.sep + os.path.basename(watershed) + "_FlowPaths"
                FlowLengthName = os.path.basename(Flow_Length)

                # ------------------------------------------- Derive Longest flow path for each subbasin
                # Create Longest Path Feature Class
                arcpy.CreateFeatureclass_management(watershedFD, FlowLengthName, "POLYLINE")
                arcpy.AddField_management(Flow_Length, "Subbasin", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED")
                arcpy.AddField_management(Flow_Length, "Reach", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED")
                arcpy.AddField_management(Flow_Length, "Type", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED")
                arcpy.AddField_management(Flow_Length, "Length_ft", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")

                AddMsgAndPrint("\nCalculating watershed flow path(s)")

                # -------------------------------------------- Raster Flow Length Analysis
                # Set mask to watershed to limit calculations
                arcpy.env.mask = watershed

                # Calculate total upstream flow length on FlowDir grid
                UP_GRID = FlowLength(FlowDir, "UPSTREAM")

                # Calculate total downsteam flow length on FlowDir grid
                DOWN_GRID = FlowLength(FlowDir, "DOWNSTREAM")

                # Sum total upstream and downstream flow lengths
                PLUS_GRID = Plus(UP_GRID, DOWN_GRID)

                # Get Maximum downstream flow length in each subbasin
                MAX_GRID = ZonalStatistics(watershed, "Subbasin", DOWN_GRID, "MAXIMUM", "DATA")

                # Subtract tolerance from Maximum flow length -- where do you get tolerance from?
                MINUS_GRID = Minus(MAX_GRID, 0.3)

                # Extract cells with positive difference to isolate longest flow path(s)
                LONGPATH = GreaterThan(PLUS_GRID, MINUS_GRID)
                LP_Extract = Con(LONGPATH, LONGPATH, "", "\"VALUE\" = 1")

                # Try to use Stream to Feature process to convert the raster Con result to a line (DUE TO 10.5.0 BUG)
                LFP_StreamLink = StreamLink(LP_Extract, FlowDir)
                LongpathTemp = StreamToFeature(LFP_StreamLink, FlowDir, "NO_SIMPLIFY")

                # Smooth and Dissolve results
                LP_Smooth = "in_memory" + os.sep + os.path.basename(arcpy.CreateScratchName("LP_Smooth",data_type="FeatureClass",workspace=watershedGDB_path))
                CA.SmoothLine(LongpathTemp, LP_Smooth, "PAEK", "100 Feet", "FIXED_CLOSED_ENDPOINT", "NO_CHECK")

                # Intersect with watershed to get subbasin ID
                LongpathTemp1 = "in_memory" + os.sep + os.path.basename(arcpy.CreateScratchName("LongpathTemp1",data_type="FeatureClass",workspace=watershedGDB_path))
                arcpy.Intersect_analysis(LP_Smooth + "; " + watershed, LongpathTemp1, "ALL", "", "INPUT")

                # Dissolve to create single lines for each subbasin
                arcpy.Dissolve_management(LongpathTemp1, Flow_Length, "Subbasin", "", "MULTI_PART", "DISSOLVE_LINES")

                # Add Fields / attributes & calculate length in feet
                arcpy.AddField_management(Flow_Length, "Reach", "SHORT", "", "", "", "", "NULLABLE", "NON_REQUIRED")
                objectIDfld2 = "!" + arcpy.da.Describe(Flow_Length)['OIDFieldName'] + "!"
                arcpy.CalculateField_management(Flow_Length, "Reach", objectIDfld2, "PYTHON3")

                arcpy.AddField_management(Flow_Length, "Type", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
                arcpy.CalculateField_management(Flow_Length, "Type", '"Natural Watercourse"', "PYTHON3", "")

                arcpy.AddField_management(Flow_Length, "Length_ft", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

                if linearUnits == "Meters":
                    arcpy.CalculateField_management(Flow_Length, "Length_ft", "!Shape_Length! * 3.28084", "PYTHON3")
                else:
                    arcpy.CalculateField_management(Flow_Length, "Length_ft", "!Shape_Length!", "PYTHON3")

                # ---------------------------------------------------------------------------------------------- Set up Domains
                # Apply domains to watershed geodatabase and Flow Length fields to aid in user editing
                ID_Table = os.path.join(os.path.dirname(sys.argv[0]), "Support.gdb" + os.sep + "ID_TABLE")
                Reach_Table = os.path.join(os.path.dirname(sys.argv[0]), "Support.gdb" + os.sep + "REACH_TYPE")

                # If support tables not present skip domains -- user is on their own.
                if not arcpy.Exists(ID_Table) or not arcpy.Exists(Reach_Table):
                    bDomainTables = False
                else:
                    bDomainTables = True

                if bDomainTables:
                    # describe present domains, establish and apply if needed
                    listOfDomains = arcpy.da.Describe(watershedGDB_path)['domains']

                    if not "Reach_Domain" in listOfDomains:
                        arcpy.TableToDomain_management(ID_Table, "IDENT", "ID_DESC", watershedGDB_path, "Reach_Domain", "Reach_Domain", "REPLACE")

                    if not "Type_Domain" in listOfDomains:
                        arcpy.TableToDomain_management(Reach_Table, "TYPE", "TYPE", watershedGDB_path, "Type_Domain", "Type_Domain", "REPLACE")

                    # Assign domain to flow length fields for User Edits...
                    arcpy.AssignDomainToField_management(Flow_Length, "Reach", "Reach_Domain")
                    arcpy.AssignDomainToField_management(Flow_Length, "TYPE", "Type_Domain")

                #---------------------------------------------------------------------- Flow Path Calculations complete
                AddMsgAndPrint("\n\tSuccessfully extracted watershed flow path(s)")

            except:
                # If Calc LHL fails prompt user to delineate manually and continue...  ...capture error for reference
                print_exception()
                AddMsgAndPrint("\nUnable to Calculate Flow Path(s) .. You will have to trace your stream network to create them manually.."+ arcpy.GetMessages(2),2)
                AddMsgAndPrint("\nContinuing....",1)

        # ----------------------------------------------------------------------------------------------- Calculate Average Slope
        bCalcAvgSlope = False

        # ----------------------------- Retrieve Z Units from AOI
        if arcpy.Exists(projectAOI):

            # Assign Z-factor based on XY and Z units of DEM
            # the following represents a matrix of possible z-Factors
            # using different combination of xy and z units
            # ----------------------------------------------------
            #                      Z - Units
            #                       Meter    Foot     Centimeter     Inch
            #          Meter         1	    0.3048	    0.01	    0.0254
            #  XY      Foot        3.28084	  1	      0.0328084	    0.083333
            # Units    Centimeter   100	    30.48	     1	         2.54
            #          Inch        39.3701	  12       0.393701	      1
            # ---------------------------------------------------

            unitLookUpDict = {'Meter':0,'Meters':0,'Foot':1,'Foot_US':1,'Feet':1,'Centimeter':2,'Centimeters':2,'Inch':3,'Inches':3}
            zFactorList = [[1,0.3048,0.01,0.0254],
                           [3.28084,1,0.0328084,0.083333],
                           [100,30.48,1.0,2.54],
                           [39.3701,12,0.393701,1.0]]

            zUnits = [row[0] for row in arcpy.da.SearchCursor(projectAOI, 'Z_UNITS')][0]
            zFactor = zFactorList[unitLookUpDict.get(zUnits)][unitLookUpDict.get(linearUnits)]

        else:
            zFactor  = 0 # trapped for below so if Project AOI not present slope isnt calculated

        # --------------------------------------------------------------------------------------------------------
        if zFactor  > 0:
            AddMsgAndPrint("\nCalculating average slope...")

            arcpy.env.mask = watershed

            if arcpy.Exists(DEM_aoi):

                # Run Focal Statistics on the DEM_aoi to remove exteraneous values
                outFocalStats = FocalStatistics(DEM_aoi, "RECTANGLE 3 3 CELL","MEAN","DATA")

                arcpy.AddField_management(watershed, "Avg_Slope", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")

                slopeGrid = Slope(outFocalStats, "PERCENT_RISE", zFactor)
                ZonalStatisticsAsTable(watershed, "Subbasin", slopeGrid, slopeStats, "DATA")
                bCalcAvgSlope = True

            else:
                AddMsgAndPrint("\nMissing DEMsmooth or DEM_aoi from FGDB. Could not Calculate Average Slope",2)

        else:
            AddMsgAndPrint("\nMissing Project AOI from FGDB. Could not retrieve Z Factor to Calculate Average Slope",2)

        # -------------------------------------------------------------------------------------- Update Watershed FC with Average Slope
        if bCalcAvgSlope:

            AddMsgAndPrint("\n\tSuccessfully Calculated Average Slope")

            AddMsgAndPrint("\nCreate Watershed Results:")
            AddMsgAndPrint("\n===================================================")
            AddMsgAndPrint("\tUser Watershed: " + str(watershedOut))

            with arcpy.da.UpdateCursor(watershed,['Subbasin','Avg_Slope','Acres','SHAPE@AREA']) as cursor:
                for row in cursor:
                    subBasinNumber = row[0]
                    expression = (u'{} = ' + str(subBasinNumber)).format(arcpy.AddFieldDelimiters(slopeStats, "Subbasin"))
                    avgSlope = [row[0] for row in arcpy.da.SearchCursor(slopeStats,["MEAN"],where_clause=expression)][0]
                    row[1] = avgSlope
                    cursor.updateRow(row)

                    # Inform the user of Watershed Acres, area and avg. slope
                    AddMsgAndPrint("\n\tSubbasin: " + str(subBasinNumber))
                    AddMsgAndPrint("\t\tAcres: " + str(splitThousands(round(row[2],2))))
                    AddMsgAndPrint("\t\tArea: " + str(splitThousands(round(row[3],2))) + " Sq. " + linearUnits)
                    AddMsgAndPrint("\t\tAvg. Slope: " + str(round(avgSlope,2)))

            AddMsgAndPrint("\n===================================================")

        time.sleep(3)

        # ------------------------------------------------------------------------------------------------ Compact FGDB
        try:
            arcpy.compact_management(watershedGDB_path)
            AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path),1)
        except:
            pass

        # ------------------------------------------------------------------------------------------------ Prepare to Add to Arcmap
        # Set paths for derived layers
        arcpy.SetParameterAsText(4, outletFC)
        arcpy.SetParameterAsText(5, watershed)

        if bCalcLHL:
            arcpy.SetParameterAsText(6, Flow_Length)
            del Flow_Length

        AddMsgAndPrint("\nAdding Layers to ArcGIS Pro Session")
        AddMsgAndPrint("\n")

    except:
        print_exception()

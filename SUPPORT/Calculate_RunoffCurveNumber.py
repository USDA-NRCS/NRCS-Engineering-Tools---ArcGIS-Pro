# ==========================================================================================
# Name: Calculate_RunoffCurveNumber.py
#
# Author: Peter Mead
#         Becker Soil Water Conservation District
#         Red River Valley Conservation Service Area
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

# Created by Peter Mead, Adolfo Diaz, USDA NRCS, 2013
# Updated by Chris Morse, USDA NRCS, 2019

# ==========================================================================================
# Updated  5/11/2020 - Adolfo Diaz
#
# - The 'Perform checks on landuse and condition attributes' section should be rewritten
#   into 1 update cursor.
# - The 'Join LU Descriptions and assign codes for RCN Lookup' section should be rewritten
#   to lookup from a dictionary to avoid joins and creating temporary layers.  The lookup
#   dictionary would be created from the GDB itself so that future additions/removals
#   can easily be made.
# - Need to add functionality to get Soils data directly from SDA instead of locally.
#
# - Removed the 'Check for RCN Grid' section and updated the output layer of the
#   NLCD_RunoffCurveNumber tool to watershedGDB_path + os.sep + wsName + "_RCN_Grid"
#   It made no sense to name 2 layers the same when one is a grid.
# - Updated and Tested for ArcGIS Pro 2.4.2 and python 3.6
# - Added functionality to utilize a DEM image service or a DEM in GCS.  Added 2 new
#   function to handle this capability: extractSubsetFromGCSdem and getPCSresolutionFromGCSraster.
# - If GCS DEM is used then the coordinate system of the FGDB will become the same as the AOI
#   assuming the AOI is in a PCS.  If both AOI and DEM are in a GCS then the tool will exit.
# - All temporary raster layers such as Fill and Minus are stored in Memory and no longer
#   written to hard disk.
# - All describe functions use the arcpy.da.Describe functionality.
# - All field calculation expressions are in PYTHON3 format.
# - Used acre conversiont dictionary and z-factor lookup table
# - All cursors were updated to arcpy.da
# - Added code to remove layers from an .aprx rather than simply deleting them
# - Updated AddMsgAndPrint to remove ArcGIS 10 boolean and gp function
# - Updated print_exception function.  Traceback functions slightly changed for Python 3.6.
# - Added Snap Raster environment
# - Added parallel processing factor environment
# - swithced from exit() to exit()
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

    try:

        import getpass, time
        arcInfo = arcpy.GetInstallInfo()  # dict of ArcGIS Pro information

        f = open(textFilePath,'a+')
        f.write("\n################################################################################################################\n")
        f.write("Executing \"2.Calculate Runoff Curve Number\" Tool \n")
        f.write("User Name: " + getpass.getuser() + "\n")
        f.write("Date Executed: " + time.ctime() + "\n")
        f.write(arcInfo['ProductName'] + ": " + arcInfo['Version'] + "\n")
        f.write("User Parameters:\n")
        f.write("\tinWatershed: " + inWatershed + "\n")

        f.close
        del f

    except:
        print_exception()
        exit()

## ================================================================================================================
# Import system modules
import sys, os, string, traceback, arcpy

if __name__ == '__main__':

    try:

        # --------------------------------------------------------------------------------------------- Input Parameters
        inWatershed = arcpy.GetParameterAsText(0)

        # Uncomment line below to run from pythonWin
##        inWatershed = r'C:\flex\flex_EngTools.gdb\Layers\testing10_Watershed'

        # Set environmental variables
        arcpy.env.parallelProcessingFactor = "75%"
        arcpy.env.overwriteOutput = True

        # ---------------------------------------------------------------------------- Define Variables
        # inWatershed can ONLY be a feature class
        watershed_path = arcpy.Describe(inWatershed).CatalogPath

        if watershed_path.find('.gdb') > 0:
            watershedGDB_path = watershed_path[:watershed_path.find('.gdb')+4]

        else:
            AddMsgAndPrint("\n\nWatershed Layer must be a File Geodatabase Feature Class!.....Exiting",2)
            AddMsgAndPrint("You must run \"Prepare Soils and Landuse\" tool first before running this tool\n",2)
            exit()

        watershedFD_path = watershedGDB_path + os.sep + "Layers"
        watershedGDB_name = os.path.basename(watershedGDB_path)
        userWorkspace = os.path.dirname(watershedGDB_path)
        wsName = os.path.basename(inWatershed)

        inLanduse = watershedFD_path + os.sep + wsName + "_Landuse"
        inSoils = watershedFD_path + os.sep + wsName + "_Soils"

        # -------------------------------------------------------------------------- Permanent Datasets
        rcn = watershedFD_path + os.sep + wsName + "_RCN"

        # log File Path
        textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.txt"

        # record basic user inputs and settings to log file for future purposes
        logBasicSettings()

        # ---------------------------------------------------- Map Layers
        rcnOut = "" + str(wsName) + "_RCN"

        # -------------------------------------------------------------------------- Lookup Tables
        HYD_GRP_Lookup_Table = os.path.join(os.path.dirname(sys.argv[0]), "Support.gdb" + os.sep + "HYD_GRP_Lookup")
        TR_55_RCN_Lookup = os.path.join(os.path.dirname(sys.argv[0]), "Support.gdb" + os.sep + "TR_55_RCN_Lookup")

        # -------------------------------------------------------------------------- Check Soils / Landuse Inputs
        # Exit if input watershed is landuse or soils layer
        if inWatershed.find("_Landuse") > 0 or inWatershed.find("_Soils") > 0:
            AddMsgAndPrint("\nYou have mistakingly inputted your landuse or soils layer...Enter your watershed layer!",2)
            AddMsgAndPrint("Exiting",2)
            exit()

        # Exit if "Subbasin" field not found in watershed layer
        if not len(arcpy.ListFields(inWatershed,"Subbasin")) > 0:
            AddMsgAndPrint("\n\"Subbasin\" field was not found in " + os.path.basename(inWatershed) + "layer\n",2)
            AddMsgAndPrint("You must run \"Prepare Soils and Landuse\" tool first before running this tool\n",2)
            exit()

        # Exit if Soils fc not found in FD
        if not arcpy.Exists(inSoils):
            AddMsgAndPrint("\nSoils data not found in " + str(watershedFD_path) + "\n",2)
            AddMsgAndPrint("You must run \"Prepare Soils and Landuse\" tool first before running this tool\n",2)
            exit()

        # Exit if landuse fc not found in FD
        if not arcpy.Exists(inLanduse):
            AddMsgAndPrint("\nLanduse data not present in " + str(watershedFD_path) +".\n",2)
            AddMsgAndPrint("You must run Step 1. -Prepare Soils and Landuse - first, and attribute the resulting Watershed Soils and Landuse Layers..EXITING.\n",2)
            exit()

        # Exit if Hydro group lookup table is missing
        if not arcpy.Exists(HYD_GRP_Lookup_Table):
            AddMsgAndPrint("\n\"HYD_GRP_Lookup_Table\" was not found! Make sure \"Support.gdb\" is located within the same location as this script",2)
            exit()

        # Exit if TR 55 lookup table is missing
        if not arcpy.Exists(TR_55_RCN_Lookup):
            AddMsgAndPrint("\n\"TR_55_RCN_Lookup\" was not found! Make sure \"Support.gdb\" is located within the same location as this script",2)
            exit()

        # ------------------------------------------------------------------------------------------------ Check for Null Values in Landuse Field
        AddMsgAndPrint("\nChecking Values in landuse layer...")

        # Landuse Field MUST be populated.  It is acceptable to have Condition field unpopulated.
        query = "\"LANDUSE\" LIKE '%Select%' OR \"LANDUSE\" Is Null"
        nullFeatures = [row[0] for row in arcpy.da.SearchCursor(inLanduse,["LANDUSE"],where_clause=query)]

        if  len(nullFeatures) > 0:
            AddMsgAndPrint("\n\tThere are " + str(len(nullFeatures)) + " NULL or un-populated values in the LANDUSE or CONDITION Field of your landuse layer.",2)
            AddMsgAndPrint("\tMake sure all rows are attributed in an edit session, save your edits, stop editing and re-run this tool.",2)
            exit()

        # ------------------------------------------------------------------------------------------------ Check for Combined Classes in Soils Layer...
        AddMsgAndPrint("\nChecking Values in soils layer...")

        query = "\"HYDGROUP\" LIKE '%/%' OR \"HYDGROUP\" Is Null"
        combClasses = [row[0] for row in arcpy.da.SearchCursor(inSoils,["HYDGROUP"],where_clause=query)]

        if len(combClasses) > 0:
            AddMsgAndPrint("\n\tThere are " + str(len(combClasses)) + " Combined or un-populated classes in the HYDGROUP Field of your watershed soils layer.",2)
            AddMsgAndPrint("\tYou will need to make sure all rows are attributed with a single class in an edit session,",2)
            AddMsgAndPrint("\tsave your edits, stop editing and re-run this tool.\n",2)
            exit()

        # -------------------------------------------------------------------------- Delete Previous data Layers if present (only 1)
        if arcpy.Exists(rcn):
            AddMsgAndPrint("\nRemoving old datasets from FGDB: " + watershedGDB_name )
            AddMsgAndPrint("\tDeleting....." + os.path.basename(rcn))
            arcpy.Delete_management(rcn)

        # ------------------------------------------------------------------------------------------------ Intersect Soils, Landuse and Subbasins.
        if not len(arcpy.ListFields(inWatershed,"RCN")) > 0:
            arcpy.AddField_management(inWatershed, "RCN", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED")

        if not len(arcpy.ListFields(inWatershed,"Acres")) > 0:
            arcpy.AddField_management(inWatershed, "Acres", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")

        arcpy.CalculateField_management(inWatershed, "Acres", "!shape.area@ACRES!", "PYTHON3")

        wtshdLanduseSoilsIntersect = arcpy.CreateScratchName("wtshdLanduseSoilsIntersect",data_type="FeatureClass",workspace="in_memory")
        arcpy.Intersect_analysis([inWatershed,inLanduse,inSoils], wtshdLanduseSoilsIntersect, "NO_FID", "", "INPUT")

        arcpy.AddField_management(wtshdLanduseSoilsIntersect, "LUDESC", "TEXT", "255", "", "", "", "NULLABLE", "NON_REQUIRED")
        arcpy.AddField_management(wtshdLanduseSoilsIntersect, "LU_CODE", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")
        arcpy.AddField_management(wtshdLanduseSoilsIntersect, "HYDROL_ID", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")
        arcpy.AddField_management(wtshdLanduseSoilsIntersect, "HYD_CODE", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")
        arcpy.AddField_management(wtshdLanduseSoilsIntersect, "RCN_ACRES", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")
        arcpy.AddField_management(wtshdLanduseSoilsIntersect, "WGTRCN", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")
        arcpy.AddField_management(wtshdLanduseSoilsIntersect, "IDENT", "TEXT", "", "", "", "", "NULLABLE", "NON_REQUIRED")

        AddMsgAndPrint("\nSuccessfully intersected Hydrologic Groups, Landuse, and Subbasin Boundaries")

        # ------------------------------------------------------------------------------------------------ Perform Checks on Landuse and Condition Attributes
        # Make all edits to feature layer; delete intersect fc.
        wtshdLanduseSoilsIntersect_Layer = "wtshdLanduseSoilsIntersect_Layer"
        arcpy.MakeFeatureLayer_management(wtshdLanduseSoilsIntersect, wtshdLanduseSoilsIntersect_Layer)

        AddMsgAndPrint("\nChecking Landuse and Condition Values in intersected data")
        assumptions = 0

        #+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # Check #1: Set the condition to the following landuses to NULL
        query = "\"LANDUSE\" = 'Fallow Bare Soil' OR \"LANDUSE\" = 'Farmstead' OR \"LANDUSE\" LIKE 'Roads%' OR \"LANDUSE\" LIKE 'Paved%' OR \"LANDUSE\" LIKE '%Districts%' OR \"LANDUSE\" LIKE 'Newly Graded%' OR \"LANDUSE\" LIKE 'Surface Water%' OR \"LANDUSE\" LIKE 'Wetland%'"
        arcpy.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "NEW_SELECTION", query)
        count = int(arcpy.GetCount_management(wtshdLanduseSoilsIntersect_Layer).getOutput(0))

        if count > 0:
            arcpy.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "CONDITION", "\"\"", "PYTHON3",)

        arcpy.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "CLEAR_SELECTION")
        del query, count

        #+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # Check #2: Convert All 'N/A' Conditions to 'Good'
        arcpy.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "NEW_SELECTION", "\"CONDITION\" = 'N/A'")
        count = int(arcpy.GetCount_management(wtshdLanduseSoilsIntersect_Layer).getOutput(0))

        if count > 0:
            AddMsgAndPrint("\n\tThere were " + str(count) + " Landuse polygons with CONDITION 'N/A' that require a condition of Poor, Fair, or Good.",1)
            AddMsgAndPrint("\tCondition for these areas will be assumed to be 'Good'.")
            arcpy.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "CONDITION", '"Good"', "PYTHON3")
            assumptions = assumptions + 1

        arcpy.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "CLEAR_SELECTION")
        del count

        #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # Check #3: "Open Space Grass Cover 50 to 75 percent" should have a condition of "Fair"
        query = "\"LANDUSE\" = 'Open Space Grass Cover 50 to 75 percent' AND \"CONDITION\" <> 'Fair'"
        arcpy.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "NEW_SELECTION", query)
        count = int(arcpy.GetCount_management(wtshdLanduseSoilsIntersect_Layer).getOutput(0))

        if count > 0:
            AddMsgAndPrint("\n\tThere were " + str(count) + " 'Open Space Grass Cover 50 to 75 percent' polygons with a condition other than fair.",1)
            AddMsgAndPrint("\tA condition of fair will be assigned to these polygons.",1)
            arcpy.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "CONDITION", '"Fair"', "PYTHON3")
            assumptions = assumptions + 1

        arcpy.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "CLEAR_SELECTION")
        del query, count

        #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # Check #4: "Open Space Grass Cover greater than 75 percent" should have a condition of "Good"
        query = "\"LANDUSE\" = 'Open Space Grass Cover greater than 75 percent' AND \"CONDITION\" <> 'Good'"
        arcpy.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "NEW_SELECTION", query)
        count = int(arcpy.GetCount_management(wtshdLanduseSoilsIntersect_Layer).getOutput(0))

        if count > 0:
            AddMsgAndPrint("\n\tThere were " + str(count) + " 'Open Space Grass Cover greater than 75 percent' polygons with a condition other than Good. Greater than 75 percent cover assumes a condition of 'Good'..\n",1)
            AddMsgAndPrint("\tA condition of Good will be assigned to these polygons.\n",1)
            arcpy.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "CONDITION", '"Good"', "PYTHON3")
            assumptions = assumptions + 1

        arcpy.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "CLEAR_SELECTION")
        del query, count

        #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # Check #5: "Open Space, Grass Cover less than 50 percent" should have a condition of "Poor"
        query = "\"LANDUSE\" = 'Open Space, Grass Cover less than 50 percent' AND  \"CONDITION\" <> 'Poor'"
        arcpy.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "NEW_SELECTION", query)
        count = int(arcpy.GetCount_management(wtshdLanduseSoilsIntersect_Layer).getOutput(0))

        if count > 0:
            AddMsgAndPrint("\n\n\tThere were " + str(count) + " 'Open Space, Grass Cover less than 50 percent' polygons with a condition other than Poor. Less than 50 percent cover assumes a condition of 'Poor'..\n",1)
            AddMsgAndPrint("\tA condition of Poor will be assigned to these polygons.\n",1)
            arcpy.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "CONDITION", '"Poor"', "PYTHON3")
            assumptions = assumptions + 1

        arcpy.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "CLEAR_SELECTION")
        del query, count

        #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # Check #6: "Meadow or Continuous Grass Not Grazed Generally Hayed" should have a condition of "Good"
        query = "\"LANDUSE\" = 'Meadow or Continuous Grass Not Grazed Generally Hayed' AND  \"CONDITION\" <> 'Good'"
        arcpy.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "NEW_SELECTION", query)
        count = int(arcpy.GetCount_management(wtshdLanduseSoilsIntersect_Layer).getOutput(0))

        if count > 0:
            AddMsgAndPrint("\n\n\tThere were " + str(count) + " 'Meadow or Continuous Grass Not Grazed Generally Hayed' polygons with a condition other than Good.",1)
            AddMsgAndPrint("\tA condition of Good will be assigned to these polygons.\n",1)
            arcpy.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "CONDITION", '"Good"', "PYTHON3")
            assumptions = assumptions + 1

        arcpy.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "CLEAR_SELECTION")
        del query, count

        #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # Check #7: "Woods Grazed Not Burned Some forest Litter" should have a condition of "Fair"
        query = "\"LANDUSE\" = 'Woods Grazed Not Burned Some forest Litter' AND \"CONDITION\" <> 'Fair'"
        arcpy.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "NEW_SELECTION", query)
        count = int(arcpy.GetCount_management(wtshdLanduseSoilsIntersect_Layer).getOutput(0))

        if count > 0:
            AddMsgAndPrint("\n\n\tThere were " + str(count) + " 'Woods Grazed Not Burned Some forest Litter' polygons with a condition other than fair.",1)
            AddMsgAndPrint("\tA condition of fair will be assigned to these polygons.\n",1)
            arcpy.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "CONDITION", '"Fair"', "PYTHON3")
            assumptions = assumptions + 1

        arcpy.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "CLEAR_SELECTION")
        del query, count

        #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # Check #8: "Woods Not Grazed Adequate litter and brush" should have a condition of "Good"
        query = "\"LANDUSE\" = 'Woods Not Grazed Adequate litter and brush' AND  \"CONDITION\" <> 'Good'"
        arcpy.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "NEW_SELECTION", query)
        count = int(arcpy.GetCount_management(wtshdLanduseSoilsIntersect_Layer).getOutput(0))

        if count > 0:
            AddMsgAndPrint("\n\n\tThere were " + str(count) + " 'Woods Not Grazed Adequate litter and brush' polygons with a condition other than Good.",1)
            AddMsgAndPrint("\tA condition of Good will be assigned to these polygons.\n",1)
            arcpy.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "CONDITION", '"Good"', "PYTHON3")
            assumptions = assumptions + 1

        arcpy.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "CLEAR_SELECTION")
        del query, count

        #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # Check #9: "Woods Heavily Grazed or Burned" should have a condition of "Poor"
        query = "\"LANDUSE\" = 'Woods Heavily Grazed or Burned' AND  \"CONDITION\" <> 'Poor'"
        arcpy.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "NEW_SELECTION", query)
        count = int(arcpy.GetCount_management(wtshdLanduseSoilsIntersect_Layer).getOutput(0))

        if count > 0:
            AddMsgAndPrint("\n\tThere were " + str(count) + " 'Woods Heavily Grazed or Burned' polygons with a condition other than Poor.",1)
            AddMsgAndPrint("\tA condition of Poor will be assigned to these polygons.\n",1)
            arcpy.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "CONDITION", '"Poor"', "PYTHON3")
            assumptions = assumptions + 1

        arcpy.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "CLEAR_SELECTION")
        del query, count

        #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # Check #10: Fallow crops, Row crops, Small Grains or closed seed should have a condition of 'Good' or 'Poor' - default to Good
        query = "\"LANDUSE\" LIKE 'Fallow Crop%' AND \"CONDITION\" = 'Fair' OR \"LANDUSE\" LIKE 'Row Crops%' AND \"CONDITION\" = 'Fair' OR \"LANDUSE\" LIKE 'Small Grain%' AND \"CONDITION\" = 'Fair' OR \"LANDUSE\" LIKE 'Close Seeded%' AND \"CONDITION\" = 'Fair'"
        arcpy.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "NEW_SELECTION", query)
        count = int(arcpy.GetCount_management(wtshdLanduseSoilsIntersect_Layer).getOutput(0))

        if count > 0:
            AddMsgAndPrint("\n\tThere were " + str(count) + " Cropland related polygons with a 'Fair' condition listed. This Landuse assumes a condition of 'Good' or 'Poor'..\n",1)
            AddMsgAndPrint("\tA condition of Good will be assumed and assigned to these polygons.\n",1)
            arcpy.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "CONDITION", '"Good"', "PYTHON3")
            assumptions = assumptions + 1

        arcpy.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "CLEAR_SELECTION")
        del query, count

        if assumptions == 0:
            AddMsgAndPrint("\n\tAll populated correctly!",0)

        # ------------------------------------------------------------------------------------------------ Join LU Descriptions and assign codes for RCN Lookup
        # Select Landuse categories that arent assigned a condition (these dont need to be concatenated)
        query = "\"CONDITION\" = ''"
        arcpy.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "NEW_SELECTION", query)
        count = int(arcpy.GetCount_management(wtshdLanduseSoilsIntersect_Layer).getOutput(0))

        if count > 0:
            arcpy.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "LUDESC", "!LANDUSE!", "PYTHON3")

        # Concatenate Landuse and Condition fields together
        arcpy.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "SWITCH_SELECTION", "")
        arcpy.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "LUDESC", "!LANDUSE!" + "' '" +  "!CONDITION!", "PYTHON3")
        arcpy.SelectLayerByAttribute_management(wtshdLanduseSoilsIntersect_Layer, "CLEAR_SELECTION")
        del query, count

        # Join Layer and TR_55_RCN_Lookup table to get LUCODE
        # Had to create inJoinFld variable b/c createscratchanme appends a number at the end of the name
        arcpy.AddJoin_management(wtshdLanduseSoilsIntersect_Layer, "LUDESC", TR_55_RCN_Lookup, "LandUseDes", "KEEP_ALL")
        inJoinFld = ''.join((os.path.basename(wtshdLanduseSoilsIntersect),'.LU_CODE'))
        arcpy.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, inJoinFld, "!TR_55_RCN_Lookup.LU_CODE!", "PYTHON3")
        arcpy.RemoveJoin_management(wtshdLanduseSoilsIntersect_Layer, "TR_55_RCN_Lookup")
        AddMsgAndPrint("\nSuccesfully Joined to TR_55_RCN Lookup table to assign Land Use Codes")

        # Join Layer and HYD_GRP_Lookup table to get HYDCODE
        arcpy.AddJoin_management(wtshdLanduseSoilsIntersect_Layer, "HYDGROUP", HYD_GRP_Lookup_Table, "HYDGRP", "KEEP_ALL")
        inJoinFld = ''.join((os.path.basename(wtshdLanduseSoilsIntersect),'.HYDROL_ID'))
        arcpy.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, inJoinFld, "!HYD_GRP_Lookup.HYDCODE!", "PYTHON3")
        arcpy.RemoveJoin_management(wtshdLanduseSoilsIntersect_Layer, "HYD_GRP_Lookup")
        AddMsgAndPrint("\nSuccesfully Joined to HYD_GRP_Lookup table to assign Hydro Codes")

        # ------------------------------------------------------------------------------------------------ Join and Populate RCN Values
        # Concatenate LU Code and Hydrol ID to create HYD_CODE for RCN Lookup
        #exp = "int(str(int(!LU_CODE!)) + str(int(!HYDROL_ID!)))"
        exp = "''.join([str(int(!LU_CODE!)),str(int(!HYDROL_ID!))])"
        arcpy.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "HYD_CODE", exp,"PYTHON3")

        # Join Layer and TR_55_RCN_Lookup to get RCN value
        arcpy.AddJoin_management(wtshdLanduseSoilsIntersect_Layer, "HYD_CODE", TR_55_RCN_Lookup, "HYD_CODE", "KEEP_ALL")
        inJoinFld = ''.join((os.path.basename(wtshdLanduseSoilsIntersect),'.RCN'))
        arcpy.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, inJoinFld, "!TR_55_RCN_Lookup.RCN!", "PYTHON3")
        arcpy.RemoveJoin_management(wtshdLanduseSoilsIntersect_Layer, "TR_55_RCN_Lookup")
        AddMsgAndPrint("\nSuccesfully Joined to TR_55_RCN Lookup table to assign Curve Numbers for Unique Combinations")

        # ------------------------------------------------------------------------------------------------ Calculate Weighted RCN For Each Subbasin
        # Update acres for each new polygon
        arcpy.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "RCN_ACRES", "!shape.area@ACRES!", "PYTHON3")

        # Get weighted acres
        arcpy.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "WGTRCN", "(!RCN_ACRES! / !ACRES!) * !RCN!", "PYTHON3")

        rcn_stats = arcpy.CreateScratchName("rcn_stats",data_type="ArcInfoTable",workspace="in_memory")
        arcpy.Statistics_analysis(wtshdLanduseSoilsIntersect_Layer, rcn_stats, "WGTRCN SUM", "Subbasin")
        AddMsgAndPrint("\nSuccessfully Calculated Weighted Runoff Curve Number for each SubBasin")

        # ------------------------------------------------------------------------------------------------ Put the results in Watershed Attribute Table
        with arcpy.da.UpdateCursor(inWatershed,['Subbasin','RCN']) as cursor:
            for row in cursor:

                # Get the RCN Value from rcn_stats table by subbasin number
                subBasinNumber = row[0]

                # subbasin values should not be NULL
                if subBasinNumber is None or len(str(subBasinNumber)) < 1:
                    AddMsgAndPrint("\n\tSubbasin record is NULL in " + wsName,2)
                    continue

                expression = (u'{} = ' + str(subBasinNumber)).format(arcpy.AddFieldDelimiters(rcn_stats, "Subbasin"))
                rcnValue = [row[0] for row in arcpy.da.SearchCursor(rcn_stats,["SUM_WGTRCN"],where_clause=expression)][0]

                # Update the inWatershed subbasin RCN value
                row[1] = rcnValue
                cursor.updateRow(row)

                AddMsgAndPrint("\n\tSubbasin ID: " + str(subBasinNumber))
                AddMsgAndPrint("\t\tWeighted Average RCN Value: " + str(round(rcnValue,0)))

        # ------------------------------------------------------------------------------------------------ Create fresh new RCN Layer
        AddMsgAndPrint("\nAdding unique identifier to each subbasin's soil and landuse combinations")

        exp = "''.join([str(int(!HYD_CODE!)),str(int(!Subbasin!))])"
        arcpy.CalculateField_management(wtshdLanduseSoilsIntersect_Layer, "IDENT", exp, "PYTHON3")

        # Dissolve the intersected layer by Subbasin and Hyd_code to produce rcn layer
        statFields = [['IDENT','FIRST'],['LANDUSE','FIRST'],['CONDITION','FIRST'],['HYDGROUP','FIRST'],['RCN','FIRST'],['Acres','FIRST']]
        arcpy.Dissolve_management(wtshdLanduseSoilsIntersect_Layer, rcn, ["Subbasin","HYD_CODE"], statFields, "MULTI_PART", "DISSOLVE_LINES")

        # Remove 'FIRST' from the field name and update alias as well
        for fld in [f.name for f in arcpy.ListFields(rcn)]:
            if fld.startswith('FIRST'):
                arcpy.AlterField_management(rcn,fld,fld[6:],fld[6:])

        # Update Acres
        arcpy.CalculateField_management(rcn, "Acres", "!shape.area@ACRES!", "PYTHON3")

        # Remove Unnecessary fields
        arcpy.DeleteField_management(rcn,['IDENT','HYD_CODE'])

        arcpy.Delete_management(rcn_stats)
        arcpy.Delete_management(wtshdLanduseSoilsIntersect)
        arcpy.Delete_management(wtshdLanduseSoilsIntersect_Layer)

        AddMsgAndPrint("\nSuccessfully created RCN Layer: " + str(os.path.basename(rcn)))

        # ---------------------------------------------------------------------------------------------------------------------------- Compact FGDB
        arcpy.Compact_management(watershedGDB_path)
        AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path))

        # --------------------------------------------------------------------------------------------------------------------------- Prepare to Add to Arcmap
        arcpy.SetParameterAsText(1, rcn)
        AddMsgAndPrint("\nAdding Layers to ArcGIS Pro")

    except:
        print_exception()

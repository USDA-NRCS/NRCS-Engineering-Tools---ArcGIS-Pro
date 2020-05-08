# ==========================================================================================
# Name: PrepareSoils_Landuse.py
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

# Created by Peter Mead, Adolfo Diaz, USDA NRCS, 2013
# Updated by Chris Morse, USDA NRCS, 2019

# ==========================================================================================
# Updated  5/4/2020 - Adolfo Diaz
#
# - Removed entire section of 'Remove domains from fields if they exist'  This section
#   makes no sense b/c landuse and wssoils do NOT exist yet so there is nothing to remove
#   from.
# - No longer check to see if soils, clu or watershed are polygons.  The tool properties
#   will check for this.
# - No longer check for presence of hydrologic field since it is a dependency of the soils
#   layer.
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

    try:

        import getpass, time
        arcInfo = arcpy.GetInstallInfo()  # dict of ArcGIS Pro information

        f = open(textFilePath,'a+')
        f.write("\n################################################################################################################\n")
        f.write("Executing \"1.Prepare Soils and Landuse\" Tool for ArcGIS 9.3 and 10\n")
        f.write("User Name: " + getpass.getuser() + "\n")
        f.write("Date Executed: " + time.ctime() + "\n")
        f.write(arcInfo['ProductName'] + ": " + arcInfo['Version'] + "\n")
        f.write("User Parameters:\n")
        f.write("\tWorkspace: " + userWorkspace + "\n")
        f.write("\tInput Soils Data: " + inSoils + "\n")
        f.write("\tInput Hydro Groups Field: " + hydroField + "\n")

        if bSplitLU:
            f.write("\tInput CLU Layer: " + inCLU + " \n")
        else:
            f.write("\tInput CLU Layer: N/A " + " \n")

        f.close
        del f

    except:
        print_exception()
        exit()

## ================================================================================================================
# Import system modules
import arcpy, sys, os, string, traceback
from arcpy.sa import *

if __name__ == '__main__':

    try:
        # Script Parameters
        inWatershed = arcpy.GetParameterAsText(0)
        inSoils = arcpy.GetParameterAsText(1)
        hydroField = arcpy.GetParameterAsText(2)
        inCLU = arcpy.GetParameterAsText(3)

        # Uncomment the following 6 lines to run from pythonWin
##        inWatershed = r'E:\NRCS_Engineering_Tools_ArcPro\Testing\Testing_EngTools.gdb\Layers\ProWatershed'
##        inSoils = r'E:\NRCS_Engineering_Tools_ArcPro\Testing\Testing_EngTools.gdb\Layers\WI025_soils'
##        hydroField = r'HYDROLGRP_DCD'
##        inCLU = ''

        # Set environmental variables
        arcpy.env.parallelProcessingFactor = "75%"
        arcpy.env.overwriteOutput = True

        # --------------------------------------------------------------------------- Define Variables
        wshdDesc = arcpy.da.Describe(inWatershed)
        inWatershedPath = wshdDesc['catalogPath']
        wshdSR = wshdDesc['spatialReference']

        inSoils = arcpy.da.Describe(inSoils)['catalogPath']

        if inWatershedPath.find('.gdb') > -1 or inWatershedPath.find('.mdb') > -1:

            # inWatershedPath was created using 'Create Watershed Tool'
            if inWatershedPath.find('_EngTools'):
                watershedGDB_path = inWatershedPath[:inWatershedPath.find('.') + 4]

            # inWatershedPath is a fc from a DB not created using 'Create Watershed Tool'
            else:
                watershedGDB_path = os.path.dirname(inWatershedPath[:inWatershedPath.find('.')+4]) + os.sep + os.path.basename(inWatershedPath).replace(" ","_") + "_EngTools.gdb"

        # inWatershedPath is a shapefile
        elif inWatershedPath.find('.shp')> -1:
            watershedGDB_path = os.path.dirname(inWatershedPath[:inWatershedPath.find('.')+4]) + os.sep + os.path.basename(inWatershedPath).replace(".shp","").replace(" ","_") + "_EngTools.gdb"

        else:
            AddMsgAndPrint("\n\nWatershed Polygon must either be a feature class or shapefile!.....Exiting",2)
            exit()

        watershedFD = watershedGDB_path + os.sep + "Layers"
        watershedGDB_name = os.path.basename(watershedGDB_path)
        userWorkspace = os.path.dirname(watershedGDB_path)
        wsName = os.path.splitext(os.path.basename(inWatershedPath))[0]

        # log File Path
        textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.txt"

        # Determine if CLU is present
        if len(str(inCLU)) > 0:
            inCLU = arcpy.da.Describe(inCLU)['catalogPath']
            bSplitLU = True

        else:
            bSplitLU = False

        # record basic user inputs and settings to log file for future purposes
        logBasicSettings()

        # ----------------------------------------------------------------------------- Datasets
        # --------------------------------------------------- Permanent Datasets
        wsSoils = watershedFD + os.sep + wsName + "_Soils"
        landuse = watershedFD + os.sep + wsName + "_Landuse"
        watershed = watershedFD + os.sep + wsName

        # ----------------------------------------------------------- Lookup Tables
        TR_55_LU_Lookup = os.path.join(os.path.dirname(sys.argv[0]), "Support.gdb" + os.sep + "TR_55_LU_Lookup")
        Hydro_Groups_Lookup = os.path.join(os.path.dirname(sys.argv[0]), "Support.gdb" + os.sep + "HydroGroups")
        Condition_Lookup = os.path.join(os.path.dirname(sys.argv[0]), "Support.gdb" + os.sep + "ConditionTable")

        # ----------------------------------------------------------------------------- Check Some Parameters
        # Exit if watershed is empty....why would it be??
        if not int(arcpy.GetCount_management(inWatershedPath).getOutput(0)) > 0:
            AddMsgAndPrint("\n\nWatershed Layer is empty.....Exiting!",2)
            exit()

        # Exit if TR55 table not found in directory.
        if not arcpy.Exists(TR_55_LU_Lookup):
            AddMsgAndPrint("\n\n\"TR_55_LU_Lookup\" was not found! Make sure \"Support.gdb\" is located within the same location as this script",2)
            exit()

        # Exit if Hydro Groups Lookup table not found in directory
        if not arcpy.Exists(Hydro_Groups_Lookup):
            AddMsgAndPrint("\n\n\"Hydro_Groups_Lookup\" was not found! Make sure \"Support.gdb\" is located within the same location as this script",2)
            exit()

        # Exit if Condition lookup table not found in directory
        if not arcpy.Exists(Condition_Lookup):
            AddMsgAndPrint("\n\n\"Condition_Lookup\" was not found! Make sure \"Support.gdb\" is located within the same location as this script",2)
            exit()

        # --------------------------------------------------------------------------- Create FGDB, FeatureDataset
        # Boolean - Assume FGDB already exists
        FGDBexists = True

        # Create Watershed FGDB and feature dataset if it doesn't exist
        if not arcpy.Exists(watershedGDB_path):
            arcpy.CreateFileGDB_management(userWorkspace, watershedGDB_name)
            arcpy.CreateFeatureDataset_management(watershedGDB_path, "Layers", wshdSR)
            AddMsgAndPrint("\nSuccessfully created File Geodatabase: " + watershedGDB_name)
            FGDBexists = False

        # if GDB already existed but feature dataset doesn't
        if not arcpy.Exists(watershedFD):
            arcpy.CreateFeatureDataset_management(watershedGDB_path, "Layers", wshdSR)

        # ---------------------------------------------------------------------------------------------- Delete any project layers from ArcMap
        datasetsToRemove = (wsSoils,landuse)       # Full path of layers
        datasetsBaseName = [os.path.basename(x) for x in datasetsToRemove]  # layer names as they would appear in .aprx

        # Remove layers from ArcGIS Pro Session if executed from an .aprx
        try:
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            for maps in aprx.listMaps():
                for lyr in maps.listLayers():
                    if lyr.name in datasetsBaseName:
                        maps.removeLayer(lyr)
        except:
            pass

        x = 0
        for layer in datasetsToRemove:

            if arcpy.Exists(layer):
                if x == 0:
                    AddMsgAndPrint("\nRemoving old datasets from FGDB: " + watershedGDB_name )
                    x+=1

                try:
                    AddMsgAndPrint("\tDeleting....." + os.path.basename(layer))
                    #arcpy.Delete_management(layer)
                except:
                    pass

        # ----------------------------------------------------------------------------------------------- Create Watershed
        # if paths are not the same then assume AOI was manually digitized
        # or input is some from some other feature class/shapefile

        # True if watershed was not created from this Eng tools
        bExternalWatershed = False

        if not inWatershedPath == watershed:

            # delete the AOI feature class; new one will be created
            if arcpy.Exists(watershed):

                arcpy.Delete_management(watershed)
                arcpy.CopyFeatures_management(inWatershedPath, watershed)
                AddMsgAndPrint("\nSuccessfully Overwrote existing Watershed")

            else:
                arcpy.CopyFeatures_management(inWatershedPath, watershed)
                AddMsgAndPrint("\nSuccessfully Created Watershed " + os.path.basename(watershed))

            bExternalWatershed = True

        # paths are the same therefore input IS projectAOI
        else:
            AddMsgAndPrint("\nUsing existing " + os.path.basename(watershed) + " feature class")

        if bExternalWatershed:
            watershedDesc = arcpy.da.Describe(watershed)

            # Delete all fields in watershed layer except for obvious ones
            for field in [f.name for f in arcpy.ListFields(watershed)]:

                # Delete all fields that are not the following
                if not field in (watershedDesc['shapeFieldName'],watershedDesc['OIDFieldName'],"Subbasin"):
                    arcpy.DeleteField_management(watershed,field)

            if not len(arcpy.ListFields(watershed,"Subbasin")) > 0:
                arcpy.AddField_management(watershed, "Subbasin", "SHORT", "", "", "", "", "NULLABLE", "NON_REQUIRED")
                arcpy.CalculateField_management(watershed, "Subbasin",watershedDesc['OIDFieldName'],"PYTHON3")

            if not len(arcpy.ListFields(watershed,"Acres")) > 0:
                arcpy.AddField_management(watershed, "Acres", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED")
                arcpy.CalculateField_management(watershed, "Acres", "!shape.area@ACRES!", "PYTHON3")

        # ------------------------------------------------------------------------------------------------ Create Landuse Layer
        if bSplitLU:

            # Dissolve in case the watershed has multiple polygons
            watershedDissolve = "in_memory" + os.sep + os.path.basename(arcpy.CreateScratchName("watershedDissolve",data_type="FeatureClass",workspace=watershedGDB_path))
            arcpy.Dissolve_management(inWatershedPath, watershedDissolve, "", "", "MULTI_PART", "DISSOLVE_LINES")

            # Clip the CLU layer to the dissolved watershed layer
            cluClip = "in_memory" + os.sep + os.path.basename(arcpy.CreateScratchName("cluClip",data_type="FeatureClass",workspace=watershedGDB_path))
            arcpy.Clip_analysis(inCLU, watershedDissolve, cluClip)
            AddMsgAndPrint("\nSuccessfully clipped the CLU to your Watershed Layer")

            # Union the CLU and dissolve watershed layer simply to fill in gaps
            arcpy.Union_analysis(cluClip +";" + watershedDissolve, landuse, "ONLY_FID", "", "GAPS")
            AddMsgAndPrint("\nSuccessfully filled in any CLU gaps and created Landuse Layer: " + os.path.basename(landuse))

            # Delete FID field
            fields = [f.name for f in arcpy.ListFields(landuse,"FID*")]

            if len(fields):
                for field in fields:
                    arcpy.DeleteField_management(landuse,field)

            arcpy.Delete_management(watershedDissolve)
            arcpy.Delete_management(cluClip)

        else:
            AddMsgAndPrint("\nNo CLU Layer Detected",1)

            arcpy.Dissolve_management(inWatershedPath, landuse, "", "", "MULTI_PART", "DISSOLVE_LINES")
            AddMsgAndPrint("\nSuccessfully created Watershed Landuse layer: " + os.path.basename(landuse),1)

        arcpy.AddField_management(landuse, "LANDUSE", "TEXT", "", "", "254", "", "NULLABLE", "NON_REQUIRED", "")
        arcpy.CalculateField_management(landuse, "LANDUSE", "\"- Select Land Use -\"", "PYTHON3")

        arcpy.AddField_management(landuse, "CONDITION", "TEXT", "", "", "25", "", "NULLABLE", "NON_REQUIRED", "")
        arcpy.CalculateField_management(landuse, "CONDITION", "\"- Select Condition -\"", "PYTHON3")

        # ---------------------------------------------------------------------------------------------- Set up Domains
        watershedGDBdesc = arcpy.da.Describe(watershedGDB_path)
        domains = watershedGDBdesc['domains']

        if not "LandUse_Domain" in domains:
            arcpy.TableToDomain_management(TR_55_LU_Lookup, "LandUseDesc", "LandUseDesc", watershedGDB_path, "LandUse_Domain", "LandUse_Domain", "REPLACE")

        if not "Hydro_Domain" in domains:
            arcpy.TableToDomain_management(Hydro_Groups_Lookup, "HydrolGRP", "HydrolGRP", watershedGDB_path, "Hydro_Domain", "Hydro_Domain", "REPLACE")

        if not "Condition_Domain" in domains:
            arcpy.TableToDomain_management(Condition_Lookup, "CONDITION", "CONDITION", watershedGDB_path, "Condition_Domain", "Condition_Domain", "REPLACE")

        # Assign Domain To Landuse Fields for User Edits...
        arcpy.AssignDomainToField_management(landuse, "LANDUSE", "LandUse_Domain", "")
        arcpy.AssignDomainToField_management(landuse, "CONDITION", "Condition_Domain", "")

        AddMsgAndPrint("\nSuccessufully added \"LANDUSE\" and \"CONDITION\" fields to Landuse Layer and associated Domains")

        # ---------------------------------------------------------------------------------------------------------------------------------- Work with soils

        # --------------------------------------------------------------------------------------- Clip Soils
        # Clip the soils to the dissolved (and possibly unioned) watershed
        arcpy.Clip_analysis(inSoils,landuse,wsSoils)

        AddMsgAndPrint("\nSuccessfully clipped soils layer to Landuse layer and removed unnecessary fields")

        # --------------------------------------------------------------------------------------- Check Hydrologic Values
        AddMsgAndPrint("\nChecking Hydrologic Group Attributes in Soil Layer.....")

        validHydroValues = ['A','B','C','D','A/D','B/D','C/D','W']
        valuesToConvert = ['A/D','B/D','C/D','W']

        # List of input soil Hydrologic group values
        soilHydValues = list(set([row[0] for row in arcpy.da.SearchCursor(wsSoils,hydroField)]))

        # List of NULL hydrologic values in input soils
        expression = arcpy.AddFieldDelimiters(wsSoils, hydroField) + " IS NULL OR " + arcpy.AddFieldDelimiters(wsSoils, hydroField) + " = \'\'"
        nullSoilHydValues = [row[0] for row in arcpy.da.SearchCursor(wsSoils,hydroField,where_clause=expression)]

        # List of invalid hydrologic values relative to validHydroValues list
        invalidHydValues = [val for val in soilHydValues if not val in validHydroValues]
        hydValuesToConvert = [val for val in soilHydValues if val in valuesToConvert]

        if len(invalidHydValues):
            AddMsgAndPrint("\t\tThe following Hydrologic Values are not valid: " + str(invalidHydValues),1)

        if len(hydValuesToConvert):
            AddMsgAndPrint("\t\tThe following Hydrologic Values need to be converted: " + str(hydValuesToConvert) + " to a single class i.e. \"B/D\" to \"B\"",1)

        if nullSoilHydValues:
            AddMsgAndPrint("\tThere are " + str(len(nullSoilHydValues)) + " NULL polygon(s) that need to be attributed with a Hydrologic Group Value",1)

        # ------------------------------------------------------------------------------------------- Compare Input Field to SSURGO HydroGroup field name
        if hydroField.upper() != "HYDGROUP":
            arcpy.AddField_management(wsSoils, "HYDGROUP", "TEXT", "", "", "20", "", "NULLABLE", "NON_REQUIRED")
            arcpy.CalculateField_management(wsSoils, "HYDGROUP", "!" + str(hydroField) + "!", "PYTHON3")
            AddMsgAndPrint("\n\tAdded " + "\"HYDGROUP\" to soils layer.  Please Populate the Hydrologic Group Values manually for this field")

        # Delete any soil field not in the following list
        fieldsToKeep = ["MUNAME","MUKEY","HYDGROUP","MUSYM","OBJECTID"]

        for field in [f.name for f in arcpy.ListFields(wsSoils)]:
            if not field.upper() in fieldsToKeep and field.find("Shape") < 0:
                arcpy.DeleteField_management(wsSoils,field)

        arcpy.AssignDomainToField_management(wsSoils, "HYDGROUP", "Hydro_Domain", "")

        # ---------------------------------------------------------------------------------------------------------------------------- Compact FGDB
        arcpy.Compact_management(watershedGDB_path)
        AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path))

        # --------------------------------------------------------------------------------------------------------------------------- Prepare to Add to Arcmap
        arcpy.SetParameterAsText(4, landuse)
        arcpy.SetParameterAsText(5, wsSoils)

        if bExternalWatershed:
            arcpy.SetParameterAsText(6, watershed)

        AddMsgAndPrint("\nAdding Layers to ArcGIS Pro")
        AddMsgAndPrint("\n\t=========================================================================")
        AddMsgAndPrint("\tBEFORE CALCULATING THE RUNOFF CURVE NUMBER FOR YOUR WATERSHED MAKE SURE TO",1)
        AddMsgAndPrint("\tATTRIBUTE THE \"LANDUSE\" AND \"CONDITION\" FIELDS IN " + os.path.basename(landuse) + " LAYER",1)

        if len(hydValuesToConvert) > 0:
            AddMsgAndPrint("\tAND CONVERT THE " + str(len(hydValuesToConvert)) + " COMBINED HYDROLOGIC GROUPS IN " + os.path.basename(wsSoils) + " LAYER",1)

        if len(nullSoilHydValues) > 0:
            AddMsgAndPrint("\tAS WELL AS POPULATE VALUES FOR THE " + str(len(nullSoilHydValues)) + " NULL POLYGONS IN " + os.path.basename(wsSoils) + " LAYER",1)

        AddMsgAndPrint("\t=========================================================================\n")

    except:
        print_exception()


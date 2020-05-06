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
        f.write("\tInput Hydro Groups Field: " + inputField + "\n")

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
import sys, os, string, traceback
from arcpy.sa import *

if __name__ == '__main__':

    try:

        # Script Parameters
        inWatershed = arcpy.getparameterAstext(0)
        inSoils = arcpy.GetParameterAsText(1)
        inputField = arcpy.GetParameterAsText(2)
        inCLU = arcpy.GetParameterAsText(3)

        # Uncomment the following 6 lines to run from pythonWin
    ##    inWatershed = r'C:\flex\flex_EngTools.gdb\Layers\testing10_Watershed'
    ##    inSoils = r'C:\flex\soilmu_a_wi025.shp'
    ##    inputField = r'HydGroup'
    ##    inCLU = r'G:\MLRAData\common_land_unit\clu_a_wi_201110.shp'

        # --------------------------------------------------------------------------- Define Variables
        inWatershed = arcpy.da.Describe(inWatershed)['catalogPath']
        inSoils = arcpy.da.Describe(inSoils)['catalogPath']

        if inWatershed.find('.gdb') > -1 or inWatershed.find('.mdb') > -1:

            # inWatershed was created using 'Create Watershed Tool'
            if inWatershed.find('_EngTools'):
                watershedGDB_path = inWatershed[:inWatershed.find('.') + 4]

            # inWatershed is a fc from a DB not created using 'Create Watershed Tool'
            else:
                watershedGDB_path = os.path.dirname(inWatershed[:inWatershed.find('.')+4]) + os.sep + os.path.basename(inWatershed).replace(" ","_") + "_EngTools.gdb"

        # inWatershed is a shapefile
        elif inWatershed.find('.shp')> -1:
            watershedGDB_path = os.path.dirname(inWatershed[:inWatershed.find('.')+4]) + os.sep + os.path.basename(inWatershed).replace(".shp","").replace(" ","_") + "_EngTools.gdb"

        else:
            AddMsgAndPrint("\n\nWatershed Polygon must either be a feature class or shapefile!.....Exiting",2)
            exit()

        watershedFD = watershedGDB_path + os.sep + "Layers"
        watershedGDB_name = os.path.basename(watershedGDB_path)
        userWorkspace = os.path.dirname(watershedGDB_path)
        wsName = os.path.splitext(os.path.basename(inWatershed))[0]

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

        # ---------------------------------------------------- Temporary Datasets
        cluClip = watershedFD + os.sep + "cluClip"
        watershedDissolve = watershedFD + os.sep + "watershedDissolve"
        luUnion = watershedFD + os.sep + "luUnion"

        # ----------------------------------------------------------- Lookup Tables
        TR_55_LU_Lookup = os.path.join(os.path.dirname(sys.argv[0]), "Support.gdb" + os.sep + "TR_55_LU_Lookup")
        Hydro_Groups_Lookup = os.path.join(os.path.dirname(sys.argv[0]), "Support.gdb" + os.sep + "HydroGroups")
        Condition_Lookup = os.path.join(os.path.dirname(sys.argv[0]), "Support.gdb" + os.sep + "ConditionTable")

        # ----------------------------------------------------------------------------- Check Some Parameters
        # Exit if any are true
        if not int(arcpy.GetCount_management(inWatershed).getOutput(0)) > 0:
            AddMsgAndPrint("\n\nWatershed Layer is empty.....Exiting!",2)
            exit()

        # Exit if wathershed layer not a polygon
        if arcpy.Describe(inWatershed).ShapeType != "Polygon":
            AddMsgAndPrint("\n\nYour Watershed Layer must be a polygon layer!.....Exiting!",2)
            exit()

        # Exit if soils layer not a polygon
        if arcpy.Describe(inSoils).ShapeType != "Polygon":
            AddMsgAndPrint("\n\nYour Soils Layer must be a polygon layer!.....Exiting!",2)
            exit()

        # Exit if CLU layer not a polygon
        if bSplitLU:
            if arcpy.Describe(inCLU).ShapeType != "Polygon":
                AddMsgAndPrint("\n\nYour CLU Layer must be a polygon layer!.....Exiting!",2)
                exit()

        # Exit if Hydro Group field not present
        if not len(arcpy.ListFields(inSoils,inputField)) > 0:
            AddMsgAndPrint("\nThe field specified for Hydro Groups does not exist in your soils data.. please specify another name and try again..EXITING",2)
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
            desc = arcpy.Describe(inWatershed)
            sr = desc.SpatialReference

            arcpy.CreateFileGDB_management(userWorkspace, watershedGDB_name)
            arcpy.CreateFeatureDataset_management(watershedGDB_path, "Layers", sr)
            AddMsgAndPrint("\nSuccessfully created File Geodatabase: " + watershedGDB_name,1)
            FGDBexists = False
            del desc, sr

        # if GDB already existed but feature dataset doesn't
        if not arcpy.Exists(watershedFD):
            desc = arcpy.Describe(inWatershed)
            sr = desc.SpatialReference
            arcpy.CreateFeatureDataset_management(watershedGDB_path, "Layers", sr)
            del desc, sr
        # --------------------------------------------------------------------------- Remove domains from fields if they exist
        desc = arcpy.describe(watershedGDB_path)
        listOfDomains = []

        domains = desc.Domains

        for domain in domains:
            listOfDomains.append(domain)

        del desc, domains

        if "LandUse_Domain" in listOfDomains:
            try:
                arcpy.RemoveDomainFromField(landuse, "LANDUSE")
            except:
                pass
        if "Condition_Domain" in listOfDomains:
            try:
                arcpy.RemoveDomainFromField(landuse, "CONDITION")
            except:
                pass

        if "Hydro_Domain" in listOfDomains:
            try:
                arcpy.RemoveDomainFromField(wsSoils, "HYDGROUP")
            except:
                pass

        del listOfDomains

        # ---------------------------------------------------------------------------------------------- Delete any project layers from ArcMap
        # ------------------------------- Map Layers
        landuseOut = "" + wsName + "_Landuse"
        soilsOut = "" + wsName + "_Soils"

        # ------------------------------------- Delete previous layers from ArcMap if they exist
        layersToRemove = (landuseOut,soilsOut)

        x = 0
        for layer in layersToRemove:

            if arcpy.Exists(layer):
                if x == 0:
                    AddMsgAndPrint("\nRemoving previous layers from your ArcMap session " + watershedGDB_name ,1)
                    x+=1

                try:
                    arcpy.delete_management(layer)
                    AddMsgAndPrint("\tRemoving " + layer + "",0)
                except:
                    pass

        del x
        del layer
        del layersToRemove
        # -------------------------------------------------------------------------- Delete Previous Data if present

        if FGDBexists:

            layersToRemove = (wsSoils,landuse,cluClip,watershedDissolve,luUnion)

            x = 0
            for layer in layersToRemove:

                if arcpy.Exists(layer):

                    # strictly for formatting
                    if x == 0:
                        AddMsgAndPrint("\nRemoving old files from FGDB: " + watershedGDB_name ,1)
                        x += 1

                    try:
                        arcpy.delete_management(layer)
                        AddMsgAndPrint("\tDeleting....." + os.path.basename(layer),0)
                    except:
                        pass

            del x, layersToRemove

        arcpy.RefreshCatalog(watershedGDB_path)

        # ----------------------------------------------------------------------------------------------- Create Watershed
        # if paths are not the same then assume AOI was manually digitized
        # or input is some from some other feature class/shapefile

        # True if watershed was not created from this Eng tools
        externalWshd = False

        if not arcpy.Describe(inWatershed).CatalogPath == watershed:

            # delete the AOI feature class; new one will be created
            if arcpy.Exists(watershed):

                try:
                    arcpy.delete_management(watershed)
                    arcpy.CopyFeatures_management(inWatershed, watershed)
                    AddMsgAndPrint("\nSuccessfully Overwrote existing Watershed",1)
                except:
                    print_exception()
                    arcpy.OverWriteOutput = 1

            else:
                arcpy.CopyFeatures_management(inWatershed, watershed)
                AddMsgAndPrint("\nSuccessfully Created Watershed " + os.path.basename(watershed) ,1)

            externalWshd = True

        # paths are the same therefore input IS projectAOI
        else:
            AddMsgAndPrint("\nUsing existing " + os.path.basename(watershed) + " feature class",1)

        if externalWshd:

            # Delete all fields in watershed layer except for obvious ones
            fields = arcpy.ListFields(watershed)

            for field in fields:

                fieldName = field.Name

                if fieldName.find("Shape") < 0 and fieldName.find("OBJECTID") < 0 and fieldName.find("Subbasin") < 0:
                    arcpy.deletefield_management(watershed,fieldName)

                del fieldName

            del fields

            if not len(arcpy.ListFields(watershed,"Subbasin")) > 0:
                arcpy.AddField_management(watershed, "Subbasin", "SHORT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
                arcpy.CalculateField_management(watershed, "Subbasin","[OBJECTID]","VB", "")

            if not len(arcpy.ListFields(watershed,"Acres")) > 0:
                arcpy.AddField_management(watershed, "Acres", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
                arcpy.CalculateField_management(watershed, "Acres", "!shape.area@ACRES!", "PYTHON", "")

        # ------------------------------------------------------------------------------------------------ Create Landuse Layer
        if bSplitLU:

            # Dissolve in case the watershed has multiple polygons
            arcpy.Dissolve_management(inWatershed, watershedDissolve, "", "", "MULTI_PART", "DISSOLVE_LINES")

            # Clip the CLU layer to the dissolved watershed layer
            arcpy.Clip_analysis(inCLU, watershedDissolve, cluClip, "")
            AddMsgAndPrint("\nSuccessfully clipped the CLU to your Watershed Layer",1)

            # Union the CLU and dissolve watershed layer simply to fill in gaps
            arcpy.Union_analysis(cluClip +";" + watershedDissolve, landuse, "ONLY_FID", "", "GAPS")
            AddMsgAndPrint("\nSuccessfully filled in any CLU gaps and created Landuse Layer: " + os.path.basename(landuse),1)

            # Delete FID field
            fields = arcpy.ListFields(landuse,"FID*")

            for field in fields:
                arcpy.deletefield_management(landuse,field.Name)

            del fields

            arcpy.Delete_management(watershedDissolve)
            arcpy.Delete_management(cluClip)

        else:
            AddMsgAndPrint("\nNo CLU Layer Detected",1)

            arcpy.Dissolve_management(inWatershed, landuse, "", "", "MULTI_PART", "DISSOLVE_LINES")
            AddMsgAndPrint("\nSuccessfully created Watershed Landuse layer: " + os.path.basename(landuse),1)

        arcpy.AddField_management(landuse, "LANDUSE", "TEXT", "", "", "254", "", "NULLABLE", "NON_REQUIRED", "")
        arcpy.CalculateField_management(landuse, "LANDUSE", "\"- Select Land Use -\"", "VB", "")

        arcpy.AddField_management(landuse, "CONDITION", "TEXT", "", "", "25", "", "NULLABLE", "NON_REQUIRED", "")
        arcpy.CalculateField_management(landuse, "CONDITION", "\"- Select Condition -\"", "VB", "")

        # ---------------------------------------------------------------------------------------------- Set up Domains
        desc = arcpy.describe(watershedGDB_path)
        listOfDomains = []

        domains = desc.Domains

        for domain in domains:
            listOfDomains.append(domain)

        del desc, domains

        if not "LandUse_Domain" in listOfDomains:
            arcpy.TableToDomain_management(TR_55_LU_Lookup, "LandUseDesc", "LandUseDesc", watershedGDB_path, "LandUse_Domain", "LandUse_Domain", "REPLACE")

        if not "Hydro_Domain" in listOfDomains:
            arcpy.TableToDomain_management(Hydro_Groups_Lookup, "HydrolGRP", "HydrolGRP", watershedGDB_path, "Hydro_Domain", "Hydro_Domain", "REPLACE")

        if not "Condition_Domain" in listOfDomains:
            arcpy.TableToDomain_management(Condition_Lookup, "CONDITION", "CONDITION", watershedGDB_path, "Condition_Domain", "Condition_Domain", "REPLACE")

        del listOfDomains

        # Assign Domain To Landuse Fields for User Edits...
        arcpy.AssignDomainToField_management(landuse, "LANDUSE", "LandUse_Domain", "")
        arcpy.AssignDomainToField_management(landuse, "CONDITION", "Condition_Domain", "")

        AddMsgAndPrint("\nSuccessufully added \"LANDUSE\" and \"CONDITION\" fields to Landuse Layer and associated Domains",1)

        # ---------------------------------------------------------------------------------------------------------------------------------- Work with soils

        # --------------------------------------------------------------------------------------- Clip Soils
        # Clip the soils to the dissolved (and possibly unioned) watershed
        arcpy.Clip_analysis(inSoils,landuse,wsSoils)

        AddMsgAndPrint("\nSuccessfully clipped soils layer to Landuse layer and removed unnecessary fields",1)

        # --------------------------------------------------------------------------------------- check the soils input Field to make
        # --------------------------------------------------------------------------------------- sure they are valid Hydrologic Group values
        AddMsgAndPrint("\nChecking Hydrologic Group Attributes in Soil Layer.....",1)

        validHydroValues = ['A','B','C','D','A/D','B/D','C/D','W']
        valuesToConvert = ['A/D','B/D','C/D','W']

        rows = arcpy.searchcursor(wsSoils)
        row = rows.next()

        invalidHydValues = 0
        valuesToConvertCount = 0
        emptyValues = 0
        missingValues = 0

        while row:

            hydValue = str(row.GetValue(inputField))

            if len(hydValue) > 0:  # Not NULL Value

                if not hydValue in validHydroValues:
                    invalidHydValues += 1
                    AddMsgAndPrint("\t\t" + "\"" + hydValue + "\" is not a valid Hydrologic Group Attribute",0)

                if hydValue in valuesToConvert:
                    valuesToConvertCount += 1
                    #AddMsgAndPrint("\t" + "\"" + hydValue + "\" needs to be converted -------- " + str(valuesToConvertCount),1)

            else: # NULL Value
                emptyValues += 1

            row = rows.next()

        del rows, row

        # ------------------------------------------------------------------------------------------- Inform the user of Hydgroup Attributes
        if invalidHydValues > 0:
            AddMsgAndPrint("\tThere are " + str(invalidHydValues) + " invalid attribute(s) found in your Soil's " + "\"" + inputField + "\"" + " Field",1)

        if valuesToConvertCount > 0:
            AddMsgAndPrint("\tThere are " + str(valuesToConvertCount) + " attribute(s) that need to be converted to a single class i.e. \"B/D\" to \"B\"",0)

        if emptyValues > 0:
            AddMsgAndPrint("\tThere are " + str(emptyValues) + " NULL polygon(s) that need to be attributed with a Hydrologic Group",0)

        if emptyValues == int(arcpy.GetCount_management(inSoils).getOutput(0)):
            AddMsgAndPrint("\t" + "\"" + inputField + "\"" + "Field is blank.  It must be populated before using the 2nd tool Loser!",2)
            missingValues = 1

        del validHydroValues, valuesToConvert, invalidHydValues

        # ------------------------------------------------------------------------------------------- Compare Input Field to SSURGO HydroGroup field name
        if inputField.upper() != "HYDGROUP":
            arcpy.AddField_management(wsSoils, "HYDGROUP", "TEXT", "", "", "20", "", "NULLABLE", "NON_REQUIRED", "")

            if missingValues == 0:
                arcpy.CalculateField_management(wsSoils, "HYDGROUP", "[" + str(inputField) + "]", "VB", "")

            else:
                AddMsgAndPrint("\n\tAdded " + "\"HYDGROUP\" to soils layer.  Please Populate the Hydrologic Group Values manually for this field",0)

        # Delete any field not in the following list
        fieldsToKeep = ["MUNAME","MUKEY","HYDGROUP","MUSYM","OBJECTID"]

        fields = arcpy.ListFields(wsSoils)

        for field in fields:

            fieldName = field.Name

            if not fieldName.upper() in fieldsToKeep and fieldName.find("Shape") < 0:
                arcpy.deletefield_management(wsSoils,fieldName)

        del fields, fieldsToKeep, missingValues

        arcpy.AssignDomainToField_management(wsSoils, "HYDGROUP", "Hydro_Domain", "")

        # ---------------------------------------------------------------------------------------------------------------------------- Compact FGDB
        try:
            arcpy.compact_management(watershedGDB_path)
            AddMsgAndPrint("\nSuccessfully Compacted FGDB: " + os.path.basename(watershedGDB_path),1)
        except:
            pass

        # --------------------------------------------------------------------------------------------------------------------------- Prepare to Add to Arcmap

        arcpy.SetParameterAsText(4, landuse)
        arcpy.SetParameterAsText(5, wsSoils)

        if externalWshd:
            arcpy.SetParameterAsText(6, watershed)

        AddMsgAndPrint("\nAdding Layers to ArcMap",1)
        AddMsgAndPrint("\n\t=========================================================================",0)
        AddMsgAndPrint("\tBEFORE CALCULATING THE RUNOFF CURVE NUMBER FOR YOUR WATERSHED MAKE SURE TO",1)
        AddMsgAndPrint("\tATTRIBUTE THE \"LANDUSE\" AND \"CONDITION\" FIELDS IN " + os.path.basename(landuse) + " LAYER",1)

        if valuesToConvertCount > 0:
            AddMsgAndPrint("\tAND CONVERT THE " + str(valuesToConvertCount) + " COMBINED HYDROLOGIC GROUPS IN " + os.path.basename(wsSoils) + " LAYER",1)

        if emptyValues > 0:
            AddMsgAndPrint("\tAS WELL AS POPULATE VALUES FOR THE " + str(emptyValues) + " NULL POLYGONS IN " + os.path.basename(wsSoils) + " LAYER",1)

        AddMsgAndPrint("\t=========================================================================\n",0)

        import time
        time.sleep(3)

        del valuesToConvertCount, emptyValues

except:
    print_exception()


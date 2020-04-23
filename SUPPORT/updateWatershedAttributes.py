# ==========================================================================================
# Name: updateWatershedAttributes.py
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
# Updated  4/23/2020 - Adolfo Diaz
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
    f.write("Executing \"4.Update Watershed Attributess\" Tool\n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write(arcInfo['ProductName'] + ": " + arcInfo['Version'] + "\n")
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
import sys, os, traceback, string, re, time
from arcpy.sa import *

if __name__ == '__main__':

    try:
        # --------------------------------------------------------------------- Input Parameters
        watershed = arcpy.GetParameterAsText(0)

        # Set environmental variables
        arcpy.env.parallelProcessingFactor = "75%"
        arcpy.env.overwriteOutput = True

        # --------------------------------------------------------------------- Variables
        watershedPath = arcpy.da.Describe(watershed)['catalogPath']
        watershedGDB_path = watershedPath[:watershedPath.find('.gdb')+4]
        watershedGDB_name = os.path.basename(watershedGDB_path)
        userWorkspace = os.path.dirname(watershedGDB_path)
        watershedFD = watershedGDB_path + os.sep + "Layers"
        wsName = os.path.basename(watershed)
        projectName = arcpy.ValidateTableName(os.path.basename(userWorkspace).replace(" ","_"))
        projectAOI = watershedFD + os.sep + projectName + "_AOI"
        Flow_Length = watershedFD + os.sep + wsName + "_FlowPaths"

        # log File Path
        textFilePath = userWorkspace + os.sep + projectName + "_EngTools.txt"

        # record basic user inputs and settings to log file for future purposes
        logBasicSettings()

        if arcpy.Exists(Flow_Length):
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

        # --------------------------------------------------------------------- Get XY linearUnits From inWatershed
        # Input DEM Spatial Reference Information
        demDesc = arcpy.da.Describe(DEM_aoi)
        demName = demDesc['name']
        demPath = demDesc['catalogPath']
        demCellSize = demDesc['meanCellWidth']
        demSR = demDesc['spatialReference']
        linearUnits = demSR.linearUnitName

        if linearUnits == "Meter":
            linearUnits = "Meters"
        elif linearUnits == "Foot":
            linearUnits = "Feet"
        elif linearUnits == "Foot_US":
            linearUnits = "Feet"

        # ----------------------------------- Set Environment Settings
        arcpy.env.extent = "MINOF"
        arcpy.env.cellSize = demCellSize
        arcpy.env.snapRaster = demPath
        arcpy.env.outputCoordinateSystem = demSR
        arcpy.env.workspace = watershedGDB_path

        # ---------------------------------------------------------------------- Update Drainage Area(s)
        if len(arcpy.ListFields(watershed,"Acres")) < 1:
            arcpy.AddField_management(watershed, "Acres", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

        arcpy.CalculateField_management(watershed, "Acres", "!shape.area@acres!", "PYTHON3")
        AddMsgAndPrint("\nSuccessfully updated drainage area(s)")

        # ---------------------------------------------------------------------- Update Flow Path Length (if present)
        if updateFlowLength:

            if len(arcpy.ListFields(Flow_Length,"Length_ft")) < 1:
                arcpy.AddField_management(Flow_Length, "Length_ft", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")

            if linearUnits == "Meters":
                arcpy.CalculateField_management(Flow_Length, "Length_ft", "!Shape_Length! * 3.28084", "PYTHON3")
            else:
                arcpy.CalculateField_management(Flow_Length, "Length_ft", "!Shape_Length!", "PYTHON3")

        # ----------------------------------------------------------------------- Update Average Slope
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

                if len(arcpy.ListFields(watershed,"Avg_Slope")) < 1:
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

            AddMsgAndPrint("\n\tSuccessfully re-calculated Average Slope")

            AddMsgAndPrint("\n===================================================")
            AddMsgAndPrint("\tUser Watershed: " + str(wsName))

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

    except:
        print_exception()

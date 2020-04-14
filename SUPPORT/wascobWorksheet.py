# ---------------------------------------------------------------------------
# wascobWorksheet.py
#----------------------------------------------------------------------------
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
                #gp.AddMessage("    ")
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
    f.write("Executing \"6. Wascob Design Worksheet\" Tool\n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write("User Parameters:\n")
    f.write("\tWorkspace: " + userWorkspace + "\n")
    f.write("\tInput Watershed: " + inWatershed + "\n")
        
    f.close
    del f   

## ================================================================================================================
# Import system modules
import sys, os, arcgisscripting, traceback, subprocess, time, shutil

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

    # ---------------------------------------------- Variables
    
    watershed_path = gp.Describe(inWatershed).CatalogPath
    watershedGDB_path = watershed_path[:watershed_path .find(".gdb")+4]
    watershedFD_path = watershedGDB_path + os.sep + "Layers"
    watershedGDB_name = os.path.basename(watershedGDB_path)
    userWorkspace = os.path.dirname(watershedGDB_path)
    wsName = os.path.basename(inWatershed)
    outputFolder = userWorkspace + os.sep + "gis_output"
    tables = outputFolder + os.sep + "tables"
    Documents = userWorkspace + os.sep + "Documents"
    
    # log File Path
    textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.txt"    
    # record basic user inputs and settings to log file for future purposes
    logBasicSettings()
    
    # ------------------------------------------------ Existing Data
    
    inWorksheet = os.path.join(os.path.dirname(sys.argv[0]), "LiDAR_WASCOB.xlsm")
    rcn = watershedFD_path + os.sep + wsName + "_RCN"

    # ------------------------------------------------ Permanent Datasets
    
    stakeoutPoints = watershedFD_path + os.sep + "stakeoutPoints"
    rcnTable = tables + os.sep + "RCNsummary.dbf"
    watershedTable = tables + os.sep + "watershed.dbf"

    # ---------------------------- Layers in ArcMap
    outPoints = "StakeoutPoints"

    # ------------------------------------------------------------------ Check some parameters
    
    # ----------------------------------- Make sure RCN layer was created
    if not gp.Exists(rcn):
        AddMsgAndPrint("\n\n" + str(os.path.basename(rcn)) + " not found in " + str(watershedGDB_name),2)
        AddMsgAndPrint("\nYou must run Tool #5: \"Calculate Runoff Curve Number\" before executing this tool.....EXITING",2)
        sys.exit(0)
        
    # ----------------------------------- Make Sure RCN Field is in the Watershed
    
    if not len(gp.ListFields(inWatershed,"RCN")) > 0:
        AddMsgAndPrint("\n\nRCN Field not found in " + str(wsName),2)
        AddMsgAndPrint("\nYou must run Tool #5: \"Calculate Runoff Curve Number\" before executing this tool.....EXITING",2)
        sys.exit(0)        

    # ---------------------------------- Make Sure RCN Field has valid value(s)
    rows = gp.searchcursor(inWatershed)
    row = rows.next()
    invalidValue = 0
    
    while row:
        
        rcnValue = str(row.RCN)
        
        if not len(rcnValue) > 0:  # NULL Value
            invalidValue += 1
                            
        row = rows.next()
 
    del rows, row
    
    if invalidValue > 0:
        AddMsgAndPrint("\n\nRCN Field in " + str(wsName) + " contains invalid or Null values!",2)
        AddMsgAndPrint("\nRe-run Tool #5: \"Calculate Runoff Curve Number\" or manually correct RCN value(s).....EXITING",2)
        sys.exit(0)         
    del invalidValue
    # --------------------------------------- Make sure Wacob Worksheet template exists
    if not gp.Exists(inWorksheet):
        AddMsgAndPrint("\n\nLiDAR_WASCOB.xlsm Worksheet template not found in " + str(os.path.dirname(sys.argv[0])),2)
        AddMsgAndPrint("\nPlease Check the Support Folder and replace the file if necessary....EXITING",2)
        sys.exit(0)
        
    # ---------------------------------------- Check Addnt'l directories
    
    if not gp.Exists(outputFolder):
        gp.CreateFolder_management(userWorkspace, "gis_output")
    if not gp.Exists(tables):
        gp.CreateFolder_management(outputFolder, "tables")
        
    # If Documents folder not present, create and copy required files to it
    if not gp.exists(Documents):
        gp.CreateFolder_management(userWorkspace, "Documents")
        DocumentsFolder =  os.path.join(os.path.dirname(sys.argv[0]), "Documents")
        if gp.Exists(DocumentsFolder):
            gp.Copy_management(DocumentsFolder, Documents, "Folder")
        del DocumentsFolder
        
    # think that about covers it....
    
    # ------------------------------------------------------------------ Copy User Watershed and RCN Layer tables for spreadsheet import
    AddMsgAndPrint("\nCopying results to tables...\n",1)
    gp.CopyRows_management(inWatershed, watershedTable, "")
    gp.CopyRows_management(rcn, rcnTable, "")
        
    # ------------------------------------------------------------------ Create Wascob Worksheet
    #os.path.basename(userWorkspace).replace(" ","_") + "_Wascob.gdb" 
    outWorksheet = Documents + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_WASCOB.xlsm"
    x = 1
    while x > 0:
        if gp.exists(outWorksheet):
            outWorksheet = Documents + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_WASCOB" + str(x) + ".xlsm"
            x += 1
        else:
            x = 0
    del x

    # Copy template and save as defined
    shutil.copyfile(inWorksheet, outWorksheet)
                    
    # --------------------------------------------------------------------------- Create Stakeout Points FC    
    if not gp.Exists(outPoints):
    
        gp.CreateFeatureclass_management(watershedFD_path, "stakeoutPoints", "POINT", "", "DISABLED", "DISABLED", "", "", "0", "0", "0")
        gp.AddField_management(stakeoutPoints, "ID", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        gp.AddField_management(stakeoutPoints, "Subbasin", "LONG", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        gp.AddField_management(stakeoutPoints, "Elev", "DOUBLE", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        gp.AddField_management(stakeoutPoints, "Notes", "TEXT", "", "", "50", "", "NULLABLE", "NON_REQUIRED", "")

        # ------------------------------------------------------------------------------------------------ Compact FGDB
        try:
            gp.compact_management(watershedGDB_path)
        except:
            pass
        
        # ------------------------------------------------------------------------------------------------ add to ArcMap
        AddMsgAndPrint("\nAdding Stakeout Points to ArcMap Session\n",1)    
        gp.SetParameterAsText(1, stakeoutPoints)       
   

    # ----------------------------------------------------------------------- Launch Wascob Spreadsheet
    AddMsgAndPrint("\nSearching for path to Microsoft Excel...",1)
    
    # Open Wascob Spreadsheet in Excel -- paths provided for Office '03 - '10 & 32 /64 bit machines
    # Path added for Office 2016 on Windows 10, as of 11/29/2017
    if gp.Exists ("C:\Program Files\Microsoft Office\Office14\EXCEL.EXE"):
        AppPath = (r'C:\Program Files\Microsoft Office\Office14\EXCEL.EXE')
    elif gp.Exists ("C:\Program Files\Microsoft Office\Office12\EXCEL.EXE"):
        AppPath = (r'C:\Program Files\Microsoft Office\Office12\EXCEL.EXE')
    elif gp.Exists ("C:\Program Files\Microsoft Office\Office10\EXCEL.EXE"):
        AppPath = (r'C:\Program Files\Microsoft Office\Office10\EXCEL.EXE')       
    elif gp.Exists (r'C:\Program Files (x86)\Microsoft Office\Office14\EXCEL.EXE'):
        AppPath = (r'C:\Program Files (x86)\Microsoft Office\Office14\EXCEL.EXE')
    elif gp.Exists (r'C:\Program Files (x86)\Microsoft Office\Office12\EXCEL.EXE'):
        AppPath = (r'C:\Program Files (x86)\Microsoft Office\Office12\EXCEL.EXE')
    elif gp.Exists (r'C:\Program Files (x86)\Microsoft Office\Office10\EXCEL.EXE'):
        AppPath = (r'C:\Program Files (x86)\Microsoft Office\Office10\EXCEL.EXE')
    elif gp.Exists (r'C:\Program Files (x86)\Microsoft Office\Office15\EXCEL.EXE'):
        AppPath = (r'C:\Program Files (x86)\Microsoft Office\Office15\EXCEL.EXE')
    elif gp.Exists (r'C:\Program Files (x86)\Microsoft Office\root\Office16\EXCEL.EXE'):
        AppPath = (r'C:\Program Files (x86)\Microsoft Office\root\Office16\EXCEL.EXE')
        
    else:
        # If path not found instruct user to open manually from Excel
        AppPath = 0
        AddMsgAndPrint("\n\t===============================================================",1)
        AddMsgAndPrint("\n\tThe path to Microsoft Excel Could not be found...",0)
        AddMsgAndPrint("\tYou will have to manually open the worksheet " + str(outWorksheet) + "",0)
        AddMsgAndPrint("\tin Microsoft Excel from the Documents folder in "+ str(userWorkspace) + "",0)
        AddMsgAndPrint("\n\t===============================================================",1)
        time.sleep(5)

    if len(str(AppPath)) > 1:
        AddMsgAndPrint("\n\t===============================================================",1)
        AddMsgAndPrint("\n\tThe LiDAR_WASCOB Spreadsheet will open in Microsoft Excel",0)
        AddMsgAndPrint("\tand has been saved to " + str(userWorkspace)+ " \Documents.",0)
        AddMsgAndPrint("\n\tOnce Excel is open, enable macros (if not already enabled),",0)
        AddMsgAndPrint("\tand set the path to your project folder to import your gis data.",0)
        AddMsgAndPrint("\n\tOnce you have completed the Wascob Design Sheet(s) you can return ",0)
        AddMsgAndPrint("\tto ArcMAP and complete the degign height and tile layout steps.",0)
        AddMsgAndPrint("\n\t===============================================================",1)

        time.sleep(5)  
        excel = subprocess.Popen([AppPath, outWorksheet])
        del excel
        

    AddMsgAndPrint("\nProcessing Finished\n",1)

    # ------------------------------------------------------------------ Cleanup

    try:
        del inWatershed
        del outPoints
        del watershed_path
        del watershedGDB_path
        del watershedGDB_name
        del watershedFD_path
        del userWorkspace
        del wsName
        del outputFolder
        del tables
        del Documents
        del textFilePath
        del inWorksheet
        del rcn
        del outWorksheet
        del stakeoutPoints
        del rcnTable
        del watershedTable   
        del AppPath
        del gp
    except:
        pass
    
except SystemExit:
    pass

except KeyboardInterrupt:
    AddMsgAndPrint("Interruption requested....exiting")

except:
    print_exception()


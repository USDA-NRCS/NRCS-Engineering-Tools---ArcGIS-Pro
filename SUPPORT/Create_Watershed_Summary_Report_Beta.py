#Created 8/6/2014
#Use this script to compile relevant information from various tables from the watershed delineation process
#and aggregates it into a user named output text file that gets stored in the project workspace.
#Summary items include the watershed/subbasin name/number, associated area (ac), slope (pct), Weighted total
#runoff curve number (RCN), longest flow path length, and a detailed RCN breakdown of hydrologic group and land use
#combinations.

#Start
#Standard code blocks for messaging and error tracing
#---------------------------------------------------------------------------------------------------------
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
    f.write("Executing \"Create Watershed Summary Report\" Tool \n")
    f.write("User Name: " + getpass.getuser() + "\n")
    f.write("Date Executed: " + time.ctime() + "\n")
    f.write("ArcGIS Version: " + str(version) + "\n")
    f.write("User Parameters:\n")
    f.write("\tinWatershed: " + inWatershed + "\n")
    f.write("\toutputTextFile: " + outTxt + "\n")
    
    f.close
    del f

## ================================================================================================================
# Import system modules
import sys, os, string, traceback, arcgisscripting

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
    gp.AddError("\nThis tool requires ArcGIS version 9.3 or Greater.....EXITING")
    sys.exit("")          

try:
    # Script Parameters
    inWatershed = gp.GetParameterAsText(0)
    outTxt = gp.GetParametersAsText(1)

    # inWatershed can ONLY be a feature class
    watershed_path = gp.Describe(inWatershed).CatalogPath
    if watershed_path.find('.gdb') > 0:
        watershedGDB_path = watershed_path[:watershed_path.find('.gdb')+4]

    else:
        AddMsgAndPrint("\n\nWatershed Layer must be a File Geodatabase Feature Class!.....Exiting",2)
        AddMsgAndPrint("You must run \"Calculate Runoff Curve Number\" tool first before running this tool\n",2)
        sys.exit()

    # Derived Parameters
    ## Feature Dataset
    watershedFD_path = watershedGDB_path + os.sep + "Layers"

    ## Geodatabase
    watershedGDB_name = os.path.basename(watershedGDB_path)

    ## Workspace that contains geodatabase
    userWorkspace = os.path.dirname(watershedGDB_path)

    ## Feature Class name of input watershed
    wsName = os.path.basename(inWatershed)

    ## Feature Class name of related flowpath file
    inFlowpath = watershedFD_Path + os.sep + wsName + "_FlowPaths"

    ## Feature Class name of related soils file
    inSoils = watershedFD_Path + os.sep + wsName + "_Soils"
    
    ## Feature Class name of related detailed RCN file
    rcn = watershedFD_path + os.sep + wsName + "_RCN"
   
    ## Drop extension and replace spaces, if any, with underscores for the user entered output text file name
    txtNameLength = (len(outTxt) - 4)
    if outTxt[txtNameLength:] == ".txt":
        NewOutTxt = outTxt[0:txtNameLength]
    else:
        NewOutTxt = outTxt

    # log File Path
    textFilePath = userWorkspace + os.sep + os.path.basename(userWorkspace).replace(" ","_") + "_EngTools.txt"

    # record basic user inputs and settings to log file for future purposes
    logBasicSettings()

    del outTxt
    del txtNameLength
    
    outTxtPath = userWorkspace + os.sep + NewOutTxt.replace(" ","_") + "_Summary_Report.txt"
    del NewOutTxt


    # Check Inputs
    # Exit if input watershed is RCN layer
    if inWatershed.find("_RCN") > 0:
        AddMsgAndPrint("\nYou have mistakenly input your detailed RCN layer...Enter your watershed layer!",2)
        AddMsgAndPrint("Exiting",2)
        sys.exit("")
        
    # Exit if "RCN" field not found in watershed layer
    if not len(gp.ListFields(inWatershed,"RCN")) > 0:
        AddMsgAndPrint("\n\"RCN\" field was not found in " + os.path.basename(inWatershed) + "layer\n",2)
        AddMsgAndPrint("You must run \"Calculate Runoff Curve Number\" tool first before running this tool\n",2)
        sys.exit("")

### Loop through subbasins in the watershed layer/table
### For each subbasin:
        ### Write Subbasin number
        ### Write Subbasin Acres (to the tenth)
        ### Write Subbasin Avg Slope
        ### Write Subbasin Flow Length
        ### Write Subbasin's Detailed RCN Table of
            ###Land Use & Condition, Hydrologic Group, RCN, and Acres (to the tenth)

        

# This originally came from "Create_Watershed.py" tool.  Whenever a feature was inputed instead of manually digitized the tool would fail.  I thought it was failing b/c
# it couldn't check the path of 'outlets' but it turned out I was removing a layer before checking for this.

# ----------------------------------------------------------------------------------------------- Create New Outlet
# -------------------------------------------- Features reside on hard disk;
#                                              No heads up digitizing was used.
if (os.path.dirname(gp.Describe(outlets).CatalogPath)).find("memory") < 0:

    # if paths between outlets and outletFC are NOT the same       
    if not gp.Describe(outlets).CatalogPath == outletsFC:            

        # delete the outlets feature class; new one will be created            
        if gp.exists(outletsFC):
            gp.delete_management(outletsFC)
            gp.CopyFeatures_management(outlets, outletsFC)
            AddMsgAndPrint("\nSuccessfully Recreated \"Outlets\" feature class from existing layer",1)                
            
        else:    
            gp.CopyFeatures_management(outlets, outletsFC)
            AddMsgAndPrint("\nSuccessfully Created \"Outlets\" feature class from existing layer",1)

    # paths are the same therefore input IS pour point
    else:
        outletsFC = gp.Describe(outlets).CatalogPath
        AddMsgAndPrint("\nUsing Existing \"Outlets\" feature class",1)

# -------------------------------------------- Features reside in Memory;
#                                              heads up digitizing was used.       
else:
        
    if gp.exists(outletsFC):
        gp.delete_management(outletsFC)
        gp.CopyFeatures_management(outlets, outletsFC)
        AddMsgAndPrint("\nSuccessfully Recreated \"Outlets\" feature class from digitizing",1)

    else:
        gp.CopyFeatures_management(outlets, outletsFC)
        AddMsgAndPrint("\nSuccessfully Created \"Outlets\" feature class from digitizing",1)

if gp.Describe(outletsFC).ShapeType != "Polyline" and gp.Describe(outletsFC).ShapeType != "Line":
    AddMsgAndPrint("\n\nYour Outlet must be a Line or Polyline layer!.....Exiting!",2)
    sys.exit()    
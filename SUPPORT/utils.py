from os import path
from sys import exc_info
from traceback import format_exception

from arcpy import AddError, AddMessage, AddWarning, Exists, GetActivePortalURL, GetSigninToken, ListPortalURLs
from arcpy.da import Walk
from arcpy.management import CalculateGeometryAttributes, Delete
from arcpy.metadata import Metadata


def addLyrxByConnectionProperties(map, lyr_name_list, lyrx_layer, gdb_path, visible=True):
    ''' Add a layer to a map by setting the lyrx file connection properties.'''
    if lyrx_layer.name not in lyr_name_list:
        lyrx_cp = lyrx_layer.connectionProperties
        lyrx_cp['connection_info']['database'] = gdb_path
        lyrx_cp['dataset'] = lyrx_layer.name
        lyrx_layer.updateConnectionProperties(lyrx_layer.connectionProperties, lyrx_cp)
        map.addLayer(lyrx_layer)

    lyr_list = map.listLayers()
    for lyr in lyr_list:
        if lyr.longName == lyrx_layer.name:
            lyr.visible = visible


def AddMsgAndPrint(msg, severity=0, textFilePath=None):
    ''' Log messages to text file and ESRI tool messages dialog.'''
    if textFilePath:
        with open(textFilePath, 'a+') as f:
            f.write(f"{msg}\n")
    if severity == 0:
        AddMessage(msg)
    elif severity == 1:
        AddWarning(msg)
    elif severity == 2:
        AddError(msg)


def deleteScratchLayers(scratchLayers):
    ''' Delete layers in a given list.'''
    for lyr in scratchLayers:
        try:
            Delete(lyr)
        except:
            continue


def errorMsg(tool_name):
    ''' Return exception details for logging, ignore sys.exit exceptions.'''
    exc_type, exc_value, exc_traceback = exc_info()
    exc_message = f"\t{format_exception(exc_type, exc_value, exc_traceback)[1]}\n\t{format_exception(exc_type, exc_value, exc_traceback)[-1]}"
    if exc_message.find('sys.exit') > -1:
        pass
    else:
        return f"\n\t------------------------- {tool_name} Tool Error -------------------------\n{exc_message}"


def getPortalTokenInfo(portalURL):
    try:
        # i.e. 'https://gis.sc.egov.usda.gov/portal/'
        activePortal = GetActivePortalURL()

        # targeted portal is NOT set as default
        if activePortal != portalURL:
            # List of managed portals
            managedPortals = ListPortalURLs()

            # portalURL is available in managed list
            if activePortal in managedPortals:
                AddMsgAndPrint(f"\nYour Active portal is set to: {activePortal}", 2)
                AddMsgAndPrint(f"Set your active portal and sign into: {portalURL}", 2)
                return False

            # portalURL must first be added to list of managed portals
            else:
                AddMsgAndPrint(f"\nYou must add {portalURL} to your list of managed portals", 2)
                AddMsgAndPrint('Open the Portals Tab to manage portal connections', 2)
                AddMsgAndPrint('For more information visit the following ArcGIS Pro documentation:', 2)
                AddMsgAndPrint('https://pro.arcgis.com/en/pro-app/help/projects/manage-portal-connections-from-arcgis-pro.htm', 2)
                return False

        # targeted Portal is correct; try to generate token
        else:
            # Get Token information
            tokenInfo = GetSigninToken()

            # Not signed in.  Token results are empty
            if not tokenInfo:
                AddMsgAndPrint(f"\nYou are not signed into: {portalURL}", 2)
                return False

            # Token generated successfully
            else:
                return tokenInfo

    except:
        errorMsg()
        return False


def removeMapLayers(map, map_layers):
    ''' Remove layers from the active map for a given list of lyr objects.'''
    for lyr in map.listLayers():
        try:
            if lyr.name in map_layers:
                map.removeLayer(lyr)
        except:
            continue


def delete_datasets(datasets):
    for fc in datasets:
        try:
            if Exists(fc):
                Delete(fc)
        except:
            continue


def emptyScratchGDB(gdb_path):
    ''' Delete everything in a given geodatabase.'''
    gdb_contents = []
    for dirpath, dirnames, filenames in Walk(gdb_path):
        for filename in filenames:
            gdb_contents.append(path.join(dirpath, filename))
    for fc in gdb_contents:
        Delete(fc)



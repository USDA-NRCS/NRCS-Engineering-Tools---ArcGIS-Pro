# NRCS-Engineering-Tools---ArcGIS-Pro
NRCS engineering tools for runoff curve number (RCN) generation and general elevation data workflows in ArcGIS Pro.

## **General Notes:**
- Support enabled for ArcGIS Pro enabled.
- Current ArcGIS Pro Versions supported: 3.2.x through 3.6.1.
- Support for ArcMap versions of the tools ended.
- Toolbox reorganized to remove redundancies in tools and related code.
- Starting template added with updated (basic) layouts.
- Enclosed toolbox must be used from within the provided APRX template, which can be further customized as needed.
  - This is a remnant of not yet addressing the possibility for multiple maps in ArcGIS Pro, compared to a maximum of one available data frame in ArcMap.
  - Issue has been logged to revisit in the future.
- Project folder reorganized to separate work for general analysis to one geodatabase and work for WASCOB analysis to a second geoodatabase.
- Input data is converted to streamline the computational workflow inside the toolbox.
  - Users aren't re-prompted for the same x, y, and z units information as often, reducing the opportunities for user error, typos, or misclick.
  - Input data is converted to WGS 1984 UTM (selected zone) to minimize conversions throughout the workflow.
  - Input data is converted to vertical international feet to minimize conversions throughout the workflow.
  - Resulting Project DEM is x,y meters and z international feet.
  - Finished products can be exported back to desired coordinate systems and vertical units manually using standard ArcGIS Pro export procedures on datasets, as needed.
- NLCD RCN tool for large watersheds not converted yet due to a high number of assumptions for only one region of the country present in the original ArcMap version.
  - Issue has been logged to revisit in the future.

## **Version 1.0.3 (02/06/2026; Production Release):**
### **New Features/Changes**
- Corrected bug for layer names out of range when tables are included in the ArcGIS Pro Contents pane.

## **Version History:**
### Version 1.0.2 (Production Release)
- Regression testing for ArcGIS Pro 3.6.x completed.
- Small bug corrections

### Version 1.0.1 (Production Release)
- Small bug corrections

### Version 1.0.0 (Production Release)
- Initial ArcGIS Pro release following beta versions
- Support for versions of ArcGIS Pro 3.1 and lower ended.
- Terrain analysis formulas were reviewed and parameters were updated to give the user more options to tune their analysis and results on those tools.
- Land use tables updated with all known NRCS engineering handbook and state supplemental entries for use when attributing land uses to prepare for RCN calculations.

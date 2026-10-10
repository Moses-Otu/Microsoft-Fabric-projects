# Capital Bikeshare on Microsoft Fabric

This folder sets up the bike sharing data on Fabric so that Power BI holds the official version of every number. Two notebooks do the work. The first builds a lakehouse with eight clean reporting tables from the raw files. The second builds a Direct Lake semantic model on top, with the relationships, a date table, 44 agreed measures and row-level security already in place. Reports, the governance controls and anyone asking "what does this number mean" all point back to that one model.

The data is the same as in the Claude dashboard: Capital Bikeshare's public trip records for 2011 and 2012 (3,255,678 trips), today's station feed for station positions, and the UCI Bike Sharing daily and hourly totals with weather (3,292,679 rentals).

## What's in the folder

- `notebooks/01_build_lakehouse.ipynb` downloads the raw files into the lakehouse, cleans them, runs data checks and writes the reporting tables with descriptions on every table and column.
- `notebooks/02_build_semantic_model.ipynb` creates the semantic model, adds the measures and security, refreshes it and checks the results against known values.
- `notebooks/03_export_for_dashboard.ipynb` queries the semantic model and packs the results into one small zip for the Claude dashboard, so the dashboard shows the model's numbers.
- `model/measures.dax` lists every measure with its formula and description, plus the security role rules, for review or for pasting into Power BI's DAX query view.
- `DATA_DICTIONARY.md` describes every table and column.
- `GOVERNANCE.md` covers who can do what, endorsement, sensitivity labels, security, change control and audit.

## Setting it up

You need a Fabric capacity (a trial works) and permission to create items in a workspace.

1. Create a workspace, for example *Bike Share [Dev]*, on your Fabric capacity. GOVERNANCE.md explains how this grows into Dev, Test and Prod.
2. In the workspace, create a lakehouse called `bike_lakehouse`. If you use another name, change `LAKEHOUSE` at the top of notebook 02.
3. Import both notebooks (Workspace, Import, Notebook, From this computer).
4. Open notebook 01, attach `bike_lakehouse` as its default lakehouse, and run all cells. It downloads about 70 MB, takes a few minutes, and stops before writing anything if a data check fails. If your tenant blocks a download, the notebook tells you which file to upload to `Files/raw` by hand.
5. Open the `security_user_region` table and replace the placeholder row with the real people and the regions they may see. GOVERNANCE.md describes how this works.
6. Run notebook 02 in the same workspace. Its last cell compares the model's numbers with the expected ones: 3,255,678 trips, 3,292,679 rentals, busiest day 15 September 2012, quietest 29 October 2012, and so on.
7. To feed the Claude dashboard from the model, run notebook 03, download `Files/exports/dashboard/dashboard_export.zip` and load it into the dashboard.
8. If you also want a Power BI report, build it on the model (suggested layout below), then work through GOVERNANCE.md.

If you'd rather not use notebook 02, you can create the semantic model from the lakehouse in the Fabric interface, pick the eight tables, draw the relationships listed in DATA_DICTIONARY.md, and paste `model/measures.dax` into DAX query view to add the measures.

## Building the report

The model is built so the Power BI report can work like the Report page of the Claude dashboard.

For the report page, use slicers on `dim_date[date]` (between), `dim_date[day_type]`, `dim_member_type[member_type]` and `dim_date[weather_group]`. The rider slicer works on both the trip records and the UCI totals, because the *Selected Rider* measures read it. Put **Summary Text** and **Extremes Text** in a card or text box at the top. Under them, add a line chart of **Selected Rider Avg Daily** by date, a column chart of **Avg Rentals per Hour** by `dim_hour[hour_label]` with **Rush Hour Text** beside it, and a bar chart of **Selected Rider Avg Daily** by weather group with **Weather Text**. Every sentence rewrites itself as the slicers change.

For a stations page, an Azure Maps visual with `dim_station[latitude]` and `[longitude]`, bubble size **Trips** and **Trips Ended** in the tooltip shows the network. A column chart of **Downtown Net Arrivals** by hour, filtered to working days, shows the morning flow into downtown and the evening flow out.

The animated bike road, the moving riders and the draggable station bubbles from the Claude dashboard don't exist in standard Power BI visuals. They would need a custom visual built with the Power BI visuals SDK, and the dashboard's D3 code would be the starting point.

## Numbers that differ slightly from the Claude dashboard

The trip records hold about 1% fewer trips than the UCI daily totals, because Capital Bikeshare removes staff trips, test-station trips and trips under 60 seconds before publishing. The model keeps both and names them differently (**Trips** for the records, **Rentals** for the UCI totals), so they are never mixed up.

The dashboard's map left out the 10,038 trips at the one station that couldn't be placed (12th & Army Navy Dr). The lakehouse keeps them, with that station flagged `is_mapped = false`. That's why Dupont Circle shows 107,162 trips started here and 107,155 on the dashboard map, and why there are 194 active stations instead of 193.

## What was and wasn't tested

Notebook 01's download, cleaning and checks were run on your actual files and every check passed. The step that writes Delta tables uses Spark, which couldn't be run outside Fabric. The same goes for notebook 02, which uses Fabric's Semantic Link Labs library. Every measure was checked for matching brackets and for referring only to real columns and measures, and the expected values in notebook 02's last cell were computed from the same data. If any cell errors in your tenant, the message will name the step, and the fix is usually a library version difference in `semantic-link-labs`.

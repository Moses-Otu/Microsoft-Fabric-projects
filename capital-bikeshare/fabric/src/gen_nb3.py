import json
import os; HERE=os.path.dirname(os.path.abspath(__file__)); core=open(os.path.join(HERE,'export_core.py')).read()
def md(s): return {"cell_type":"markdown","metadata":{},"source":s.strip("\n").splitlines(True)}
def code(s): return {"cell_type":"code","metadata":{},"execution_count":None,"outputs":[],"source":s.strip("\n").splitlines(True)}
nb={"nbformat":4,"nbformat_minor":5,"metadata":{"kernelspec":{"name":"synapse_pyspark","display_name":"Synapse PySpark","language":"python"},"language_info":{"name":"python"}},"cells":[
md("""
# 03 · Export the dashboard data from the semantic model

Runs DAX queries against the certified **Capital Bikeshare** semantic model, so every number the Claude dashboard shows comes from the model's own measures and definitions. It writes one file, `Files/exports/dashboard/dashboard_export.zip` (about 0.5 MB), with the thirteen small tables the dashboard reads.

**Before you run it:** attach `bike_lakehouse` as the default lakehouse, and run it in the workspace that holds the semantic model. It uses Semantic Link (`sempy`), which comes with Fabric.

**After it runs:** download the zip (Lakehouse explorer, Files, exports, dashboard, then the **...** menu on the file, then Download) and save it in your Bike sharing folder. Then tell Claude it's there. Run it again whenever the model changes and you want the dashboard to catch up.
"""),
code('MODEL = "Capital Bikeshare"   # semantic model name\nWORKSPACE = None               # None = this notebook\'s workspace\n\n'+core),
code("""
import sempy.fabric as fabric
results = {}
for name, q in QUERIES.items():
    results[name] = fabric.evaluate_dax(dataset=MODEL, dax_string=q, workspace=WORKSPACE)
    print(f"{name:14} {len(results[name]):>8,} rows")
"""),
code("""
exported_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
out = shape(results, MODEL, exported_at)

checks = {
    "731 days of daily totals": len(out["day"]) == 731,
    "daily totals add up to 3,292,679 rentals": int(out["day"]["cnt"].sum()) == 3292679,
    "hourly totals agree with daily totals": int(out["hour"]["cnt"].sum()) == int(out["day"]["cnt"].sum()),
    "3,255,678 trips in the model": int(out["map_summary"]["trips_total"].iloc[0]) == 3255678,
    "193 stations on the map": len(out["map_stations"]) == 193,
    "500 working days": int(out["map_summary"]["working_days"].iloc[0]) == 500,
}
for k, v in checks.items():
    print(("OK   " if v else "CHECK") + " " + k)
for name, df in out.items():
    print(f"  {name:20} {len(df):>7,} rows")
"""),
code("""
path = write_zip(out, EXPORT_DIR)
for name, df in out.items():                      # the individual files too, for anyone browsing the lakehouse
    df.to_json(f"{EXPORT_DIR}/{name}.json", orient="records")
print("Wrote", path, f"({os.path.getsize(path):,} bytes)")
print("Download it from Files/exports/dashboard and save it in your Bike sharing folder.")
"""),
]}
json.dump(nb,open(os.path.join(HERE,'..','notebooks','03_export_for_dashboard.ipynb'),'w'),indent=1,ensure_ascii=False)
import ast
for c in nb['cells']:
    if c['cell_type']=='code': ast.parse(''.join(c['source']))
print('ok')

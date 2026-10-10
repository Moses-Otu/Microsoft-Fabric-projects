import json, pprint, importlib.util, sys
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spec
core = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'build_core.py')).read()

def md(s): return {"cell_type": "markdown", "metadata": {}, "source": s.strip("\n").splitlines(True)}
def code(s): return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": s.strip("\n").splitlines(True)}
def nb(cells): return {"nbformat": 4, "nbformat_minor": 5, "cells": cells,
    "metadata": {"kernelspec": {"name": "synapse_pyspark", "display_name": "Synapse PySpark", "language": "python"},
                 "language_info": {"name": "python"}}}
lit = lambda name, v: f"{name} = " + pprint.pformat(v, width=140, sort_dicts=False) + "\n"

desc = {t: {"table": d, "columns": cols} for t, (d, cols) in spec.TABLES.items()}

nb1 = nb([
md("""
# 01 · Build the Capital Bikeshare lakehouse

This notebook takes the raw data from source to reporting tables in one run:

1. **Bronze**: downloads the 2011 and 2012 trip files, today's station feed and the UCI daily and hourly totals into `Files/raw` (skipping any file already there).
2. **Silver**: cleans and types the trips, matches every station to a position, and turns the UCI fields back into real units.
3. **Gold**: writes eight Delta tables with table and column descriptions, ready for a Direct Lake semantic model.

**Before you run it:** attach your lakehouse as this notebook's default lakehouse (Lakehouse explorer, left of the notebook). If a download is blocked in your tenant, upload the file to `Files/raw` with the same name and run again.

Expected result: 3,255,678 trips, 194 stations, 731 days, and all checks `True`.
"""),
code(core),
code("""
status = fetch_raw(download=True)
for k, v in status.items():
    print(f"{k:12} {v}")
"""),
code("""
gold = build_gold()
for name, df in gold.items():
    print(f"{name:22} {len(df):>10,} rows  {df.shape[1]} columns")
results = checks(gold)
for k, v in results.items():
    print(("OK   " if v else "FAIL ") + k)
assert all(results.values()), "A data check failed: stop and look before writing tables."
"""),
code(lit("DESCRIPTIONS", desc) + """
from pyspark.sql import functions as F
spark.conf.set("spark.sql.execution.arrow.pyspark.enabled", "true")
spark.conf.set("spark.sql.session.timeZone", "UTC")   # keep local times exactly as published

DATE_COLUMNS = {"dim_date": ["date"], "dim_station": ["first_trip_date", "last_trip_date"], "fact_trips": ["start_date"],
                "fact_daily_rentals": ["date"], "fact_hourly_rentals": ["date"]}

def to_plain(pdf):
    out = pdf.copy()
    for c in out.columns:
        dt = str(out[c].dtype)
        if dt == "Int64":
            out[c] = out[c].astype("int64") if not out[c].isna().any() else out[c].astype("float64")
        elif dt == "boolean":
            out[c] = out[c].fillna(False).astype(bool)
        elif dt.startswith("string"):
            out[c] = out[c].astype(object).where(out[c].notna(), None)
        elif dt.startswith("datetime64"):
            out[c] = out[c].astype("datetime64[ns]")
    return out

def sql_text(s):
    return s.replace("\\\\", "\\\\\\\\").replace("'", "\\\\'")

for name, pdf in gold.items():
    sdf = spark.createDataFrame(to_plain(pdf))
    for c in DATE_COLUMNS.get(name, []):
        sdf = sdf.withColumn(c, F.to_date(c))
    sdf.write.mode("overwrite").option("overwriteSchema", "true").format("delta").saveAsTable(name)
    d = DESCRIPTIONS[name]
    try:
        spark.sql(f"COMMENT ON TABLE {name} IS '{sql_text(d['table'])}'")
        for col, text in d["columns"].items():
            spark.sql(f"ALTER TABLE {name} ALTER COLUMN {col} COMMENT '{sql_text(text)}'")
    except Exception as e:
        print(f"  (descriptions not written for {name}: {e})")
    print(f"wrote {name}")
"""),
code("""
expected = {"fact_trips": 3255678, "dim_station": 194, "dim_date": 731, "dim_hour": 24, "dim_member_type": 3,
            "fact_daily_rentals": 731, "fact_hourly_rentals": 17379}
for t, n in expected.items():
    got = spark.table(t).count()
    print(("OK   " if got == n else "CHECK"), f"{t:22} {got:>10,}  (expected {n:,})")
print("Daily rentals total:", spark.sql("SELECT SUM(total) FROM fact_daily_rentals").first()[0], "(expected 3,292,679)")
display(spark.sql("SELECT region_name, COUNT(*) AS stations FROM dim_station GROUP BY region_name ORDER BY stations DESC"))
"""),
md("""
**Next:** edit the one-row `security_user_region` table to list who may see which region (see the governance guide), then run notebook 02 to build the semantic model.

If region names show as *Region 42* and so on, the station feed's region list could not be downloaded. Upload `system_regions.json` to `Files/raw` and run again, or update `region_name` in `dim_station`.
"""),
])

model_lits = "".join([
    lit("RELATIONSHIPS", spec.RELATIONSHIPS), lit("SORT_BY", spec.SORT_BY), lit("HIDDEN_COLUMNS", spec.HIDDEN_COLUMNS),
    lit("DO_NOT_SUM", spec.DO_NOT_SUM), lit("DATA_CATEGORY", spec.DATA_CATEGORY), lit("HIERARCHIES", spec.HIERARCHIES),
    lit("MEASURES", spec.MEASURES), lit("ROLES", spec.ROLES),
])
TABLE_LIST = list(spec.TABLES.keys())

nb2 = nb([
md("""
# 02 · Build the governed semantic model

Creates a **Direct Lake** semantic model over the lakehouse tables from notebook 01, then adds everything that makes it the single trusted source: relationships, the date table, sort orders, hidden keys, a calendar hierarchy, **44 agreed measures** (including the sentences that rewrite themselves for any filter), and **row-level and object-level security**.

Run it in the same workspace as the lakehouse. Running it again rebuilds the model from scratch (`OVERWRITE = True`), so make model changes here, or in Git, and not by hand in the service.
"""),
code("%pip install -q semantic-link-labs"),
code(f'''
MODEL = "Capital Bikeshare"          # semantic model name
LAKEHOUSE = "bike_lakehouse"         # the lakehouse notebook 01 wrote to
WORKSPACE = None                     # None = this notebook's workspace
OVERWRITE = True
TABLES = {TABLE_LIST!r}
''' + "\n" + model_lits),
code("""
import sempy.fabric as fabric
from sempy_labs.directlake import generate_direct_lake_semantic_model

generate_direct_lake_semantic_model(dataset=MODEL, tables=TABLES, source=LAKEHOUSE, source_type="Lakehouse",
                                    workspace=WORKSPACE, refresh=False, overwrite=OVERWRITE)
print("Created", MODEL)
"""),
code("""
from sempy_labs.tom import connect_semantic_model

with connect_semantic_model(dataset=MODEL, readonly=False, workspace=WORKSPACE) as tom:
    T = tom.model.Tables

    have = {(r.FromTable.Name, r.FromColumn.Name, r.ToTable.Name, r.ToColumn.Name) for r in tom.model.Relationships}
    for ft, fc, tt, tc, active in RELATIONSHIPS:
        if (ft, fc, tt, tc) not in have:
            tom.add_relationship(from_table=ft, from_column=fc, to_table=tt, to_column=tc,
                                 from_cardinality="Many", to_cardinality="One", is_active=active)

    tom.mark_as_date_table(table_name="dim_date", column_name="date")

    for t, c, s in SORT_BY:
        T[t].Columns[c].SortByColumn = T[t].Columns[s]
    for t, c in HIDDEN_COLUMNS:
        T[t].Columns[c].IsHidden = True
    for t, c in DO_NOT_SUM:
        tom.set_summarize_by(table_name=t, column_name=c, value="None")
    for t, c, cat in DATA_CATEGORY:
        T[t].Columns[c].DataCategory = cat
    T["security_user_region"].IsHidden = True

    for t, name, cols in HIERARCHIES:
        if name not in [h.Name for h in T[t].Hierarchies]:
            tom.add_hierarchy(table_name=t, hierarchy_name=name, columns=cols)

    have_m = {m.Name for m in tom.all_measures()}
    for home, folder, name, expr, fmt, desc in MEASURES:
        if name in have_m:
            m = T[home].Measures[name]
            m.Expression, m.DisplayFolder, m.Description = expr, folder, desc
            if fmt: m.FormatString = fmt
        else:
            tom.add_measure(table_name=home, measure_name=name, expression=expr, format_string=fmt,
                            display_folder=folder, description=desc)

    have_r = {r.Name for r in tom.model.Roles}
    for role, permission, desc, filters, ols in ROLES:
        if role not in have_r:
            tom.add_role(role_name=role, model_permission=permission, description=desc)
        for t, f in filters:
            tom.set_rls(role_name=role, table_name=t, filter_expression=f)
        for t, c, p in ols:
            tom.set_ols(role_name=role, table_name=t, column_name=c, permission=p)

print("Model updated: relationships, date table, formatting, measures and security.")
"""),
code("""
fabric.refresh_dataset(dataset=MODEL, workspace=WORKSPACE)
print("Refresh requested. Give it a minute, then run the checks below.")
"""),
code("""
# Every number here should match the dashboard and the expected values.
q = '''
EVALUATE
ROW (
    "Trips", [Trips], "Rentals", [Rentals], "Member Share", [Member Share], "Registered Share", [Registered Share],
    "Busiest Day", [Busiest Day], "Busiest Day Rentals", [Busiest Day Rentals],
    "Quietest Day", [Quietest Day], "Quietest Day Rentals", [Quietest Day Rentals],
    "Morning Peak Hour", [Morning Peak Hour], "Evening Peak Hour", [Evening Peak Hour],
    "Active Stations", [Active Stations], "Summary Text", [Summary Text]
)'''
display(fabric.evaluate_dax(dataset=MODEL, dax_string=q, workspace=WORKSPACE))
print('''Expected: Trips 3,255,678 · Rentals 3,292,679 · Member Share 81.0% · Registered Share 81.2%
Busiest 15 Sep 2012 (8,714) · Quietest 29 Oct 2012 (22) · Morning peak 8am · Evening peak 5pm · Active stations 194''')

q2 = '''
EVALUATE
TOPN ( 3, SUMMARIZECOLUMNS ( dim_station[station_name], "Trips", [Trips] ), [Trips], DESC )'''
display(fabric.evaluate_dax(dataset=MODEL, dax_string=q2, workspace=WORKSPACE))
print("Expected top station: Massachusetts Ave & Dupont Circle NW, 107,162")

q3 = '''
EVALUATE
CALCULATETABLE (
    ROW ( "Downtown arrivals 8am", [Downtown Arrivals], "Downtown departures 8am", [Downtown Departures] ),
    dim_hour[hour] = 8, dim_date[is_working_day] = TRUE ()
)'''
display(fabric.evaluate_dax(dataset=MODEL, dax_string=q3, workspace=WORKSPACE))
print("Expected over the 500 working days: 91,405 arrivals and 32,618 departures")
"""),
md("""
**Next:** follow the governance guide: give people access through workspace roles, add members to the two security roles in the model's *Security* settings, apply a sensitivity label, endorse the model, and connect the workspace to Git.
"""),
])

json.dump(nb1, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'notebooks', '01_build_lakehouse.ipynb'), 'w'), indent=1, ensure_ascii=False)
json.dump(nb2, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'notebooks', '02_build_semantic_model.ipynb'), 'w'), indent=1, ensure_ascii=False)
print(len(spec.MEASURES), 'measures')

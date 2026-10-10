import re, json, os, io, zipfile, datetime
import pandas as pd
import numpy as np

EXPORT_DIR = "/lakehouse/default/Files/exports/dashboard"

# Every query asks the certified semantic model, so the numbers use its measures and definitions.
QUERIES = {
    "working_days": """
EVALUATE ROW ( "working_days", CALCULATE ( COUNTROWS ( dim_date ), dim_date[is_working_day] = TRUE () ) )""",
    "day": """
EVALUATE
SUMMARIZECOLUMNS (
    dim_date[date], dim_date[year], dim_date[season_sort], dim_date[month], dim_date[is_holiday],
    dim_date[weekday_num], dim_date[is_working_day], dim_date[weather_code], dim_date[temp_c],
    "casual", [Casual Rentals], "registered", [Registered Rentals], "cnt", [Rentals]
)""",
    "hour": """
DEFINE
    MEASURE fact_hourly_rentals[_casual] = SUM ( fact_hourly_rentals[casual] )
    MEASURE fact_hourly_rentals[_registered] = SUM ( fact_hourly_rentals[registered] )
    MEASURE fact_hourly_rentals[_total] = SUM ( fact_hourly_rentals[total] )
EVALUATE
SUMMARIZECOLUMNS (
    dim_date[date], dim_date[is_working_day], dim_hour[hour],
    "casual", [_casual], "registered", [_registered], "cnt", [_total]
)""",
    "stations": """
EVALUATE
SUMMARIZECOLUMNS (
    dim_station[station_key], dim_station[station_name], dim_station[latitude], dim_station[longitude],
    dim_station[is_position_approximate], dim_station[is_mapped], dim_station[first_trip_date],
    "starts", [Trips], "ends", [Trips Ended], "member_share", [Member Share]
)""",
    "station_month": """
EVALUATE SUMMARIZECOLUMNS ( dim_station[station_key], dim_date[year_month], "starts", [Trips] )""",
    "station_hour": """
EVALUATE
SUMMARIZECOLUMNS (
    dim_station[station_key], dim_hour[hour], TREATAS ( { TRUE () }, dim_date[is_working_day] ),
    "starts", [Trips], "ends", [Trips Ended]
)""",
    "pairs": """
EVALUATE
SUMMARIZECOLUMNS ( fact_trips[start_station_key], fact_trips[end_station_key], "trips", [Trips], "member_share", [Member Share] )""",
    "pair_hour": """
EVALUATE
SUMMARIZECOLUMNS (
    fact_trips[start_station_key], fact_trips[end_station_key], fact_trips[start_hour],
    TREATAS ( { TRUE () }, dim_date[is_working_day] ), "trips", [Trips]
)""",
    "pair_month": """
EVALUATE SUMMARIZECOLUMNS ( fact_trips[start_station_key], fact_trips[end_station_key], dim_date[year_month], "trips", [Trips] )""",
    "totals": """
EVALUATE ROW ( "trips", [Trips], "rentals", [Rentals] )""",
}


def clean(df):
    """'dim_date[date]' -> 'date', '[cnt]' -> 'cnt'."""
    df = df.copy()
    df.columns = [re.sub(r"^.*\[(.*)\]$", r"\1", str(c)) for c in df.columns]
    return df


def shape(R, model_name, exported_at):
    """Turn the model's query results into the files the dashboard reads. R maps query name -> DataFrame."""
    R = {k: clean(v) for k, v in R.items()}
    nwd = int(R["working_days"]["working_days"].iloc[0])
    ymd = lambda s: pd.to_datetime(s).dt.strftime("%Y-%m-%d")
    out = {}

    d = R["day"].sort_values("date")
    out["day"] = pd.DataFrame({
        "dteday": ymd(d["date"]), "yr": (d["year"].astype(int) - 2011), "season": d["season_sort"].astype(int),
        "mnth": d["month"].astype(int), "holiday": d["is_holiday"].astype(bool).astype(int),
        "weekday": (d["weekday_num"].astype(int) % 7), "workingday": d["is_working_day"].astype(bool).astype(int),
        "weathersit": d["weather_code"].astype(int), "temp_c": d["temp_c"].astype(float).round(1),
        "casual": d["casual"].astype(int), "registered": d["registered"].astype(int), "cnt": d["cnt"].astype(int),
    })

    h = R["hour"].sort_values(["date", "hour"])
    out["hour"] = pd.DataFrame({
        "dteday": ymd(h["date"]), "hr": h["hour"].astype(int), "workingday": h["is_working_day"].astype(bool).astype(int),
        "casual": h["casual"].astype(int), "registered": h["registered"].astype(int), "cnt": h["cnt"].astype(int),
    })

    s = R["stations"]
    s = s[s["is_mapped"].astype(bool)].copy()
    mapped = set(s["station_key"].astype(int))
    out["map_stations"] = pd.DataFrame({
        "num": s["station_key"].astype(int), "name": s["station_name"].astype(str).str.strip(),
        "lat": s["latitude"].astype(float).round(5), "lon": s["longitude"].astype(float).round(5),
        "approx": s["is_position_approximate"].astype(bool), "first_month": pd.to_datetime(s["first_trip_date"]).dt.strftime("%Y-%m"),
        "starts": s["starts"].fillna(0).astype(int), "ends": s["ends"].fillna(0).astype(int),
        "member_share": s["member_share"].astype(float).round(3),
    }).sort_values("num")

    sm = R["station_month"]
    sm = sm[sm["station_key"].astype(int).isin(mapped)]
    out["map_station_month"] = pd.DataFrame({"num": sm["station_key"].astype(int), "ym": sm["year_month"].astype(str), "starts": sm["starts"].astype(int)})

    sh = R["station_hour"]
    sh = sh[sh["station_key"].astype(int).isin(mapped)]
    out["map_station_hour"] = pd.DataFrame({
        "num": sh["station_key"].astype(int), "hr": sh["hour"].astype(int),
        "starts": (sh["starts"].fillna(0) / nwd).round(2), "ends": (sh["ends"].fillna(0) / nwd).round(2),
    })

    def pairs(df):
        df = df.rename(columns={"start_station_key": "from", "end_station_key": "to"}).copy()
        df["from"] = df["from"].astype(int); df["to"] = df["to"].astype(int)
        return df[df["from"].isin(mapped) & df["to"].isin(mapped)]

    P = pairs(R["pairs"]); P["trips"] = P["trips"].astype(int)
    PH = pairs(R["pair_hour"]).rename(columns={"start_hour": "hr"}); PH["hr"] = PH["hr"].astype(int)
    PM = pairs(R["pair_month"]).rename(columns={"year_month": "ym"}); PM["ym"] = PM["ym"].astype(str)
    O, OH = P[P["from"] != P["to"]], PH[PH["from"] != PH["to"]]

    # busiest routes: top 150 overall plus the top 12 in each working-day hour
    keep = set(map(tuple, O.nlargest(150, "trips")[["from", "to"]].values))
    for _, grp in OH.groupby("hr"):
        keep |= set(map(tuple, grp.nlargest(12, "trips")[["from", "to"]].values))
    inkeep = lambda df: df[[(a, b) in keep for a, b in zip(df["from"], df["to"])]]
    R_ = inkeep(O)
    out["map_routes"] = pd.DataFrame({"from": R_["from"], "to": R_["to"], "trips": R_["trips"], "member_share": R_["member_share"].astype(float).round(3)})
    rh = inkeep(OH)
    out["map_route_hour"] = pd.DataFrame({"from": rh["from"], "to": rh["to"], "hr": rh["hr"], "trips": (rh["trips"] / nwd).round(3)})
    rm = inkeep(PM[PM["from"] != PM["to"]])
    out["map_route_month"] = pd.DataFrame({"from": rm["from"], "to": rm["to"], "ym": rm["ym"], "trips": rm["trips"].astype(int)})

    # each station's five most common destinations and origins
    od = O.sort_values(["from", "trips"], ascending=[True, False]).groupby("from").head(5).copy()
    od["rank"] = od.groupby("from").cumcount() + 1
    od = pd.DataFrame({"num": od["from"], "dir": "out", "rank": od["rank"], "other": od["to"], "trips": od["trips"]})
    oi = O.sort_values(["to", "trips"], ascending=[True, False]).groupby("to").head(5).copy()
    oi["rank"] = oi.groupby("to").cumcount() + 1
    oi = pd.DataFrame({"num": oi["to"], "dir": "in", "rank": oi["rank"], "other": oi["from"], "trips": oi["trips"]})
    out["map_station_links"] = pd.concat([od, oi], ignore_index=True)
    links = set(zip(od["num"], od["other"])) | set(zip(oi["other"], oi["num"]))
    inl = lambda df: df[[(a, b) in links for a, b in zip(df["from"], df["to"])]]
    lh = inl(OH)
    out["map_link_hour"] = pd.DataFrame({"from": lh["from"], "to": lh["to"], "hr": lh["hr"], "trips": (lh["trips"] / nwd).round(3)})
    lm = inl(PM[PM["from"] != PM["to"]])
    out["map_link_month"] = pd.DataFrame({"from": lm["from"], "to": lm["to"], "ym": lm["ym"], "trips": lm["trips"].astype(int)})

    tot = R["totals"]
    out["map_summary"] = pd.DataFrame([{
        "trips_total": int(tot["trips"].iloc[0]), "trips_mapped": int(P["trips"].sum()),
        "stations": int(len(out["map_stations"])), "working_days": nwd,
    }])
    out["export_manifest"] = pd.DataFrame([{
        "exported_at": exported_at, "export_date": exported_at[:10], "source": f"{model_name} semantic model (Microsoft Fabric)",
        "trips": int(tot["trips"].iloc[0]), "rentals": int(tot["rentals"].iloc[0]),
    }])
    return out


def write_zip(out, folder):
    os.makedirs(folder, exist_ok=True)
    zpath = os.path.join(folder, "dashboard_export.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for name, df in out.items():
            z.writestr(f"{name}.json", df.to_json(orient="records"))
    return zpath

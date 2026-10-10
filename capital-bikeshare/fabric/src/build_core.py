# ---- Settings -------------------------------------------------------------
# In Fabric, attach your lakehouse as the notebook's default lakehouse; its Files area is mounted here.
FILES = "/lakehouse/default/Files"
RAW = f"{FILES}/raw"

SOURCES = {
    "trips_2011": ("https://s3.amazonaws.com/capitalbikeshare-data/2011-capitalbikeshare-tripdata.zip", "2011-capitalbikeshare-tripdata.zip"),
    "trips_2012": ("https://s3.amazonaws.com/capitalbikeshare-data/2012-capitalbikeshare-tripdata.zip", "2012-capitalbikeshare-tripdata.zip"),
    "stations":   ("https://gbfs.lyft.com/gbfs/1.1/dca-cabi/en/station_information.json", "station_information.json"),
    "regions":    ("https://gbfs.lyft.com/gbfs/1.1/dca-cabi/en/system_regions.json", "system_regions.json"),
    "uci":        ("https://archive.ics.uci.edu/static/public/275/bike+sharing+dataset.zip", "bike+sharing+dataset.zip"),
}

# Stations used in 2011-2012 that today's feed lists under a new number (matched by name).
RENUMBERED = {31613: 31699, 31051: 31141}
# Closed stations placed at the street corner or landmark they were named after (approximate).
APPROXIMATE = {
    31200: (38.9101, -77.0444),  # Massachusetts Ave & Dupont Circle NW
    31246: (38.9050, -77.0569),  # M St & Pennsylvania Ave NW
    31248: (38.8884, -77.0283),  # Smithsonian-National Mall / Jefferson Dr & 12th St SW
    31614: (38.9000, -76.9915),  # 11th & H St NE
}
# A station that is certainly in Washington, DC; closed stations above take its region.
DC_REFERENCE_STATION = 31201  # 15th & P St NW
# Downtown box used by the "Downtown" measures (roughly Foggy Bottom to Penn Quarter).
DOWNTOWN = dict(lat_min=38.893, lat_max=38.906, lon_min=-77.045, lon_max=-77.018)

WEATHER = {1: "Clear or partly cloudy", 2: "Mist or cloud", 3: "Light rain or snow", 4: "Heavy rain or snow"}
# UCI codes seasons 1-4 starting in late December, so code 1 is winter (its readme labels it "springer").
SEASON = {1: "Winter", 2: "Spring", 3: "Summer", 4: "Fall"}


# ---- Bronze: get the raw files ---------------------------------------------
import os, io, json, zipfile, glob
import pandas as pd
import numpy as np


def fetch_raw(download=True):
    """Download each source into Files/raw unless it is already there. Upload by hand if a download is blocked."""
    os.makedirs(RAW, exist_ok=True)
    status = {}
    for key, (url, name) in SOURCES.items():
        path = f"{RAW}/{name}"
        if os.path.exists(path) and os.path.getsize(path) > 0:
            status[key] = "already in Files/raw"
            continue
        if not download:
            status[key] = "missing"
            continue
        try:
            import requests
            r = requests.get(url, timeout=300)
            r.raise_for_status()
            with open(path, "wb") as f:
                f.write(r.content)
            status[key] = f"downloaded ({len(r.content):,} bytes)"
        except Exception as e:  # noqa: BLE001
            status[key] = f"NOT downloaded: {e}. Upload {name} to Files/raw by hand."
    return status


def read_trips():
    frames = []
    for name in ("2011-capitalbikeshare-tripdata.zip", "2012-capitalbikeshare-tripdata.zip"):
        with zipfile.ZipFile(f"{RAW}/{name}") as z:
            for member in sorted(z.namelist()):
                if member.lower().endswith(".csv"):
                    with z.open(member) as fh:
                        frames.append(pd.read_csv(fh, dtype={"Bike number": "string", "Member type": "string",
                                                              "Start station": "string", "End station": "string"}))
    t = pd.concat(frames, ignore_index=True)
    t.columns = [c.strip() for c in t.columns]
    return t


def read_uci():
    with zipfile.ZipFile(f"{RAW}/bike+sharing+dataset.zip") as z:
        day = pd.read_csv(z.open("day.csv"))
        hour = pd.read_csv(z.open("hour.csv"))
    return day, hour


def read_json(name):
    with open(f"{RAW}/{name}") as f:
        return json.load(f)


# ---- Silver + Gold ---------------------------------------------------------
def build_gold():
    trips_raw = read_trips()
    day, hour = read_uci()
    feed = pd.DataFrame(read_json("station_information.json")["data"]["stations"])
    try:
        regions = pd.DataFrame(read_json("system_regions.json")["data"]["regions"])[["region_id", "name"]]
        regions["region_id"] = regions["region_id"].astype(str)
    except Exception:  # noqa: BLE001
        regions = pd.DataFrame(columns=["region_id", "name"])

    # trips (silver)
    t = pd.DataFrame({
        "start_datetime": pd.to_datetime(trips_raw["Start date"]),
        "end_datetime": pd.to_datetime(trips_raw["End date"]),
        "duration_sec": pd.to_numeric(trips_raw["Duration"], errors="coerce").astype("Int64"),
        "start_station_key": pd.to_numeric(trips_raw["Start station number"], errors="coerce").astype("Int64"),
        "end_station_key": pd.to_numeric(trips_raw["End station number"], errors="coerce").astype("Int64"),
        "start_station_name": trips_raw["Start station"].str.strip(),
        "end_station_name": trips_raw["End station"].str.strip(),
        "bike_number": trips_raw["Bike number"],
        "member_type": trips_raw["Member type"].fillna("Unknown").str.strip(),
    })
    t = t.dropna(subset=["start_datetime", "start_station_key", "end_station_key"]).sort_values("start_datetime").reset_index(drop=True)
    t.loc[~t.member_type.isin(["Member", "Casual"]), "member_type"] = "Unknown"

    # dim_station
    used = pd.concat([
        t[["start_datetime", "start_station_key", "start_station_name"]].set_axis(["at", "station_key", "station_name"], axis=1),
        t[["start_datetime", "end_station_key", "end_station_name"]].set_axis(["at", "station_key", "station_name"], axis=1),
    ])
    span = used.groupby("station_key")["at"].agg(["min", "max"])
    names = used.sort_values("at").drop_duplicates("station_key", keep="last").set_index("station_key")["station_name"]
    feed["num"] = pd.to_numeric(feed["short_name"], errors="coerce")
    feed = feed.dropna(subset=["num"]).drop_duplicates("num").set_index("num")
    dc_region = str(feed.loc[DC_REFERENCE_STATION, "region_id"]) if DC_REFERENCE_STATION in feed.index else None
    rows = []
    for key, name in names.items():
        k = int(key)
        lat = lon = None; region = None
        if k in APPROXIMATE:
            lat, lon = APPROXIMATE[k]; source = "Named street corner (approximate)"; region = dc_region
        elif RENUMBERED.get(k, k) in feed.index:
            f = feed.loc[RENUMBERED.get(k, k)]
            lat, lon = float(f["lat"]), float(f["lon"]); region = str(f.get("region_id")) if pd.notna(f.get("region_id")) else None
            source = "Station feed (matched by name)" if k in RENUMBERED else "Station feed"
        else:
            source = "Not placed (closed, location unknown)"
        rows.append(dict(station_key=k, station_name=name, latitude=lat, longitude=lon, position_source=source,
                         is_position_approximate=k in APPROXIMATE, is_mapped=lat is not None, region_id=region,
                         first_trip_date=span.loc[key, "min"].normalize(), last_trip_date=span.loc[key, "max"].normalize()))
    st = pd.DataFrame(rows)
    st = st.merge(regions.rename(columns={"name": "region_name"}), on="region_id", how="left")
    st["region_name"] = st["region_name"].fillna(st["region_id"].map(lambda r: f"Region {r}" if isinstance(r, str) else "Unknown"))
    st["is_downtown"] = (st.latitude.between(DOWNTOWN["lat_min"], DOWNTOWN["lat_max"]) & st.longitude.between(DOWNTOWN["lon_min"], DOWNTOWN["lon_max"])).fillna(False)
    dim_station = st.sort_values("station_key").reset_index(drop=True)

    # fact_trips (gold)
    fact_trips = t.drop(columns=["start_station_name", "end_station_name"]).copy()
    fact_trips.insert(0, "trip_id", np.arange(1, len(fact_trips) + 1, dtype="int64"))
    fact_trips["start_date"] = fact_trips.start_datetime.dt.normalize()
    fact_trips["start_hour"] = fact_trips.start_datetime.dt.hour.astype("int32")
    fact_trips["duration_min"] = (fact_trips.duration_sec.astype("float64") / 60).round(2)
    fact_trips["is_round_trip"] = fact_trips.start_station_key == fact_trips.end_station_key

    # dim_date from the UCI daily file (weather lives here)
    d = day.copy()
    d["date"] = pd.to_datetime(d["dteday"])
    dim_date = pd.DataFrame({
        "date": d["date"],
        "date_key": d["date"].dt.strftime("%Y%m%d").astype("int32"),
        "year": d["date"].dt.year.astype("int32"),
        "quarter": ("Q" + d["date"].dt.quarter.astype(str)),
        "month": d["date"].dt.month.astype("int32"),
        "month_name": d["date"].dt.strftime("%B"),
        "month_short": d["date"].dt.strftime("%b"),
        "year_month": d["date"].dt.strftime("%Y-%m"),
        "year_month_sort": (d["date"].dt.year * 100 + d["date"].dt.month).astype("int32"),
        "day_of_month": d["date"].dt.day.astype("int32"),
        "weekday_num": (d["date"].dt.dayofweek + 1).astype("int32"),
        "weekday_name": d["date"].dt.strftime("%A"),
        "weekday_short": d["date"].dt.strftime("%a"),
        "is_holiday": d["holiday"].astype(bool),
        "is_working_day": d["workingday"].astype(bool),
        "day_type": np.where(d["workingday"] == 1, "Working day", "Weekend or holiday"),
        "season": d["season"].map(SEASON),
        "season_sort": d["season"].astype("int32"),
        "weather_code": d["weathersit"].astype("int32"),
        "weather": d["weathersit"].map(WEATHER),
        "weather_group": d["weathersit"].map({1: "Clear", 2: "Mist or cloud", 3: "Rain or snow", 4: "Rain or snow"}),
        "temp_c": (d["temp"] * 41).round(1),
        "feels_like_c": (d["atemp"] * 50).round(1),
        "humidity_pct": (d["hum"] * 100).round(1),
        "wind_speed": (d["windspeed"] * 67).round(1),
    })
    dim_date["temp_band"] = pd.cut(dim_date.temp_c, [-50, 10, 20, 30, 60], right=False,
                                   labels=["Below 10°C", "10–20°C", "20–30°C", "30°C and above"]).astype(str)

    fact_daily = pd.DataFrame({"date": d["date"], "casual": d["casual"].astype("int64"),
                               "registered": d["registered"].astype("int64"), "total": d["cnt"].astype("int64")})

    h = hour.copy()
    fact_hourly = pd.DataFrame({
        "date": pd.to_datetime(h["dteday"]), "hour": h["hr"].astype("int32"),
        "casual": h["casual"].astype("int64"), "registered": h["registered"].astype("int64"), "total": h["cnt"].astype("int64"),
        "weather_code": h["weathersit"].astype("int32"), "weather": h["weathersit"].map(WEATHER),
        "temp_c": (h["temp"] * 41).round(1), "feels_like_c": (h["atemp"] * 50).round(1),
        "humidity_pct": (h["hum"] * 100).round(1), "wind_speed": (h["windspeed"] * 67).round(1),
    })

    def lab(x):
        return "12am" if x == 0 else f"{x}am" if x < 12 else "12pm" if x == 12 else f"{x-12}pm"
    dim_hour = pd.DataFrame({"hour": np.arange(24, dtype="int32")})
    dim_hour["hour_label"] = dim_hour.hour.map(lab)
    dim_hour["hour_range"] = dim_hour.hour.map(lambda x: f"{lab(x)}–{lab((x + 1) % 24)}")
    dim_hour["day_part"] = pd.cut(dim_hour.hour, [-1, 5, 9, 15, 19, 23], labels=["Night", "Morning rush", "Midday", "Evening rush", "Evening"]).astype(str)
    dim_hour["day_part_sort"] = pd.cut(dim_hour.hour, [-1, 5, 9, 15, 19, 23], labels=[1, 2, 3, 4, 5]).astype("int32")

    dim_member_type = pd.DataFrame({"member_type": ["Member", "Casual", "Unknown"], "member_type_sort": np.array([1, 2, 3], dtype="int32"),
                                    "rider_group": ["Registered member", "Casual rider", "Unknown"]})

    security = pd.DataFrame({"user_email": ["someone@yourcompany.com"], "region_name": [dim_station.loc[dim_station.region_id == dc_region, "region_name"].iloc[0] if dc_region else "Unknown"]})

    return {
        "dim_date": dim_date, "dim_hour": dim_hour, "dim_member_type": dim_member_type, "dim_station": dim_station,
        "fact_trips": fact_trips, "fact_daily_rentals": fact_daily, "fact_hourly_rentals": fact_hourly,
        "security_user_region": security,
    }


def checks(g):
    """Quick data checks; each should be True."""
    ft, ds, dd = g["fact_trips"], g["dim_station"], g["dim_date"]
    return {
        "every trip's start station is in dim_station": bool(ft.start_station_key.isin(ds.station_key).all()),
        "every trip's end station is in dim_station": bool(ft.end_station_key.isin(ds.station_key).all()),
        "every trip date is in dim_date": bool(ft.start_date.isin(dd.date).all()),
        "dim_date has 731 unbroken days": bool(len(dd) == 731 and dd.date.diff().dropna().eq(pd.Timedelta(days=1)).all()),
        "station keys are unique": bool(ds.station_key.is_unique),
        "daily totals = registered + casual": bool((g["fact_daily_rentals"].total == g["fact_daily_rentals"].registered + g["fact_daily_rentals"].casual).all()),
        "hourly totals add up to daily totals": bool(g["fact_hourly_rentals"].total.sum() == g["fact_daily_rentals"].total.sum()),
    }

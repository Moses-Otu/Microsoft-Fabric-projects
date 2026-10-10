"""One source of truth for table descriptions, column descriptions, relationships, measures and security.
The notebooks and the docs are generated from this file."""

TABLES = {
    "dim_date": ("One row per day, 1 Jan 2011 to 31 Dec 2012, with calendar attributes and that day's weather (from the UCI daily file). Marked as the model's date table.", {
        "date": "Calendar date. Key for every fact table's date.",
        "date_key": "Date as a number, yyyymmdd.",
        "year": "Calendar year.", "quarter": "Calendar quarter, Q1 to Q4.",
        "month": "Month number, 1 to 12.", "month_name": "Month name, e.g. January. Sorted by month.",
        "month_short": "Short month name, e.g. Jan. Sorted by month.",
        "year_month": "Year and month, e.g. 2011-01. Sorted by year_month_sort.", "year_month_sort": "yyyymm, for sorting.",
        "day_of_month": "Day of the month.", "weekday_num": "Day of the week, Monday = 1 to Sunday = 7.",
        "weekday_name": "Day name, e.g. Monday. Sorted by weekday_num.", "weekday_short": "Short day name, e.g. Mon.",
        "is_holiday": "True on Washington, DC public holidays (from the UCI file).",
        "is_working_day": "True when the day is neither a weekend nor a holiday.",
        "day_type": "Working day, or Weekend or holiday.",
        "season": "Winter, Spring, Summer or Fall. The UCI source codes seasons from late December, so its code 1 is winter even though its readme says 'springer'.",
        "season_sort": "Season order, 1 to 4.",
        "weather_code": "UCI weather situation code, 1 to 4.",
        "weather": "Weather that day: Clear or partly cloudy, Mist or cloud, Light rain or snow, Heavy rain or snow.",
        "weather_group": "Weather in three groups: Clear, Mist or cloud, Rain or snow.",
        "temp_c": "Average temperature, °C (UCI normalised value × 41).",
        "feels_like_c": "Average 'feels like' temperature, °C (UCI normalised value × 50).",
        "humidity_pct": "Average humidity, %.",
        "wind_speed": "Average wind speed (UCI normalised value × 67; the source does not state units).",
        "temp_band": "Temperature band: Below 10°C, 10–20°C, 20–30°C, 30°C and above.",
    }),
    "dim_hour": ("One row per hour of the day.", {
        "hour": "Hour, 0 to 23.", "hour_label": "Hour as text, e.g. 8am. Sorted by hour.",
        "hour_range": "The hour as a range, e.g. 8am–9am. Sorted by hour.",
        "day_part": "Night (0–5), Morning rush (6–9), Midday (10–15), Evening rush (16–19), Evening (20–23).",
        "day_part_sort": "Day part order, 1 to 5.",
    }),
    "dim_member_type": ("Rider types in the trip records.", {
        "member_type": "Member, Casual or Unknown (21 trips have no rider type).",
        "member_type_sort": "Display order.", "rider_group": "Longer label: Registered member, Casual rider, Unknown.",
    }),
    "dim_station": ("Every station used in 2011–2012. Name as used at the time; position from today's Capital Bikeshare station feed matched by station number.", {
        "station_key": "Capital Bikeshare station number (terminal number).",
        "station_name": "Station name as it appeared in the 2011–2012 trip records (latest name used in that period).",
        "latitude": "Latitude. Blank when the station cannot be placed.",
        "longitude": "Longitude. Blank when the station cannot be placed.",
        "position_source": "Where the position comes from: Station feed; Station feed (matched by name) for two renumbered stations; Named street corner (approximate) for four closed stations; or Not placed.",
        "is_position_approximate": "True for the four closed stations placed at their named corner, including Dupont Circle.",
        "is_mapped": "True when the station has a position.",
        "region_id": "Region code from the station feed.",
        "region_name": "Region name from the station feed's region list. Used by row-level security.",
        "is_downtown": "True for stations in the downtown box (latitude 38.893–38.906, longitude −77.045 to −77.018, roughly Foggy Bottom to Penn Quarter).",
        "first_trip_date": "Date of the first trip that started or ended here in 2011–2012.",
        "last_trip_date": "Date of the last trip that started or ended here in 2011–2012.",
    }),
    "fact_trips": ("One row per trip in Capital Bikeshare's public 2011 and 2012 trip files. The operator removes staff trips, test-station trips and trips under 60 seconds, so totals are about 1% below the UCI daily counts.", {
        "trip_id": "Row number assigned at load, in start-time order.",
        "start_datetime": "When the trip started (local time).", "end_datetime": "When the trip ended (local time).",
        "duration_sec": "Trip length in seconds, as published.", "duration_min": "Trip length in minutes.",
        "start_station_key": "Start station. Active relationship to dim_station.",
        "end_station_key": "End station. Inactive relationship to dim_station, used by the 'ended' and 'arrivals' measures.",
        "bike_number": "Bike identifier. Hidden from the Region viewers role.",
        "member_type": "Member, Casual or Unknown.",
        "start_date": "Date the trip started. Relationship to dim_date.",
        "start_hour": "Hour the trip started, 0 to 23. Relationship to dim_hour.",
        "is_round_trip": "True when the trip started and ended at the same station.",
    }),
    "fact_daily_rentals": ("Daily rental totals from the UCI Bike Sharing dataset (Capital Bikeshare, 2011–2012). The reference for city-wide daily counts and weather analysis.", {
        "date": "Date. Relationship to dim_date.", "casual": "Rentals by casual riders.",
        "registered": "Rentals by registered members.", "total": "All rentals.",
    }),
    "fact_hourly_rentals": ("Hourly rental totals from the UCI Bike Sharing dataset, with that hour's weather.", {
        "date": "Date. Relationship to dim_date.", "hour": "Hour, 0 to 23. Relationship to dim_hour.",
        "casual": "Rentals by casual riders.", "registered": "Rentals by registered members.", "total": "All rentals.",
        "weather_code": "UCI weather situation code for the hour.", "weather": "Weather in that hour.",
        "temp_c": "Temperature, °C.", "feels_like_c": "'Feels like' temperature, °C.",
        "humidity_pct": "Humidity, %.", "wind_speed": "Wind speed (UCI normalised value × 67).",
    }),
    "security_user_region": ("Who may see which region, for row-level security. One row per person per region. Hidden in the model.", {
        "user_email": "The person's sign-in (user principal name), in lower case.",
        "region_name": "A region_name from dim_station they may see.",
    }),
}

RELATIONSHIPS = [  # from_table, from_column, to_table, to_column, active
    ("fact_trips", "start_date", "dim_date", "date", True),
    ("fact_trips", "start_hour", "dim_hour", "hour", True),
    ("fact_trips", "member_type", "dim_member_type", "member_type", True),
    ("fact_trips", "start_station_key", "dim_station", "station_key", True),
    ("fact_trips", "end_station_key", "dim_station", "station_key", False),
    ("fact_daily_rentals", "date", "dim_date", "date", True),
    ("fact_hourly_rentals", "date", "dim_date", "date", True),
    ("fact_hourly_rentals", "hour", "dim_hour", "hour", True),
]

SORT_BY = [  # table, column, sort by column
    ("dim_date", "month_name", "month"), ("dim_date", "month_short", "month"),
    ("dim_date", "weekday_name", "weekday_num"), ("dim_date", "weekday_short", "weekday_num"),
    ("dim_date", "year_month", "year_month_sort"), ("dim_date", "season", "season_sort"),
    ("dim_hour", "hour_label", "hour"), ("dim_hour", "hour_range", "hour"), ("dim_hour", "day_part", "day_part_sort"),
    ("dim_member_type", "member_type", "member_type_sort"),
]

HIDDEN_COLUMNS = [
    ("fact_trips", c) for c in ["trip_id", "start_date", "start_hour", "member_type", "start_station_key", "end_station_key"]
] + [("fact_daily_rentals", "date"), ("fact_hourly_rentals", "date"), ("fact_hourly_rentals", "hour"),
     ("dim_date", "year_month_sort"), ("dim_date", "season_sort"), ("dim_hour", "day_part_sort"),
     ("dim_member_type", "member_type_sort"), ("dim_station", "region_id")]

DO_NOT_SUM = [("dim_date", c) for c in ["date_key", "year", "month", "day_of_month", "weekday_num", "weather_code", "year_month_sort", "season_sort"]] + \
    [("dim_hour", "hour"), ("dim_hour", "day_part_sort"), ("dim_station", "station_key"), ("dim_station", "latitude"), ("dim_station", "longitude"),
     ("fact_trips", "trip_id"), ("fact_trips", "start_station_key"), ("fact_trips", "end_station_key"), ("fact_trips", "start_hour"),
     ("fact_hourly_rentals", "hour"), ("fact_hourly_rentals", "weather_code"), ("dim_member_type", "member_type_sort")]

DATA_CATEGORY = [("dim_station", "latitude", "Latitude"), ("dim_station", "longitude", "Longitude")]

HIERARCHIES = [("dim_date", "Calendar", ["year", "quarter", "month_name", "date"])]

# ---- Measures: (home table, folder, name, DAX, format string, description) ----
SR = 'SELECTEDVALUE ( dim_member_type[member_type] )'
MEASURES = [
    # Trips (trip records)
    ("fact_trips", "Trips", "Trips", "COUNTROWS ( fact_trips )", "#,0", "Number of trips in the trip records, counted at the start station."),
    ("fact_trips", "Trips", "Trips Ended", "CALCULATE ( [Trips], USERELATIONSHIP ( fact_trips[end_station_key], dim_station[station_key] ) )", "#,0", "Trips counted at the end station. Use with station fields to see arrivals."),
    ("fact_trips", "Trips", "Member Trips", 'CALCULATE ( [Trips], KEEPFILTERS ( dim_member_type[member_type] = "Member" ) )', "#,0", "Trips by registered members."),
    ("fact_trips", "Trips", "Casual Trips", 'CALCULATE ( [Trips], KEEPFILTERS ( dim_member_type[member_type] = "Casual" ) )', "#,0", "Trips by casual riders."),
    ("fact_trips", "Trips", "Member Share", "DIVIDE ( [Member Trips], [Trips] )", "0.0%", "Share of trips taken by registered members."),
    ("fact_trips", "Trips", "Round Trips", "CALCULATE ( [Trips], KEEPFILTERS ( fact_trips[is_round_trip] = TRUE () ) )", "#,0", "Trips that ended where they started."),
    ("fact_trips", "Trips", "Average Trip Minutes", "AVERAGE ( fact_trips[duration_min] )", "0.0", "Average trip length in minutes."),
    ("fact_trips", "Trips", "Median Trip Minutes", "MEDIAN ( fact_trips[duration_min] )", "0.0", "Middle trip length in minutes; less affected by very long trips."),
    ("fact_trips", "Trips", "Active Stations", "DISTINCTCOUNT ( fact_trips[start_station_key] )", "#,0", "Stations where at least one trip started."),
    ("fact_trips", "Trips", "Trips per Day", "DIVIDE ( [Trips], DISTINCTCOUNT ( fact_trips[start_date] ) )", "#,0", "Average trips per day that had trips."),
    ("fact_trips", "Trips\\Downtown", "Downtown Departures", "CALCULATE ( [Trips], KEEPFILTERS ( dim_station[is_downtown] = TRUE () ) )", "#,0", "Trips that started at a downtown station."),
    ("fact_trips", "Trips\\Downtown", "Downtown Arrivals", "CALCULATE ( [Trips], USERELATIONSHIP ( fact_trips[end_station_key], dim_station[station_key] ), KEEPFILTERS ( dim_station[is_downtown] = TRUE () ) )", "#,0", "Trips that ended at a downtown station."),
    ("fact_trips", "Trips\\Downtown", "Downtown Net Arrivals", "[Downtown Arrivals] - [Downtown Departures]", "#,0;-#,0", "Arrivals minus departures downtown. Positive in the morning rush, negative in the evening."),
    ("fact_trips", "Data quality", "Trips at Unplaced Stations", "CALCULATE ( [Trips], KEEPFILTERS ( dim_station[is_mapped] = FALSE () ) )", "#,0", "Trips starting at a station with no known position."),

    # Rentals (UCI daily totals)
    ("fact_daily_rentals", "Rentals", "Rentals", "SUM ( fact_daily_rentals[total] )", "#,0", "All rentals in the UCI daily totals."),
    ("fact_daily_rentals", "Rentals", "Registered Rentals", "SUM ( fact_daily_rentals[registered] )", "#,0", "Rentals by registered members."),
    ("fact_daily_rentals", "Rentals", "Casual Rentals", "SUM ( fact_daily_rentals[casual] )", "#,0", "Rentals by casual riders."),
    ("fact_daily_rentals", "Rentals", "Registered Share", "DIVIDE ( [Registered Rentals], [Rentals] )", "0.0%", "Share of rentals by registered members."),
    ("fact_daily_rentals", "Rentals", "Days", "COUNTROWS ( fact_daily_rentals )", "#,0", "Number of days in the current selection."),
    ("fact_daily_rentals", "Rentals", "Avg Daily Rentals", "DIVIDE ( [Rentals], [Days] )", "#,0", "Average rentals per day."),
    ("fact_daily_rentals", "Rentals\\Rider slicer", "Selected Rider Rentals", f'SWITCH ( {SR}, "Member", [Registered Rentals], "Casual", [Casual Rentals], [Rentals] )', "#,0", "Rentals for the rider type picked on a dim_member_type slicer (all riders when none or several are picked)."),
    ("fact_daily_rentals", "Rentals\\Rider slicer", "Selected Rider Avg Daily", "DIVIDE ( [Selected Rider Rentals], [Days] )", "#,0", "Average rentals per day for the picked rider type."),
    ("fact_daily_rentals", "Rentals\\Year on year", "Selected Rider Avg Daily LY", "CALCULATE ( [Selected Rider Avg Daily], SAMEPERIODLASTYEAR ( dim_date[date] ) )", "#,0", "The same measure on the same dates a year earlier."),
    ("fact_daily_rentals", "Rentals\\Year on year", "Selected Rider YoY %",
     "VAR firstDay = MIN ( fact_daily_rentals[date] )\nVAR cur = [Selected Rider Avg Daily]\nVAR ly = [Selected Rider Avg Daily LY]\nRETURN\n    IF ( firstDay >= DATE ( 2012, 1, 1 ) && NOT ISBLANK ( ly ), DIVIDE ( cur - ly, ly ) )",
     "+0.0%;-0.0%;0.0%", "Change in rentals per day against the same dates in 2011. Only shown when the selection is within 2012, so it never compares against partial data."),
    ("fact_daily_rentals", "Rentals\\Extremes", "Busiest Day",
     'VAR t = FILTER ( ADDCOLUMNS ( VALUES ( dim_date[date] ), "@r", [Selected Rider Rentals] ), NOT ISBLANK ( [@r] ) )\nRETURN MAXX ( TOPN ( 1, t, [@r], DESC ), dim_date[date] )', "d mmm yyyy", "Day with the most rentals in the selection."),
    ("fact_daily_rentals", "Rentals\\Extremes", "Busiest Day Rentals",
     'VAR t = FILTER ( ADDCOLUMNS ( VALUES ( dim_date[date] ), "@r", [Selected Rider Rentals] ), NOT ISBLANK ( [@r] ) )\nRETURN MAXX ( t, [@r] )', "#,0", "Rentals on the busiest day."),
    ("fact_daily_rentals", "Rentals\\Extremes", "Quietest Day",
     'VAR t = FILTER ( ADDCOLUMNS ( VALUES ( dim_date[date] ), "@r", [Selected Rider Rentals] ), NOT ISBLANK ( [@r] ) )\nRETURN MAXX ( TOPN ( 1, t, [@r], ASC ), dim_date[date] )', "d mmm yyyy", "Day with the fewest rentals in the selection."),
    ("fact_daily_rentals", "Rentals\\Extremes", "Quietest Day Rentals",
     'VAR t = FILTER ( ADDCOLUMNS ( VALUES ( dim_date[date] ), "@r", [Selected Rider Rentals] ), NOT ISBLANK ( [@r] ) )\nRETURN MINX ( t, [@r] )', "#,0", "Rentals on the quietest day."),
    ("fact_daily_rentals", "Rentals\\Weather", "Avg Daily Rentals Clear", 'CALCULATE ( [Selected Rider Avg Daily], KEEPFILTERS ( dim_date[weather_group] = "Clear" ) )', "#,0", "Average rentals per day on clear days."),
    ("fact_daily_rentals", "Rentals\\Weather", "Avg Daily Rentals Rain or Snow", 'CALCULATE ( [Selected Rider Avg Daily], KEEPFILTERS ( dim_date[weather_group] = "Rain or snow" ) )', "#,0", "Average rentals per day on days with rain or snow."),
    ("fact_daily_rentals", "Rentals\\Weather", "Rain or Snow Drop %", "DIVIDE ( [Avg Daily Rentals Clear] - [Avg Daily Rentals Rain or Snow], [Avg Daily Rentals Clear] )", "0.0%", "How much lower rentals are on rain or snow days than on clear days."),

    # Hourly (UCI hourly totals)
    ("fact_hourly_rentals", "Hourly", "Hourly Rentals", f'SWITCH ( {SR}, "Member", SUM ( fact_hourly_rentals[registered] ), "Casual", SUM ( fact_hourly_rentals[casual] ), SUM ( fact_hourly_rentals[total] ) )', "#,0", "Rentals in the hourly totals, for the picked rider type."),
    ("fact_hourly_rentals", "Hourly", "Avg Rentals per Hour", "DIVIDE ( [Hourly Rentals], CALCULATE ( DISTINCTCOUNT ( fact_hourly_rentals[date] ), REMOVEFILTERS ( dim_hour ) ) )", "#,0", "Average rentals in each hour across the days selected. Put dim_hour on the axis."),
    ("fact_hourly_rentals", "Hourly", "Morning Peak Hour",
     'VAR t = ADDCOLUMNS ( FILTER ( ALL ( dim_hour[hour] ), dim_hour[hour] >= 6 && dim_hour[hour] <= 9 ), "@r", [Avg Rentals per Hour] )\nVAR h = MAXX ( TOPN ( 1, t, [@r], DESC ), dim_hour[hour] )\nRETURN CALCULATE ( MAX ( dim_hour[hour_label] ), REMOVEFILTERS ( dim_hour ), dim_hour[hour] = h )', None, "Busiest hour between 6am and 10am."),
    ("fact_hourly_rentals", "Hourly", "Morning Peak Rentals",
     'VAR t = ADDCOLUMNS ( FILTER ( ALL ( dim_hour[hour] ), dim_hour[hour] >= 6 && dim_hour[hour] <= 9 ), "@r", [Avg Rentals per Hour] )\nRETURN MAXX ( t, [@r] )', "#,0", "Average rentals in the morning peak hour."),
    ("fact_hourly_rentals", "Hourly", "Evening Peak Hour",
     'VAR t = ADDCOLUMNS ( FILTER ( ALL ( dim_hour[hour] ), dim_hour[hour] >= 15 && dim_hour[hour] <= 19 ), "@r", [Avg Rentals per Hour] )\nVAR h = MAXX ( TOPN ( 1, t, [@r], DESC ), dim_hour[hour] )\nRETURN CALCULATE ( MAX ( dim_hour[hour_label] ), REMOVEFILTERS ( dim_hour ), dim_hour[hour] = h )', None, "Busiest hour between 3pm and 8pm."),
    ("fact_hourly_rentals", "Hourly", "Evening Peak Rentals",
     'VAR t = ADDCOLUMNS ( FILTER ( ALL ( dim_hour[hour] ), dim_hour[hour] >= 15 && dim_hour[hour] <= 19 ), "@r", [Avg Rentals per Hour] )\nRETURN MAXX ( t, [@r] )', "#,0", "Average rentals in the evening peak hour."),
    ("fact_hourly_rentals", "Hourly", "Peak Hour",
     'VAR t = ADDCOLUMNS ( ALL ( dim_hour[hour] ), "@r", [Avg Rentals per Hour] )\nVAR h = MAXX ( TOPN ( 1, t, [@r], DESC ), dim_hour[hour] )\nRETURN CALCULATE ( MAX ( dim_hour[hour_label] ), REMOVEFILTERS ( dim_hour ), dim_hour[hour] = h )', None, "Busiest hour of the day."),
    ("fact_hourly_rentals", "Hourly", "Peak Hour Rentals",
     'VAR t = ADDCOLUMNS ( ALL ( dim_hour[hour] ), "@r", [Avg Rentals per Hour] )\nRETURN MAXX ( t, [@r] )', "#,0", "Average rentals in the busiest hour."),
    ("fact_hourly_rentals", "Hourly", "Midday Average Rentals",
     'AVERAGEX ( FILTER ( ALL ( dim_hour[hour] ), dim_hour[hour] >= 10 && dim_hour[hour] <= 14 ), [Avg Rentals per Hour] )', "#,0", "Average rentals per hour from 10am to 3pm, used to tell a commuting pattern from a leisure one."),

    # Narrative text for cards and text boxes
    ("fact_daily_rentals", "Narrative", "Summary Text",
     'VAR n = [Days]\nVAR d0 = MIN ( fact_daily_rentals[date] )\nVAR d1 = MAX ( fact_daily_rentals[date] )\n'
     f'VAR who = SWITCH ( {SR}, "Member", "registered members", "Casual", "casual riders", "riders" )\n'
     'VAR yoy = [Selected Rider YoY %]\n'
     'VAR main =\n    IF ( n = 1,\n        "On " & FORMAT ( d0, "dddd d mmmm yyyy" ) & ", " & who & " took " & FORMAT ( [Selected Rider Rentals], "#,0" ) & " trips.",\n'
     '        "From " & FORMAT ( d0, "d mmm yyyy" ) & " to " & FORMAT ( d1, "d mmm yyyy" ) & ", " & who & " took " & FORMAT ( [Selected Rider Rentals], "#,0" )\n'
     '            & " trips, an average of " & FORMAT ( [Selected Rider Avg Daily], "#,0" ) & " a day across " & FORMAT ( n, "#,0" ) & " days." )\n'
     'VAR share = IF ( ISBLANK ( ' + SR + ' ), " Registered members made " & FORMAT ( [Registered Share], "0.0%" ) & " of them." )\n'
     'VAR change = IF ( NOT ISBLANK ( yoy ), " Per day, that is " & IF ( yoy >= 0, "up ", "down " ) & FORMAT ( ABS ( yoy ), "0.0%" ) & " on the same dates in 2011." )\n'
     'RETURN IF ( ISBLANK ( n ), "No days match these filters.", main & share & change )',
     None, "Opening sentence of the report. It rewrites itself for whatever is selected."),
    ("fact_daily_rentals", "Narrative", "Extremes Text",
     'IF ( [Days] > 1,\n    "The busiest day was " & FORMAT ( [Busiest Day], "dddd d mmmm yyyy" ) & ", with " & FORMAT ( [Busiest Day Rentals], "#,0" ) & " trips. The quietest was "\n'
     '        & FORMAT ( [Quietest Day], "dddd d mmmm yyyy" ) & ", with " & FORMAT ( [Quietest Day Rentals], "#,0" )\n'
     '        & IF ( [Quietest Day] = DATE ( 2012, 10, 29 ), ", the day Hurricane Sandy reached Washington.", "." ) )',
     None, "The busiest and quietest days in the selection."),
    ("fact_hourly_rentals", "Narrative", "Rush Hour Text",
     'VAR am = [Morning Peak Rentals]\nVAR pm = [Evening Peak Rentals]\nVAR mid = [Midday Average Rentals]\nRETURN\n'
     '    SWITCH ( TRUE (),\n        ISBLANK ( [Peak Hour Rentals] ) || [Peak Hour Rentals] < 3, "There are too few trips in this selection to show a clear daily rhythm.",\n'
     '        am > mid * 1.4 && pm > mid * 1.2,\n            "Riding has two rush hours: a morning peak at " & [Morning Peak Hour] & " with " & FORMAT ( am, "#,0" ) & " trips in the hour, and an evening peak at "\n'
     '                & [Evening Peak Hour] & " with " & FORMAT ( pm, "#,0" ) & ". That is the shape of commuting.",\n'
     '        "There is no real rush hour here. Riding peaks at " & [Peak Hour] & ", with " & FORMAT ( [Peak Hour Rentals], "#,0" ) & " trips in the hour. That is the shape of leisure riding." )',
     None, "Describes the daily rhythm: commuting (two peaks) or leisure (one afternoon peak)."),
    ("fact_daily_rentals", "Narrative", "Weather Text",
     'VAR c = [Avg Daily Rentals Clear]\nVAR w = [Avg Daily Rentals Rain or Snow]\nRETURN\n'
     '    IF ( NOT ISBLANK ( c ) && NOT ISBLANK ( w ),\n        "Weather makes a big difference. Clear days averaged " & FORMAT ( c, "#,0" ) & " trips, against " & FORMAT ( w, "#,0" )\n'
     '            & " on days with rain or snow, a drop of " & FORMAT ( [Rain or Snow Drop %], "0.0%" ) & "." )',
     None, "Compares clear days with rain or snow days, when the selection has both."),
]

# ---- Security ----
ROLES = [
    ("All data", "Read", "Analysts and owners: no row filter.", [], []),
    ("Region viewers", "Read",
     "Sees trips only for stations in the regions listed against their sign-in in security_user_region. Bike numbers are hidden. City-wide UCI daily and hourly totals have no station, so they stay visible in full.",
     [("dim_station", "[region_name] IN CALCULATETABLE ( VALUES ( security_user_region[region_name] ), security_user_region[user_email] = LOWER ( USERPRINCIPALNAME () ) )"),
      ("security_user_region", "[user_email] = LOWER ( USERPRINCIPALNAME () )")],
     [("fact_trips", "bike_number", "None")]),
]

EXPECTED = {}  # filled by the checker with values computed from the same data

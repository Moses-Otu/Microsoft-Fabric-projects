# Data dictionary

These are the eight tables notebook 01 writes to the lakehouse and notebook 02 builds the semantic model on. The same descriptions are stored on the Delta tables and carried into the semantic model, so people see them in the Power BI field list too.

## dim_date

One row per day, 1 Jan 2011 to 31 Dec 2012, with calendar attributes and that day's weather (from the UCI daily file). Marked as the model's date table.

- **date**: Calendar date. Key for every fact table's date.
- **date_key**: Date as a number, yyyymmdd.
- **year**: Calendar year.
- **quarter**: Calendar quarter, Q1 to Q4.
- **month**: Month number, 1 to 12.
- **month_name**: Month name, e.g. January. Sorted by month.
- **month_short**: Short month name, e.g. Jan. Sorted by month.
- **year_month**: Year and month, e.g. 2011-01. Sorted by year_month_sort.
- **year_month_sort**: yyyymm, for sorting.
- **day_of_month**: Day of the month.
- **weekday_num**: Day of the week, Monday = 1 to Sunday = 7.
- **weekday_name**: Day name, e.g. Monday. Sorted by weekday_num.
- **weekday_short**: Short day name, e.g. Mon.
- **is_holiday**: True on Washington, DC public holidays (from the UCI file).
- **is_working_day**: True when the day is neither a weekend nor a holiday.
- **day_type**: Working day, or Weekend or holiday.
- **season**: Winter, Spring, Summer or Fall. The UCI source codes seasons from late December, so its code 1 is winter even though its readme says 'springer'.
- **season_sort**: Season order, 1 to 4.
- **weather_code**: UCI weather situation code, 1 to 4.
- **weather**: Weather that day: Clear or partly cloudy, Mist or cloud, Light rain or snow, Heavy rain or snow.
- **weather_group**: Weather in three groups: Clear, Mist or cloud, Rain or snow.
- **temp_c**: Average temperature, °C (UCI normalised value × 41).
- **feels_like_c**: Average 'feels like' temperature, °C (UCI normalised value × 50).
- **humidity_pct**: Average humidity, %.
- **wind_speed**: Average wind speed (UCI normalised value × 67; the source does not state units).
- **temp_band**: Temperature band: Below 10°C, 10–20°C, 20–30°C, 30°C and above.

## dim_hour

One row per hour of the day.

- **hour**: Hour, 0 to 23.
- **hour_label**: Hour as text, e.g. 8am. Sorted by hour.
- **hour_range**: The hour as a range, e.g. 8am–9am. Sorted by hour.
- **day_part**: Night (0–5), Morning rush (6–9), Midday (10–15), Evening rush (16–19), Evening (20–23).
- **day_part_sort**: Day part order, 1 to 5.

## dim_member_type

Rider types in the trip records.

- **member_type**: Member, Casual or Unknown (21 trips have no rider type).
- **member_type_sort**: Display order.
- **rider_group**: Longer label: Registered member, Casual rider, Unknown.

## dim_station

Every station used in 2011–2012. Name as used at the time; position from today's Capital Bikeshare station feed matched by station number.

- **station_key**: Capital Bikeshare station number (terminal number).
- **station_name**: Station name as it appeared in the 2011–2012 trip records (latest name used in that period).
- **latitude**: Latitude. Blank when the station cannot be placed.
- **longitude**: Longitude. Blank when the station cannot be placed.
- **position_source**: Where the position comes from: Station feed; Station feed (matched by name) for two renumbered stations; Named street corner (approximate) for four closed stations; or Not placed.
- **is_position_approximate**: True for the four closed stations placed at their named corner, including Dupont Circle.
- **is_mapped**: True when the station has a position.
- **region_id**: Region code from the station feed.
- **region_name**: Region name from the station feed's region list. Used by row-level security.
- **is_downtown**: True for stations in the downtown box (latitude 38.893–38.906, longitude −77.045 to −77.018, roughly Foggy Bottom to Penn Quarter).
- **first_trip_date**: Date of the first trip that started or ended here in 2011–2012.
- **last_trip_date**: Date of the last trip that started or ended here in 2011–2012.

## fact_trips

One row per trip in Capital Bikeshare's public 2011 and 2012 trip files. The operator removes staff trips, test-station trips and trips under 60 seconds, so totals are about 1% below the UCI daily counts.

Relationships: start_date → dim_date[date]; start_hour → dim_hour[hour]; member_type → dim_member_type[member_type]; start_station_key → dim_station[station_key]; end_station_key → dim_station[station_key] (inactive; used through USERELATIONSHIP).

- **trip_id**: Row number assigned at load, in start-time order.
- **start_datetime**: When the trip started (local time).
- **end_datetime**: When the trip ended (local time).
- **duration_sec**: Trip length in seconds, as published.
- **duration_min**: Trip length in minutes.
- **start_station_key**: Start station. Active relationship to dim_station.
- **end_station_key**: End station. Inactive relationship to dim_station, used by the 'ended' and 'arrivals' measures.
- **bike_number**: Bike identifier. Hidden from the Region viewers role.
- **member_type**: Member, Casual or Unknown.
- **start_date**: Date the trip started. Relationship to dim_date.
- **start_hour**: Hour the trip started, 0 to 23. Relationship to dim_hour.
- **is_round_trip**: True when the trip started and ended at the same station.

## fact_daily_rentals

Daily rental totals from the UCI Bike Sharing dataset (Capital Bikeshare, 2011–2012). The reference for city-wide daily counts and weather analysis.

Relationships: date → dim_date[date].

- **date**: Date. Relationship to dim_date.
- **casual**: Rentals by casual riders.
- **registered**: Rentals by registered members.
- **total**: All rentals.

## fact_hourly_rentals

Hourly rental totals from the UCI Bike Sharing dataset, with that hour's weather.

Relationships: date → dim_date[date]; hour → dim_hour[hour].

- **date**: Date. Relationship to dim_date.
- **hour**: Hour, 0 to 23. Relationship to dim_hour.
- **casual**: Rentals by casual riders.
- **registered**: Rentals by registered members.
- **total**: All rentals.
- **weather_code**: UCI weather situation code for the hour.
- **weather**: Weather in that hour.
- **temp_c**: Temperature, °C.
- **feels_like_c**: 'Feels like' temperature, °C.
- **humidity_pct**: Humidity, %.
- **wind_speed**: Wind speed (UCI normalised value × 67).

## security_user_region

Who may see which region, for row-level security. One row per person per region. Hidden in the model.

- **user_email**: The person's sign-in (user principal name), in lower case.
- **region_name**: A region_name from dim_station they may see.

## Measures

The model has 44 measures in display folders. Every one is listed with its formula in `model/measures.dax`. The main ones:

- **Trips** (Trips): Number of trips in the trip records, counted at the start station.
- **Trips Ended** (Trips): Trips counted at the end station. Use with station fields to see arrivals.
- **Member Trips** (Trips): Trips by registered members.
- **Casual Trips** (Trips): Trips by casual riders.
- **Member Share** (Trips): Share of trips taken by registered members.
- **Round Trips** (Trips): Trips that ended where they started.
- **Average Trip Minutes** (Trips): Average trip length in minutes.
- **Median Trip Minutes** (Trips): Middle trip length in minutes; less affected by very long trips.
- **Active Stations** (Trips): Stations where at least one trip started.
- **Trips per Day** (Trips): Average trips per day that had trips.
- **Downtown Net Arrivals** (Trips / Downtown): Arrivals minus departures downtown. Positive in the morning rush, negative in the evening.
- **Rentals** (Rentals): All rentals in the UCI daily totals.
- **Registered Rentals** (Rentals): Rentals by registered members.
- **Casual Rentals** (Rentals): Rentals by casual riders.
- **Registered Share** (Rentals): Share of rentals by registered members.
- **Days** (Rentals): Number of days in the current selection.
- **Avg Daily Rentals** (Rentals): Average rentals per day.
- **Selected Rider Rentals** (Rentals / Rider slicer): Rentals for the rider type picked on a dim_member_type slicer (all riders when none or several are picked).
- **Selected Rider YoY %** (Rentals / Year on year): Change in rentals per day against the same dates in 2011. Only shown when the selection is within 2012, so it never compares against partial data.
- **Busiest Day** (Rentals / Extremes): Day with the most rentals in the selection.
- **Peak Hour** (Hourly): Busiest hour of the day.
- **Summary Text** (Narrative): Opening sentence of the report. It rewrites itself for whatever is selected.
- **Extremes Text** (Narrative): The busiest and quietest days in the selection.
- **Rush Hour Text** (Narrative): Describes the daily rhythm: commuting (two peaks) or leisure (one afternoon peak).
- **Weather Text** (Narrative): Compares clear days with rain or snow days, when the selection has both.

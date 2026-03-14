"""
Assembles and transforms unzipped GTFS data into reachability metrics
for the scoring model.

This script calculates the maximum Euclidean distance (in kilometers, straight-line)
reachable from each public transport stop, without transfers, within a specified
time window (e.g., 30 minutes) during morning rush hours. The final output
is exported as a spatial Parquet file containing aggregated stop geometries.
"""

import pandas as pd
import geopandas as gpd
from pathlib import Path
import src.config as cfg


def gtfs_to_seconds(time_series):
    """Converts a GTFS time string column (HH:MM:SS) to total seconds."""
    time_parts = time_series.str.split(":", expand=True).astype(int)
    return time_parts[0] * 3600 + time_parts[1] * 60 + time_parts[2]


def get_stops_reachability(
    path,
    service_id,
    borders,
    epsg,
    time_window_sec: int = cfg.TIME_WINDOW_SEC,
    period_start_sec: int = cfg.ANALYSIS_START_SEC,
    period_end_sec: int = cfg.ANALYSIS_END_SEC,
):
    """
    Calculates the maximum reachability radius (straight-line distance) for public transport stops.

    Args:
        path (str or Path): Path to the folder containing unzipped GTFS data for a single carrier.
        service_id (str): Identifier for the specific schedule to process (e.g., workdays schedule).
        borders (gpd.GeoDataFrame): Polygon used to clip stops strictly to the evaluated area (e.g., city borders).
        epsg (int): EPSG code for the target coordinate reference system.
        time_window_sec (int, optional): Timeframe for calculating maximum reachability in seconds. Defaults to cfg.TIME_WINDOW_SEC.
        period_start_sec (int, optional): Start of the analytical time window in seconds from midnight. Defaults to cfg.ANALYSIS_START_SEC.
        period_end_sec (int, optional): End of the analytical time window in seconds from midnight. Defaults to cfg.ANALYSIS_END_SEC.

    Returns:
        gpd.GeoDataFrame: Aggregated spatial data containing the calculated 'max_reach_km' (Euclidean distance) for each stop.
    """
    # *******************************
    # Load GTFS data
    # *******************************
    stop_times = pd.read_csv(
        Path(path) / "stop_times.txt",
        usecols=["trip_id", "departure_time", "stop_id", "pickup_type"],
    )
    trips = pd.read_csv(
        Path(path) / "trips.txt",
        usecols=["trip_id", "route_id", "service_id", "direction_id"],
    )
    stops = pd.read_csv(
        Path(path) / "stops.txt",
        usecols=["stop_id", "stop_name", "stop_lat", "stop_lon"],
    )
    routes = pd.read_csv(
        Path(path) / "routes.txt",
        usecols=["route_id", "route_short_name", "route_type"],
    )
    # *******************************
    # Filter trips by rush hour
    # *******************************
    trip_starts = pd.merge(stop_times, trips, on="trip_id")[
        ["trip_id", "departure_time"]
    ]

    trip_starts["departure_seconds"] = gtfs_to_seconds(trip_starts["departure_time"])

    trip_starts = trip_starts.groupby("trip_id", as_index=False).agg(
        {"departure_seconds": "min"}
    )

    # Identify trips that start within the given time window
    high_time_trips = trip_starts.query(
        f"departure_seconds>={period_start_sec} and departure_seconds<={period_end_sec}"
    )["trip_id"].array

    # *******************************
    # Spatial filtering
    # *******************************
    stops_gdf = gpd.GeoDataFrame(
        stops,
        geometry=gpd.points_from_xy(stops["stop_lon"], stops["stop_lat"]),
        crs="EPSG:4326",
    )
    stops_gdf = stops_gdf.drop(columns=["stop_lat", "stop_lon"]).to_crs(epsg=epsg)

    # Keep only the stops within the given borders (Polygon)
    stops_in_borders_map = stops_gdf.sjoin(borders, predicate="within")
    stops_in_borders_array = stops_in_borders_map["stop_id"].array

    # *******************************
    # Prepare operational data
    # *******************************
    all_trips = pd.merge(stop_times, trips, how="left", on="trip_id")

    # Filter for stops within borders and a specific schedule
    # (service_id from calendar.txt, e.g., typical workday)
    trips_in_borders = all_trips[all_trips["stop_id"].isin(stops_in_borders_array)]
    workday_trips = trips_in_borders[trips_in_borders["service_id"] == service_id].drop(
        columns="service_id"
    )
    workday_trips = workday_trips.assign(
        departure_seconds=gtfs_to_seconds(workday_trips["departure_time"])
    )
    workday_trips = workday_trips.rename(columns={"stop_id": "starting_stop"}).drop(
        columns="departure_time"
    )

    # Keep only trips within the given time window
    high_time = workday_trips[workday_trips["trip_id"].isin(high_time_trips)].copy()

    # *******************************
    # Calculate reachability within given time window
    # *******************************
    high_time["target_seconds"] = high_time["departure_seconds"] + time_window_sec
    target_stops = (
        high_time[["trip_id", "starting_stop", "departure_seconds"]]
        .copy()
        .rename(columns={"starting_stop": "target_stop"})
    )

    # Sorting required for merge_asof
    high_time = high_time.sort_values("target_seconds")
    target_stops = target_stops.sort_values("departure_seconds")

    # Find the furthest reachable stop within the time window using a backward merge
    furthest_stops = pd.merge_asof(
        left=high_time,
        right=target_stops,
        by="trip_id",
        left_on="target_seconds",
        right_on="departure_seconds",
        direction="backward",
    )
    # Filter out start stops where passenger boarding is prohibited (GTFS pickup_type == 1)
    furthest_stops = furthest_stops[furthest_stops["pickup_type"] != 1].drop(
        columns="pickup_type"
    )

    # *******************************
    # Enrich data with geometries and route details
    # *******************************
    furthest_stops = furthest_stops.merge(routes, how="left", on="route_id").drop(
        columns=["departure_seconds_x", "departure_seconds_y", "target_seconds"]
    )

    # Attach geometries to both starting and target stops
    furthest_stops = (
        furthest_stops.merge(
            stops_in_borders_map,
            how="inner",
            left_on="starting_stop",
            right_on="stop_id",
        )
        .drop(columns="stop_id")
        .rename(
            columns={
                "stop_name": "starting_stop_name",
                "geometry": "starting_stop_location",
            }
        )
        .merge(
            stops_in_borders_map, how="inner", left_on="target_stop", right_on="stop_id"
        )
        .drop(columns="stop_id")
        .rename(
            columns={
                "stop_name": "target_stop_name",
                "geometry": "target_stop_location",
            }
        )
    )
    # Remove the cases where target stop is the same as the starting stop
    furthest_stops = furthest_stops[
        furthest_stops["starting_stop_name"] != furthest_stops["target_stop_name"]
    ]

    # Calculate straight-line distances between starting and target stops
    furthest_stops_clean = gpd.GeoDataFrame(
        furthest_stops[
            [
                "route_short_name",
                "route_type",
                "direction_id",
                "starting_stop_name",
                "starting_stop_location",
                "target_stop_name",
                "target_stop_location",
            ]
        ],
        geometry="starting_stop_location",
        crs=f"EPSG:{epsg}",
    )

    # *******************************
    # Calculate Euclidean distance
    # *******************************
    furthest_stops_clean["max_reach_km"] = (
        furthest_stops_clean.distance(furthest_stops_clean["target_stop_location"])
        / 1000
    )

    # *******************************
    # Aggregate final metrics
    # *******************************

    # Average max reach per route and direction from a given stop
    stop_reach = (
        furthest_stops_clean.groupby(
            [
                "starting_stop_name",
                "starting_stop_location",
                "route_short_name",
                "direction_id",
                "route_type",
            ],
            as_index=False,
        )
        .agg({"max_reach_km": "mean"})
        .rename(
            columns={
                "starting_stop_name": "stop_name",
                "starting_stop_location": "stop_location",
                "route_short_name": "route_number",
            }
        )
    )

    # Sum the average reachability of routes servicing the stop
    final_reachability = (
        stop_reach.groupby(
            [
                "stop_location",
                "stop_name",
                "route_number",
                "direction_id",
                "route_type",
            ],
            as_index=False,
        )
        .agg({"max_reach_km": "sum"})
        .sort_values(by="max_reach_km", ascending=False)
    )
    final_reachability_gdf = gpd.GeoDataFrame(
        final_reachability, geometry="stop_location", crs=f"EPSG:{epsg}"
    )
    return final_reachability_gdf


if __name__ == "__main__":
    city_borders = gpd.read_file(cfg.CITY_BORDERS_GEOJSON).to_crs(epsg=cfg.TARGET_CRS)
    transport_done = []
    for carrier_name, carrier_data in cfg.carriers.items():
        print(f"processing data for carrier {carrier_name}")
        gdf = get_stops_reachability(
            path=carrier_data["dir"],
            service_id=carrier_data["service_id"],
            borders=city_borders,
            epsg=cfg.TARGET_CRS,
        )
        transport_done.append(gdf)
    transport_full = pd.concat(transport_done, ignore_index=True)

    transport_full.to_parquet(cfg.PROCESSED_DIR / "stop_reachability.parquet")

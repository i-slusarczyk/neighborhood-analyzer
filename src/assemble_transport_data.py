import pandas as pd
import geopandas as gpd
from pathlib import Path
import src.config as cfg

mobilis_path = Path("GTFS_KRK_M")
mpk_path = Path("GTFS_KRK_A")
trams_path = Path("GTFS_KRK_T")

city_borders = gpd.read_file(
    "krakow_borders.geojson").to_crs(epsg=cfg.TARGET_CRS)


def gtfs_to_seconds(time_series):
    time_parts = time_series.str.split(":", expand=True).astype(int)
    return time_parts[0] * 3600 + time_parts[1] * 60 + time_parts[2]


def get_stops_reachability(path, service_id, borders, epsg, time_window_sec: int = 1800, rush_hour_start_sec: int = 25200, rush_hour_end_sec: int = 32400):
    stop_times = pd.read_csv(Path(path) / "stop_times.txt",
                             usecols=["trip_id", "departure_time", "stop_id", "pickup_type"])
    trips = pd.read_csv(Path(path) / "trips.txt",
                        usecols=["trip_id", "route_id", "service_id", "direction_id"])
    stops = pd.read_csv(Path(path) / "stops.txt",
                        usecols=["stop_id", "stop_name", "stop_lat", "stop_lon"])
    routes = pd.read_csv(Path(path) / "routes.txt",
                         usecols=["route_id", "route_short_name", "route_type"])

    trip_starts = pd.merge(stop_times, trips, on="trip_id")[
        ["trip_id", "departure_time"]
    ]

    trip_starts["departure_seconds"] = gtfs_to_seconds(
        trip_starts["departure_time"])

    trip_starts = trip_starts.groupby("trip_id", as_index=False).agg(
        {"departure_seconds": "min"}
    )

    high_time_trips = trip_starts.query(
        f"departure_seconds>={rush_hour_start_sec} and departure_seconds<={rush_hour_end_sec}"
    )["trip_id"].array

    stops_gdf = gpd.GeoDataFrame(
        stops,
        geometry=gpd.points_from_xy(
            stops["stop_lon"], stops["stop_lat"]
        ),
        crs="EPSG:4326",
    )
    stops_gdf = stops_gdf.drop(
        columns=["stop_lat", "stop_lon"]).to_crs(epsg=epsg)

    stops_in_borders_map = stops_gdf.sjoin(borders, predicate="within")
    stops_in_borders_array = stops_in_borders_map["stop_id"].array

    all_trips = pd.merge(stop_times, trips,
                         how="left", on="trip_id")
    trips_in_borders = all_trips[all_trips["stop_id"].isin(
        stops_in_borders_array)]
    workday_trips = trips_in_borders[trips_in_borders["service_id"] == service_id].drop(
        columns="service_id"
    )
    workday_trips = workday_trips.assign(departure_seconds=gtfs_to_seconds(
        workday_trips["departure_time"])
    )
    workday_trips = workday_trips.rename(columns={"stop_id": "starting_stop"}).drop(
        columns="departure_time"
    )

    high_time = workday_trips[workday_trips["trip_id"].isin(
        high_time_trips)].copy()

    high_time["target_seconds"] = high_time["departure_seconds"] + \
        time_window_sec
    target_stops = (
        high_time[["trip_id", "starting_stop", "departure_seconds"]]
        .copy()
        .rename(columns={"starting_stop": "target_stop"})
    )

    high_time = high_time.sort_values("target_seconds")
    target_stops = target_stops.sort_values("departure_seconds")

    furthest_stops = pd.merge_asof(
        left=high_time,
        right=target_stops,
        by="trip_id",
        left_on="target_seconds",
        right_on="departure_seconds",
        direction="backward",
    )
    furthest_stops = furthest_stops[furthest_stops["pickup_type"] != 1].drop(
        columns="pickup_type"
    )
    furthest_stops = furthest_stops.merge(
        routes, how="left", on="route_id"
    ).drop(columns=["departure_seconds_x", "departure_seconds_y", "target_seconds"])
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
    furthest_stops = furthest_stops[
        furthest_stops["starting_stop_name"] != furthest_stops["target_stop_name"]
    ]
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
    furthest_stops_clean["max_reach_km"] = (
        furthest_stops_clean.distance(
            furthest_stops_clean["target_stop_location"])
        / 1000
    )
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


trams = get_stops_reachability(
    trams_path, service_id="service_1", borders=city_borders, epsg=cfg.TARGET_CRS
)
mobilis = get_stops_reachability(
    mobilis_path, service_id="1582_PO", borders=city_borders, epsg=cfg.TARGET_CRS
)
mpk = get_stops_reachability(
    mpk_path, service_id="service_1", borders=city_borders, epsg=cfg.TARGET_CRS
)

transport_full = pd.concat([trams, mobilis, mpk], ignore_index=True)

transport_full.to_parquet(cfg.PROCESSED_DIR / "stop_reachability.parquet")

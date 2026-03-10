import math
import geopandas as gpd
import pandas as pd
import shapely
import src.config as cfg


# pin on the map as gpd series
def get_target_point(lon: float, lat: float):
    return gpd.GeoSeries([shapely.Point(lon, lat)], crs="EPSG:4326").to_crs(
        epsg=cfg.TARGET_CRS
    )


# selecting just the points within radius
def points_in_radius(
    gdf: gpd.GeoDataFrame,
    lon: float,
    lat: float,
    radius: int = cfg.BUFFER_RADIUS_METERS,
    add_distance_col: bool = True,
) -> gpd.GeoDataFrame:
    target_point = get_target_point(lon, lat)

    distances = gdf.geometry.distance(target_point.iloc[0])

    mask = distances <= radius
    gdf_filtered = gdf.loc[mask].copy()

    if add_distance_col:
        gdf_filtered["distance"] = distances
    return gdf_filtered


# clipping areas to radius
def clip_to_buffer(
    gdf: gpd.GeoDataFrame,
    lon: float,
    lat: float,
    radius: int = cfg.BUFFER_RADIUS_METERS,
) -> gpd.GeoDataFrame:
    target_point = get_target_point(lon, lat)

    gdf_target_buffer = target_point.buffer(radius)
    gdf_clipped = gpd.clip(gdf, gdf_target_buffer)

    gdf_clipped["distance"] = gdf_clipped.geometry.distance(target_point.iloc[0])
    return gdf_clipped


# applying distance decay function
def apply_distance_decay(
    distances: pd.Series, max_dist: float, optimal_dist: float, power: float = math.e
):
    clipped_dist = distances.clip(lower=optimal_dist, upper=max_dist)

    normalized_dist = (clipped_dist - optimal_dist) / (max_dist - optimal_dist)

    penalty = normalized_dist**power

    return 1 - penalty


def get_count_adjusted(gdf, category, dynamics):
    result_gdf = gdf.copy()
    result_gdf["adjusted_value"] = 0.0

    if result_gdf.empty:
        return result_gdf

    dynamics = dynamics[category]

    for subcategory in dynamics:
        category_max_dist = dynamics[subcategory]["max_dist"]
        category_optimal_dist = dynamics[subcategory]["optimal_dist"]
        category_power = dynamics[subcategory]["power"]

        mask = gdf["category"] == subcategory

        if not mask.any():
            continue

        distances = result_gdf.loc[mask, "distance"]

        result_gdf.loc[mask, "adjusted_value"] = apply_distance_decay(
            distances, category_max_dist, category_optimal_dist, category_power
        )
    return result_gdf


# subtracting area from lower weighted amenities
def intersecting_nature(gdf, weights):
    gdf_polygons = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]

    if gdf_polygons.empty:
        return gdf_polygons

    partial = weights["nature"]["partial"]

    priority_order = sorted(partial, key=partial.get, reverse=True)

    accumulated_layers = gpd.GeoDataFrame(geometry=[], crs=gdf.crs)

    for category in priority_order:
        current_layer = gdf_polygons[gdf_polygons["category"] == category].copy()
        if current_layer.empty:
            continue
        if accumulated_layers.empty:
            accumulated_layers = current_layer.copy()
        else:
            current_layer = gpd.overlay(
                current_layer, accumulated_layers, how="difference", keep_geom_type=True
            )
            accumulated_layers = pd.concat(
                [accumulated_layers, current_layer], ignore_index=True
            )
    return accumulated_layers


# automatically calculating nature threshold based on given radius
def calculate_nature_threshold_exp(
    radius: int = cfg.BUFFER_RADIUS_METERS,
    max_threshold: float = cfg.NATURE_THRESHOLD_MAX,
    steepness=cfg.NATURE_THRESHOLD_STEEPNESS,
) -> float:
    return max_threshold * math.exp(-steepness * radius)


# straightforward - distance from point to the city center
def get_distance_to_center(lon, lat, city_center_lon, city_center_lat):
    center_series = get_target_point(city_center_lon, city_center_lat)
    pin_series = get_target_point(lon, lat)
    return pin_series.distance(center_series).iloc[0]


# sigmoid function assigning points based on distance to city center
def calculate_distance_ratio(
    distance_to_center_m: float,
    midpoint: float = cfg.DIST_TO_CENTER_MIDPOINT,
    steepness: float = cfg.DIST_TO_CENTER_STEEPNESS,
) -> float:
    if distance_to_center_m < 0:
        return 1.0
    ratio = 1.0 / (1.0 + math.exp(steepness * (distance_to_center_m - midpoint)))
    if distance_to_center_m < 200:
        return 1.0
    if ratio < 0.05:
        return 0.0
    return ratio


# bus and tram stops reachability - how many kilometers you can reach without changing
def find_reachability(gdf: gpd.GeoDataFrame):
    # dropping repeated trips, leaving only the ones on the closest stop
    gdf = gdf.sort_values(by="distance", ascending=True)
    gdf = gdf.drop_duplicates(subset=["route_number", "direction_id"], keep="first")
    # leaving only names and geometries for pretty visualization on map
    gdf_pretty = gpd.GeoDataFrame(
        data=(
            gdf.groupby(
                ["stop_location", "stop_name", "distance", "route_type"], as_index=False
            ).agg({"max_reach_km": "sum"})
        ),
        geometry="stop_location",
        crs=gdf.crs,
    )

    return gdf_pretty


# to be added: area lower threshold for parks, distance decay func
def nature_score(
    gdf: gpd.GeoDataFrame,
    weights: dict,
    dynamics,
    radius: int = cfg.BUFFER_RADIUS_METERS,
):
    adjusted_gdf = get_count_adjusted(gdf, "nature", dynamics)

    if not adjusted_gdf.empty:
        adjusted_gdf["area_adjusted"] = (
            adjusted_gdf.area * adjusted_gdf["adjusted_value"]
        )
    else:
        adjusted_gdf["area_adjusted"] = 0.0

    partial = weights["nature"]["partial"]
    threshold = max(calculate_nature_threshold_exp(radius), 0.12)
    global_weight = weights["nature"]["global"]

    area_sum = 0.0

    for category_name, category_weight in partial.items():
        category_gdf = adjusted_gdf[adjusted_gdf["category"] == category_name]
        weighted_area = category_gdf["area_adjusted"].sum() * category_weight
        area_sum += weighted_area

    total_buffer_area = radius**2 * math.pi

    score = min((area_sum / (total_buffer_area * threshold)), 1) * global_weight

    return score


# score for daily infastructure
def daily_score(gdf: gpd.GeoDataFrame, weights: dict, dynamics):
    adjusted_gdf = get_count_adjusted(gdf, "daily", dynamics)

    partial = weights["daily"]["partial"]
    thresholds = weights["daily"]["threshold"]
    global_weight = weights["daily"]["global"]

    score_sum = 0.0

    for category_name, category_weight in partial.items():
        category_count = adjusted_gdf[adjusted_gdf["category"] == category_name][
            "adjusted_value"
        ].sum()

        category_ratio = min(category_count / thresholds[category_name], 1)

        score_sum += category_ratio * category_weight

    return score_sum * global_weight


# access to culture score
def culture_score(
    gdf: gpd.GeoDataFrame, weights: dict, distance_to_center: int, dynamics
):
    adjusted_gdf = get_count_adjusted(gdf, "culture", dynamics)

    partial = weights["culture"]["partial"]
    thresholds = weights["culture"]["threshold"]
    global_weight = weights["culture"]["global"]

    # distance to the city center
    distance_ratio = calculate_distance_ratio(distance_to_center)

    score_sum = distance_ratio * partial["distance_to_center"]

    for category_name, category_weight in partial.items():
        if category_name == "distance_to_center":
            continue
        category_count = adjusted_gdf[adjusted_gdf["category"] == category_name][
            "adjusted_value"
        ].sum()

        category_ratio = min(category_count / thresholds[category_name], 1)

        score_sum += category_ratio * category_weight

    return score_sum * global_weight


# destructor points - meant to be subtracted from base score
def destructors(
    gdf_poi: gpd.GeoDataFrame,
    gdf_industrial: gpd.GeoDataFrame,
    dynamics,
    weights: dict,
    radius: int = cfg.BUFFER_RADIUS_METERS,
):
    adjusted_gdf_poi = get_count_adjusted(gdf_poi, "destructors", dynamics)
    adjusted_gdf_industrial = get_count_adjusted(
        gdf_industrial, "destructors", dynamics
    )

    if not adjusted_gdf_industrial.empty:
        adjusted_gdf_industrial["area_adjusted"] = (
            adjusted_gdf_industrial.area * adjusted_gdf_industrial["adjusted_value"]
        )
        industrial_area = adjusted_gdf_industrial["area_adjusted"].sum()
    else:
        industrial_area = 0.0

    partial = weights["destructors"]["partial"]
    restaurant_threshold = weights["destructors"]["restaurant_threshold"]

    restaurants_count = adjusted_gdf_poi[adjusted_gdf_poi["category"] == "restaurant"][
        "adjusted_value"
    ].sum()
    liquor_stores_count = adjusted_gdf_poi[
        adjusted_gdf_poi["category"] == "liquor_store"
    ]["adjusted_value"].sum()
    abandoned_count = adjusted_gdf_poi[adjusted_gdf_poi["category"] == "abandoned"][
        "adjusted_value"
    ].sum()

    total_buffer_area = radius**2 * math.pi
    industrial_ratio = industrial_area / total_buffer_area * 100

    noise_penalty = max(
        5 * (math.log(restaurants_count + 1, restaurant_threshold + 1) - 1), 0
    )

    industrial_penalty = industrial_ratio ** (3 / 2) * partial["industrial"]
    liquor_penalty = liquor_stores_count**2 * partial["liquor_store"]
    abandoned_penalty = abandoned_count**2 * partial["abandoned"]

    return noise_penalty + industrial_penalty + liquor_penalty + abandoned_penalty


# access to children infrastructure
def children_score(gdf: gpd.GeoDataFrame, weights: dict, dynamics):
    adjusted_gdf = get_count_adjusted(gdf, "children", dynamics)

    partial = weights["children"]["partial"]
    thresholds = weights["children"]["threshold"]
    global_weight = weights["children"]["global"]

    score_sum = 0.0

    for category_name, category_weight in partial.items():
        category_count = adjusted_gdf[adjusted_gdf["category"] == category_name][
            "adjusted_value"
        ].sum()

        category_ratio = min(category_count / thresholds[category_name], 1)

        score_sum += category_ratio * category_weight

    return score_sum * global_weight


# quality of public transport nearby
def transport_score(gdf, dynamics, weights, saturation_point, tram_route_code):
    gdf_transport = gdf.copy()

    global_weight = weights["transport"]["global"]
    if gdf_transport.empty:
        return 0.0

    gdf_transport["category"] = "bus_stop"
    gdf_transport.loc[gdf_transport["route_type"] == tram_route_code, "category"] = (
        "tram_stop"
    )

    adjusted_gdf = get_count_adjusted(gdf_transport, "transport", dynamics)

    # bonus for trams reliability
    is_tram = adjusted_gdf["route_type"] == tram_route_code
    adjusted_gdf.loc[is_tram, "max_reach_km"] = (
        gdf_transport.loc[is_tram, "max_reach_km"] * 1.5
    )

    distance_adjusted = (
        adjusted_gdf["max_reach_km"] * adjusted_gdf["adjusted_value"]
    ).sum()

    score = (
        min(math.log(distance_adjusted + 1, saturation_point + 1), 1) * global_weight
    )
    return score

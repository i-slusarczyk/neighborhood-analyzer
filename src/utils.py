"""
Utility functions for the neighborhood scoring model.

This module handles core spatial operations (buffering, clipping, index-based filtering)
and calculates individual component scores (nature, transport, amenities) using
distance decay functions and predefined weights.
"""

import math
import geopandas as gpd
import pandas as pd
import shapely
from pyproj import Transformer
import src.config as cfg

# Initialize a global coordinate transformer for high-performance point translation
# mapping from standard GPS (EPSG:4326) to the local projection defined in config.
_TRANSFORMER = Transformer.from_crs(
    "EPSG:4326", f"EPSG:{cfg.TARGET_CRS}", always_xy=True
)


# pin on the map as gpd series
def get_target_point(lon: float, lat: float) -> shapely.Point:
    """
    Transforms WGS84 coordinates into the local CRS metric point.

    Args:
        lon (float): Longitude.
        lat (float): Latitude.

    Returns:
        shapely.Point: A geometry point in the target coordinate reference system.
    """
    x, y = _TRANSFORMER.transform(lon, lat)
    return shapely.Point(x, y)


def points_in_radius(
    gdf: gpd.GeoDataFrame,
    lon: float,
    lat: float,
    radius: int = cfg.BUFFER_RADIUS_METERS,
    add_distance_col: bool = True,
) -> gpd.GeoDataFrame:
    """
    Filters points within a specified radius using a highly optimized spatial index.

    Employs an R-Tree bounding box query to pre-filter data before calculating
    exact Euclidean distances.

    Args:
        gdf (gpd.GeoDataFrame): City-wide points dataset.
        lon (float): Target longitude.
        lat (float): Target latitude.
        radius (int, optional): Search radius in meters. Defaults to cfg.BUFFER_RADIUS_METERS.
        add_distance_col (bool, optional): Whether to append a 'distance' column. Defaults to True.

    Returns:
        gpd.GeoDataFrame: A subset of points falling strictly within the defined radius.
    """

    target_point = get_target_point(lon, lat)
    target_buffer = target_point.buffer(radius)

    possible_matches_index = gdf.sindex.query(target_buffer, predicate="intersects")
    possible_matches = gdf.iloc[possible_matches_index].copy()

    if possible_matches.empty:
        if add_distance_col:
            possible_matches["distance"] = pd.Series(dtype=float)
        return possible_matches

    distances = possible_matches.geometry.distance(target_point)
    mask = distances <= radius
    gdf_filtered = possible_matches.loc[mask].copy()

    if add_distance_col:
        gdf_filtered["distance"] = distances.loc[mask]

    return gdf_filtered


# clipping areas to radius
def clip_to_buffer(
    gdf: gpd.GeoDataFrame,
    lon: float,
    lat: float,
    radius: int = cfg.BUFFER_RADIUS_METERS,
) -> gpd.GeoDataFrame:
    """
    Clips polygon geometries to a defined circular buffer using spatial indexing.

    Args:
        gdf (gpd.GeoDataFrame): Polygon dataset (e.g., nature or industrial areas).
        lon (float): Target longitude.
        lat (float): Target latitude.
        radius (int, optional): Buffer radius in meters. Defaults to cfg.BUFFER_RADIUS_METERS.

    Returns:
        gpd.GeoDataFrame: Polygons clipped to the buffer boundaries with an added distance column.
    """

    target_point = get_target_point(lon, lat)
    target_buffer = target_point.buffer(radius)

    possible_matches_index = gdf.sindex.query(target_buffer, predicate="intersects")
    possible_matches = gdf.iloc[possible_matches_index]

    if possible_matches.empty:
        possible_matches["distance"] = pd.Series(dtype=float)
        return possible_matches

    gdf_clipped = gpd.clip(possible_matches, target_buffer)

    gdf_clipped["distance"] = gdf_clipped.geometry.distance(target_point)
    return gdf_clipped


def apply_distance_decay(
    distances: pd.Series, max_dist: float, optimal_dist: float, power: float
) -> pd.Series:
    """
    Applies a non-linear decay penalty to points based on their distance from the origin.

    Objects closer than 'optimal_dist' receive full value (1.0). Value decreases
    exponentially until 'max_dist', beyond which it drops to 0.

    Args:
        distances (pd.Series): Distance values in meters.
        max_dist (float): Distance threshold where the value reaches 0.
        optimal_dist (float): Distance within which the object retains full value.
        power (float, optional): Exponent dictating the decay curve. Defaults to math.e.

    Returns:
        pd.Series: Adjusted multiplier values between 0.0 and 1.0.
    """
    clipped_dist = distances.clip(lower=optimal_dist, upper=max_dist)

    normalized_dist = (clipped_dist - optimal_dist) / (max_dist - optimal_dist)

    penalty = normalized_dist**power

    return 1 - penalty


def get_count_adjusted(
    gdf: gpd.GeoDataFrame,
    dynamics: dict,
    category: str,
) -> gpd.GeoDataFrame:
    """
    Enriches a GeoDataFrame with distance-adjusted values based on subcategory dynamics.

    Args:
        gdf (gpd.GeoDataFrame): Dataset containing pre-calculated 'distance' and 'category' columns.
        dynamics (dict): Configuration dictionary holding distance parameters.
        category (str): The primary category key (e.g., 'nature', 'daily') in the dynamics dict.

    Returns:
        gpd.GeoDataFrame: Original dataframe with a new 'adjusted_value' column.
    """
    result_gdf = gdf.copy()
    result_gdf["adjusted_value"] = 0.0

    if result_gdf.empty:
        return result_gdf

    category_dynamics = dynamics[category]

    for subcategory in category_dynamics:
        category_max_dist = category_dynamics[subcategory]["max_dist"]
        category_optimal_dist = category_dynamics[subcategory]["optimal_dist"]
        category_power = category_dynamics[subcategory]["power"]

        mask = gdf["category"] == subcategory

        if not mask.any():
            continue

        distances = result_gdf.loc[mask, "distance"]

        result_gdf.loc[mask, "adjusted_value"] = apply_distance_decay(
            distances, category_max_dist, category_optimal_dist, category_power
        )
    return result_gdf


def intersecting_nature(gdf: gpd.GeoDataFrame, weights: dict) -> gpd.GeoDataFrame:
    """
    Resolves overlapping nature polygons by subtracting lower-weighted geometries
    from higher-priority ones to prevent double-counting area.

    Args:
        gdf (gpd.GeoDataFrame): Dataset of natural areas.
        weights (dict): Configuration dictionary containing nature category priorities.

    Returns:
        gpd.GeoDataFrame: Geometries without topological overlaps.
    """
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


def calculate_nature_threshold_exp(
    radius: int = cfg.BUFFER_RADIUS_METERS,
    max_threshold: float = cfg.NATURE_THRESHOLD_MAX,
    steepness=cfg.NATURE_THRESHOLD_STEEPNESS,
) -> float:
    """Calculates dynamic nature area requirements scaling with the buffer radius."""
    return max_threshold * math.exp(-steepness * radius)


def get_distance_to_center(
    lon: float, lat: float, city_center_lon: float, city_center_lat: float
):
    """Calculates straight-line distance to the city center."""
    center_point = get_target_point(city_center_lon, city_center_lat)
    pin_point = get_target_point(lon, lat)
    return pin_point.distance(center_point)


def calculate_distance_ratio(
    distance_to_center_m: float,
    midpoint: float = cfg.DIST_TO_CENTER_MIDPOINT,
    steepness: float = cfg.DIST_TO_CENTER_STEEPNESS,
) -> float:
    """
    Applies a sigmoid decay function to reward proximity to the city center.
    Returns 1.0 for central locations and drops sharply beyond the defined midpoint.
    """
    if distance_to_center_m < 0:
        return 1.0
    ratio = 1.0 / (1.0 + math.exp(steepness * (distance_to_center_m - midpoint)))
    if distance_to_center_m < 200:
        return 1.0
    if ratio < 0.05:
        return 0.0
    return ratio


def find_reachability(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Filters nearby public transport data to retain only the closest unique stop
    for each distinct route and direction.
    """

    # Dropping repeated routes on further stops
    gdf = gdf.sort_values(by="distance", ascending=True)
    gdf = gdf.drop_duplicates(subset=["route_number", "direction_id"], keep="first")

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


def nature_score(
    gdf: gpd.GeoDataFrame,
    weights: dict,
    dynamics,
    radius: int = cfg.BUFFER_RADIUS_METERS,
) -> float:
    """
    Calculates the weighted score for local green areas and water bodies.

    The score is area-based. Each polygon's area is penalized by its distance from
    the given point (distance decay) - distances are calculated earlier in clip_to_buffer function.
    The total effective area is then compared against a
    dynamic threshold (smaller buffers require a higher percentage of nature
    to score max points).

    Args:
        gdf (gpd.GeoDataFrame): Clipped geometries of natural areas.
        weights (dict): Configuration containing 'partial' weights and a 'global' weight.
        dynamics (dict): Distance decay parameters for each nature subcategory.
        radius (int, optional): Buffer radius used to calculate the area threshold.

    Returns:
        float: The final nature score, capped between 0.0 and the global weight maximum.
    """

    adjusted_gdf = get_count_adjusted(gdf=gdf, category="nature", dynamics=dynamics)

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


def daily_score(gdf: gpd.GeoDataFrame, weights: dict, dynamics: dict) -> float:
    """
    Calculates the score for access to daily infrastructure (supermarkets, pharmacies).

    Evaluates POIs based on a count-threshold model. Points are penalized by distance.
    Achieving the required threshold (e.g., 2 supermarkets nearby) yields a max sub-score
    of 1.0, which is then multiplied by its specific category weight.

    Args:
        gdf (gpd.GeoDataFrame): Local POIs within the buffer.
        weights (dict): Threshold requirements and partial/global weights.
        dynamics (dict): Distance decay parameters.

    Returns:
        float: Aggregated daily infrastructure score.
    """
    adjusted_gdf = get_count_adjusted(gdf=gdf, category="daily", dynamics=dynamics)

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


def culture_score(
    gdf: gpd.GeoDataFrame, weights: dict, dynamics: dict, distance_to_center: int
) -> float:
    """
    Calculates the culture and entertainment score, incorporating a city-center bonus.

    Standard POIs (cafes, restaurants) are evaluated using a count-threshold model.
    Additionally, a sigmoid function evaluates the 'distance_to_center', heavily
    rewarding areas in the urban core and decaying sharply in the suburbs.

    Args:
        gdf (gpd.GeoDataFrame): Local POIs within the buffer.
        weights (dict): Category thresholds and weights.
        dynamics (dict): Distance decay parameters.
        distance_to_center (int): Straight-line distance to the city center in meters.

    Returns:
        float: Aggregated culture score.
    """
    adjusted_gdf = get_count_adjusted(gdf=gdf, category="culture", dynamics=dynamics)

    partial = weights["culture"]["partial"]
    thresholds = weights["culture"]["threshold"]
    global_weight = weights["culture"]["global"]

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


def destructors(
    gdf_poi: gpd.GeoDataFrame,
    gdf_industrial: gpd.GeoDataFrame,
    dynamics: dict,
    weights: dict,
    radius: int = cfg.BUFFER_RADIUS_METERS,
) -> float:
    """
    Calculates penalty points to be subtracted from the base livability score.

    Applies specific mathematical models to different nuisance types:
    - Noise (Restaurants): Uses a logarithmic curve to simulate saturation
      (many places clustered together don't scale linearly in noise perception).
    - Industrial: Uses a polynomial penalty based on the percentage of industrial
      area within the buffer to heavily penalize large factories.
    - Urban Decay: Directly penalizes abandoned buildings and 24/7 liquor stores.

    Args:
        gdf_poi (gpd.GeoDataFrame): Points of Interest containing potential destructors.
        gdf_industrial (gpd.GeoDataFrame): Clipped industrial polygons.
        dynamics (dict): Distance decay parameters.
        weights (dict): Multipliers and thresholds for calculating penalties.
        radius (int, optional): Buffer radius used to calculate industrial area ratio.

    Returns:
        float: Total penalty points to be subtracted.
    """
    adjusted_gdf_poi = get_count_adjusted(
        gdf=gdf_poi, category="destructors", dynamics=dynamics
    )
    adjusted_gdf_industrial = get_count_adjusted(
        gdf_industrial, category="destructors", dynamics=dynamics
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


def children_score(gdf: gpd.GeoDataFrame, weights: dict, dynamics: dict) -> float:
    """
    Calculates the score for child-friendly infrastructure (schools, kindergartens).

    Similar to daily_score, it evaluates the presence of specific POIs against
    a predefined threshold, adjusting for the distance decay of each facility.

    Args:
        gdf (gpd.GeoDataFrame): Local POIs within the buffer.
        weights (dict): Category thresholds and weights.
        dynamics (dict): Distance decay parameters.

    Returns:
        float: Aggregated child-friendly infrastructure score.
    """
    adjusted_gdf = get_count_adjusted(gdf=gdf, category="children", dynamics=dynamics)

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


def transport_score(
    gdf: gpd.GeoDataFrame,
    weights: dict,
    dynamics: dict,
) -> float:
    """
    Calculates public transport quality based on reachable GTFS kilometers.

    Unlike standard count models, this evaluates how far a user can travel without
    transfers. It rewards independent transit (trams) with a reliability multiplier
    and applies a logarithmic saturation curve to simulate diminishing returns
    (having 500 km of reachable routes isn't twice as good as 250 km).

    Args:
        gdf (gpd.GeoDataFrame): Unique transport stops with their 'max_reach_km'.
        weights (dict): Global weight for transport.
        dynamics (dict): Distance decay parameters for walking to stops.

    Returns:
        float: Final transport quality score.
    """
    gdf_transport = gdf.copy()

    global_weight = weights["transport"]["global"]
    if gdf_transport.empty:
        return 0.0

    gdf_transport["category"] = "bus_stop"
    gdf_transport.loc[
        gdf_transport["route_type"] == cfg.TRAM_ROUTE_CODE, "category"
    ] = "tram_stop"

    adjusted_gdf = get_count_adjusted(
        gdf=gdf_transport, dynamics=dynamics, category="transport"
    )

    # Bonus points for trams reliability
    is_tram = adjusted_gdf["route_type"] == cfg.TRAM_ROUTE_CODE
    adjusted_gdf.loc[is_tram, "max_reach_km"] = (
        gdf_transport.loc[is_tram, "max_reach_km"] * cfg.TRAM_COEFFICIENT
    )

    distance_adjusted = (
        adjusted_gdf["max_reach_km"] * adjusted_gdf["adjusted_value"]
    ).sum()

    score = (
        min(math.log(distance_adjusted + 1, cfg.TRANSPORT_SATURATION_POINT + 1), 1)
        * global_weight
    )
    return score

import math
import geopandas as gpd
import pandas as pd
import shapely
import src.config as cfg


# pin on the map as gpd series
def get_target_point(lon: float, lat: float):
    return gpd.GeoSeries([shapely.Point(lon, lat)], crs="EPSG:4326").to_crs(epsg=cfg.TARGET_CRS)


# selecting just the points within radius
def points_in_radius(gdf: gpd.GeoDataFrame, lon: float, lat: float, radius: int = cfg.BUFFER_RADIUS_METERS, add_distance_col: bool = True) -> gpd.GeoDataFrame:
    target_point = get_target_point(lon, lat)

    distances = gdf.geometry.distance(target_point.iloc[0])

    mask = distances <= radius
    gdf_filtered = gdf.loc[mask].copy()

    if add_distance_col:
        gdf_filtered["distance"] = distances
    return gdf_filtered


# clipping areas to radius
def clip_to_buffer(gdf: gpd.GeoDataFrame, lon: float, lat: float, radius: int = cfg.BUFFER_RADIUS_METERS) -> gpd.GeoDataFrame:
    target_point = get_target_point(lon, lat)

    gdf_target_buffer = target_point.buffer(radius)
    gdf_clipped = gpd.clip(gdf, gdf_target_buffer)

    gdf_clipped["distance"] = gdf_clipped.geometry.distance(
        target_point.iloc[0])
    return gdf_clipped


# applying distance decay function
def apply_distance_decay(distances: pd.Series, max_dist: float, optimal_dist: float, power: float = math.e):
    clipped_dist = distances.clip(lower=optimal_dist, upper=max_dist)

    normalized_dist = (clipped_dist - optimal_dist) / (max_dist - optimal_dist)

    penalty = normalized_dist ** power

    return 1-penalty


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
            distances, category_max_dist, category_optimal_dist, category_power)
    return result_gdf


# subtracting area from lower weighted amenities
def intersecting_nature(gdf, weights):
    gdf_polygons = gdf[gdf.geometry.geom_type.isin(
        ["Polygon", "MultiPolygon"])]

    if gdf_polygons.empty:
        return gdf_polygons

    partial = weights["nature"]["partial"]

    priority_order = sorted(partial, key=partial.get, reverse=True)

    accumulated_layers = gpd.GeoDataFrame(geometry=[], crs=gdf.crs)

    for category in priority_order:
        current_layer = gdf_polygons[gdf_polygons["category"] == category].copy(
        )
        if current_layer.empty:
            continue
        if accumulated_layers.empty:
            accumulated_layers = current_layer.copy()
        else:
            current_layer = gpd.overlay(
                current_layer, accumulated_layers, how="difference", keep_geom_type=True)
            accumulated_layers = pd.concat(
                [accumulated_layers, current_layer], ignore_index=True)
    return accumulated_layers


# automatically calculating nature threshold based on given radius
def calculate_nature_threshold_exp(radius: int = cfg.BUFFER_RADIUS_METERS, max_threshold: float = cfg.NATURE_THRESHOLD_MAX, steepness=cfg.NATURE_THRESHOLD_STEEPNESS) -> float:
    return max_threshold * math.exp(-steepness * radius)


# straightforward - distance from point to the city center
def get_distance_to_center(lon, lat, city_center_lon, city_center_lat):
    center_series = get_target_point(city_center_lon, city_center_lat)
    pin_series = get_target_point(lon, lat)
    return pin_series.distance(center_series).iloc[0]


# sigmoid function assigning points based on distance to city center
def calculate_distance_ratio(distance_to_center_m: float, midpoint: float = cfg.DIST_TO_CENTER_MIDPOINT, steepness: float = cfg.DIST_TO_CENTER_STEEPNESS) -> float:
    if distance_to_center_m < 0:
        return 1.0
    ratio = 1.0 / (1.0 + math.exp(steepness *
                   (distance_to_center_m - midpoint)))
    if distance_to_center_m < 200:
        return 1.0
    if ratio < 0.05:
        return 0.0
    return ratio


# bus and tram stops reachability - how many kilometers you can reach without changing
def find_reachability(gdf: gpd.GeoDataFrame):
    # dropping repeated trips, leaving only the ones on the closest stop
    gdf = gdf.sort_values(by="distance", ascending=True)
    gdf = gdf.drop_duplicates(
        subset=["route_number", "direction_id"], keep="first")
    # leaving only names and geometries for pretty visualization on map
    gdf_pretty = gpd.GeoDataFrame(
        data=(
            gdf.groupby(["stop_location", "stop_name",
                        "distance", "route_type"], as_index=False)
            .agg({"max_reach_km": "sum"})),

        geometry="stop_location",
        crs=gdf.crs)

    return gdf_pretty


# to be added: area lower threshold for parks, distance decay func
def nature_score(gdf: gpd.GeoDataFrame, weights: dict, dynamics, radius: int = cfg.BUFFER_RADIUS_METERS):
    adjusted_gdf = get_count_adjusted(gdf, "nature", dynamics)

    parks = adjusted_gdf[adjusted_gdf["category"] == "park"]
    water = adjusted_gdf[adjusted_gdf["category"] == "water"]
    meadows = adjusted_gdf[adjusted_gdf["category"] == "meadow"]
    forests = adjusted_gdf[adjusted_gdf["category"] == "forest"]
    grassland = adjusted_gdf[adjusted_gdf["category"] == "grassland"]
    reserves = adjusted_gdf[adjusted_gdf["category"] == "nature_reserve"]

    parks["area_adjusted"] = parks.area * parks["adjusted_value"]
    water["area_adjusted"] = water.area * water["adjusted_value"]
    meadows["area_adjusted"] = meadows.area * meadows["adjusted_value"]
    forests["area_adjusted"] = forests.area * forests["adjusted_value"]
    grassland["area_adjusted"] = grassland.area * grassland["adjusted_value"]
    reserves["area_adjusted"] = reserves.area * reserves["adjusted_value"]

    partial = weights["nature"]["partial"]
    threshold = calculate_nature_threshold_exp(radius)
    global_weight = weights["nature"]["global"]

    weighted_area = (
        water["area_adjusted"].sum() * partial["water"] +
        forests["area_adjusted"].sum() * partial["forest"] +
        parks["area_adjusted"].sum() * partial["park"] +
        meadows["area_adjusted"].sum() * partial["meadow"] +
        grassland["area_adjusted"].sum() * partial["grassland"] +
        reserves["area_adjusted"].sum() * partial["nature_reserve"]
    )

    total_buffer_area = radius**2*math.pi

    score = min((weighted_area / (total_buffer_area * threshold)),
                1) * global_weight

    return score


# score for daily infastructure
def daily_score(gdf: gpd.GeoDataFrame, weights: dict, dynamics):  # seems good
    adjusted_gdf = get_count_adjusted(gdf, "daily", dynamics)

    clinics_count = adjusted_gdf[adjusted_gdf["category"]
                                 == "clinic"]["adjusted_value"].sum()
    pharmacies_count = adjusted_gdf[adjusted_gdf["category"]
                                    == "pharmacy"]["adjusted_value"].sum()
    convenience_count = adjusted_gdf[adjusted_gdf["category"]
                                     == "convenience"]["adjusted_value"].sum()
    supermarkets_count = adjusted_gdf[adjusted_gdf["category"]
                                      == "supermarket"]["adjusted_value"].sum()

    partial = weights["daily"]["partial"]
    thresholds = weights["daily"]["threshold"]
    global_weight = weights["daily"]["global"]

    clinics_ratio = min(
        clinics_count, thresholds["clinic"])/thresholds["clinic"]
    convenience_ratio = min(
        convenience_count, thresholds["convenience"])/thresholds["convenience"]
    supermarkets_ratio = min(
        supermarkets_count, thresholds["supermarket"])/thresholds["supermarket"]
    pharmacies_ratio = min(
        pharmacies_count, thresholds["pharmacy"])/thresholds["pharmacy"]

    score = (supermarkets_ratio * partial["supermarket"] + pharmacies_ratio * partial["pharmacy"] +
             clinics_ratio * partial["clinic"] + convenience_ratio * partial["convenience"]) * global_weight
    return score


# access to culture score
def culture_score(gdf: gpd.GeoDataFrame, weights: dict, distance_to_center: int, dynamics):  # done for now
    adjusted_gdf = get_count_adjusted(gdf, "culture", dynamics)

    cafes_count = adjusted_gdf[adjusted_gdf["category"]
                               == "cafe"]["adjusted_value"].sum()
    restaurants_count = adjusted_gdf[adjusted_gdf["category"]
                                     == "restaurant"]["adjusted_value"].sum()

    partial = weights["culture"]["partial"]
    thresholds = weights["culture"]["threshold"]
    global_weight = weights["culture"]["global"]

    # distance to the city center
    distance_ratio = calculate_distance_ratio(distance_to_center)

    cafe_ratio = min(cafes_count/thresholds["cafe"], 1)

    restaurant_ratio = min(
        restaurants_count/thresholds["restaurant"], 1)

    distance_weighted = distance_ratio * partial["distance_to_center"]
    cafe_weighted = cafe_ratio * partial["cafe"]
    restaurant_weighted = restaurant_ratio * partial["restaurant"]

    score = distance_weighted + cafe_weighted + restaurant_weighted
    return score * global_weight


# destructor points - meant to be subtracted from base score
def destructors(gdf_poi: gpd.GeoDataFrame, gdf_industrial: gpd.GeoDataFrame, dynamics, weights: dict, radius: int = cfg.BUFFER_RADIUS_METERS):
    adjusted_gdf_poi = get_count_adjusted(gdf_poi, "destructors", dynamics)
    adjusted_gdf_industrial = get_count_adjusted(
        gdf_industrial, "destructors", dynamics)

    partial = weights["destructors"]["partial"]
    restaurant_threshold = weights["destructors"]["restaurant_threshold"]

    adjusted_gdf_industrial["area_adjusted"] = adjusted_gdf_industrial.area * \
        adjusted_gdf_industrial["adjusted_value"]

    restaurants_count = adjusted_gdf_poi[adjusted_gdf_poi["category"] == "restaurant"]["adjusted_value"].sum(
    )
    liquor_stores_count = adjusted_gdf_poi[adjusted_gdf_poi["category"] == "liquor_store"]["adjusted_value"].sum(
    )
    abandoned_count = adjusted_gdf_poi[adjusted_gdf_poi["category"] == "abandoned"]["adjusted_value"].sum(
    )
    industrial_area = adjusted_gdf_industrial["area_adjusted"].sum()

    total_buffer_area = radius**2*math.pi

    noise_penalty = max(5*(math.log(restaurants_count+1,
                        restaurant_threshold+1)-1), 0)
    industrial_ratio = industrial_area / total_buffer_area * 100

    total_penalty = (
        noise_penalty + (industrial_ratio**(3/2) * partial["industrial"]) +
        (liquor_stores_count**2 * partial["liquor_store"]) +
        (abandoned_count**2 * partial["abandoned"])
    )
    return total_penalty


# access to children infrastructure
def children_score(gdf: gpd.GeoDataFrame, weights: dict, dynamics):
    adjusted_gdf = get_count_adjusted(gdf, "children", dynamics)

    kindergartens_count = adjusted_gdf[adjusted_gdf["category"]
                                       == "kindergarten"]["adjusted_value"].sum()
    school_count = adjusted_gdf[adjusted_gdf["category"]
                                == "school"]["adjusted_value"].sum()
    playground_count = adjusted_gdf[adjusted_gdf["category"]
                                    == "playground"]["adjusted_value"].sum()

    partial = weights["children"]["partial"]
    thresholds = weights["children"]["threshold"]
    global_weight = weights["children"]["global"]

    kindergarten_ratio = min(
        kindergartens_count, thresholds["kindergarten"])/thresholds["kindergarten"]
    school_ratio = min(
        school_count, thresholds["school"])/thresholds["school"]
    playground_ratio = min(
        playground_count, thresholds["playground"])/thresholds["playground"]

    score = (kindergarten_ratio * partial["kindergarten"] + school_ratio *
             partial["school"] + playground_ratio * partial["playground"]) * global_weight
    return score


# quality of public transport nearby
def transport_score(gdf, dynamics, weights, saturation_point, tram_route_code):
    gdf["category"] = "bus_stop"
    gdf.loc[gdf["route_type"] ==
            tram_route_code, "category"] = "tram_stop"

    adjusted_gdf = get_count_adjusted(gdf, "transport", dynamics)

    global_weight = weights["transport"]["global"]
    if gdf.empty:
        return 0
    gdf_transport = adjusted_gdf
    is_tram = gdf_transport["route_type"] == tram_route_code

    # bonus points for trams
    gdf_transport.loc[is_tram,
                      "max_reach_km"] = gdf_transport.loc[is_tram, "max_reach_km"]*1.5

    distance_adjusted = (
        gdf_transport["max_reach_km"] * gdf_transport["adjusted_value"]).sum()

    score = min(math.log(distance_adjusted+1,
                saturation_point+1), 1) * global_weight
    return score

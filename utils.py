import geopandas as gpd
import shapely
import math
import config


def get_target_point(lat: float, lon: float):
    return gpd.GeoSeries([shapely.Point(lon, lat)], crs="EPSG:4326").to_crs(epsg=config.TARGET_CRS)


def local_pois(gdf_poi: gpd.GeoDataFrame, lat: float, lon: float, radius: int = config.BUFFER_RADIUS_METERS) -> gpd.GeoDataFrame:
    target_point = get_target_point(lat, lon)
    distances = gdf_poi["geometry"].distance(target_point.iloc[0])
    return gdf_poi.loc[distances <= radius]


def get_flats_nearby(gdf_flats: gpd.GeoDataFrame, lat: float, lon: float, radius: int = config.BUFFER_RADIUS_METERS):
    target_point = get_target_point(lat, lon)
    distances = gdf_flats["geometry"].distance(target_point.iloc[0])
    return gdf_flats.loc[distances <= radius]


def clip_to_buffer(gdf: gpd.GeoDataFrame, lat: float, lon: float, radius: int = config.BUFFER_RADIUS_METERS) -> gpd.GeoDataFrame:
    gdf_target_buffer = get_target_point(lat, lon).buffer(radius)
    gdf_clipped = gpd.clip(gdf, gdf_target_buffer)
    return gdf_clipped


def calculate_nature_threshold_exp(radius: int = config.BUFFER_RADIUS_METERS) -> float:
    A = 0.28
    k = 0.0012
    return A * math.exp(-k * radius)


def nature_score(gdf: gpd.GeoDataFrame, weights: dict, radius: int = config.BUFFER_RADIUS_METERS):  # done for now
    parks = gdf[gdf["category"] == "park"]
    water = gdf[gdf["category"] == "water"]
    meadows = gdf[gdf["category"] == "meadow"]
    forests = gdf[gdf["category"] == "forest"]
    grassland = gdf[gdf["category"] == "grassland"]
    reserves = gdf[gdf["category"] == "nature_reserve"]

    partial = weights["nature"]["partial"]
    threshold = calculate_nature_threshold_exp(radius)
    global_weight = weights["nature"]["global"]

    weighted_area = (
        water.area.sum() * partial["water"] +
        forests.area.sum() * partial["forest"] +
        parks.area.sum() * partial["park"] +
        meadows.area.sum() * partial["meadow"] +
        grassland.area.sum() * partial["grassland"] +
        reserves.area.sum() * partial["nature_reserve"]
    )

    total_buffer_area = radius**2*math.pi

    score = min((weighted_area / (total_buffer_area * threshold)),
                1) * global_weight

    return score


def daily_score(gdf: gpd.GeoDataFrame, weights: dict):  # seems good
    clinics_count = len(gdf[gdf["category"] == "clinic"])
    pharmacies_count = len(gdf[gdf["category"] == "pharmacy"])
    convenience_count = len(gdf[gdf["category"] == "convenience"])
    supermarkets_count = len(gdf[gdf["category"] == "supermarket"])

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


def calculate_distance_ratio(distance_to_center_m: float, midpoint: float = 2300.0, steepness: float = 0.002) -> float:
    if distance_to_center_m < 0:
        return 1.0
    ratio = 1.0 / (1.0 + math.exp(steepness *
                   (distance_to_center_m - midpoint)))
    if distance_to_center_m < 200:
        return 1.0
    if ratio < 0.05:
        return 0.0
    return ratio


def get_distance_to_center(lat, lon, city_center_lat, city_center_lon):
    center_series = get_target_point(city_center_lat, city_center_lon)
    pin_series = get_target_point(lat, lon)
    return pin_series.distance(center_series).iloc[0]


def culture_score(gdf: gpd.GeoDataFrame, weights: dict, distance_to_center: int):  # done for now
    cafes_count = len(gdf[gdf["category"] == "cafe"])
    restaurants_count = len(gdf[gdf["category"] == "restaurant"])

    partial = weights["culture"]["partial"]
    thresholds = weights["culture"]["threshold"]
    global_weight = weights["culture"]["global"]

    distance_ratio = calculate_distance_ratio(distance_to_center)
    cafe_ratio = min(cafes_count/thresholds["cafe"], 1)

    restaurant_ratio = min(
        cafes_count/thresholds["restaurant"], 1)

    distance_weighted = distance_ratio * partial["distance_to_center"]
    cafe_weighted = cafe_ratio * partial["cafe"]
    restaurant_weighted = restaurant_ratio * partial["restaurant"]

    score = distance_weighted + cafe_weighted + restaurant_weighted
    return score * global_weight


# industrial area to be counted
def destructors(gdf_poi: gpd.GeoDataFrame, gdf_industrial: gpd.GeoDataFrame, weights: dict, radius: int = config.BUFFER_RADIUS_METERS):
    partial = weights["destructors"]["partial"]
    restaurant_threshold = weights["destructors"]["restaurant_threshold"]

    restaurants_count = len(gdf_poi[gdf_poi["category"] == "restaurant"])
    liquor_stores_count = len(gdf_poi[gdf_poi["category"] == "liquor_store"])
    abandoned_count = len(gdf_poi[gdf_poi["category"] == "abandoned"])
    industrial_area = gdf_industrial.area.sum()

    total_buffer_area = radius**2*math.pi

    noise_penalty = max(5*(math.log(restaurants_count+1,
                        restaurant_threshold+1)-1), 0)
    industrial_ratio = industrial_area / total_buffer_area * 100

    total_penalty = (
        noise_penalty + (industrial_ratio*partial["industrial"])**2 +
        (liquor_stores_count**2 * partial["liquor_store"]) +
        (abandoned_count**2 * partial["abandoned"])
    )
    return total_penalty


def children_score(gdf: gpd.GeoDataFrame, weights: dict):
    kindergartens_count = len(gdf[gdf["category"] == "kindergarten"])
    school_count = len(gdf[gdf["category"] == "school"])
    playground_count = len(gdf[gdf["category"] == "playground"])

    partial = weights["children"]["partial"]
    thresholds = weights["children"]["threshold"]
    global_weight = weights["children"]["global"]

    kindergarten_ratio = min(
        kindergartens_count, thresholds["kindergarten"])/thresholds["kindergarten"]
    school_ratio = min(
        school_count, thresholds["school"])/thresholds["school"]
    playyground_ratio = min(
        playground_count, thresholds["playground"])/thresholds["playground"]

    score = (kindergarten_ratio * partial["kindergarten"] + school_ratio *
             partial["school"] + playyground_ratio * partial["playground"]) * global_weight
    return score


# powinno brać liczbę połączeń na godzinę - ZTP GTFS, albo liczba linii
def transport_score(gdf: gpd.GeoDataFrame, weights: dict):
    bus_stops_count = len(gdf[gdf["category"] == "bus_stop"])
    tram_stops_count = len(gdf[gdf["category"] == "tram_stop"])

    partial = weights["transport"]["partial"]
    thresholds = weights["transport"]["threshold"]
    global_weight = weights["transport"]["global"]

    bus_stop_ratio = min(
        bus_stops_count, thresholds["bus_stop"])/thresholds["bus_stop"]
    tram_stop_ratio = min(
        tram_stops_count, thresholds["tram_stop"])/thresholds["tram_stop"]

    score = (tram_stop_ratio * partial["tram_stop"] + bus_stop_ratio *
             partial["bus_stop"]) * global_weight
    return score

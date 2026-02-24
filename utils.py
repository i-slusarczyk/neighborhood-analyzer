import geopandas as gpd
import shapely
import math


def get_target_point(lat: float, lon: float):
    return gpd.GeoSeries([shapely.Point(lon, lat)], crs="EPSG:4326").to_crs(epsg=2180)


def get_poi(gdf_poi: gpd.GeoDataFrame, lat: float, lon: float, category: str, radius: int = 1000) -> gpd.GeoDataFrame:
    target_point = get_target_point(lat, lon)
    gdf_poi = gdf_poi.loc[gdf_poi["category"] == category]
    distances = gdf_poi["geometry"].distance(target_point.iloc[0])
    return gdf_poi.loc[distances <= radius]


def get_flats_nearby(gdf_flats: gpd.GeoDataFrame, lat: float, lon: float, radius: int = 500):
    target_point = get_target_point(lat, lon)
    distances = gdf_flats["geometry"].distance(target_point.iloc[0])
    return gdf_flats.loc[distances <= radius]


def get_nature(gdf_nature: gpd.GeoDataFrame, lat: float, lon: float, radius: int = 1000) -> gpd.GeoDataFrame:
    gdf_target_buffer = get_target_point(lat, lon).buffer(radius)
    gdf_clipped = gpd.clip(gdf_nature, gdf_target_buffer)
    return gdf_clipped


def nature_score(gdf: gpd.GeoDataFrame, partial_weights: dict, global_weight: float, threshold: float = 0.08, radius: int = 1000):
    parks = gdf[gdf["category"] == "park"]
    water = gdf[gdf["category"] == "water"]
    meadows = gdf[gdf["category"] == "meadow"]
    forests = gdf[gdf["category"] == "forest"]
    grassland = gdf[gdf["category"] == "grassland"]
    score = (min(
        ((water.area.sum() * partial_weights["water"] +
          forests.area.sum() * partial_weights["forest"] +
          parks.area.sum() * partial_weights["park"] +
          meadows.area.sum() * partial_weights["meadow"] +
          grassland.area.sum() * partial_weights["grassland"])
         / (radius**2*3.14159*threshold)), 1)
    ) * global_weight
    return score


def daily_score(gdf: gpd.GeoDataFrame, partial_weights: dict, global_weight: float):
    clinics = gdf[gdf["category"] == "clinic"]
    pharmacies gdf[gdf["category"] == "pharmacy"]
    convenience = gdf[gdf["category"] == "convenience"]
    supermarkets = gdf[gdf["category"] == "supermarket"]
    score =


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
    return pin_series.distance(center_series)


def culture_score(gdf: gpd.GeoDataFrame, weights: dict, distance_to_center: int):
    partial = weights["culture"]["partial"]
    thresholds = weights["culture"]["threshold"]
    global_weight = weights["culture"]["global"]

    distance_ratio = calculate_distance_ratio(
        distance_to_center_m=distance_to_center)
    cafe_ratio = min(math.log(cafes+1, weights["threshold"]["cafe"]+1), 1)
    restaurant_ratio = min(
        math.log(restaurants+1, weights["threshold"]["restaurant"]+1), 1)
    distance_weighted = distance_ratio * partial["distance_to_center"]
    cafe_weighted = cafe_ratio * partial["cafe"]
    restaurant_weighted = restaurant_ratio * partial["restaurant"]
    score = distance_weighted + cafe_weighted + restaurant_weighted


def destructors():
    noise_penalty = max(math.log(restaurants+1, 21)-1, 0)
    total_penalty = (
        noise penalty +
        (industrial*partial_weights["industrial"])**2 +
        (liquor_stores*partial_weights["liquor_stores"])**2 +
        (abandoned * partial_weights["abandoned"])**2
    )
    final_score = max(base_score - penalty, 0.0)

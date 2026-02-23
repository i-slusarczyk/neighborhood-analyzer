import geopandas as gpd
import shapely


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


def get_nature(gdf_nature: gpd.GeoDataFrame, lat: float, lon: float, radius: int = 800) -> gpd.GeoDataFrame:
    gdf_target_buffer = get_target_point(lat, lon).buffer(radius)
    gdf_clipped = gpd.clip(gdf_nature, gdf_target_buffer)
    return gdf_clipped


def nature_score():
    """NATURE_GLOBAL_WEIGHT = 27.1
nature_weights = {
    "water": 0.24,
    "park": 0.37,
    "meadow" : 0.08,
    "grassland": 0.03,
    "forest": 0.28,
}
nature_threshold_area = 0.2*buffer.area
nature_points = min(((water.area * nature_weights["water"] +
                    forests.area * nature_weights["forest"] +
                    parks.area * nature_weights["park"] +
                    meadows_area * nature_weights["meadow"] +
                    grassland.aarea * nature_weights["grassland"])/nature_threshold_area), 1
                    ) * NATURE_GLOBAL_WEIGHT"""

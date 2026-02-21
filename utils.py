import osmnx as ox
import geopandas as gpd
import shapely


def get_poi(gdf_poi: gpd.GeoDataFrame, lat: float, lon: float, category: str, radius: int = 1000) -> gpd.GeoDataFrame:
    target_point = shapely.Point(lon, lat)
    gdf_target_point = gpd.GeoSeries(
        [target_point], crs="EPSG:4326").to_crs(epsg=2180)
    gdf_poi = gdf_poi.loc[gdf_poi["category"] == category]
    distances = gdf_poi["geometry"].distance(gdf_target_point.iloc[0])
    return gdf_poi.loc[distances <= radius]


def get_flats_nearby(gdf_flats: gpd.GeoDataFrame, lat: float, lon: float, radius: int = 500):
    target_point = shapely.Point(lon, lat)
    gdf_target_point = gpd.GeoSeries(
        [target_point], crs="EPSG:4326").to_crs(epsg=2180)
    distances = gdf_flats["geometry"].distance(gdf_target_point.iloc[0])
    return gdf_flats.loc[distances <= radius]

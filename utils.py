import osmnx as ox
import geopandas as gpd
import pandas as pd
import shapely


def get_poi(lat: float, lon: float, tags: dict, radius: int = 1000) -> gpd.GeoDataFrame:
    try:
        gdf_poi = ox.features_from_point(
            (lat, lon), dist=radius, tags=tags)
        gdf_poi_clean_metric = gdf_poi.reset_index(
        )[["name", "geometry"]].to_crs(epsg=2180)
        gdf_poi_clean_metric["geometry"] = gdf_poi_clean_metric["geometry"].centroid
        return gdf_poi_clean_metric
    except Exception:
        return None


def get_flats_nearby(gdf_flats: gpd.GeoDataFrame, lat: float, lon: float, radius: int = 500):
    gdf_flats = gpd.read_parquet(r"data\krakow.parquet")
    target_point = shapely.Point(lon, lat)
    gdf_target_point = gpd.GeoSeries(
        [target_point], crs="EPSG:4326").to_crs(epsg=2180)
    distances = gdf_flats["geometry"].distance(gdf_target_point.iloc[0])
    median_price = gdf_flats.loc[distances <= radius, "pricePerMeter"].median()
    return median_price

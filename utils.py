import osmnx as ox
import geopandas as gpd
import pandas as pd


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

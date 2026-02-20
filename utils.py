import osmnx as ox
import geopandas as gpd
import pandas as pd


def get_cafes(lat: float, lon: float, radius: int = 1000) -> gpd.GeoDataFrame:
    try:
        cafes = ox.features_from_point(
            (lat, lon), dist=radius, tags={"amenity": "cafe"})
        cafes_clean_metric = cafes.reset_index(
        )[["name", "geometry"]].to_crs(epsg=2180)
        return cafes_clean_metric
    except Exception:
        return None


def get_shops(lat: float, lon: float, radius: int = 1000) -> gpd.GeoDataFrame:
    try:
        shops = ox.features_from_point(
            (lat, lon), dist=radius, tags={"shop": True})
        shops_clean_metric = shops.reset_index(
        )[["name", "geometry"]].to_crs(epsg=2180)
        return shops_clean_metric
    except Exception:
        return None

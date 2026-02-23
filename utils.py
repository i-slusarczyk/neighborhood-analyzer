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


def get_nature(gdf_nature: gpd.GeoDataFrame, lat: float, lon: float, radius: int = 1000) -> gpd.GeoDataFrame:
    gdf_target_buffer = get_target_point(lat, lon).buffer(radius)
    gdf_clipped = gpd.clip(gdf_nature, gdf_target_buffer)
    return gdf_clipped


def nature_score(gdf: gpd.GeoDataFrame, partial_weights: dict, global_weight: float, threshold: float = 0.09, radius: int = 1000):
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


"""def exclude_polygons():

    if False:
            gdf_clipped = gdf_clipped[gdf_clipped.geom_type.isin(
            ["Polygon", "MultiPolygon"])]

        parks_poly = gdf_clipped[gdf_clipped["category"] == "park"].unary_union
        forests_poly = gdf_clipped[gdf_clipped["category"] == "forest"].unary_union
        water_poly = gdf_clipped[gdf_clipped["category"] == "water"].unary_union
        meadows_poly = gdf_clipped[gdf_clipped["category"] == "meadow"].unary_union
        grassland_poly = gdf_clipped[gdf_clipped["category"]
                                    == "grassland"].unary_union

        if parks_poly:
            if forests_poly:
                pure_forests = forests_poly.difference(parks_poly)
            if meadows_poly:
                pure_meadows = meadows_poly.difference(parks_poly)
            if water_poly:
                pure_water = water_poly.difference(parks_poly)
            if grassland_poly:
                pure_grassland = grassland_poly.difference(parks_poly)
        else:
            pure_forests = forests_poly
            pure_meadows = meadows_poly
            pure_water = water_poly
            pure_grassland = grassland_poly
        if pure_forests:

        forests_merged = gdf_clipped[gdf_clipped["category"]
                                    == "forest"].unary_union"""

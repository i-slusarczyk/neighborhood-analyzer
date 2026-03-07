import geopandas as gpd
import h3
import shapely
from tqdm import tqdm
import src.config as cfg
import src.utils as ut
import src.scoring as scoring


def get_borders():
    with open(cfg.RAW_DIR / "krakow_borders.geojson", encoding="UTF-8") as file:
        return shapely.from_geojson(file.read())


def main():
    print("loading geospatial data...")
    poi_gdf = gpd.read_parquet(cfg.POI_PARQUET)
    flats_gdf = gpd.read_parquet(cfg.FLATS_PARQUET)
    industrial_gdf = gpd.read_parquet(cfg.INDUSTRIAL_PARQUET)
    reachability_gdf = gpd.read_parquet(cfg.REACHABILITY_PARQUET)
    nature_gdf = gpd.read_parquet(cfg.NATURE_PARQUET)

    print("cleaning intersecting nature...")
    nature_clean_gdf = ut.intersecting_nature(nature_gdf, cfg.weights)

    print("generating hexagonal grid (H3)")

    resolution = 9
    h3shape_borders = h3.geo_to_h3shape(get_borders())
    hexagons = h3.polygon_to_cells(h3shape_borders, resolution)

    print("scoring...")

    results = []
    geometries = []

    for hex_id in tqdm(hexagons):
        lat, lon = h3.cell_to_latlng(hex_id)

        score_data = scoring.calculate_full_score(
            lon, lat, poi_gdf, industrial_gdf, reachability_gdf, nature_clean_gdf, flats_gdf, cfg.city_center)

        results.append({
            "hex_id": hex_id,
            "final_score": score_data["final_score"],
            "base_score": score_data["base_score"],
            "destructors": score_data["destructors"],
            "median_price": score_data["median_price"],
            "value_ratio": score_data["value_ratio"]
        })

        boundary = h3.cell_to_boundary(hex_id)

        boundary_flipped = [(lon, lat) for lat, lon in boundary]

        hex_poly = shapely.Polygon(boundary_flipped)

        geometries.append(hex_poly)

    h3_gdf = gpd.GeoDataFrame(results, geometry=geometries, crs="EPSG:4326")
    h3_gdf.to_parquet(cfg.PROCESSED_DIR / "h3.parquet")


if __name__ == "__main__":
    main()

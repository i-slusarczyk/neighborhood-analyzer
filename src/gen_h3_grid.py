"""
Generates an H3 hexagonal grid over the defined city borders and calculates 
a comprehensive spatial score for each cell.

This script acts as the main execution pipeline for the scoring model. It loads 
preprocessed spatial layers (POIs, nature, industrial, reachability, flats), 
constructs an H3 grid at a specified resolution, and applies the scoring 
algorithm to evaluate the real estate attractiveness of each hexagon.
"""

import geopandas as gpd
import h3
import shapely
from tqdm import tqdm
import src.config as cfg
import src.utils as ut
import src.scoring as scoring


def get_borders() -> shapely.Geometry:
    """
    Reads the city borders from a GeoJSON file.

    Returns:
        shapely.Geometry: A Shapely polygon representing the city's administrative or analytical boundaries.
    """
    with open(cfg.CITY_BORDERS_GEOJSON, encoding="UTF-8") as file:
        return shapely.from_geojson(file.read())


def main():
    """
    Main pipeline execution function. Orchestrates data loading, grid generation,
    scoring computation, and the final export to a spatial Parquet file.
    """

    print("loading geospatial data...")
    poi_gdf = gpd.read_parquet(cfg.POI_PARQUET)
    flats_gdf = gpd.read_parquet(cfg.FLATS_PARQUET)
    industrial_gdf = gpd.read_parquet(cfg.INDUSTRIAL_PARQUET)
    reachability_gdf = gpd.read_parquet(cfg.REACHABILITY_PARQUET)
    nature_gdf = gpd.read_parquet(cfg.NATURE_PARQUET)

    print("cleaning intersecting nature...")
    nature_clean_gdf = ut.intersecting_nature(nature_gdf, cfg.weights)

    print("generating hexagonal grid (H3)")

    # Convert shapely geometry to an h3 compatible geometry and fill it with hexagons
    h3shape_borders = h3.geo_to_h3shape(get_borders())
    hexagons = h3.polygon_to_cells(h3shape_borders, cfg.H3_RESOLUTION)

    print("scoring...")

    results = []
    geometries = []

    #Calculate score for each individual hex cell
    for hex_id in tqdm(hexagons):
        lat, lon = h3.cell_to_latlng(hex_id)

        score_data = scoring.calculate_full_score(
            lon,
            lat,
            poi_gdf,
            industrial_gdf,
            reachability_gdf,
            nature_clean_gdf,
            flats_gdf,
            cfg.city_center,
        )

        results.append(
            {
                "hex_id": hex_id,
                "final_score": score_data["final_score"],
                "base_score": score_data["base_score"],
                "destructors": score_data["destructors"],
                "median_price": score_data["median_price"],
                "value_ratio": score_data["value_ratio"],
            }
        )


        #Extract hex boundary points to create the hex polygon
        boundary = h3.cell_to_boundary(hex_id)

        # H3 returns (lat, lon), but Shapely expects (lon, lat)
        boundary_flipped = [(lon, lat) for lat, lon in boundary]
        hex_poly = shapely.Polygon(boundary_flipped)

        geometries.append(hex_poly)

    # Assemble the final scored grid
    h3_gdf = gpd.GeoDataFrame(results, geometry=geometries, crs="EPSG:4326")
    h3_gdf.to_parquet(cfg.H3_PARQUET)


if __name__ == "__main__":
    main()

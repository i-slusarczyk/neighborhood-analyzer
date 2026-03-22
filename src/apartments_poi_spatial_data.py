"""
Extracts, transforms, and loads spatial features (Apartments, POIs, Nature, Industrial)
for the Urban Quality of Life scoring model.
"""

import pandas as pd
import geopandas as gpd
import osmnx as ox
import src.config as cfg
from pathlib import Path

# Configure OSMnx globally
ox.settings.use_cache = True
ox.settings.log_console = False


def process_apartments(
    dir_path: Path, city_name: str, target_crs: int, output_parquet: Path
):
    """Loads CSV flat listings, deduplicates by ID, and converts to a GeoDataFrame."""
    csv_files = sorted(dir_path.glob("*.csv"))
    print(f"Found flats files to process: {len(csv_files)}")

    df_list = []
    for i, filepath in enumerate(csv_files, 1):
        print(f"Loading file {i}/{len(csv_files)}: {filepath.name} ...")
        try:
            df = pd.read_csv(filepath, index_col=None, header=0)
            df_list.append(df)
        except Exception as e:
            print(f"Error loading {filepath.name}: {e}")

    if not df_list:
        print("Couldn't load any apartment files. Exiting apartment processing.")
        return

    print("Concatenating apartment files...")
    df_out = pd.concat(df_list, ignore_index=True)

    # Cleaning and filtering
    filtered_flats = df_out.loc[
        df_out["city"].str.lower() == city_name.lower()
    ].drop_duplicates(subset="id", keep="last")
    filtered_flats = filtered_flats[
        ["price", "latitude", "longitude", "squareMeters"]
    ].assign(pricePerMeter=lambda x: (x["price"] / x["squareMeters"]).round(2))

    # Converting to GeoDataFrame
    gdf_city_full = gpd.GeoDataFrame(
        data=filtered_flats,
        geometry=gpd.points_from_xy(
            filtered_flats["longitude"], filtered_flats["latitude"]
        ),
        crs=4326,
    ).to_crs(epsg=target_crs)

    gdf_city_full.to_parquet(output_parquet)
    print(f"Flats data saved successfully! Shape: {gdf_city_full.shape}")


def fetch_osm_features(city_name: str, poi_config: dict, target_crs: int):
    """Fetches and categorizes points of interest, nature, and industrial zones via OSMnx."""
    poi_list, nature_list, industrial_list = [], [], []
    nature_categories = [
        "meadow",
        "park",
        "forest",
        "water",
        "nature_reserve",
        "grassland",
    ]

    for category_name, tags in poi_config.items():
        print(f"Downloading: {category_name}...")
        try:
            gdf = ox.features_from_place(city_name, tags=tags)

            if gdf.empty:
                print(f"No data found for {category_name}.")
                continue

            gdf["name"] = gdf.get("name", "Unknown name").fillna("Unknown name")
            gdf = gdf.reset_index().to_crs(epsg=target_crs)
            gdf["category"] = category_name

            # Nature handling
            if category_name in nature_categories:
                if category_name == "nature_reserve" and "protect_class" in gdf.columns:
                    gdf = gdf.loc[
                        gdf["protect_class"].isin(["19", "1b", "2", "3", "4", "97"])
                    ]
                nature_list.append(gdf[["name", "category", "geometry"]])

            # Industrial handling
            elif category_name == "industrial":
                industrial_list.append(gdf[["name", "category", "geometry"]])

            # General PoI handling
            else:
                if category_name == "liquor_store":
                    if "opening_hours" in gdf.columns:
                        gdf = gdf.loc[gdf["opening_hours"] == "24/7"]
                    else:
                        gdf = gdf.iloc[0:0]  # Empty dataframe

                # Converting polygons to points for standard PoIs
                gdf["geometry"] = gdf["geometry"].centroid
                poi_list.append(gdf[["name", "category", "geometry"]])

        except Exception as e:
            print(f"Error loading {category_name}: {e}")

    # saving outputs
    if poi_list:
        pd.concat(poi_list, ignore_index=True).to_parquet(cfg.POI_PARQUET)
        print("POIs saved.")
    if nature_list:
        pd.concat(nature_list, ignore_index=True).to_parquet(cfg.NATURE_PARQUET)
        print("Nature saved.")
    if industrial_list:
        pd.concat(industrial_list, ignore_index=True).to_parquet(cfg.INDUSTRIAL_PARQUET)
        print("Industrial saved.")


if __name__ == "__main__":
    # 1. Processing apartments
    process_apartments(
        dir_path=cfg.RAW_DIR / "flats_dataset",
        city_name=cfg.FLATS_DATA_CITY_NAME,
        target_crs=cfg.TARGET_CRS,
        output_parquet=cfg.FLATS_PARQUET,
    )

    # 2. Fetching osm features
    fetch_osm_features(
        city_name=cfg.OSMNX_CITY_NAME,
        poi_config=cfg.osmnx_poi_config,
        target_crs=cfg.TARGET_CRS,
    )

from pathlib import Path

BUFFER_RADIUS_METERS = 1800
TARGET_CRS = 2180

ROOT_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"
RAW_DIR = DATA_DIR / "raw"

NATURE_PARQUET = PROCESSED_DIR / "krakow_nature.parquet"
INDUSTRIAL_PARQUET = PROCESSED_DIR / "krakow_industrial.parquet"
POI_PARQUET = PROCESSED_DIR / "krakow_poi.parquet"
FLATS_PARQUET = PROCESSED_DIR / "krakow_flats.parquet"
REACHABILITY_PARQUET = PROCESSED_DIR / "krakow_stop_reachability.parquet"

# in standard gtfs tram route type is 0, but for Kraków, for some reason it is 900
TRAM_ROUTE_CODE = 900
TRANSPORT_SATURATION_POINT = 180

# in order: longitude, latitude
city_center = (19.937989, 50.061466)
default_point = (19.921678, 50.066130)

NATURE_THRESHOLD_STEEPNESS = 0.0012
NATURE_THRESHOLD_MAX = 0.28

DIST_TO_CENTER_STEEPNESS = 0.002
DIST_TO_CENTER_MIDPOINT = 2300.0


weights = {
    "nature": {
        "global": 27.2,
        "partial": {
            "water": 0.25,
            "park": 0.42,
            "meadow": 0.12,
            "grassland": 0.08,
            "forest": 0.25,
            "nature_reserve": 0.5,
        },
    },
    "destructors": {
        "partial": {"industrial": 0.13, "abandoned": 0.08, "liquor_store": 0.17},
        "restaurant_threshold": 20,
    },
    "children": {
        "global": 5.9,
        "partial": {"school": 0.3, "kindergarten": 0.5, "playground": 0.2},
        "threshold": {"school": 3, "kindergarten": 3, "playground": 4},
    },
    "daily": {
        "global": 27.8,
        "partial": {
            "convenience": 0.45,
            "supermarket": 0.20,
            "clinic": 0.25,
            "pharmacy": 0.10,
        },
        "threshold": {"supermarket": 3, "convenience": 4, "clinic": 2, "pharmacy": 2},
    },
    "culture": {
        "global": 9.2,
        "partial": {"restaurant": 0.4, "cafe": 0.3, "distance_to_center": 0.3},
        "threshold": {"cafe": 20, "restaurant": 40},
    },
    "transport": {
        "global": 29.9,
        "partial": {"tram_stop": 0.70, "bus_stop": 0.30},
        "threshold": {"tram_stop": 4, "bus_stop": 4},
    },
}


spatial_dynamics = {
    "daily": {
        "clinic": {"optimal_dist": 600, "max_dist": 1500, "power": 2.0},
        "pharmacy": {"optimal_dist": 600, "max_dist": 1500, "power": 2.0},
        "convenience": {"optimal_dist": 350, "max_dist": 800, "power": 1.0},
        "supermarket": {"optimal_dist": 500, "max_dist": 800, "power": 2.0},
    },
    "nature": {
        "park": {"optimal_dist": 300, "max_dist": 1800, "power": 1.5},
        "water": {"optimal_dist": 300, "max_dist": 1800, "power": 1.5},
        "forest": {"optimal_dist": 300, "max_dist": 1800, "power": 1.5},
        "meadow": {"optimal_dist": 300, "max_dist": 1800, "power": 1.5},
        "grassland": {"optimal_dist": 300, "max_dist": 1800, "power": 1.5},
        "nature_reserve": {"optimal_dist": 300, "max_dist": 1800, "power": 1.5},
    },
    "children": {
        "school": {"optimal_dist": 300, "max_dist": 1200, "power": 2.0},
        "kindergarten": {"optimal_dist": 300, "max_dist": 800, "power": 1.0},
        "playground": {"optimal_dist": 250, "max_dist": 800, "power": 1.0},
    },
    "destructors": {
        "industrial": {"optimal_dist": 0, "max_dist": 2000, "power": 2.0},
        "abandoned": {"optimal_dist": 0, "max_dist": 400, "power": 1.0},
        "liquor_store": {"optimal_dist": 0, "max_dist": 400, "power": 1.0},
        "restaurant": {"optimal_dist": 0, "max_dist": 300, "power": 2.0},
    },
    "culture": {
        "cafe": {"optimal_dist": 250, "max_dist": 900, "power": 1.0},
        "restaurant": {"optimal_dist": 300, "max_dist": 1200, "power": 2.0},
    },
    "transport": {
        "tram_stop": {"optimal_dist": 400, "max_dist": 1000, "power": 0.67},
        "bus_stop": {"optimal_dist": 400, "max_dist": 1000, "power": 0.67},
    },
}

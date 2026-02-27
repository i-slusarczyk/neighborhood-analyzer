import math
from pathlib import Path

BUFFER_RADIUS_METERS = 1200
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


city_center = (50.061466, 19.937989)
default_point = (50.066130, 19.921678)


weights = {
    "nature": {
        "global": 29.2,
        "partial": {
            "water": 0.22,
            "park": 0.42,
            "meadow": 0.09,
            "grassland": 0.02,
            "forest": 0.25,
            "nature_reserve": 0.5  # high weight over 1.0 because it's a nice addition - not a need
        }
    },
    "destructors": {
        "partial": {
            "industrial": 0.25,
            "abandoned": 0.10,
            "liquor_store": 0.25
        },
        "restaurant_threshold": 20
    },
    "children": {
        "global": 5.9,
        "partial": {
            "school": 0.3,
            "kindergarten": 0.5,
            "playground": 0.2
        },
        "threshold": {
            "school": 3,
            "kindergarten": 3,
            "playground": 4
        }
    },
    "daily": {
        "global": 27.8,
        "partial": {
            "convenience": 0.45,
            "supermarket": 0.20,
            "clinic": 0.25,
            "pharmacy": 0.10
        },
        "threshold": {
            "supermarket": 3,
            "convenience": 4,
            "clinic": 2,
            "pharmacy": 2
        }
    },

    "culture": {
        "global": 7.2,
        "partial": {
            "restaurant": 0.4,
            "cafe": 0.3,
            "distance_to_center": 0.3
        },
        "threshold": {
            "cafe": 20,
            "restaurant": 40
        }
    },

    "transport": {
        "global": 29.9,
        "partial": {
            "tram_stop": 0.70,
            "bus_stop": 0.30
        },
        "threshold": {
            "tram_stop": 4,
            "bus_stop": 4
        }
    }
}

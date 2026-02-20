from utils import *
import pandas as pd


def load_data():
    return gpd.read_parquet(r"data\krakow.parquet")


testing_point = (50.066130, 19.921678)
lat = testing_point[0]
lon = testing_point[1]

shops = get_poi(lat, lon, tags={"shop": True})
amenities = get_poi(lat, lon, tags={"amenity": True})


markers = pd.concat([shops, amenities])

median_price = get_flats_nearby(load_data(), lat, lon)
print(median_price)

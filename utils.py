import osmnx as ox
import geopandas as gpd
cafes = ox.features_from_point((50.066303, 19.921035),
                               dist=1000, tags={"amenity": "cafe"})
print(cafes.info())

import osmnx as ox


agh = (50.067, 19.913)
tags = {'shop': 'convenience'}
gdf = ox.features_from_point(agh, tags=tags, dist=1000)

print(gdf.head())
print(gdf.shape)  # Ile ich znalazł?

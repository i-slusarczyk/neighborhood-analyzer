from utils import *
import pandas as pd

mapbox_token = "pk.eyJ1Ijoia2phbHYiLCJhIjoiY21lbWk5N3BqMG9xazJpczlxdTZyb2xueiJ9._l4sMzp9t6JVxx1ESh6EBQ"
style_id = "light-v11"
mapbox_url = f"https://api.mapbox.com/styles/v1/mapbox/{style_id}/tiles/256/{{z}}/{{x}}/{{y}}@2x?access_token={mapbox_token}"

dom = (50.172617, 19.916644)
lat = dom[0]
lon = dom[1]
# cafes = get_cafes(lat, lon)
shops = get_poi(lat, lon, tags={"shop": True})
amenities = get_poi(lat, lon, tags={"amenity": True})
shops.explore(marker_type="marker", tiles=mapbox_url,
              attr="© Mapbox © OpenStreetMap", cmap="viridis").save("features.html")

markers = pd.concat([shops, amenities])
markers.explore(marker_type="marker", tiles=mapbox_url,
                attr="© Mapbox © OpenStreetMap", cmap="viridis").save("features.html")
print("Success")

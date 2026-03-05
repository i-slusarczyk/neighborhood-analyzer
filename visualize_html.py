import geopandas as gpd
gdf = gpd.read_parquet("h3.parquet")
gdf["final_score"] = gdf["final_score"]**2
gdf.explore(column="final_score", cmap="RdYlGn", tooltip=[
    "final_score", "median_price", "value_ratio"]).save("mapa.html")
print(gdf.loc[gdf["final_score"].idxmax(), "hex_id"])

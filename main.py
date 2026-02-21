from utils import get_poi, get_flats_nearby
import geopandas as gpd
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium
from pathlib import Path


@st.cache_data
def load_data():
    return gpd.read_parquet(Path("data") / "krakow_flats.parquet")


testing_point = (50.066130, 19.921678)
lat = testing_point[0]
lon = testing_point[1]


median_price = get_flats_nearby(load_data(), lat, lon)
st.write(
    f"Mediana ceny za metr w okolicy twojej pinezki to {median_price} zł")
mapa = markers.explore(marker_kwds={"radius": '10'})
st_folium(mapa)

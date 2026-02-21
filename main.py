from utils import get_poi, get_flats_nearby
import geopandas as gpd
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from pathlib import Path
from folium.plugins import BeautifyIcon


@st.cache_data
def load_poi():
    return gpd.read_parquet(Path("data")/"krakow_poi.parquet")


@st.cache_data
def load_nature():
    return gpd.read_parquet(Path("data")/"krakow_nature.parquet")


@st.cache_data
def load_flats():
    return gpd.read_parquet(Path("data")/"krakow_flats.parquet")


testing_point = (50.066130, 19.921678)
lat = testing_point[0]
lon = testing_point[1]

median_price = get_flats_nearby(load_flats(), lat, lon)[
    "pricePerMeter"].median()
st.write(f"Mediana ceny za metr w okolicy twojej pinezki to {median_price} zł")

icons_config = {
    "cafe": {"icon": "coffee", "color": "darkred"},
    "kindergarten": {"icon": "child", "color": "blue"},
    "supermarket": {"icon": "shopping-cart", "color": "green"},
    "tram_stop": {"icon": "train", "color": "cadetblue"}
}

ikona_przedszkola = BeautifyIcon(
    icon="child",
    icon_shape="circle",  # To usuwa nóżkę pinezki i robi idealne koło
    border_color="#1E90FF",  # Niebieska obwódka (DodgerBlue)
    text_color="#1E90FF",  # Kolor samej ikonki
    background_color="white",  # Tło wewnątrz kółka
    border_width=2  # Grubość obwódki w pikselach
)

kindergartens = get_poi(load_poi(), lat, lon, "kindergarten", radius=20000)
m = kindergartens.explore(marker_type="marker", marker_kwds={
                          "icon": folium.Icon(icon="child", prefix="fa", color="blue")})
folium.LayerControl().add_to(m)
st_folium(m)

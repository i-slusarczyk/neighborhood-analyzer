import geopandas as gpd
from pathlib import Path
import streamlit as st
import folium
from streamlit_folium import st_folium
from utils import get_poi, get_flats_nearby, get_nature, nature_score


@st.cache_data
def load_poi():
    return gpd.read_parquet(Path("data")/"krakow_poi.parquet")


@st.cache_data
def load_nature():
    return gpd.read_parquet(Path("data")/"krakow_nature.parquet")


@st.cache_data
def load_flats():
    return gpd.read_parquet(Path("data")/"krakow_flats.parquet")


city_center_lon = 19.937989
city_center_lat = 50.061466

if "pin_lat" not in st.session_state:
    default_point = (50.066130, 19.921678)
    st.session_state.pin_lat = default_point[0]
    st.session_state.pin_lon = default_point[1]
    st.session_state.map_center_lat = st.session_state.pin_lat
    st.session_state.map_center_lon = st.session_state.pin_lon
    st.session_state.map_zoom = 14
lat = st.session_state.pin_lat
lon = st.session_state.pin_lon

distance_to_center = get_distance_to_center(
    lat, lon, city_center_lat, city_center_lon)


median_price = get_flats_nearby(load_flats(), lat, lon)[
    "pricePerMeter"].median()
st.write(
    f"Mediana ceny w latach 2023-2024 za metr mieszkania w okolicy twojej pinezki to {median_price:.2f} zł")


local_nature = get_nature(load_nature(), lat, lon)

nature_score = nature_score(
    gdf=local_nature, partial_weights=nature_weights, global_weight=global_weights["nature"])
st.write(nature_score)

m_base = folium.Map(
    location=[st.session_state.map_center_lat,
              st.session_state.map_center_lon],
    zoom_start=st.session_state.map_zoom
)
local_nature.explore(m=m_base)
map_data = st_folium(m_base, key="Green areas", width=800, height=600)
st.write(local_nature.area.sum())
st.write(map_data)


if map_data and map_data.get("last_clicked"):
    clicked_lat = map_data["last_clicked"]["lat"]
    clicked_lon = map_data["last_clicked"]["lng"]
    if clicked_lat != st.session_state.pin_lat or clicked_lon != st.session_state.pin_lon:
        st.session_state.pin_lat = clicked_lat
        st.session_state.pin_lon = clicked_lon

        if map_data.get("center"):
            st.session_state.map_center_lat = map_data["center"]["lat"]
            st.session_state.map_center_lon = map_data["center"]["lng"]

        if map_data.get("zoom"):
            st.session_state.map_zoom = map_data["zoom"]

        st.rerun()

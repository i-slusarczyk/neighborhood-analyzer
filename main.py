import geopandas as gpd
from pathlib import Path
import streamlit as st
import folium
from streamlit_folium import st_folium
from utils import *
import config


@st.cache_data
def load_poi():
    return gpd.read_parquet(Path("data")/"krakow_poi.parquet")


@st.cache_data
def load_nature():
    return gpd.read_parquet(Path("data")/"krakow_nature.parquet")


@st.cache_data
def load_flats():
    return gpd.read_parquet(Path("data")/"krakow_flats.parquet")


@st.cache_data
def load_industrial():
    return gpd.read_parquet(Path("data") / "krakow_industrial.parquet")


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


daily = list(config.weights["daily"]["partial"])
children = list(config.weights["children"]["partial"])
culture = list(config.weights["culture"]["partial"])
transport = list(config.weights["transport"]["partial"])


median_price = get_flats_nearby(load_flats(), lat, lon)[
    "pricePerMeter"].median()
st.write(
    f"Mediana ceny w latach 2023-2024 za metr mieszkania w okolicy twojej pinezki to {median_price:.2f} zł")


local_nature = clip_to_buffer(load_nature(), lat, lon)
local_pois = local_pois(load_poi(), lat, lon)
local_industry = clip_to_buffer(load_industrial(), lat, lon)

nature_score = nature_score(
    gdf=local_nature, weights=config.weights)
st.write(f"Nature score: {nature_score:.2f}")

culture_score = culture_score(local_pois, config.weights, distance_to_center)
st.write(f"Culture score: {culture_score:.2f}")

daily_score = daily_score(local_pois, config.weights)
st.write(f"Daily score: {daily_score:.2f}")

transport_score = transport_score(local_pois, config.weights)
st.write(f"Transport score: {transport_score:.2f}")

children_score = children_score(local_pois, config.weights)
st.write(f"Children score: {children_score:.2f}")

destructors = destructors(local_pois, local_industry, config.weights)
st.write(f"Destructors: {destructors:.2f}")

total_base_score = nature_score + children_score + \
    transport_score + daily_score + culture_score
final_score = max(total_base_score - destructors, 0.0)
st.write(f"Total base score: {total_base_score:.2f}")
st.write(f"Final score: {final_score:.2f}")
m_base = folium.Map(
    location=[st.session_state.map_center_lat,
              st.session_state.map_center_lon],
    zoom_start=st.session_state.map_zoom
)
local_nature.explore(m=m_base)
map_data = st_folium(m_base, key="Green areas", width=800, height=600)


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

import geopandas as gpd
from pathlib import Path
import streamlit as st
import folium
from streamlit_folium import st_folium
import src.config as cfg
import src.utils as ut


@st.cache_data
def load_geodata(file_path):
    return gpd.read_parquet(file_path)


poi_gdf = load_geodata(cfg.POI_PARQUET)
nature_gdf = load_geodata(cfg.NATURE_PARQUET)
flats_gdf = load_geodata(cfg.FLATS_PARQUET)
industrial_gdf = load_geodata(cfg.INDUSTRIAL_PARQUET)
reachability_gdf = load_geodata(cfg.REACHABILITY_PARQUET)


city_center_lon, city_center_lat = cfg.city_center[0], cfg.city_center[1]

default_point = cfg.default_point

if "pin_lat" not in st.session_state:
    st.session_state.pin_lon = default_point[0]
    st.session_state.pin_lat = default_point[1]
    st.session_state.map_center_lat = st.session_state.pin_lat
    st.session_state.map_center_lon = st.session_state.pin_lon
    st.session_state.map_zoom = 14

pin_lon = st.session_state.pin_lon
pin_lat = st.session_state.pin_lat

distance_to_center = ut.get_distance_to_center(
    pin_lon, pin_lat, city_center_lon, city_center_lat)


daily = list(cfg.weights["daily"]["partial"])
children = list(cfg.weights["children"]["partial"])
culture = list(cfg.weights["culture"]["partial"])
transport = list(cfg.weights["transport"]["partial"])


median_price = ut.get_flats_nearby(flats_gdf, pin_lon, pin_lat)[
    "pricePerMeter"].median()
st.write(
    f"Mediana ceny w latach 2023-2024 za metr mieszkania w okolicy twojej pinezki to {median_price:.2f} zł")


local_nature = ut.clip_to_buffer(nature_gdf, pin_lon, pin_lat)
local_pois = ut.local_pois(poi_gdf, pin_lon, pin_lat)
local_industry = ut.clip_to_buffer(industrial_gdf, pin_lon, pin_lat)

nature_score = ut.nature_score(
    gdf=local_nature, weights=cfg.weights)
st.write(f"Nature score: {nature_score:.2f}")

culture_score = ut.culture_score(
    local_pois, cfg.weights, distance_to_center)
st.write(f"Culture score: {culture_score:.2f}")

daily_score = ut.daily_score(local_pois, cfg.weights)
st.write(f"Daily score: {daily_score:.2f}")

transport_score = ut.transport_score(local_pois, cfg.weights)
st.write(f"Transport score: {transport_score:.2f}")

children_score = ut.children_score(local_pois, cfg.weights)
st.write(f"Children score: {children_score:.2f}")

destructors = ut.destructors(local_pois, local_industry, cfg.weights)
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
    if clicked_lon != st.session_state.pin_lon or clicked_lat != st.session_state.pin_lat:
        st.session_state.pin_lon = clicked_lon
        st.session_state.pin_lat = clicked_lat

        if map_data.get("center"):
            st.session_state.map_center_lon = map_data["center"]["lng"]
            st.session_state.map_center_lat = map_data["center"]["lat"]

        if map_data.get("zoom"):
            st.session_state.map_zoom = map_data["zoom"]

        st.rerun()

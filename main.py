import geopandas as gpd
import streamlit as st
import folium
from streamlit_folium import st_folium
import src.config as cfg
import src.utils as ut
import src.scoring as scoring


@st.cache_data
# loading data from parquet files
def load_geodata(file_path):
    return gpd.read_parquet(file_path)


@st.cache_data(max_entries=1)
# cleaning intersecting nature
def clean_nature(_gdf: gpd.GeoDataFrame, weights: dict):
    return ut.intersecting_nature(_gdf, weights)


# streamlit initial variables
def init_session_state(default_point):
    if "pin_lat" not in st.session_state:
        st.session_state.pin_lon = default_point[0]
        st.session_state.pin_lat = default_point[1]
        st.session_state.map_center_lat = st.session_state.pin_lat
        st.session_state.map_center_lon = st.session_state.pin_lon
        st.session_state.map_zoom = 14


# handling changing selected point on map
def handle_map_interactions(map_data):
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


def main():
    default_point = cfg.default_point
    init_session_state(default_point)

    # loading data
    poi_gdf = load_geodata(cfg.POI_PARQUET)

    flats_gdf = load_geodata(cfg.FLATS_PARQUET)
    industrial_gdf = load_geodata(cfg.INDUSTRIAL_PARQUET)
    reachability_gdf = load_geodata(cfg.REACHABILITY_PARQUET)

    nature_gdf = load_geodata(cfg.NATURE_PARQUET)
    nature_clean_gdf = clean_nature(nature_gdf, cfg.weights)

    pin_lon = st.session_state.pin_lon
    pin_lat = st.session_state.pin_lat

    result = scoring.calculate_full_score(pin_lon, pin_lat, poi_gdf, industrial_gdf,
                                          reachability_gdf, nature_clean_gdf, flats_gdf, cfg.city_center, True)

    layers = result["layers"]

    # output
    st.write(
        f"Mediana ceny w latach 2023-2024 za metr mieszkania w okolicy twojej pinezki to {result["median_price"]:.2f} zł")
    st.write(f"Total base score: {result["base_score"]:.2f}")
    st.write(f"Final score: {result["final_score"]:.2f}")

    # map rendering
    m_base = folium.Map(
        location=[st.session_state.map_center_lat,
                  st.session_state.map_center_lon],
        zoom_start=st.session_state.map_zoom
    )

    if not layers["nature"].empty:
        layers["nature"].explore(
            m=m_base,
            name="Green areas",
            highlight=True,
            tooltip=False
        )
    if not layers["transport"].empty:
        layers["transport"].explore(
            m=m_base,
            name="Public transport stops",
            highlight=True,
        )
    folium.Marker(location=(pin_lat, pin_lon)).add_to(m_base)
    folium.LayerControl(collapsed=False).add_to(m_base)
    map_data = st_folium(m_base, key="PoI map", width=800, height=600)

    # streamlit map interactions
    handle_map_interactions(map_data)


if __name__ == "__main__":
    main()

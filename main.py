import geopandas as gpd
import streamlit as st
import folium
from streamlit_folium import st_folium
import src.config as cfg
import src.utils as ut


@st.cache_data
def load_geodata(file_path):
    return gpd.read_parquet(file_path)


def init_session_state(default_point):
    if "pin_lat" not in st.session_state:
        st.session_state.pin_lon = default_point[0]
        st.session_state.pin_lat = default_point[1]
        st.session_state.map_center_lat = st.session_state.pin_lat
        st.session_state.map_center_lon = st.session_state.pin_lon
        st.session_state.map_zoom = 14


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
    nature_gdf = load_geodata(cfg.NATURE_PARQUET)
    flats_gdf = load_geodata(cfg.FLATS_PARQUET)
    industrial_gdf = load_geodata(cfg.INDUSTRIAL_PARQUET)
    reachability_gdf = load_geodata(cfg.REACHABILITY_PARQUET)

    city_center_lon, city_center_lat = cfg.city_center[0], cfg.city_center[1]

    pin_lon = st.session_state.pin_lon
    pin_lat = st.session_state.pin_lat

    distance_to_center = ut.get_distance_to_center(
        pin_lon, pin_lat, city_center_lon, city_center_lat)

    # calculations

    median_price = ut.points_in_radius(flats_gdf, pin_lon, pin_lat, add_distance_col=False)[
        "pricePerMeter"].median()

    local_nature = ut.clip_to_buffer(nature_gdf, pin_lon, pin_lat)
    local_nature_clean = ut.intersecting_nature(
        local_nature, weights=cfg.weights)

    local_pois = ut.points_in_radius(poi_gdf, pin_lon, pin_lat)

    local_industry = ut.clip_to_buffer(industrial_gdf, pin_lon, pin_lat)

    local_transport = ut.points_in_radius(
        gdf=reachability_gdf, lon=pin_lon, lat=pin_lat)
    stops_nearby_reachability = ut.find_reachability(
        local_transport)

    scores = {
        "nature": ut.nature_score(gdf=local_nature_clean, weights=cfg.weights),
        "children": ut.children_score(local_pois, cfg.weights),
        "daily": ut.daily_score(local_pois, cfg.weights),
        "transport": ut.transport_score(stops_nearby_reachability, cfg.weights, cfg.TRANSPORT_SATURATION_POINT, cfg.TRAM_ROUTE_CODE),
        "culture": ut.culture_score(local_pois, cfg.weights, distance_to_center),
    }

    destructor_points = ut.destructors(local_pois, local_industry, cfg.weights)

    total_base_score = sum(scores.values())
    final_score = max(total_base_score - destructor_points, 0.0)

    # output

    st.write(
        f"Mediana ceny w latach 2023-2024 za metr mieszkania w okolicy twojej pinezki to {median_price:.2f} zł")
    st.write(f"Total base score: {total_base_score:.2f}")
    st.write(f"Final score: {final_score:.2f}")

    # map rendering

    m_base = folium.Map(
        location=[st.session_state.map_center_lat,
                  st.session_state.map_center_lon],
        zoom_start=st.session_state.map_zoom
    )

    if not local_nature_clean.empty:
        local_nature_clean.explore(
            m=m_base,
            name="Green areas",
            highlight=True,
            tooltip=False
        )
    if not stops_nearby_reachability.empty:
        stops_nearby_reachability.explore(
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

import geopandas as gpd
import streamlit as st
import folium
from streamlit_folium import st_folium
import src.config as cfg
import src.utils as ut
import src.scoring as scoring

st.set_page_config(page_title="Kraków QoL", layout="wide")


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
    hex_gdf = load_geodata("data/processed/h3.parquet")

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

    tab1, tab2 = st.tabs(["Place Rating", "Overall Map"])

    with tab1:
        st.markdown("### Scoring Details")

        components = result["component_scores"]

        n_cols = len(components) + 2

        cols = st.columns(n_cols)

        for i, (category_name, value) in enumerate(components.items()):
            cols[i].metric(label=category_name.capitalize(),
                           value=f"{value:.1f}")
        cols[-2].metric(label="Destructors",
                        value=f"{result["destructors"]:.1f}")
        cols[-1].metric(label="Total score",
                        value=f"{result["final_score"]:.1f}")
        if result["median_price"] is not None:
            st.subheader(
                f"Median price for a square meter nearby your pin is {result['median_price']:.0f} zł")
        else:
            st.subheader("Not enough flat offers found nearby")

        # map rendering
        m_base = folium.Map(
            location=[st.session_state.map_center_lat,
                      st.session_state.map_center_lon],
            zoom_start=st.session_state.map_zoom,
            tiles=None
        )
        folium.TileLayer(tiles="CartoDB Positron",
                         name="CartoDB Positron").add_to(m_base)

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
        map_data = st_folium(m_base, key="PoI map",
                             use_container_width=True, height=500)

        handle_map_interactions(map_data)

    with tab2:
        m_hex = folium.Map(
            location=[cfg.city_center[1], cfg.city_center[0]], zoom_start=12, tiles=None)

        folium.TileLayer(tiles="CartoDB Positron",
                         name="CartoDB Positron",).add_to(m_hex)

        m_macro = hex_gdf.assign(
            final_score=hex_gdf["final_score"].round(2),
            median_price=hex_gdf["median_price"].round(0),
            value_ratio=(hex_gdf["value_ratio"]*15).round(2))

        value_ratio_map = m_macro.explore(column="value_ratio", cmap="RdYlGn", tooltip=[
            "final_score", "median_price", "value_ratio"], m=m_hex, name="Value Ratio", legend=False, show=True)
        m_macro.explore(column="final_score", cmap="RdYlGn", tooltip=[
            "final_score", "median_price", "value_ratio"], m=m_hex, name="Final Score", legend=False, show=False)
        median_price_map = m_macro.explore(column="median_price", cmap="RdYlGn", tooltip=[
            "final_score", "median_price", "value_ratio"], m=m_hex, name="Median price", legend=False, show=False)

        folium.LayerControl(collapsed=False).add_to(m_hex)

        st_folium(m_hex, use_container_width=True)

    # base map interactions


if __name__ == "__main__":
    main()

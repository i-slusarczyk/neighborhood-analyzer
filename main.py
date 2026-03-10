import geopandas as gpd
from geopy.geocoders import Nominatim
import streamlit as st
from streamlit_folium import st_folium
import src.config as cfg
import src.utils as ut
import src.scoring as scoring
import src.mapping as gen_map

st.set_page_config(page_title="Kraków QoL", layout="wide")


@st.cache_data
# loading data from parquet files
def load_geodata(file_path):
    return gpd.read_parquet(file_path)


@st.cache_data(max_entries=1)
# cleaning intersecting nature
def clean_nature(_gdf: gpd.GeoDataFrame, weights: dict):
    return ut.intersecting_nature(_gdf, weights)


@st.cache_data
def cache_top_hexagons(_gdf, sorting_col):
    geocoder = Nominatim(user_agent="krakow qol scorer")

    def get_address(row):
        try:
            location = geocoder.reverse(
                (row.geometry.centroid.y, row.geometry.centroid.x), timeout=5
            )
            return location if location else "Unknown Address"
        except Exception:
            return "Error loading address"

    needed_cols = ["final_score", "value_ratio", "median_price", "geometry"]

    if sorting_col == "value_ratio":
        top_hex_gdf = (
            _gdf.sort_values(by=sorting_col, ascending=True)
            .head(3)[needed_cols]
            .copy()
            .reset_index()
        )
    else:
        top_hex_gdf = (
            _gdf.sort_values(by=sorting_col, ascending=False)
            .head(3)[needed_cols]
            .copy()
            .reset_index()
        )

    top_hex_gdf = top_hex_gdf.assign(address=top_hex_gdf.apply(get_address, axis=1))

    return top_hex_gdf


def render_scoring_panel(result):
    st.markdown("### Scoring Details")
    c1, c2 = st.columns(2)
    categories = list(result["component_scores"].items())
    with c1:
        st.metric(
            label=categories[0][0].capitalize(), value=f"{categories[0][1]:.1f}"
        )  # Nature
        st.metric(
            label=categories[2][0].capitalize(), value=f"{categories[2][1]:.1f}"
        )  # Daily
        st.metric(
            label=categories[4][0].capitalize(), value=f"{categories[4][1]:.1f}"
        )  # Culture
    with c2:
        st.metric(
            label=categories[1][0].capitalize(), value=f"{categories[1][1]:.1f}"
        )  # Children
        st.metric(
            label=categories[3][0].capitalize(), value=f"{categories[3][1]:.1f}"
        )  # Transport
        st.metric(label="Destructors", value=f"{result['destructors']:.1f}")
    st.markdown("---")
    c3, c4 = st.columns(2)
    with c3:
        st.metric(label="Total Score", value=f"{result['final_score']:.1f} pts")

    if result["median_price"] is not None:
        with c4:
            st.metric(
                label="Price for Point", value=f"{result['value_ratio']:.1f} zł/pt"
            )
        st.info(f"**Median price nearby:** {result['median_price']:.0f} zł/m²")
    else:
        st.warning("Not enough flat offers found nearby")


def render_best_hexagons(hex_gdf):
    top_score_hex_gdf = cache_top_hexagons(hex_gdf, "final_score")
    top_value_hex_gdf = cache_top_hexagons(hex_gdf, "value_ratio")

    st.markdown("### Hexagons with highest scores")
    for i, row in top_score_hex_gdf.iterrows():
        icon = "🥇" if i == 0 else "🥈" if i == 1 else "🥉"
        st.write(f"{icon} {row['address']}")
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.caption(f"Score: **{row.final_score:.1f} pts**")
        col_m2.caption(f"Price: **{row.median_price:.0f} zł/m²**")
        col_m3.caption(f"Ratio: **{row.value_ratio:.0f} zł/pt**")

    st.markdown("---")
    st.markdown("### Hexagons with best value ratio")

    for i, row in top_value_hex_gdf.iterrows():
        icon = "🥇" if i == 0 else "🥈" if i == 1 else "🥉"
        st.write(f"{icon} {row['address']}")
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.caption(f"Score: **{row.final_score:.1f} pts**")
        col_m2.caption(f"Price: **{row.median_price:.0f} zł/m²**")
        col_m3.caption(f"Ratio: **{row.value_ratio:.0f} zł/pt**")


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
        if (
            clicked_lon != st.session_state.pin_lon
            or clicked_lat != st.session_state.pin_lat
        ):
            st.session_state.pin_lon = clicked_lon
            st.session_state.pin_lat = clicked_lat

            if map_data.get("center"):
                st.session_state.map_center_lon = map_data["center"]["lng"]
                st.session_state.map_center_lat = map_data["center"]["lat"]

            if map_data.get("zoom"):
                st.session_state.map_zoom = map_data["zoom"]

            st.rerun()


def main():

    # smaller top margin
    st.markdown(
        """
        <style>
        header.stAppHeader {
            background-color: transparent;
            pointer-events: none; 
        }
        section.stMain .block-container {
            padding-top: 2rem; 
        }
        iframe[title="streamlit_folium.st_folium"] {
        height: 70vh !important;
        }
        </style>""",
        unsafe_allow_html=True,
    )

    init_session_state(cfg.default_point)

    # loading data
    poi_gdf = load_geodata(cfg.POI_PARQUET)

    flats_gdf = load_geodata(cfg.FLATS_PARQUET)
    industrial_gdf = load_geodata(cfg.INDUSTRIAL_PARQUET)
    reachability_gdf = load_geodata(cfg.REACHABILITY_PARQUET)

    nature_gdf = load_geodata(cfg.NATURE_PARQUET)
    nature_clean_gdf = clean_nature(nature_gdf, cfg.weights)

    hex_gdf = load_geodata(cfg.H3_PARQUET)

    # output
    tab1, tab2 = st.tabs(["Place Rating", "Overall Map"])

    with tab1:
        left_panel, right_panel = st.columns([1.2, 2], gap="large")

        pin_lon = st.session_state.pin_lon
        pin_lat = st.session_state.pin_lat

        result = scoring.calculate_full_score(
            pin_lon,
            pin_lat,
            poi_gdf,
            industrial_gdf,
            reachability_gdf,
            nature_clean_gdf,
            flats_gdf,
            cfg.city_center,
            True,
        )
        layers = result["layers"]

        with left_panel:
            render_scoring_panel(result)

        with right_panel:
            st.markdown("### Points of Interest Map")
            m_base = gen_map.gen_micro_map(layers, st.session_state)
            map_data = st_folium(m_base, key="micro_map", use_container_width=True)

            handle_map_interactions(map_data)

    with tab2:
        left_marco, right_macro = st.columns([1.2, 2], gap="large")
        with left_marco:
            render_best_hexagons(hex_gdf)
        with right_macro:
            st.markdown("### Macro H3 Map")

            st_folium(
                gen_map.gen_macro_map(hex_gdf, cfg.city_center),
                key="macro_map",
                use_container_width=True,
                returned_objects=[],
            )


if __name__ == "__main__":
    main()

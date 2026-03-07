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


def generate_macro_map(_hex_gdf, city_center=cfg.city_center):
    _hex_gdf = _hex_gdf.assign(
        final_score=_hex_gdf["final_score"].round(2),
        median_price=_hex_gdf["median_price"].round(0),
        value_ratio=(_hex_gdf["value_ratio"]).round(2))

    m_macro = folium.Map(
        location=[city_center[1], city_center[0]], zoom_start=12, tiles=None)
    folium.TileLayer(tiles="CartoDB Positron",
                     name="CartoDB Positron",).add_to(m_macro)
    value_ratio_map = _hex_gdf.explore(column="value_ratio", scheme="Quantiles", k=7, cmap="RdYlGn_r", tooltip=[
        "final_score", "median_price", "value_ratio"], tooltip_kwds={"aliases": [
            "Final Score", "Median Price", "Price for Point"]}, m=m_macro, name="Price for Point", legend=False, show=True)
    final_score_map = _hex_gdf.explore(column="final_score", cmap="RdYlGn", tooltip=[
        "final_score", "median_price", "value_ratio"], tooltip_kwds={"aliases": [
            "Final Score", "Median Price", "Price for Point"]}, m=m_macro, name="Final Score", legend=False, show=False)
    median_price_map = _hex_gdf.explore(column="median_price", scheme="Quantiles", k=15, cmap="RdYlGn", tooltip=[
        "final_score", "median_price", "value_ratio"], tooltip_kwds={"aliases": [
            # 15 quantiles is very much, but I use them just to get more variety in colors - not to actually utilize quantiles
            "Final Score", "Median Price", "Price for Point"]}, m=m_macro, name="Median price", legend=False, show=False)

    folium.LayerControl(collapsed=False).add_to(m_macro)

    return m_macro


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
    st.markdown("""
        <style>
        header.stAppHeader {
            background-color: transparent;
            pointer-events: none; 
        }
        section.stMain .block-container {
            padding-top: 2rem; 
        }
        </style>""", unsafe_allow_html=True)
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

    # output

    tab1, tab2 = st.tabs(["Place Rating", "Overall Map"])

    with tab1:

        left_panel, right_panel = st.columns([1.2, 2], gap="large")

        pin_lon = st.session_state.pin_lon
        pin_lat = st.session_state.pin_lat

        result = scoring.calculate_full_score(pin_lon, pin_lat, poi_gdf, industrial_gdf,
                                              reachability_gdf, nature_clean_gdf, flats_gdf, cfg.city_center, True)
        layers = result["layers"]

        with left_panel:

            st.markdown("### Scoring Details")
            c1, c2 = st.columns(2)
            categories = list(result["component_scores"].items())
            with c1:
                st.metric(label=categories[0][0].capitalize(
                ), value=f"{categories[0][1]:.1f}")  # Nature
                st.metric(label=categories[2][0].capitalize(
                ), value=f"{categories[2][1]:.1f}")  # Daily
                st.metric(label=categories[4][0].capitalize(
                ), value=f"{categories[4][1]:.1f}")  # Culture
            with c2:
                st.metric(label=categories[1][0].capitalize(
                ), value=f"{categories[1][1]:.1f}")  # Children
                st.metric(label=categories[3][0].capitalize(
                ), value=f"{categories[3][1]:.1f}")  # Transport
                st.metric(label="Destructors",
                          value=f"{result["destructors"]:.1f}")
            st.markdown("---")
            c3, c4 = st.columns(2)
            with c3:
                st.metric(label="Total Score",
                          value=f"{result["final_score"]:.1f}")

            if result["median_price"] is not None:
                with c4:
                    st.metric(label="Price for Point",
                              value=f"{result["value_ratio"]:.1f}")
                st.info(
                    f"**Median price nearby:** {result['median_price']:.0f} zł/m²")
            else:
                st.warning("Not enough flat offers found nearby")
            # components = result["component_scores"]
            # n_cols = len(components) + 2

            # cols = st.columns(n_cols)

            # for i, (category_name, value) in enumerate(components.items()):
            #     cols[i].metric(label=category_name.capitalize(),
            #                    value=f"{value:.1f}")
            # cols[-2].metric(label="Destructors",
            #                 value=f"{result['destructors']:.1f}")
            # cols[-1].metric(label="Total score",
            #                 value=f"{result['final_score']:.1f}")
            # if result["median_price"] is not None:
            #     st.subheader(
            #         f"Median price for a square meter nearby your pin is {result['median_price']:.0f} zł")
            # else:
            #     st.subheader("Not enough flat offers found nearby")

            # st.write("Click on the map to change the location")

        with right_panel:
            # map rendering
            m_base = folium.Map(
                location=[st.session_state.map_center_lat,
                          st.session_state.map_center_lon],
                zoom_start=st.session_state.map_zoom,
                tiles=None
            )
            folium.TileLayer(tiles="CartoDB Positron",
                             name="CartoDB Positron").add_to(m_base)

            for layer in layers:
                layer_name = layer.capitalize()

                if layer == "nature":
                    if not layers[layer].empty:
                        layers[layer].explore(
                            m=m_base,
                            name=layer_name,
                            show=True,
                            tooltip=["category", "name"],
                            tooltip_kwds={"aliases": ["Category", "Name"]}
                        )
                    else:
                        folium.FeatureGroup(
                            name=layer_name, show=True).add_to(m_base)
                elif layer == "transport":
                    if not layers[layer].empty:
                        layers[layer].explore(
                            m=m_base,
                            name=layer_name,
                            show=True,
                            tooltip=["route_type",
                                     "stop_name", "max_reach_km"],
                            tooltip_kwds={"aliases": [
                                "Category", "Name", "Max Reach"]}
                        )
                    else:
                        folium.FeatureGroup(
                            name=layer_name, show=False).add_to(m_base)
                else:
                    if not layers[layer].empty:
                        layers[layer].explore(
                            m=m_base,
                            name=layer_name,
                            show=False,
                            tooltip=["category", "name"],
                            tooltip_kwds={"aliases": ["Category", "Name"]}
                        )
                    else:
                        folium.FeatureGroup(
                            name=layer_name, show=False).add_to(m_base)

            folium.Marker(location=(pin_lat, pin_lon)).add_to(m_base)
            folium.LayerControl(collapsed=False).add_to(m_base)
            map_data = st_folium(m_base, key="micro_map",
                                 use_container_width=True, height=600)

            handle_map_interactions(map_data)

    with tab2:
        st.markdown("### Macro H3 Map")
        st_folium(generate_macro_map(hex_gdf, cfg.city_center), key="macro_map",
                  use_container_width=True, height=500, returned_objects=[])

    # base map interactions


if __name__ == "__main__":
    main()

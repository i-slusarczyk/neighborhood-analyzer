"""
Geospatial visualization module for the scoring model.

Provides functions to generate interactive Folium maps:
- Macro View: A hexagonal grid overview of the entire city, comparing price-to-quality ratios.
- Micro View: A detailed breakdown of individual scoring layers (POI, nature, transport)
  for a specific location.
"""

import pandas as pd
import folium
import src.config as cfg


def gen_macro_map(_hex_gdf, city_center=cfg.city_center):
    """
    Generates an interactive city-wide map with hexagonal scoring layers.

    Args:
        _hex_gdf (gpd.GeoDataFrame): The scored H3 hexagonal grid.
        city_center (tuple, optional): Map center coordinates (lon, lat). Defaults to cfg.city_center.

    Returns:
        folium.Map: A map object with switchable layers for 'Final Score', 'Median Price',
            and 'Price for Point' (value ratio).
    """

    hex_gdf = _hex_gdf.copy()

    # Creating more user-friendly data format for visualization
    hex_gdf = hex_gdf.assign(
        score_display=hex_gdf["final_score"].apply(
            lambda x: f"{x:.1f} pts" if pd.notna(x) else "No data available"
        ),
        median_display=hex_gdf["median_price"].apply(
            lambda x: (
                f"{x:.0f} zł/m²"
                if pd.notna(x)
                else "Not enough flat offers found nearby"
            )
        ),
        value_ratio_display=(hex_gdf["value_ratio"]).apply(
            lambda x: (
                f"{x:.1f} zł for point"
                if pd.notna(x)
                else "Not enough flat offers found nearby"
            )
        ),
    )

    m_macro = folium.Map(
        location=[city_center[1], city_center[0]], zoom_start=12, tiles=None
    )
    folium.TileLayer(
        tiles="CartoDB Positron",
        name="CartoDB Positron",
    ).add_to(m_macro)

    hex_gdf.explore(
        column="value_ratio",
        scheme="Quantiles",
        k=7,
        cmap="RdYlGn_r",
        tooltip=["score_display", "median_display", "value_ratio_display"],
        tooltip_kwds={"aliases": ["Final Score", "Median Price", "Price for Point"]},
        m=m_macro,
        name="Price for Point",
        legend=False,
        show=True,
    )

    hex_gdf.explore(
        column="final_score",
        cmap="RdYlGn",
        tooltip=["score_display", "median_display", "value_ratio_display"],
        tooltip_kwds={"aliases": ["Final Score", "Median Price", "Price for Point"]},
        m=m_macro,
        name="Final Score",
        legend=False,
        show=False,
    )

    hex_gdf.explore(
        column="median_price",
        scheme="Quantiles",
        # Higher 'k' value used for finer color graduation
        k=15,
        cmap="viridis",
        tooltip=["score_display", "median_display", "value_ratio_display"],
        tooltip_kwds={"aliases": ["Final Score", "Median Price", "Price for Point"]},
        m=m_macro,
        name="Median price",
        legend=False,
        show=False,
    )

    folium.LayerControl(collapsed=False).add_to(m_macro)

    return m_macro


def gen_micro_map(layers, session_state):
    """
    Generates a detailed map of a specific area showing all scoring components.

    Visualizes individual data layers (Nature, Transport, POIs) within the scoring buffer
    to provide context for the calculated score.

    Args:
        layers (dict): Dictionary of GeoDataFrames (nature, transport, poi, etc.)
            clipped to the local buffer.
        session_state (object): State object containing current pin location and map settings.

    Returns:
        folium.Map: A detailed map with categorized and interactive spatial features.
    """

    # Importing Streamlit data
    m_base = folium.Map(
        location=[session_state.map_center_lat, session_state.map_center_lon],
        zoom_start=session_state.map_zoom,
        tiles=None,
    )
    folium.TileLayer(tiles="CartoDB Positron", name="CartoDB Positron").add_to(m_base)

    for layer_key, layer_data in layers.items():
        layer_name = layer_key.capitalize()

        layer_gdf = layer_data.copy()

        # Default visible layer
        is_visible = layer_key == "nature"

        if layer_key != "transport" and not layer_gdf.empty:
            layer_gdf = layer_gdf[
                ~layer_gdf.geometry.is_empty & layer_gdf.geometry.notna()
            ]

        # Empty layers remain visible in menu
        if layer_gdf.empty:
            folium.FeatureGroup(name=layer_name, show=is_visible).add_to(m_base)
            continue

        if layer_key == "nature":
            layer_gdf.explore(
                m=m_base,
                name=layer_name,
                show=is_visible,
                column="category",
                cmap="Set3",
                tooltip=["category", "name"],
                tooltip_kwds={"aliases": ["Category", "Name"]},
                legend=False,
            )
        elif layer_key == "transport":
            layer_gdf = layer_gdf.assign(
                category=layer_gdf["route_type"].apply(
                    lambda x: "Tram Stop" if x == cfg.TRAM_ROUTE_CODE else "Bus Stop"
                ),
                reach_pretty=layer_gdf["max_reach_km"].apply(lambda x: f"{x:.2f} km"),
            )

            layer_gdf.explore(
                m=m_base,
                name=layer_name,
                show=is_visible,
                column="category",
                cmap="Set1",
                tooltip=["category", "stop_name", "reach_pretty"],
                tooltip_kwds={
                    "aliases": ["Category", "Name", "Reachable distance (Unique)"]
                },
                marker_kwds={"radius": 3.5},
                legend=False,
            )
        else:
            layer_gdf.explore(
                m=m_base,
                name=layer_name,
                show=is_visible,
                column="category",
                cmap="Set2",
                tooltip=["category", "name"],
                tooltip_kwds={"aliases": ["Category", "Name"]},
                marker_kwds={"radius": 3.5},
                legend=False,
            )

    # Adding Marker on the location of last click
    folium.Marker(location=(session_state.pin_lat, session_state.pin_lon)).add_to(
        m_base
    )
    folium.LayerControl(collapsed=False).add_to(m_base)
    return m_base

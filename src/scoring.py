import src.utils as ut
import src.config as cfg


def calculate_full_score(
    lon: float,
    lat: float,
    poi_gdf,
    industrial_gdf,
    reachability_gdf,
    nature_gdf,
    flats_gdf,
    city_center: tuple,
    return_layers: bool = False,
) -> dict:
    """
    Computes a comprehensive spatial score for a single geographic point.

    The score evaluates the local neighborhood based on multiple weighted components:
    proximity to nature, child-friendly infrastructure, daily amenities, transport reachability,
    and cultural POIs. It penalizes the score based on industrial destructors and calculates
    an investment value ratio using the local median flat price.

    Args:
        lon (float): Longitude of the evaluated point.
        lat (float): Latitude of the evaluated point.
        poi_gdf (gpd.GeoDataFrame): City-wide points of interest (amenities, culture, etc.).
        industrial_gdf (gpd.GeoDataFrame): City-wide industrial areas (destructors).
        reachability_gdf (gpd.GeoDataFrame): Public transport reachability data.
        nature_gdf (gpd.GeoDataFrame): Greenery and nature polygons.
        flats_gdf (gpd.GeoDataFrame): Real estate listings data.
        city_center (tuple): Coordinates of the city center as (longitude, latitude).
        return_layers (bool, optional): If True, includes the locally clipped GeoDataFrames
            used for scoring in the result dictionary. Defaults to False.

    Returns:
        dict: A dictionary containing the 'final_score', 'base_score', specific 'component_scores',
            applied 'destructors', 'median_price', the calculated 'value_ratio', and optionally
            the local geometry 'layers'.
    """

    # Distance to the city center
    distance_to_center = ut.get_distance_to_center(
        lon, lat, city_center[0], city_center[1]
    )

    # *******************************
    # Calculations
    # *******************************

    local_flats = ut.points_in_radius(
        flats_gdf, lon, lat, radius=cfg.FLAT_FETCH_RADIUS, add_distance_col=False
    )
    if len(local_flats) >= cfg.FLAT_COUNT_THRESHOLD:
        median_price = local_flats["pricePerMeter"].median()
    else:
        median_price = None

    local_nature = ut.clip_to_buffer(nature_gdf, lon, lat)
    local_pois = ut.points_in_radius(poi_gdf, lon, lat)
    local_industry = ut.clip_to_buffer(industrial_gdf, lon, lat)
    local_transport = ut.points_in_radius(reachability_gdf, lon, lat)
    stops_nearby_reachability = ut.find_reachability(local_transport)

    component_scores = {
        "nature": ut.nature_score(
            gdf=local_nature, weights=cfg.weights, dynamics=cfg.spatial_dynamics
        ),
        "children": ut.children_score(
            gdf=local_pois, weights=cfg.weights, dynamics=cfg.spatial_dynamics
        ),
        "daily": ut.daily_score(
            gdf=local_pois, weights=cfg.weights, dynamics=cfg.spatial_dynamics
        ),
        "transport": ut.transport_score(
            gdf=stops_nearby_reachability,
            weights=cfg.weights,
            dynamics=cfg.spatial_dynamics,
        ),
        "culture": ut.culture_score(
            gdf=local_pois,
            weights=cfg.weights,
            dynamics=cfg.spatial_dynamics,
            distance_to_center=distance_to_center,
        ),
    }

    destructor_points = ut.destructors(
        gdf_poi=local_pois,
        gdf_industrial=local_industry,
        weights=cfg.weights,
        dynamics=cfg.spatial_dynamics,
    )

    total_base_score = sum(component_scores.values())
    final_score = max(total_base_score - destructor_points, 0.0)

    value_ratio = (median_price / final_score) if median_price else None
    result = {
        "final_score": final_score,
        "base_score": total_base_score,
        "component_scores": component_scores,
        "destructors": destructor_points,
        "median_price": median_price,
        "value_ratio": value_ratio,
    }

    if return_layers:
        result["layers"] = {
            "nature": local_nature,
            "transport": stops_nearby_reachability,
            "children": local_pois[
                local_pois["category"].isin(cfg.weights["children"]["partial"].keys())
            ],
            "daily": local_pois[
                local_pois["category"].isin(cfg.weights["daily"]["partial"].keys())
            ],
            "culture": local_pois[
                local_pois["category"].isin(cfg.weights["culture"]["partial"].keys())
            ],
            "industry": local_industry,
        }

    return result

import src.utils as ut
import src.config as cfg


def calculate_full_score(lon, lat, poi_gdf, industrial_gdf, reachability_gdf, nature_gdf, flats_gdf, city_center, return_layers=False):
    distance_to_center = ut.get_distance_to_center(
        lon, lat, city_center[0], city_center[1])

    # calculations
    local_flats = ut.points_in_radius(
        flats_gdf, lon, lat, radius=800, add_distance_col=False)
    if len(local_flats) >= 5:
        median_price = local_flats["pricePerMeter"].median()
    else:
        median_price = None

    local_nature = ut.clip_to_buffer(nature_gdf, lon, lat)
    local_pois = ut.points_in_radius(poi_gdf, lon, lat)
    local_industry = ut.clip_to_buffer(industrial_gdf, lon, lat)
    local_transport = ut.points_in_radius(reachability_gdf, lon, lat)
    stops_nearby_reachability = ut.find_reachability(local_transport)

    component_scores = {
        "nature": ut.nature_score(gdf=local_nature, weights=cfg.weights, dynamics=cfg.spatial_dynamics),
        "children": ut.children_score(local_pois, cfg.weights, cfg.spatial_dynamics),
        "daily": ut.daily_score(local_pois, cfg.weights, cfg.spatial_dynamics),
        "transport": ut.transport_score(stops_nearby_reachability, cfg.spatial_dynamics, cfg.weights, cfg.TRANSPORT_SATURATION_POINT, cfg.TRAM_ROUTE_CODE),
        "culture": ut.culture_score(local_pois, cfg.weights, distance_to_center, cfg.spatial_dynamics),
    }

    destructor_points = ut.destructors(
        local_pois, local_industry, cfg.spatial_dynamics, cfg.weights)

    total_base_score = sum(component_scores.values())
    final_score = max(total_base_score - destructor_points, 0.0)

    value_ratio = (median_price / final_score) if median_price else None
    result = {
        "final_score": final_score,
        "base_score": total_base_score,
        "component_scores": component_scores,
        "destructors": destructor_points,
        "median_price": median_price,
        "value_ratio": value_ratio
    }

    if return_layers:
        result["layers"] = {
            "nature": local_nature,
            "transport": stops_nearby_reachability,
            "children": local_pois[local_pois["category"].isin(cfg.weights["children"]["partial"].keys())],
            "daily": local_pois[local_pois["category"].isin(cfg.weights["daily"]["partial"].keys())],
            "culture": local_pois[local_pois["category"].isin(cfg.weights["culture"]["partial"].keys())],
            "industry": local_industry
        }

    return result

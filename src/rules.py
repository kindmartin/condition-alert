"""Evaluate a site's configured wind layers against fetched hourly forecast data."""
from interpolate import wind_at_altitude


def direction_ok(direction_deg, ranges):
    if not ranges:
        return True
    for r in ranges:
        lo, hi = r["min_deg"], r["max_deg"]
        if lo <= hi:
            if lo <= direction_deg <= hi:
                return True
        else:  # wraps through north, e.g. 315 -> 45
            if direction_deg >= lo or direction_deg <= hi:
                return True
    return False


def cloud_base_estimate_m(temperature_c, dew_point_c):
    if temperature_c is None or dew_point_c is None:
        return None
    return round(125 * (temperature_c - dew_point_c))


def evaluate_layer(layer, site, points_hourly, hour_index):
    point_name = layer["point"]
    hourly = points_hourly[point_name]

    if layer["kind"] == "surface":
        speed = hourly["wind_speed_10m"][hour_index]
        direction = hourly["wind_direction_10m"][hour_index]
        gust = hourly.get("wind_gusts_10m", [None])[hour_index]
        extrapolated = False
    else:
        elevation_m = site["points"][point_name]["elevation_m"]
        target_height = layer["meters"] if layer["kind"] == "msl" else elevation_m + layer["meters"]
        speed, direction, extrapolated = wind_at_altitude(hourly, hour_index, target_height)
        gust = None

    passed = speed is not None
    if passed:
        if "min_speed_kmh" in layer and speed < layer["min_speed_kmh"]:
            passed = False
        if "max_speed_kmh" in layer and speed > layer["max_speed_kmh"]:
            passed = False
        if gust is not None and "max_gust_kmh" in layer and gust > layer["max_gust_kmh"]:
            passed = False
        if "directions" in layer and direction is not None:
            if not direction_ok(direction, layer["directions"]):
                passed = False

    return {
        "passed": passed,
        "speed_kmh": speed,
        "direction_deg": direction,
        "gust_kmh": gust,
        "extrapolated": extrapolated,
    }


def evaluate_layers(layers, site, points_hourly):
    """Evaluate one subscriber's layers (AND'd together) against a site's forecast.

    Returns a list of per-hour results: [{time, passed, layers: {...}, cloud: {...}}, ...].
    """
    ref_point = next(iter(points_hourly))
    times = points_hourly[ref_point]["time"]

    launch_hourly = points_hourly.get("launch")
    results = []
    for hour_index, time_str in enumerate(times):
        layer_results = {
            layer["id"]: evaluate_layer(layer, site, points_hourly, hour_index)
            for layer in layers
        }
        hour_passed = all(r["passed"] for r in layer_results.values())

        cloud = {}
        if launch_hourly is not None:
            temp = launch_hourly.get("temperature_2m", [None])[hour_index]
            dew = launch_hourly.get("dew_point_2m", [None])[hour_index]
            cloud = {
                "cloud_cover": launch_hourly.get("cloud_cover", [None])[hour_index],
                "cloud_cover_low": launch_hourly.get("cloud_cover_low", [None])[hour_index],
                "cloud_cover_mid": launch_hourly.get("cloud_cover_mid", [None])[hour_index],
                "cloud_cover_high": launch_hourly.get("cloud_cover_high", [None])[hour_index],
                "freezing_level_height_m": launch_hourly.get("freezing_level_height", [None])[hour_index],
                "cloud_base_estimate_m": cloud_base_estimate_m(temp, dew),
            }

        results.append({"time": time_str, "passed": hour_passed, "layers": layer_results, "cloud": cloud})
    return results

"""Batched Open-Meteo forecast fetch for all configured site points."""
from collections import defaultdict

import requests

API_URL = "https://api.open-meteo.com/v1/forecast"

PRESSURE_LEVELS = [1000, 925, 850, 700, 600, 500]

DEFAULT_MODEL = "best_match"

# best_match blends several models automatically; the rest are explicit picks
# a site can opt into (docs/sites.json "model" field) if they want to compare
# a specific model instead of letting Open-Meteo choose.
ALLOWED_MODELS = {
    "best_match",
    "gfs_seamless",
    "ecmwf_ifs025",
    "icon_seamless",
    "jma_seamless",
    "gem_seamless",
    "meteofrance_seamless",
    "gfs_graphcast025",
}

HOURLY_VARS = (
    ["wind_speed_10m", "wind_direction_10m", "wind_gusts_10m"]
    + [f"wind_speed_{lvl}hPa" for lvl in PRESSURE_LEVELS]
    + [f"wind_direction_{lvl}hPa" for lvl in PRESSURE_LEVELS]
    + [f"geopotential_height_{lvl}hPa" for lvl in PRESSURE_LEVELS]
    + [
        "temperature_2m",
        "dew_point_2m",
        "cloud_cover",
        "cloud_cover_low",
        "cloud_cover_mid",
        "cloud_cover_high",
        "freezing_level_height",
    ]
)


def collect_points(sites):
    """Flatten every (site_id, point_name) -> point config into an ordered list.

    A site can set a top-level "model" field (one of ALLOWED_MODELS) to pin
    its forecast to a specific Open-Meteo model instead of the "best_match"
    default — every point of that site inherits it.
    """
    points = []
    for site in sites:
        model = site.get("model") or DEFAULT_MODEL
        if model not in ALLOWED_MODELS:
            model = DEFAULT_MODEL
        for point_name, point in site["points"].items():
            points.append(
                {
                    "site_id": site["id"],
                    "point_name": point_name,
                    "lat": point["lat"],
                    "lon": point["lon"],
                    "model": model,
                }
            )
    return points


def _fetch_one_model(points, model, forecast_days, session):
    """One batched request to Open-Meteo for every point sharing the same model."""
    params = {
        "latitude": ",".join(str(p["lat"]) for p in points),
        "longitude": ",".join(str(p["lon"]) for p in points),
        "hourly": ",".join(HOURLY_VARS),
        "wind_speed_unit": "kmh",
        "timezone": "auto",
        "forecast_days": forecast_days,
    }
    if model != DEFAULT_MODEL:
        params["models"] = model
    resp = session.get(API_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    # Single point -> API returns a plain object instead of a list.
    results = data if isinstance(data, list) else [data]
    if len(results) != len(points):
        raise ValueError(
            f"Open-Meteo returned {len(results)} results for {len(points)} requested points (model={model})"
        )
    return results


def fetch_forecast(points, forecast_days=2, session=None):
    """Batched request(s) to Open-Meteo, one per distinct model in use.

    Returns {(site_id, point_name): hourly_dict}.
    """
    if not points:
        return {}

    session = session or requests

    by_model = defaultdict(list)
    for point in points:
        by_model[point.get("model") or DEFAULT_MODEL].append(point)

    out = {}
    for model, model_points in by_model.items():
        results = _fetch_one_model(model_points, model, forecast_days, session)
        for point, result in zip(model_points, results):
            key = (point["site_id"], point["point_name"])
            out[key] = result
    return out

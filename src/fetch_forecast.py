"""Batched Open-Meteo forecast fetch for all configured site points."""
import requests

API_URL = "https://api.open-meteo.com/v1/forecast"

PRESSURE_LEVELS = [1000, 925, 850, 700, 600, 500]

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
    """Flatten every (site_id, point_name) -> point config into an ordered list."""
    points = []
    for site in sites:
        for point_name, point in site["points"].items():
            points.append(
                {
                    "site_id": site["id"],
                    "point_name": point_name,
                    "lat": point["lat"],
                    "lon": point["lon"],
                }
            )
    return points


def fetch_forecast(points, forecast_days=2, session=None):
    """One batched request to Open-Meteo. Returns {(site_id, point_name): hourly_dict}."""
    if not points:
        return {}

    session = session or requests
    params = {
        "latitude": ",".join(str(p["lat"]) for p in points),
        "longitude": ",".join(str(p["lon"]) for p in points),
        "hourly": ",".join(HOURLY_VARS),
        "wind_speed_unit": "kmh",
        "timezone": "auto",
        "forecast_days": forecast_days,
    }
    resp = session.get(API_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    # Single point -> API returns a plain object instead of a list.
    results = data if isinstance(data, list) else [data]
    if len(results) != len(points):
        raise ValueError(
            f"Open-Meteo returned {len(results)} results for {len(points)} requested points"
        )

    out = {}
    for point, result in zip(points, results):
        key = (point["site_id"], point["point_name"])
        out[key] = result
    return out

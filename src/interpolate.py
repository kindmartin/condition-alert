"""Interpolate wind speed/direction at an arbitrary altitude from pressure-level data.

Open-Meteo gives wind speed + direction + geopotential height at a fixed set of
pressure levels (1000/925/850/700/600/500 hPa). To estimate wind at an arbitrary
altitude (e.g. "1000m AGL above launch") we interpolate between the two bracketing
levels for that hour. Raw direction degrees can't be averaged directly (wraps at
0/360), so we convert to u/v vector components, interpolate those, and convert back.
"""
import math

from fetch_forecast import PRESSURE_LEVELS


def _to_uv(speed, direction_deg):
    rad = math.radians(direction_deg)
    u = -speed * math.sin(rad)
    v = -speed * math.cos(rad)
    return u, v


def _from_uv(u, v):
    speed = math.hypot(u, v)
    direction = (math.degrees(math.atan2(-u, -v))) % 360
    return speed, direction


def level_profile(hourly, hour_index):
    """Sorted list of (height_m_asl, speed_kmh, direction_deg) for one hour, low to high."""
    profile = []
    for lvl in PRESSURE_LEVELS:
        height = hourly.get(f"geopotential_height_{lvl}hPa", [None])[hour_index]
        speed = hourly.get(f"wind_speed_{lvl}hPa", [None])[hour_index]
        direction = hourly.get(f"wind_direction_{lvl}hPa", [None])[hour_index]
        if height is None or speed is None or direction is None:
            continue
        profile.append((height, speed, direction))
    profile.sort(key=lambda row: row[0])
    return profile


def wind_at_altitude(hourly, hour_index, target_height_m):
    """Returns (speed_kmh, direction_deg, extrapolated: bool) at target_height_m ASL."""
    profile = level_profile(hourly, hour_index)
    if not profile:
        return None, None, True

    if target_height_m <= profile[0][0]:
        return profile[0][1], profile[0][2], True
    if target_height_m >= profile[-1][0]:
        return profile[-1][1], profile[-1][2], True

    for (h_lo, spd_lo, dir_lo), (h_hi, spd_hi, dir_hi) in zip(profile, profile[1:]):
        if h_lo <= target_height_m <= h_hi:
            fraction = (target_height_m - h_lo) / (h_hi - h_lo)
            u_lo, v_lo = _to_uv(spd_lo, dir_lo)
            u_hi, v_hi = _to_uv(spd_hi, dir_hi)
            u = u_lo + (u_hi - u_lo) * fraction
            v = v_lo + (v_hi - v_lo) * fraction
            speed, direction = _from_uv(u, v)
            return speed, direction, False

    # Shouldn't happen given the bounds checks above, but fail safe.
    return None, None, True

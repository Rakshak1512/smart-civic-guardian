"""
Location Service
-----------------
Helpers for validating and comparing complaint locations.
GPS is optional everywhere: if latitude/longitude are missing, a manual
location name is still accepted and the complaint is never blocked.
"""

import math


def haversine_distance_meters(lat1, lon1, lat2, lon2):
    """Great-circle distance between two lat/lon points, in meters."""
    if None in (lat1, lon1, lat2, lon2):
        return None

    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def is_valid_coordinate(lat, lon):
    try:
        lat, lon = float(lat), float(lon)
        return -90 <= lat <= 90 and -180 <= lon <= 180
    except (TypeError, ValueError):
        return False


def resolve_location(form_lat, form_lon, form_location_name, manual_location_name):
    """
    Decides the final location to store for a complaint.
    Priority: valid GPS coordinates > manual location text.
    Never raises — always returns something usable so submission
    is never blocked by a missing/denied GPS permission.
    """
    if is_valid_coordinate(form_lat, form_lon):
        return {
            "latitude": float(form_lat),
            "longitude": float(form_lon),
            "location_name": form_location_name or manual_location_name or "GPS location",
        }

    return {
        "latitude": None,
        "longitude": None,
        "location_name": manual_location_name or form_location_name or "Location not specified",
    }

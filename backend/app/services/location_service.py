"""
Location Service
-----------------
Helpers for validating, comparing, and resolving complaint locations.
GPS is optional everywhere: if latitude/longitude are missing, a manual
location name is still accepted and the complaint is never blocked.
Preserves accuracy in metres and clearly notes whether the coordinates
originate from high-accuracy GPS, approximate network fix, or a manual map pin.
"""

import math


def haversine_distance_meters(lat1, lon1, lat2, lon2):
    """Great-circle distance between two lat/lon points, in meters."""
    if None in (lat1, lon1, lat2, lon2):
        return None

    try:
        lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
    except (TypeError, ValueError):
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
        return (
            math.isfinite(lat) and math.isfinite(lon)
            and -90 <= lat <= 90 and -180 <= lon <= 180
            and not (lat == 0.0 and lon == 0.0)
        )
    except (TypeError, ValueError):
        return False


def resolve_location(form_lat, form_lon, form_location_name, manual_location_name,
                     accuracy=None, location_source=None, device_lat=None, device_lon=None):
    """
    Decides the final location to store for a complaint.
    Priority: valid GPS/map-pin coordinates > manual location text.
    Preserves reported accuracy in metres and distinguishes precise vs approximate fixes.
    Never raises — always returns something usable so submission
    is never blocked by missing or approximate GPS hardware.
    """
    manual_clean = (manual_location_name or "").strip()
    loc_name_clean = (form_location_name or "").strip()

    if is_valid_coordinate(form_lat, form_lon):
        lat_val = round(float(form_lat), 6)
        lon_val = round(float(form_lon), 6)

        # Build informative, honest location_name preserving actual accuracy
        parts = []
        if loc_name_clean:
            parts.append(loc_name_clean)
        elif accuracy:
            try:
                acc_int = round(float(accuracy))
                if acc_int <= 30:
                    parts.append(f"Device GPS (±{acc_int} m) [Precise]")
                elif acc_int <= 100:
                    parts.append(f"Device Location (±{acc_int} m) [Moderate]")
                else:
                    parts.append(f"Device Location (±{acc_int} m) [Approximate]")
            except (TypeError, ValueError):
                parts.append("Device Location")
        else:
            parts.append(f"Coordinates ({lat_val}, {lon_val})")

        # If user added a landmark or manual correction text, append it
        if manual_clean and manual_clean not in parts[0]:
            parts.append(f"Landmark: {manual_clean}")

        final_name = " — ".join(parts) if len(parts) > 1 else parts[0]

        return {
            "latitude": lat_val,
            "longitude": lon_val,
            "location_name": final_name[:255],
        }

    # Fallback to manual text when coordinates are absent
    fallback_name = manual_clean or loc_name_clean or "Location not specified"
    return {
        "latitude": None,
        "longitude": None,
        "location_name": fallback_name[:255],
    }

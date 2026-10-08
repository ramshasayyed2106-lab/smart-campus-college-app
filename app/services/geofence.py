from math import radians, sin, cos, sqrt, atan2

EARTH_RADIUS_M = 6_371_000


def haversine_distance_m(lat1, lon1, lat2, lon2):
    p1, p2 = radians(lat1), radians(lat2)
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = sin(dlat / 2) ** 2 + cos(p1) * cos(p2) * sin(dlon / 2) ** 2
    return EARTH_RADIUS_M * 2 * atan2(sqrt(a), sqrt(1 - a))


def inside_geofence(student_lat, student_lon, target_lat, target_lon, radius_m):
    distance = haversine_distance_m(
        student_lat, student_lon, target_lat, target_lon
    )
    return distance <= radius_m, distance

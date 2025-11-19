"""
URL builders for Google Maps directions.
Implements both address-based and coordinate-based URLs + mobile-friendly chunks.
"""

from typing import List, Optional, Tuple
import urllib.parse

LatLon = Tuple[float, float]


def _fmt_latlon(coord: LatLon) -> str:
    lat, lon = coord
    return f"{lat:.6f},{lon:.6f}"

def google_maps_directions_link_from_coords(stops_latlon: List[Optional[LatLon]]) -> Optional[str]:
    """
    Build URL using coordinates (requires successful geocoding).
    """
    if not stops_latlon or any(c is None for c in stops_latlon):
        return None

    origin = _fmt_latlon(stops_latlon[0])  # type: ignore[arg-type]
    destination = _fmt_latlon(stops_latlon[-1])  # type: ignore[arg-type]
    waypoints_list = [_fmt_latlon(c) for c in stops_latlon[1:-1] if c is not None]

    params = {"api": "1", "origin": origin, "destination": destination}
    if waypoints_list:
        params["waypoints"] = "|".join(waypoints_list)
    return "https://www.google.com/maps/dir/?" + urllib.parse.urlencode(params)

def google_maps_directions_link_from_addresses(addresses: List[str]) -> Optional[str]:
    """
    Build URL directly from raw addresses (no geocoding).
    """
    addrs = [str(a).strip() for a in addresses if str(a).strip()]
    if len(addrs) < 2:
        return None
    origin = addrs[0]
    destination = addrs[-1]
    waypoints = addrs[1:-1]
    params = {"api": "1", "origin": origin, "destination": destination}
    if waypoints:
        params["waypoints"] = "|".join(waypoints)
    return "https://www.google.com/maps/dir/?" + urllib.parse.urlencode(params)

def split_addresses_for_mobile(addresses: List[str], max_waypoints: int = 10) -> List[List[str]]:
    """
    Split addresses into route chunks (~10 waypoints per URL on mobile).
    Overlaps the last stop of a chunk as the first of the next chunk.
    """
    chunks: List[List[str]] = []
    start = 0
    n = len(addresses)
    if n < 2:
        return [addresses]

    while start < n - 1:
        end = min(start + max_waypoints + 1, n)
        chunk = addresses[start:end]
        chunks.append(chunk)
        start = end - 1
    return chunks

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


def google_maps_directions_link_from_coords(
    stops_latlon: List[Optional[LatLon]],
) -> Optional[str]:
    """
    Build ONE Google Maps directions URL using coordinates (requires successful geocoding).
    """
    if not stops_latlon or any(c is None for c in stops_latlon):
        return None

    origin = _fmt_latlon(stops_latlon[0])  # type: ignore[arg-type]
    destination = _fmt_latlon(stops_latlon[-1])  # type: ignore[arg-type]
    waypoints_list = [_fmt_latlon(c) for c in stops_latlon[1:-1] if c is not None]

    params = {"api": "1", "origin": origin, "destination": destination, "travelmode": "driving"}
    if waypoints_list:
        params["waypoints"] = "|".join(waypoints_list)

    return "https://www.google.com/maps/dir/?" + urllib.parse.urlencode(params)


def google_maps_directions_link_from_addresses(addresses: List[str]) -> Optional[str]:
    """
    Build ONE Google Maps directions URL directly from raw addresses (no geocoding).

    Encodes each address separately and keeps the '|' separators unescaped in waypoints
    so Google interprets each stop correctly.
    """
    addrs = [str(a).strip() for a in addresses if str(a).strip()]
    if len(addrs) < 2:
        return None

    origin = addrs[0]
    destination = addrs[-1]
    waypoints = addrs[1:-1]

    def enc(value: str) -> str:
        return urllib.parse.quote(value, safe="")

    origin_enc = enc(origin)
    dest_enc = enc(destination)
    waypoints_enc = "|".join(enc(w) for w in waypoints) if waypoints else ""

    base_url = "https://www.google.com/maps/dir/?"
    parts = [
        "api=1",
        f"origin={origin_enc}",
        f"destination={dest_enc}",
        "travelmode=driving",
    ]
    if waypoints_enc:
        parts.append(f"waypoints={waypoints_enc}")

    return base_url + "&".join(parts)


# -----------------------------
# ✅ NEW / FIXED CHUNKING LOGIC
# -----------------------------

def split_stops_for_mobile(
    stops: List[str],
    max_stops_per_url: int = 9,
    overlap: int = 1,
) -> List[List[str]]:
    """
    Split stops into chunks where each chunk generates ONE Google Maps URL.

    - max_stops_per_url counts TOTAL stops in the URL (origin + waypoints + destination).
    - overlap repeats the last `overlap` stops of chunk N as the first stops of chunk N+1.
      overlap=1 gives continuity: chunk2 starts where chunk1 ended.

    Example (max_stops_per_url=9, overlap=1):
      chunk1: 1..9
      chunk2: 9..17
      chunk3: 17..25
    """
    clean = [str(s).strip() for s in stops if str(s).strip()]
    n = len(clean)

    if n <= max_stops_per_url:
        return [clean]
    if max_stops_per_url < 2:
        # You need at least origin+destination
        return [clean]
    if overlap < 0:
        overlap = 0
    if overlap >= max_stops_per_url:
        # overlap can't be >= chunk size or you'd never advance
        overlap = max_stops_per_url - 1

    chunks: List[List[str]] = []
    step = max_stops_per_url - overlap
    start = 0

    while start < n - 1:  # need at least 2 points for a route
        end = min(start + max_stops_per_url, n)
        chunk = clean[start:end]
        if len(chunk) >= 2:
            chunks.append(chunk)
        if end >= n:
            break
        start += step

    return chunks


def google_maps_links_from_addresses(
    stops: List[str],
    max_stops_per_url: int = 9,
    overlap: int = 1,
) -> List[str]:
    """
    Build MULTIPLE Google Maps URLs from stops (addresses/intersections/etc.).
    """
    chunks = split_stops_for_mobile(stops, max_stops_per_url=max_stops_per_url, overlap=overlap)
    urls: List[str] = []
    for ch in chunks:
        url = google_maps_directions_link_from_addresses(ch)
        if url:
            urls.append(url)
    return urls


def google_maps_links_from_coords(
    stops_latlon: List[Optional[LatLon]],
    max_stops_per_url: int = 9,
    overlap: int = 1,
) -> List[str]:
    """
    Build MULTIPLE Google Maps URLs from coordinate stops.
    If any coord is None, returns [] (because we can't build reliable links).
    """
    if not stops_latlon or any(c is None for c in stops_latlon):
        return []

    # Convert to strings only for chunking; we chunk by indices
    n = len(stops_latlon)
    if n <= max_stops_per_url:
        one = google_maps_directions_link_from_coords(stops_latlon)
        return [one] if one else []

    if overlap < 0:
        overlap = 0
    if overlap >= max_stops_per_url:
        overlap = max_stops_per_url - 1

    urls: List[str] = []
    step = max_stops_per_url - overlap
    start = 0

    while start < n - 1:
        end = min(start + max_stops_per_url, n)
        chunk = stops_latlon[start:end]
        url = google_maps_directions_link_from_coords(chunk)
        if url:
            urls.append(url)
        if end >= n:
            break
        start += step

    return urls

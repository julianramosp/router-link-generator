"""
URL builders for Google Maps directions.

- Address-based and coordinate-based URLs
- Mobile-friendly chunking (CHAINED segments)
- Safe encoding (never split encoded text)
- "My Location" variants (omit origin) for driver-first behavior on mobile
"""

from __future__ import annotations

from typing import List, Optional, Tuple, Dict, Any
import urllib.parse

LatLon = Tuple[float, float]


# -----------------------------
# Helpers
# -----------------------------

def _fmt_latlon(coord: LatLon) -> str:
    lat, lon = coord
    return f"{lat:.6f},{lon:.6f}"


def _clean_stops(stops: List[str]) -> List[str]:
    return [str(s).strip() for s in stops if str(s).strip()]


def _quote(s: str) -> str:
    """
    Encode a single stop safely.
    Using quote_plus keeps spaces as '+' which Google accepts fine.
    """
    return urllib.parse.quote_plus(s, safe="")


def _build_maps_url(origin: str, destination: str, waypoints: List[str]) -> str:
    """
    Build a Google Maps Directions URL using already-clean raw strings.
    Encoding is applied per-field, then we assemble the query.
    Crucially: we do NOT urlencode the whole dict when '|' is present,
    because we want '|' preserved as waypoint separator.
    """
    base_url = "https://www.google.com/maps/dir/?"

    parts = [
        "api=1",
        f"origin={_quote(origin)}",
        f"destination={_quote(destination)}",
        "travelmode=driving",
    ]

    if waypoints:
        wp = "|".join(_quote(w) for w in waypoints)
        parts.append(f"waypoints={wp}")

    return base_url + "&".join(parts)


def _build_maps_url_my_location(destination: str, waypoints: List[str]) -> str:
    """
    Build a Google Maps Directions URL WITHOUT origin, so Maps uses 'My Location'
    (especially on mobile). We keep destination + waypoints.

    Note: behavior can vary slightly across platforms, but this is the most
    driver-friendly URL pattern for mobile.
    """
    base_url = "https://www.google.com/maps/dir/?"

    parts = [
        "api=1",
        f"destination={_quote(destination)}",
        "travelmode=driving",
    ]

    if waypoints:
        wp = "|".join(_quote(w) for w in waypoints)
        parts.append(f"waypoints={wp}")

    return base_url + "&".join(parts)


def _build_maps_url_coords(origin: LatLon, destination: LatLon, waypoints: List[LatLon]) -> str:
    """
    Build URL from coordinates. We manually assemble query so '|' stays as separator.
    """
    base_url = "https://www.google.com/maps/dir/?"
    parts = [
        "api=1",
        f"origin={urllib.parse.quote_plus(_fmt_latlon(origin), safe='')}",
        f"destination={urllib.parse.quote_plus(_fmt_latlon(destination), safe='')}",
        "travelmode=driving",
    ]
    if waypoints:
        wp = "|".join(urllib.parse.quote_plus(_fmt_latlon(c), safe="") for c in waypoints)
        parts.append(f"waypoints={wp}")
    return base_url + "&".join(parts)


def _build_maps_url_coords_my_location(destination: LatLon, waypoints: List[LatLon]) -> str:
    """
    Coordinate-based 'My Location' URL (origin omitted).
    """
    base_url = "https://www.google.com/maps/dir/?"
    parts = [
        "api=1",
        f"destination={urllib.parse.quote_plus(_fmt_latlon(destination), safe='')}",
        "travelmode=driving",
    ]
    if waypoints:
        wp = "|".join(urllib.parse.quote_plus(_fmt_latlon(c), safe="") for c in waypoints)
        parts.append(f"waypoints={wp}")
    return base_url + "&".join(parts)


# -----------------------------
# Single-link builders
# -----------------------------

def google_maps_directions_link_from_coords(
    stops_latlon: List[Optional[LatLon]],
) -> Optional[str]:
    """
    Build ONE Google Maps directions URL using coordinates (requires successful geocoding).
    """
    if not stops_latlon or any(c is None for c in stops_latlon):
        return None

    origin = stops_latlon[0]  # type: ignore[assignment]
    destination = stops_latlon[-1]  # type: ignore[assignment]
    if origin is None or destination is None:
        return None

    waypoints = [c for c in stops_latlon[1:-1] if c is not None]  # type: ignore[arg-type]
    return _build_maps_url_coords(origin, destination, waypoints)  # type: ignore[arg-type]


def google_maps_directions_link_from_addresses(addresses: List[str]) -> Optional[str]:
    """
    Build ONE Google Maps directions URL directly from raw addresses (no geocoding).
    """
    addrs = _clean_stops(addresses)
    if len(addrs) < 2:
        return None

    origin = addrs[0]
    destination = addrs[-1]
    waypoints = addrs[1:-1]
    return _build_maps_url(origin, destination, waypoints)


def google_maps_directions_link_from_addresses_my_location(addresses: List[str]) -> Optional[str]:
    """
    Build ONE Google Maps directions URL where origin is omitted,
    so Google Maps uses 'My Location' (especially on mobile).

    We keep destination + waypoints.
    """
    addrs = _clean_stops(addresses)
    if len(addrs) < 1:
        return None

    destination = addrs[-1]
    waypoints = addrs[1:-1]  # ✅ drop the old origin
    return _build_maps_url_my_location(destination, waypoints)


# -----------------------------
# ✅ CHAINED CHUNKING (FIXED)
# -----------------------------

def split_stops_for_mobile_chain(
    stops: List[str],
    max_waypoints: int = 7,
) -> List[List[str]]:
    """
    Split stops into CHAINED chunks (recommended).

    Each URL represents:
      origin + up to max_waypoints + destination
    Total stops per URL = max_waypoints + 2.

    Example (max_waypoints=7 => 9 total stops per URL):
      chunk1: S0..S8
      chunk2: S8..S16
      chunk3: S16..S24
    """
    clean = _clean_stops(stops)
    n = len(clean)

    if n < 2:
        return []
    if max_waypoints < 0:
        max_waypoints = 0

    max_total = max_waypoints + 2
    if n <= max_total:
        return [clean]

    chunks: List[List[str]] = []
    i = 0

    while i < n - 1:
        j = min(i + max_total - 1, n - 1)  # destination index
        chunk = clean[i : j + 1]
        if len(chunk) >= 2:
            chunks.append(chunk)
        i = j  # chain: next origin is previous destination

    return chunks


def split_coords_for_mobile_chain(
    stops_latlon: List[Optional[LatLon]],
    max_waypoints: int = 7,
) -> List[List[LatLon]]:
    """
    Split coordinates into chained chunks.
    Returns [] if any coord is None (because link reliability matters).
    """
    if not stops_latlon or any(c is None for c in stops_latlon):
        return []

    coords: List[LatLon] = [c for c in stops_latlon if c is not None]  # type: ignore[list-item]
    n = len(coords)

    if n < 2:
        return []
    if max_waypoints < 0:
        max_waypoints = 0

    max_total = max_waypoints + 2
    if n <= max_total:
        return [coords]

    chunks: List[List[LatLon]] = []
    i = 0
    while i < n - 1:
        j = min(i + max_total - 1, n - 1)
        chunk = coords[i : j + 1]
        if len(chunk) >= 2:
            chunks.append(chunk)
        i = j

    return chunks


# -----------------------------
# Optional strict validation (used by callers or for debugging)
# -----------------------------

def _assert_chained_coverage_str(clean: List[str], chunks: List[List[str]]) -> None:
    """
    Ensure chunks cover all stops in order without loss/reordering,
    and ensure chaining (end of chunk i == start of chunk i+1).
    """
    if len(clean) < 2:
        return
    if not chunks:
        raise ValueError("No chunks produced for a non-empty stop list.")

    covered = [chunks[0][0]]
    for ch in chunks:
        covered.extend(ch[1:])

    if covered != clean:
        raise ValueError("Segmentation lost or reordered stops (chained coverage mismatch).")

    for a, b in zip(chunks, chunks[1:]):
        if a[-1] != b[0]:
            raise ValueError("Segmentation broke chaining (end != next start).")


# -----------------------------
# Multi-link builders (public API)
# -----------------------------

def google_maps_links_from_addresses(
    stops: List[str],
    max_waypoints: int = 7,
    # Backwards-compat params (converted/ignored)
    max_stops_per_url: Optional[int] = None,
    overlap: Optional[int] = None,
) -> List[str]:
    """
    Build MULTIPLE Google Maps URLs from stops (addresses/intersections/etc.)
    using CHAINED chunking.

    Preferred config:
      max_waypoints=7  (=> 9 total stops per URL)

    Backwards compatibility:
      If caller still passes max_stops_per_url, we convert it:
        max_waypoints = max(0, max_stops_per_url - 2)
      overlap is ignored in chained mode.
    """
    if max_stops_per_url is not None:
        max_waypoints = max(0, int(max_stops_per_url) - 2)

    chunks = split_stops_for_mobile_chain(stops, max_waypoints=max_waypoints)

    # Optional strict validation that no stops were lost/reordered
    clean = _clean_stops(stops)
    if chunks:
        _assert_chained_coverage_str(clean, chunks)

    urls: List[str] = []
    for ch in chunks:
        url = google_maps_directions_link_from_addresses(ch)
        if url:
            urls.append(url)
    return urls


def google_maps_my_location_links_from_addresses(
    stops: List[str],
    max_waypoints: int = 7,
    # Backwards-compat params (converted/ignored)
    max_stops_per_url: Optional[int] = None,
    overlap: Optional[int] = None,
) -> List[str]:
    """
    Build MULTIPLE Google Maps URLs from stops using CHAINED chunking,
    but with origin omitted so Google uses 'My Location' on mobile.
    """
    if max_stops_per_url is not None:
        max_waypoints = max(0, int(max_stops_per_url) - 2)

    chunks = split_stops_for_mobile_chain(stops, max_waypoints=max_waypoints)

    urls: List[str] = []
    for ch in chunks:
        url = google_maps_directions_link_from_addresses_my_location(ch)
        if url:
            urls.append(url)
    return urls


def google_maps_links_from_coords(
    stops_latlon: List[Optional[LatLon]],
    max_waypoints: int = 7,
    # Backwards-compat params (converted/ignored)
    max_stops_per_url: Optional[int] = None,
    overlap: Optional[int] = None,
) -> List[str]:
    """
    Build MULTIPLE Google Maps URLs from coordinate stops using CHAINED chunking.

    If any coord is None, returns [] (we can't build reliable links).
    """
    if not stops_latlon or any(c is None for c in stops_latlon):
        return []

    if max_stops_per_url is not None:
        max_waypoints = max(0, int(max_stops_per_url) - 2)

    chunks = split_coords_for_mobile_chain(stops_latlon, max_waypoints=max_waypoints)
    urls: List[str] = []

    for ch in chunks:
        origin = ch[0]
        destination = ch[-1]
        waypoints = ch[1:-1]
        urls.append(_build_maps_url_coords(origin, destination, waypoints))

    return urls


def google_maps_my_location_links_from_coords(
    stops_latlon: List[Optional[LatLon]],
    max_waypoints: int = 7,
    # Backwards-compat params (converted/ignored)
    max_stops_per_url: Optional[int] = None,
    overlap: Optional[int] = None,
) -> List[str]:
    """
    Build MULTIPLE Google Maps URLs from coordinate stops using CHAINED chunking,
    but with origin omitted so Google uses 'My Location' on mobile.

    If any coord is None, returns [] (we can't build reliable links).
    """
    if not stops_latlon or any(c is None for c in stops_latlon):
        return []

    if max_stops_per_url is not None:
        max_waypoints = max(0, int(max_stops_per_url) - 2)

    chunks = split_coords_for_mobile_chain(stops_latlon, max_waypoints=max_waypoints)
    urls: List[str] = []

    for ch in chunks:
        destination = ch[-1]
        waypoints = ch[:-1]  # everything before destination
        urls.append(_build_maps_url_coords_my_location(destination, waypoints))

    return urls

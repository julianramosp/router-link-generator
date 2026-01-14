"""
Route processing module.

Takes an ordered list of stops (addresses/intersections) and:
- Cleans noisy prefixes from extracted route-sheet text.
- Detects stops that are either:
    - numeric addresses (start with digits), OR
    - intersections (e.g., "Main St & 1st Ave", "Main St and 1st Ave", "Broadway @ 7th", "Hwy 12 / County Rd A")
- Optionally splits stops into segments to respect Google Directions API waypoint limits.
- Calls Google Directions API for each segment (optional).
- Builds Google Maps URL(s) for each segment and for the full route using mobile-friendly chunks:
    - max 9 stops per URL
    - overlap 1 stop between URLs for continuity
- Returns a structured dictionary ready for CLI, API, or UI.
"""

from __future__ import annotations

from typing import List, Dict, Optional
import re
import pandas as pd

from app.services.google_directions import get_directions, GoogleMapsError
from app.routes.generate_links import google_maps_links_from_addresses


# ---- Limits / tuning knobs ----

# Conservative waypoint limit per segment when calling Directions API:
# segment total stops <= MAX_WAYPOINTS + 2 (origin + destination + waypoints)
MAX_WAYPOINTS = 7

# Mobile-friendly URL chunking:
# total stops per URL (origin + waypoints + destination) <= 9
MAX_STOPS_PER_URL = 9
URL_OVERLAP = 1


# ---- Cleaning + validation ----

def clean_address_line(line: str) -> str:
    """
    Remove common route/stop/time prefixes that show up in extracted text.

    Examples removed:
    - "1 06:38 am 1 1871 County Hwy PB"  -> "1871 County Hwy PB"
    - "1. 1871 County Hwy PB"           -> "1871 County Hwy PB"
    - "1) 1871 County Hwy PB"           -> "1871 County Hwy PB"
    - "Route 3: 1871 County..."         -> "1871 County..."

    Also normalizes common intersection separators so matching is easier.
    """
    s = (line or "").strip()

    # Remove "Route X:" prefix (safe)
    s = re.sub(r"^\s*route\s*\w+\s*[:\-]\s*", "", s, flags=re.IGNORECASE)

    # Remove leading stop numbers with punctuation: "1." or "1)" (safe)
    s = re.sub(r"^\s*\d+\s*[\.\)]\s*", "", s)

    # Remove a leading "STOP TIME STOP" pattern if it exists:
    # e.g. "1 06:38 am 1 1871 County Hwy PB"
    s = re.sub(
        r"^\s*\d{1,2}\s+\d{1,2}:\d{2}\s*(?:am|pm)\s+\d{1,2}\s+",
        "",
        s,
        flags=re.IGNORECASE,
    )

    # Normalize intersection markers:
    # "A&B" -> "A & B"
    s = re.sub(r"\s*&\s*", " & ", s)

    # "A and B" (keep as-is but normalize spacing)
    s = re.sub(r"\s+\band\b\s+", " and ", s, flags=re.IGNORECASE)

    # "A/B" -> "A / B"
    s = re.sub(r"\s*/\s*", " / ", s)

    # "A@B" -> "A @ B"
    s = re.sub(r"\s*@\s*", " @ ", s)

    # Collapse repeated whitespace
    s = re.sub(r"\s{2,}", " ", s)

    return s.strip()


_INTERSECTION_PATTERN = re.compile(
    r"(.+?)\s+(?:&|and|@|/)\s+(.+?)$",
    flags=re.IGNORECASE,
)

_NUMERIC_ADDRESS_PATTERN = re.compile(r"^\d+\s+\S+")


def is_valid_stop(line: str) -> bool:
    """
    Accept either:
    - Numeric street address: starts with digits and has at least one more token
    - Intersection-like pattern using separators: &, and, @, /
    """
    s = (line or "").strip()
    if not s:
        return False

    if _NUMERIC_ADDRESS_PATTERN.match(s):
        return True

    # Intersection pattern: "A & B", "A and B", "A / B", "A @ B"
    if _INTERSECTION_PATTERN.search(s):
        # Avoid accepting junk like "&" only
        left_right = _INTERSECTION_PATTERN.search(s)
        if left_right:
            left = (left_right.group(1) or "").strip()
            right = (left_right.group(2) or "").strip()
            return bool(left) and bool(right)

    return False


# ---- Segmentation for Directions API ----

def split_stops_into_segments(stops: List[str], max_waypoints: int = MAX_WAYPOINTS) -> List[List[str]]:
    """
    Split list into segments where each segment length <= (max_waypoints + 2)
    (origin + destination + waypoints). Segments overlap the last stop as the next origin.
    """
    if len(stops) < 2:
        return []

    segments: List[List[str]] = []
    current: List[str] = [stops[0]]

    for stop in stops[1:]:
        # max points in a segment = origin + destination + max_waypoints
        # => total stops in segment <= max_waypoints + 2
        if len(current) >= (max_waypoints + 2):
            segments.append(current)
            current = [current[-1], stop]  # overlap last stop
        else:
            current.append(stop)

    if current and len(current) >= 2:
        segments.append(current)

    return segments


# ---- Core route processing ----

def process_route(
    stops: List[str],
    route_id: str,
    route_type: str,
    call_directions_api: bool = True,
) -> Dict:
    """
    Process a single ordered route (already roughly extracted).

    Returns:
      {
        route_id, route_type,
        total_stops, total_segments,
        google_maps_url, google_maps_urls,
        segments: [
          {
            segment_index,
            origin, destination, waypoints,
            google_maps_url, google_maps_urls,
            directions, error
          }, ...
        ]
      }
    """

    # Clean + validate stops (keep intersections)
    cleaned_stops: List[str] = []
    for s in stops:
        c = clean_address_line(str(s))
        if is_valid_stop(c):
            cleaned_stops.append(c)

    # If we have less than 2 usable stops, return empty-ish result
    if len(cleaned_stops) < 2:
        return {
            "route_id": route_id,
            "route_type": route_type,
            "total_stops": len(cleaned_stops),
            "total_segments": 0,
            "google_maps_url": None,
            "google_maps_urls": [],
            "segments": [],
        }

    # Build full-route links (this is what drivers likely want)
    full_route_links = google_maps_links_from_addresses(
        cleaned_stops,
        max_stops_per_url=MAX_STOPS_PER_URL,
        overlap=URL_OVERLAP,
    )
    primary_full_link = full_route_links[0] if full_route_links else None

    # Segment for Directions API (optional)
    segments_addresses = split_stops_into_segments(cleaned_stops, MAX_WAYPOINTS)

    processed_segments: List[Dict] = []

    for index, segment in enumerate(segments_addresses, start=1):
        origin = segment[0]
        destination = segment[-1]
        waypoints = segment[1:-1]

        directions_data = None
        error_message = None

        if call_directions_api:
            try:
                directions_data = get_directions(origin, waypoints, destination)
            except GoogleMapsError as e:
                directions_data = None
                error_message = str(e)

        # Build one-or-more links for THIS segment using the same URL chunking logic.
        seg_links = google_maps_links_from_addresses(
            segment,
            max_stops_per_url=MAX_STOPS_PER_URL,
            overlap=URL_OVERLAP,
        )
        seg_primary = seg_links[0] if seg_links else None

        processed_segments.append(
            {
                "segment_index": index,
                "origin": origin,
                "destination": destination,
                "waypoints": waypoints,
                "google_maps_url": seg_primary,
                "google_maps_urls": seg_links,
                "directions": directions_data,
                "error": error_message,
            }
        )

    return {
        "route_id": route_id,
        "route_type": route_type,
        "total_stops": len(cleaned_stops),
        "total_segments": len(processed_segments),
        "google_maps_url": primary_full_link,
        "google_maps_urls": full_route_links,
        "segments": processed_segments,
    }


def process_routes(
    df: pd.DataFrame,
    route_id: str | None = None,
    rtype: str | None = None,
    split_mobile: bool = False,  # kept for backward compatibility; not used here
    debug: bool = False,
) -> dict:
    """
    Process all routes in a DataFrame:
    - Filters by route_id and/or type if provided.
    - Groups by (route_id, type)
    - Sorts by sequence
    - Calls process_route()
    """

    df_filtered = df.copy()

    if route_id:
        df_filtered = df_filtered[df_filtered["route_id"] == route_id]

    if rtype:
        df_filtered = df_filtered[df_filtered["type"] == rtype]

    if df_filtered.empty:
        return {"total_routes": 0, "routes": []}

    routes_results: list[dict] = []

    for (rid, rtype_val), group in df_filtered.groupby(["route_id", "type"]):
        group_sorted = group.sort_values("sequence") if "sequence" in group.columns else group

        raw_stops = group_sorted["address"].tolist() if "address" in group_sorted.columns else []

        debug_lines = []
        stops_addresses: List[str] = []

        for s in raw_stops:
            original = "" if s is None else str(s)
            cleaned = clean_address_line(original)
            ok = is_valid_stop(cleaned)

            if ok:
                stops_addresses.append(cleaned)

            if debug:
                debug_lines.append(
                    {
                        "original": original,
                        "cleaned": cleaned,
                        "accepted": ok,
                        "reason": None if ok else "Rejected (not numeric address or intersection).",
                    }
                )

        route_result = process_route(
            stops=stops_addresses,
            route_id=str(rid),
            route_type=str(rtype_val),
            call_directions_api=True,
        )

        if debug:
            route_result["debug_addresses"] = debug_lines
            route_result["limits"] = {
                "MAX_WAYPOINTS": MAX_WAYPOINTS,
                "MAX_STOPS_PER_URL": MAX_STOPS_PER_URL,
                "URL_OVERLAP": URL_OVERLAP,
            }

        routes_results.append(route_result)

    return {
        "total_routes": len(routes_results),
        "routes": routes_results,
    }

"""
Route processing module.

Takes an ordered list of stops (addresses/intersections) and:
- Cleans noisy prefixes from extracted route-sheet text.
- Detects stops that are either:
    - numeric addresses (start with digits), OR
    - intersections (e.g., "Main St & 1st Ave", "Main St and 1st Ave", "Broadway @ 7th", "Hwy 12 / County Rd A")
- Optionally splits stops into segments to respect Google Directions API waypoint limits.
- Calls Google Directions API for each segment (optional).
- Builds Google Maps URL(s) for each segment and for the full route using mobile-friendly CHAINED chunks:
    - URL = origin + up to N waypoints + destination
- ALSO builds "My Location" variants (origin omitted) for driver-first behavior on mobile.
- Returns a structured dictionary ready for CLI, API, or UI.

Key fix (Jan 2026):
- PDF stop lines often look like: "8 08:51 am Renaissance Dr & New Freedom Ln (NW)"
  Previously, cleaning removed the stop index first, leaving "08:51 am ..." which failed validation.
  We now strip "stop# + time" (and "time-only") BEFORE removing leading numbers.
"""

from __future__ import annotations

from typing import List, Dict
import re
import pandas as pd
from typing import List

from app.services.google_directions import get_directions, GoogleMapsError
from app.routes.generate_links import (
    google_maps_links_from_addresses,
    google_maps_my_location_links_from_addresses,
    split_stops_for_mobile_chain,
)

# ---- Limits / tuning knobs ----

# Conservative waypoint limit per segment when calling Directions API:
# segment total stops <= MAX_WAYPOINTS + 2 (origin + destination + waypoints)
MAX_WAYPOINTS = 7

# Mobile-friendly URL chunking (CHAINED):
# URL total stops = MAX_URL_WAYPOINTS + 2
MAX_URL_WAYPOINTS = 7  # => 9 total stops per URL


# ---- Cleaning + validation ----

_STOP_TIME_PREFIX = re.compile(
    r"^\s*\d{1,3}\s+\d{1,2}:\d{2}\s*(?:am|pm)\s+",
    flags=re.IGNORECASE,
)

_TIME_ONLY_PREFIX = re.compile(
    r"^\s*\d{1,2}:\d{2}\s*(?:am|pm)\s+",
    flags=re.IGNORECASE,
)

_ROUTE_PREFIX = re.compile(r"^\s*route\s*\w+\s*[:\-]\s*", flags=re.IGNORECASE)
_LEADING_STOPNUM_PUNCT = re.compile(r"^\s*\d+\s*[\.\)]\s*")
_LEADING_SMALL_INDEX = re.compile(r"^\s*\d{1,2}\s+(?=\S)")


def clean_address_line(line: str) -> str:
    """
    Remove common route/stop/time prefixes that show up in extracted text.

    Crucial ordering:
    1) Remove "STOP# TIME" first (e.g., "8 08:51 am ...") so we don't leave "08:51 am ..." behind.
    2) Then remove other leading numbering patterns.
    """
    s = (line or "").strip()
    if not s:
        return ""

    # Remove "Route X:" prefix (safe)
    s = _ROUTE_PREFIX.sub("", s)

    # Remove leading patterns like "1 08:51 am " (PDF stop header)
    s = _STOP_TIME_PREFIX.sub("", s)

    # If earlier steps removed the stop#, sometimes we still have "08:51 am ..." at the front
    s = _TIME_ONLY_PREFIX.sub("", s)

    # Remove leading stop numbers with punctuation: "1." or "1)" (safe)
    s = _LEADING_STOPNUM_PUNCT.sub("", s)

    # Remove leading stop index (1–2 digits) like "1 Bus Garage" or "12 Verona Area..."
    # (after removing stop# + time, this won't break real stop lines)
    s = _LEADING_SMALL_INDEX.sub("", s)

    # Normalize intersection markers:
    s = re.sub(r"\s*&\s*", " & ", s)
    s = re.sub(r"\s+\band\b\s+", " and ", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*/\s*", " / ", s)
    s = re.sub(r"\s*@\s*", " @ ", s)

    # Collapse repeated whitespace
    s = re.sub(r"\s{2,}", " ", s)
        # --- Strip navigation instructions accidentally captured ---
    # Example: "2652 S Seminole Hwy Go west on ... Turn right ..."
    s = re.split(
        r"\s+(?=(?:go|turn|continue|merge|head|keep|take|slight|sharp)\b)",
        s,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()

    # Also strip distance-only fragments that sometimes get appended
    s = re.sub(r"\b\d+(\.\d+)?\s*(mi\.?|miles?)\b.*$", "", s, flags=re.IGNORECASE).strip()


    return s.strip()


_INTERSECTION_PATTERN = re.compile(
    r"(.+?)\s+(?:&|and|@|/)\s+(.+?)$",
    flags=re.IGNORECASE,
)

_NUMERIC_ADDRESS_PATTERN = re.compile(r"^\d+\s+\S+")


import re

_SUFFIX = r"(st|rd|dr|ln|ave|ct|cir|blvd|hwy|trl|pkwy|way|pl|pass)"
_DIR = r"\(\s*[NSEW]{1,2}\s*\)"

import re

# --- Existing building blocks you already have ---
# _DIR = r"\(\s*(?:n|s|e|w|ne|nw|se|sw)\s*\)"  # example
# _SUFFIX = r"(?:st|street|ave|avenue|rd|road|ln|lane|dr|drive|trl|trail|pass|ct|court|cir|circle|blvd|boulevard)"  # example

# -----------------------------
# NEW hard-reject rules (add these)
# -----------------------------

# "(SW)" only
_JUNK_DIRECTION_ONLY = re.compile(
    r"^\s*\(\s*(?:n|s|e|w|ne|nw|se|sw)\s*\)\s*$",
    re.IGNORECASE,
)

# One short token + optional direction tag: "Trl (NE)", "Dr (SW)", "Pass (SE)"
_JUNK_SINGLE_TOKEN_WITH_DIR = re.compile(
    r"^\s*[A-Za-z]{1,6}\s*(?:\(\s*(?:n|s|e|w|ne|nw|se|sw)\s*\))?\s*$",
    re.IGNORECASE,
)

# Street type fragments by themselves (with or without direction) are junk
_JUNK_STREET_TYPE_ONLY = re.compile(
    r"^\s*(?:dr|drive|trl|trail|pass|ln|lane|rd|road|st|street|ave|avenue|ct|court|cir|circle|blvd|boulevard)\s*"
    r"(?:\(\s*(?:n|s|e|w|ne|nw|se|sw)\s*\))?\s*$",
    re.IGNORECASE,
)

# -----------------------------
# UPDATED is_valid_stop (replace yours with this)
# -----------------------------
def is_valid_stop(line: str) -> bool:
    if not line:
        return False

    t = str(line).strip()
    if not t:
        return False

    # --- NEW hard rejects first (stronger + safer) ---
    if _JUNK_DIRECTION_ONLY.match(t):
        return False

    if _JUNK_STREET_TYPE_ONLY.match(t):
        return False

    if _JUNK_SINGLE_TOKEN_WITH_DIR.match(t):
        return False

    # --- Keep your existing rejects (no harm; redundancy is ok) ---
    # Reject pure direction only "(SW)"
    if re.fullmatch(_DIR, t, flags=re.I):
        return False

    # Reject suffix only: "Trl" / "Pass" / "Dr"
    if re.fullmatch(_SUFFIX, t, flags=re.I):
        return False

    # Reject suffix + direction only: "Trl (NE)"
    if re.fullmatch(rf"{_SUFFIX}\s*{_DIR}", t, flags=re.I):
        return False

    # --- Keep your existing accepts ---
    # Accept intersections like "X & Y"
    if "&" in t:
        return True

    # Accept numbered street address like "2652 S Seminole Hwy..."
    if re.search(r"\b\d{2,}\b", t):
        return True

    # Accept street-name + suffix like "Freedom Ln (NW)"
    # requires at least one word BEFORE the suffix
    if re.search(rf"\b[A-Za-z0-9'.-]+\s+{_SUFFIX}\b", t, flags=re.I):
        return True

    return False


def drop_leading_bus_stop(stops: List[str]) -> List[str]:
    """
    Remove leading 'Bus Stop' header if present as the first stop.
    Keep it if it appears later (could be a real label).
    """
    if not stops:
        return stops
    first = stops[0].strip().lower()
    if first.startswith("bus stop"):
        return stops[1:]
    return stops


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
        if len(current) >= (max_waypoints + 2):
            segments.append(current)
            current = [current[-1], stop]  # overlap last stop
        else:
            current.append(stop)

    if current and len(current) >= 2:
        segments.append(current)

    return segments


# ---- Internal validation for chunking ----

def _assert_chained_coverage(stops: List[str], chunks: List[List[str]]) -> None:
    """
    Ensure chunks cover all stops in order without loss/reordering,
    and ensure chaining (end of chunk i == start of chunk i+1).
    """
    if len(stops) < 2:
        return
    if not chunks:
        raise ValueError("No chunks produced for a non-empty stop list.")

    covered = [chunks[0][0]]
    for ch in chunks:
        covered.extend(ch[1:])

    if covered != stops:
        raise ValueError(
            "Chunking lost or reordered stops.\n"
            f"Expected {len(stops)} stops, covered {len(covered)}.\n"
            f"First expected: {stops[:3]}\nFirst covered: {covered[:3]}\n"
            f"Last expected: {stops[-3:]}\nLast covered: {covered[-3:]}"
        )

    for a, b in zip(chunks, chunks[1:]):
        if a[-1] != b[0]:
            raise ValueError("Chunk chaining broken (end != next start).")


# ---- Core route processing ----

def process_route(
    stops: List[str],
    route_id: str,
    route_type: str,
    call_directions_api: bool = True,
) -> Dict:
    """
    Process a single ordered route (already roughly extracted).
    """

    

    BAD_ONLY_DIR = re.compile(r"^\(\s*[NSEW]{1,2}\s*\)$", re.I)
    BAD_SUFFIX = re.compile(r"^(st|rd|dr|ln|ave|ct|cir|blvd|hwy|trl|pkwy|way|pl|pass)\b$", re.I)
    BAD_SUFFIX_DIR = re.compile(
        r"^(st|rd|dr|ln|ave|ct|cir|blvd|hwy|trl|pkwy|way|pl|pass)\s*\(\s*[NSEW]{1,2}\s*\)$",
        re.I,
    )

   # 1) Clean + validate stops (keep intersections)


    cleaned_stops: List[str] = []

    for s in stops:
        raw = str(s)
        c = clean_address_line(raw)

        reason = None
        if BAD_ONLY_DIR.match(c):
            reason = "BAD_ONLY_DIR"
        elif BAD_SUFFIX.match(c):
            reason = "BAD_SUFFIX"
        elif BAD_SUFFIX_DIR.match(c):
            reason = "BAD_SUFFIX_DIR"
        elif not is_valid_stop(c):
            reason = "is_valid_stop=False"

        print(f"STOP DEBUG | raw={raw!r} | clean={c!r} | reason={reason}")

        # hard rejects
        if BAD_ONLY_DIR.match(c) or BAD_SUFFIX.match(c) or BAD_SUFFIX_DIR.match(c):
            continue

        if is_valid_stop(c):
            cleaned_stops.append(c)

    # Drop header after loop
    cleaned_stops = drop_leading_bus_stop(cleaned_stops)

    print("DEBUG cleaned_stops count:", len(cleaned_stops))
    print("DEBUG cleaned_stops preview:", cleaned_stops[:12])

    # 2) If we have less than 2 usable stops, return empty-ish result
    if len(cleaned_stops) < 2:
        return {
            "route_id": route_id,
            "route_type": route_type,
            "total_stops": len(cleaned_stops),
            "total_segments": 0,
            "google_maps_url": None,
            "google_maps_urls": [],
            "google_maps_my_location_url": None,
            "google_maps_my_location_urls": [],
            "segments": [],
        }

    # 3) Full-route links (fixed-origin)
    full_chunks = split_stops_for_mobile_chain(cleaned_stops, max_waypoints=MAX_URL_WAYPOINTS)
    _assert_chained_coverage(cleaned_stops, full_chunks)

    full_route_links = google_maps_links_from_addresses(
        cleaned_stops,
        max_waypoints=MAX_URL_WAYPOINTS,
    )
    primary_full_link = full_route_links[0] if full_route_links else None

    # 3b) Full-route links (My Location origin omitted)
    my_loc_links = google_maps_my_location_links_from_addresses(
        cleaned_stops,
        max_waypoints=MAX_URL_WAYPOINTS,
    )
    primary_my_loc = my_loc_links[0] if my_loc_links else None

    # 4) Segment for Directions API (optional)
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

        # Segment links (fixed-origin)
        seg_chunks = split_stops_for_mobile_chain(segment, max_waypoints=MAX_URL_WAYPOINTS)
        _assert_chained_coverage(segment, seg_chunks)

        seg_links = google_maps_links_from_addresses(
            segment,
            max_waypoints=MAX_URL_WAYPOINTS,
        )
        seg_primary = seg_links[0] if seg_links else None

        # Segment links (My Location)
        seg_my_loc_links = google_maps_my_location_links_from_addresses(
            segment,
            max_waypoints=MAX_URL_WAYPOINTS,
        )
        seg_my_loc_primary = seg_my_loc_links[0] if seg_my_loc_links else None

        processed_segments.append(
            {
                "segment_index": index,
                "origin": origin,
                "destination": destination,
                "waypoints": waypoints,
                "google_maps_url": seg_primary,
                "google_maps_urls": seg_links,
                "google_maps_my_location_url": seg_my_loc_primary,
                "google_maps_my_location_urls": seg_my_loc_links,
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
        "google_maps_my_location_url": primary_my_loc,
        "google_maps_my_location_urls": my_loc_links,
        "segments": processed_segments,
    }


def process_routes(
    df: pd.DataFrame | None = None,
    stops: list[str] | None = None,
    route_id: str | None = None,
    rtype: str | None = None,
    split_mobile: bool = False,  # kept for backward compatibility; not used here
    debug: bool = False,
) -> dict:
    """
    Process routes from either:
      A) DataFrame (CSV pipeline) -> groups by (route_id, type)
      B) Explicit stops list (PDF pipeline) -> single route
    """

    # ---------------------------
    # Mode B: explicit stops list
    # ---------------------------
    if stops is not None:
        # normalize + re-validate using existing logic (single source of truth)
        debug_lines = []
        stops_addresses: List[str] = []

        for s in stops:
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
                        "reason": None if ok else "Rejected (not numeric address or intersection) after cleaning.",
                    }
                )

        # choose route_id/type defaults for PDFs
        final_route_id = route_id or "PDFRoute"
        final_route_type = rtype or "AM"

        route_result = process_route(
            stops=stops_addresses,
            route_id=str(final_route_id),
            route_type=str(final_route_type),
            call_directions_api=True,
        )

        if debug:
            route_result["debug_addresses"] = debug_lines
            route_result["limits"] = {
                "MAX_WAYPOINTS": MAX_WAYPOINTS,
                "MAX_URL_WAYPOINTS": MAX_URL_WAYPOINTS,
            }

        return {"total_routes": 1, "routes": [route_result]}

    # ---------------------------
    # Mode A: DataFrame (existing)
    # ---------------------------
    if df is None:
        return {"total_routes": 0, "routes": []}

    df_filtered = df.copy()

    if route_id and "route_id" in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["route_id"] == route_id]

    if rtype and "type" in df_filtered.columns:
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
                        "reason": None if ok else "Rejected (not numeric address or intersection) after cleaning.",
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
                "MAX_URL_WAYPOINTS": MAX_URL_WAYPOINTS,
            }

        routes_results.append(route_result)

    return {"total_routes": len(routes_results), "routes": routes_results}
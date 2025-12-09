"""
Route processing module.

This module takes an ordered list of stops (addresses) and:
- Splits them into valid segments respecting Google Directions API waypoint limits.
- Calls the Google Directions API for each segment.
- Builds a Google Maps URL for each segment.
- Returns a structured dictionary ready to be consumed by a CLI, API, or UI.
"""

from typing import List, Dict
import urllib.parse

from app.services.google_directions import get_directions, GoogleMapsError

# Google Directions API has a waypoint limit (for the free tier / standard usage).
# We keep a conservative number of waypoints per segment to avoid errors.
MAX_WAYPOINTS = 7


def split_stops_into_segments(stops: List[str], max_waypoints: int = MAX_WAYPOINTS) -> List[List[str]]:
    """
    Split the full list of stops into smaller segments that respect the waypoint limit.

    Each segment is a list of addresses where:
    - The first element is the origin.
    - The last element is the destination.
    - Middle elements (if any) are waypoints.
    - (len(segment) - 2) <= max_waypoints

    Example:
        Input stops: [A, B, C, D, E, F, G, H, I]
        Output segments might be:
            [A, B, C, D, E]
            [E, F, G, H, I]
    """
    if len(stops) < 2:
        # Not enough points to build a route
        return []

    segments: List[List[str]] = []

    # Start the first segment with the first stop as origin
    current_segment: List[str] = [stops[0]]

    for stop in stops[1:]:
        # If adding this stop would exceed the max points allowed
        # max points = origin + destination + max_waypoints
        if len(current_segment) >= (max_waypoints + 1):
            # Close current segment and start a new one.
            # The last stop of the previous segment becomes the origin of the next.
            segments.append(current_segment)
            current_segment = [current_segment[-1], stop]
        else:
            # Still within the limit, just append the stop
            current_segment.append(stop)

    # Append the last segment
    if current_segment:
        segments.append(current_segment)

    return segments


def build_google_maps_url(origin: str, waypoints: List[str], destination: str) -> str:
    """
    Build a Google Maps URL for the given origin, waypoints, and destination.

    This URL can be opened directly in a browser or a mobile device
    to start navigation using Google Maps.
    """
    base_url = "https://www.google.com/maps/dir/?api=1"

    params = {
        "origin": origin,
        "destination": destination,
        "travelmode": "driving",
    }

    if waypoints:
        # In the URL we don't need 'via:' prefix, Google Maps will still try to follow
        # the given sequence of waypoints in order.
        params["waypoints"] = "|".join(waypoints)

    # urlencode will take care of spaces and special characters.
    # The 'safe' parameter keeps the '|' characters unencoded because
    # Google supports them as waypoint separators.
    query_string = urllib.parse.urlencode(params, safe="|,")

    return f"{base_url}&{query_string}"


def process_route(stops: List[str], route_id: str, route_type: str) -> Dict:
    """
    High-level function that:
    - Splits stops into valid segments.
    - Calls Google Directions API for each segment.
    - Builds a Google Maps URL for each segment.
    - Returns a structured result.

    Parameters:
        stops (List[str]): Ordered list of stop addresses (from first pickup to final drop-off).
        route_id (str): Identifier for the route (e.g. "A1", "Bus_23").
        route_type (str): Type of route (e.g. "AM", "PM").

    Returns:
        Dict: A dictionary that can be easily serialized as JSON or used directly.
    """
    segments_addresses = split_stops_into_segments(stops, MAX_WAYPOINTS)

    processed_segments: List[Dict] = []

    for index, segment in enumerate(segments_addresses, start=1):
        origin = segment[0]
        destination = segment[-1]
        waypoints = segment[1:-1]  # Everything in between

        try:
            # Call Google Directions API for this segment
            directions_data = get_directions(origin, waypoints, destination)
            error_message = None
        except GoogleMapsError as e:
            # If something goes wrong, we keep the error attached to the segment.
            directions_data = None
            error_message = str(e)

        # Build a Maps URL that the driver can open directly.
        segment_url = build_google_maps_url(origin, waypoints, destination)

        processed_segments.append(
            {
                "segment_index": index,
                "origin": origin,
                "destination": destination,
                "waypoints": waypoints,
                "google_maps_url": segment_url,
                "directions": directions_data,
                "error": error_message,
            }
        )

    result: Dict = {
        "route_id": route_id,
        "route_type": route_type,
        "total_stops": len(stops),
        "total_segments": len(processed_segments),
        "segments": processed_segments,
    }

    return result

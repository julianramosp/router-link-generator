import os
import requests

# Base URL for Google Directions API
GOOGLE_MAPS_DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"

# API key is read from environment variables for security reasons.
API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")


class GoogleMapsError(Exception):
    """Custom exception for any error related to Google Maps API."""
    pass


def get_directions(origin: str, waypoints: list[str], destination: str) -> dict:
    """
    Calls Google Directions API and returns the JSON response.

    Parameters:
        origin (str): Starting address of the route.
        waypoints (list[str]): Intermediate stops (ordered and limited by API constraints).
        destination (str): Final destination of the route.

    Returns:
        dict: Parsed JSON from Google Directions API.

    Raises:
        GoogleMapsError: When the API key is missing, HTTP error occurs,
                         or Google returns a non-OK status.
    """
    
    # Verify that the API key exists before making the request.
    if not API_KEY:
        raise GoogleMapsError("GOOGLE_MAPS_API_KEY is not set in environment variables.")

    # Base parameters required by Google Directions API.
    params = {
        "origin": origin,
        "destination": destination,
        "key": API_KEY,
        "mode": "driving",
        "language": "en",
    }

    # If there are intermediate stops, they must be concatenated
    # and prefixed with 'via:' to force Google to respect the exact order.
    if waypoints:
        params["waypoints"] = "|".join(f"via:{w}" for w in waypoints)

    try:
        # Execute the GET request to Google Directions API.
        response = requests.get(GOOGLE_MAPS_DIRECTIONS_URL, params=params, timeout=15)

    except requests.exceptions.RequestException as e:
        # Raised if there is a network issue or timeout.
        raise GoogleMapsError(f"Request error: {e}")

    # Check if the response is not HTTP 200.
    if response.status_code != 200:
        raise GoogleMapsError(
            f"HTTP Error {response.status_code}: {response.text[:200]}"
        )

    data = response.json()

"""
Geocoding using Google Maps (if key present) with Nominatim fallback.
"""
from typing import Dict, Optional, Tuple, List
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from app.config.settings import GOOGLE_MAPS_API_KEY
from .cache_store import load_cache, save_cache

LatLon = Tuple[float, float]

try:
    import googlemaps  # type: ignore
except Exception:
    googlemaps = None  # type: ignore


def geocode_addresses(addresses: List[str]) -> Dict[str, Optional[LatLon]]:
    cache = load_cache()
    results: Dict[str, Optional[LatLon]] = {}

    # Google client (optional)
    gmaps = None
    if GOOGLE_MAPS_API_KEY and googlemaps is not None:
        try:
            gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
            print("[INFO] Using Google Maps Geocoding API")
        except Exception:
            gmaps = None

    # OSM geocoder (fallback)
    geolocator = Nominatim(user_agent="first_student_routes", timeout=5)
    geocode_slow = RateLimiter(
        geolocator.geocode,
        min_delay_seconds=1.2,
        max_retries=2,
        error_wait_seconds=2.5,
        swallow_exceptions=True,
    )

    for raw in addresses:
        key = (raw or "").strip()
        if not key:
            results[raw] = None
            continue

        if key in cache:
            results[raw] = cache[key]
            continue

        latlon: Optional[LatLon] = None

        # 1) Google
        if gmaps is not None:
            try:
                g = gmaps.geocode(key)
                if g and "geometry" in g[0]:
                    loc = g[0]["geometry"]["location"]
                    latlon = (loc["lat"], loc["lng"])
            except Exception:
                latlon = None

        # 2) OSM fallback
        if latlon is None:
            try:
                loc = geocode_slow(key)
                if loc:
                    latlon = (loc.latitude, loc.longitude)
            except Exception:
                latlon = None

        cache[key] = latlon
        results[raw] = latlon

    save_cache(cache)
    return results

# scripts/generate_route_link.py
import argparse
import json
import os
from pathlib import Path
import urllib.parse

import pandas as pd
import numpy as np

# Geocoding providers
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# --- Optional Google Maps key ---
try:
    # Define GOOGLE_MAPS_API_KEY in config/config.py to prefer Google geocoding
    from config.config import GOOGLE_MAPS_API_KEY  # type: ignore
except Exception:
    GOOGLE_MAPS_API_KEY = None

try:
    import googlemaps
except Exception:
    googlemaps = None

# --- Paths ---
ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data_raw"
DATA_PROCESSED = ROOT / "data_processed"
OUTPUTS = ROOT / "outputs"
CACHE_PATH = DATA_PROCESSED / "geocode_cache.json"

for p in [DATA_RAW, DATA_PROCESSED, OUTPUTS]:
    p.mkdir(parents=True, exist_ok=True)


# -----------------------
# Cache helpers
# -----------------------
def load_cache() -> dict:
    if CACHE_PATH.exists():
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return {}
    return {}


def save_cache(cache: dict):
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


# -----------------------
# Geocoding
# -----------------------
def geocode_addresses(addresses: list[str]) -> dict[str, tuple[float, float] | None]:
    """
    Geocode a list of addresses. Priority: Google (if key) -> OSM (Nominatim).
    Returns dict: raw_address -> (lat, lon) or None
    """
    cache = load_cache()
    results: dict[str, tuple[float, float] | None] = {}

    # Google client (optional)
    gmaps = None
    if GOOGLE_MAPS_API_KEY and googlemaps is not None:
        try:
            gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
            print("[INFO] Using Google Maps Geocoding API")
        except Exception:
            gmaps = None

    # OSM geocoder (fallback) with friendlier timeouts/rate
    geolocator = Nominatim(user_agent="first_student_routes", timeout=5)
    geocode_slow = RateLimiter(
        geolocator.geocode,
        min_delay_seconds=1.2,
        max_retries=2,
        error_wait_seconds=2.5,
        swallow_exceptions=True,
    )

    for addr in addresses:
        key = (addr or "").strip()
        if not key:
            results[addr] = None
            continue

        if key in cache:
            results[addr] = cache[key]
            continue

        latlon = None

        # 1) Try Google
        if gmaps is not None:
            try:
                g = gmaps.geocode(key)
                if g and "geometry" in g[0]:
                    loc = g[0]["geometry"]["location"]
                    latlon = (loc["lat"], loc["lng"])
            except Exception:
                latlon = None

        # 2) Fallback OSM
        if latlon is None:
            try:
                loc = geocode_slow(key)
                if loc:
                    latlon = (loc.latitude, loc.longitude)
            except Exception:
                latlon = None

        cache[key] = latlon
        results[addr] = latlon

    save_cache(cache)
    return results


# -----------------------
# URL builders
# -----------------------
def _fmt_latlon(coord: tuple[float, float]) -> str:
    lat, lon = coord
    return f"{lat:.6f},{lon:.6f}"


def google_maps_directions_link_from_coords(stops_latlon: list[tuple[float, float] | None]) -> str | None:
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


def google_maps_directions_link_from_addresses(addresses: list[str]) -> str | None:
    """
    Build URL directly from raw addresses (no geocoding). Great for demos.
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


# -----------------------
# Split helper (mobile-friendly)
# -----------------------
def split_addresses_for_mobile(addresses: list[str], max_waypoints: int = 10) -> list[list[str]]:
    """
    Split addresses into smaller route chunks that respect Google's
    ~10-waypoint mobile limit (≈12 total stops per map).
    Overlaps the last stop of a chunk as the first of the next chunk.
    """
    chunks: list[list[str]] = []
    start = 0
    n = len(addresses)
    if n < 2:
        return [addresses]

    while start < n - 1:
        end = min(start + max_waypoints + 1, n)  # +1 because origin+waypoints, destination is last element
        chunk = addresses[start:end]
        chunks.append(chunk)
        start = end - 1  # overlap: make previous destination the next origin
    return chunks


# -----------------------
# Folium map
# -----------------------
def make_folium_map(stops_ordered: list[dict], coords: list[tuple[float, float] | None]):
    try:
        import folium
    except Exception:
        print("[WARN] Folium not installed; skipping HTML map.")
        return None

    valid = [c for c in coords if c is not None]
    if not valid:
        return None

    avg_lat = sum(c[0] for c in valid) / len(valid)
    avg_lon = sum(c[1] for c in valid) / len(valid)
    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=13)

    for i, row in enumerate(stops_ordered, start=1):
        c = coords[i - 1]
        if c is None:
            continue
        popup = f"#{row['sequence']} - {row['stop_name']}<br>{row['address']}<br>{row.get('notes','')}"
        folium.Marker(location=[c[0], c[1]], popup=popup).add_to(m)

    if len(valid) >= 2:
        folium.PolyLine(locations=[[c[0], c[1]] for c in coords if c is not None]).add_to(m)

    return m


# -----------------------
# Orchestrator
# -----------------------
def process_routes(df: pd.DataFrame, route_id: str | None, rtype: str | None, split_mobile: bool = False):
    # Choose combos
    combos = (
        [(route_id, rtype)]
        if (route_id and rtype)
        else sorted(df[["route_id", "type"]].drop_duplicates().itertuples(index=False, name=None))
    )

    for rid, t in combos:
        print(f"[PROC] route_id={rid} type={t}")

        subset = (
            df[(df["route_id"].astype(str) == str(rid)) & (df["type"].astype(str).str.upper() == str(t).upper())]
            .copy()
            .sort_values("sequence")
        )

        if subset.empty:
            print(f"[WARN] No rows for route_id={rid}, type={t}")
            continue

        # Addresses (always available)
        addresses = subset["address"].astype(str).tolist()

        # --- MOBILE SPLIT OPTION ---
        if split_mobile:
            print("[INFO] Splitting route for mobile-friendly links (<=10 waypoints each)")
            chunks = split_addresses_for_mobile(addresses, max_waypoints=10)
            for i, chunk in enumerate(chunks, start=1):
                url = google_maps_directions_link_from_addresses(chunk)
                if url:
                    link_file = OUTPUTS / f"route_{rid}_{t}_part{i}.txt"
                    link_file.write_text(url, encoding="utf-8")
                    print(f"[OK] Part {i} link saved → {link_file}")
        else:
            # Full link (no geocode, demo-proof)
            direct_url = google_maps_directions_link_from_addresses(addresses)
            if direct_url:
                link_file = OUTPUTS / f"route_{rid}_{t}_link.txt"
                link_file.write_text(direct_url, encoding="utf-8")
                print(f"[OK] Google Maps link (no geocode) saved → {link_file}")

        # Then try geocoding (optional: for folium map and coords-based URL)
        coords: list[tuple[float, float] | None] = []
        try:
            print(f"[INFO] Geocoding {len(subset)} stops...")
            coords_map = geocode_addresses(addresses)
            coords = [coords_map.get(a) for a in addresses]
        except Exception as e:
            print(f"[WARN] Geocoding failed: {e}")

        # Coordinate-based URL (if we have coords and not splitting)
        if not split_mobile:
            url_from_coords = google_maps_directions_link_from_coords(coords)
            if url_from_coords:
                link_file2 = OUTPUTS / f"route_{rid}_{t}_link_coords.txt"
                link_file2.write_text(url_from_coords, encoding="utf-8")
                print(f"[OK] Google Maps link (coords) saved → {link_file2}")

        # Folium HTML map (only if we got valid coords)
        fmap = make_folium_map(
            subset[["sequence", "stop_name", "address", "notes"]].to_dict(orient="records"),
            coords,
        )
        if fmap:
            html_path = OUTPUTS / f"route_{rid}_{t}.html"
            fmap.save(str(html_path))
            print(f"[OK] HTML map saved → {html_path}")
        else:
            print("[WARN] Could not generate HTML map (no valid coords).")


# -----------------------
# Main
# -----------------------
def main():
    parser = argparse.ArgumentParser(description="Generate route links and maps from CSV.")
    parser.add_argument("--csv", default=str(DATA_RAW / "routes_verona.csv"), help="Path to input CSV")
    parser.add_argument("--route", help="Route ID to process (default: all)")
    parser.add_argument("--type", help="Route type AM/PM (use with --route)")
    parser.add_argument("--split-mobile", action="store_true",
                        help="Split route into mobile-friendly links (<=10 waypoints each)")
    args = parser.parse_args()

    print("[BOOT] generate_route_link starting")
    print(f"[ARGS] csv={args.csv} route={args.route} type={args.type} split_mobile={args.split_mobile}")

    if not os.path.exists(args.csv):
        raise FileNotFoundError(f"CSV not found: {args.csv}")

    # Read & normalize (tolerant)
    df = pd.read_csv(args.csv, dtype=str, engine="python")
    print(f"[CSV] loaded rows={len(df)} cols={list(df.columns)}")

    # Basic cleanup
    for col in ["route_id", "school", "type", "stop_name", "address", "notes", "time"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # Drop junk rows (nan route/type/address)
    df = df.replace({"nan": np.nan, "NaN": np.nan, "NAN": np.nan})
    df = df.dropna(subset=["route_id", "type", "address"])

    # Uppercase type
    if "type" in df.columns:
        df["type"] = df["type"].str.upper()

    # Validate required columns (sequence will be recomputed)
    required_cols = {"route_id", "school", "type", "stop_name", "address"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in CSV: {missing}")

    # Ensure notes
    if "notes" not in df.columns:
        df["notes"] = ""

    # Robust resequencing per (route_id, type)
    df["__seq_num"] = pd.to_numeric(df.get("sequence", pd.NA), errors="coerce")
    df["__row"] = range(len(df))
    df = df.sort_values(["route_id", "type", "__seq_num", "__row"], kind="mergesort")
    df["sequence"] = df.groupby(["route_id", "type"]).cumcount() + 1
    df = df.drop(columns=["__seq_num", "__row"])

    print("[CSV] route/type combos:\n", df[["route_id", "type"]].drop_duplicates().to_string(index=False))

    # Go
    process_routes(df, args.route, args.type, split_mobile=args.split_mobile)

    print("\nDone ✅")


if __name__ == "__main__":
    main()

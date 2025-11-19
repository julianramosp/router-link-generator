"""
High-level orchestration that mirrors your original `process_routes`.
Generates direct links, optional mobile-split links, coord-based links, and Folium map.
"""

from pathlib import Path
from typing import Optional, Tuple, List

import pandas as pd

from ..services.file_handler import extract_addresses_from_subset
from ..services.geocoding import geocode_addresses
from ..services.mapping import make_folium_map
from .generate_links import (
    google_maps_directions_link_from_addresses,
    google_maps_directions_link_from_coords,
    split_addresses_for_mobile,
)
from app.config.settings import OUTPUTS


LatLon = Tuple[float, float]


def process_routes(df: pd.DataFrame, route_id: Optional[str], rtype: Optional[str], split_mobile: bool = False) -> None:
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

        addresses = extract_addresses_from_subset(subset)

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
            direct_url = google_maps_directions_link_from_addresses(addresses)
            if direct_url:
                link_file = OUTPUTS / f"route_{rid}_{t}_link.txt"
                link_file.write_text(direct_url, encoding="utf-8")
                print(f"[OK] Google Maps link (no geocode) saved → {link_file}")

        # Geocode (optional for coord URL + folium)
        coords: List[Optional[LatLon]] = []
        try:
            print(f"[INFO] Geocoding {len(subset)} stops...")
            coords_map = geocode_addresses(addresses)
            coords = [coords_map.get(a) for a in addresses]
        except Exception as e:
            print(f"[WARN] Geocoding failed: {e}")

        if not split_mobile:
            url_from_coords = google_maps_directions_link_from_coords(coords)
            if url_from_coords:
                link_file2 = OUTPUTS / f"route_{rid}_{t}_link_coords.txt"
                link_file2.write_text(url_from_coords, encoding="utf-8")
                print(f"[OK] Google Maps link (coords) saved → {link_file2}")

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

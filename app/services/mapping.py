"""
Folium map generation from ordered stops and coordinates.
"""
from typing import List, Optional, Tuple

def make_folium_map(stops_ordered: List[dict], coords: List[Optional[Tuple[float, float]]]):
    try:
        import folium  # type: ignore
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

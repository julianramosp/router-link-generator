"""
Simple JSON cache for geocoding results.
"""
import json
from typing import Dict, Tuple, Optional
from app.config.settings import CACHE_PATH

LatLon = Tuple[float, float]

def load_cache() -> Dict[str, Optional[LatLon]]:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_cache(cache: Dict[str, Optional[LatLon]]) -> None:
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

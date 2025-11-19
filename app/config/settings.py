"""
Global configuration: paths, logging, and optional Google Maps API key.
"""
from pathlib import Path
import logging

# Project dirs
APP_DIR = Path(__file__).resolve().parent
BASE_DIR = APP_DIR.parent
ROOT = BASE_DIR.parent

DATA_RAW = ROOT / "data_raw"
DATA_PROCESSED = ROOT / "data_processed"
OUTPUTS = ROOT / "outputs"
CACHE_PATH = DATA_PROCESSED / "geocode_cache.json"

for p in [DATA_RAW, DATA_PROCESSED, OUTPUTS]:
    p.mkdir(parents=True, exist_ok=True)

# Optional Google API key (kept in your old folder: first_student_routes/config/config.py)
GOOGLE_MAPS_API_KEY = None
try:
    from config.config import GOOGLE_MAPS_API_KEY as _KEY  # type: ignore
    GOOGLE_MAPS_API_KEY = _KEY
except Exception:
    pass

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
LOGGER = logging.getLogger("route_project")

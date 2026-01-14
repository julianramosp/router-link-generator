    
from typing import List, Optional

# Lines that are NOT stops (navigation instructions)
NAV_PREFIXES = (
    "go ",
    "turn ",
    "continue ",
    "merge ",
    "head ",
    "keep ",
    "take ",
    "slight ",
    "sharp ",
)

# Common junk / labels in this format that are not stops
JUNK_PATTERNS = [
    r"^trip detail$",
    r"^trip:",
    r"^aide:",
    r"^driver:",
    r"^bus:",
    r"^print date:",
    r"^start time:",
    r"^finish time:",
    r"^total time:",
    r"^distance:",
    r"^students transported:",
    r"^max student on bus:",
    r"^stop\b",
    r"^time\b",
    r"^comment/location\b",
    r"^count\b",
    r"^student name\b",
    r"^school\b",
    r"^grade\b",
    r"^-{3,}.*pick up.*-{3,}$",
    r"^pick up$",
    r"^drop off$",
]

JUNK_RE = re.compile("|".join(f"(?:{p})" for p in JUNK_PATTERNS), re.IGNORECASE)

# Recognize "stop lines" that look like addresses/intersections
STREET_SUFFIXES = (
    "st", "street", "rd", "road", "dr", "drive", "ln", "lane", "ave", "avenue",
    "ct", "court", "cir", "circle", "blvd", "boulevard", "hwy", "highway",
    "trl", "trail", "pkwy", "parkway", "way", "pl", "place", "ter", "terrace"
)

SUFFIX_RE = re.compile(r"\b(" + "|".join(STREET_SUFFIXES) + r")\b", re.IGNORECASE)

LEADING_STOPNUM_RE = re.compile(r"^\s*\d+\s*[\.\)]\s*")  # "7." or "7)"

def looks_like_navigation(line: str) -> bool:
    s = line.strip().lower()
    return any(s.startswith(p) for p in NAV_PREFIXES)

def clean_stop_text(line: str) -> str:
    s = line.strip()
    s = LEADING_STOPNUM_RE.sub("", s)
    # collapse double spaces
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip(" -\t")

def looks_like_stop(line: str) -> bool:
    """
    A 'stop' in First Student Trip Detail is usually:
    - numeric address: starts with digits OR contains a street suffix after digits
    - intersection: contains '&' (e.g., "Flint Ln & Riverside Rd")
    - named stop with suffix (rare but possible): contains Rd/St/Ln/etc.
    And must NOT be navigation text or junk labels.
    """
    s = clean_stop_text(line)
    if not s or len(s) < 4:
        return False

    if JUNK_RE.search(s):
        return False

    if looks_like_navigation(s):
        return False

    # common non-address location label
    if s.lower() in {"bus garage", "garage", "school", "depot"}:
        return False

    # Intersection
    if "&" in s:
        return True

    # Starts with number (standard address)
    if re.match(r"^\d{1,6}\b", s):
        return True

    # Has street suffix (for lines like "Paoli St" or "Verona Frontage Rd")
    if SUFFIX_RE.search(s):
        return True

    return False

def normalize_stop(stop: str, default_city_state_zip: Optional[str]) -> str:
    """
    If stop has no comma, it likely has no city/state.
    Append default city/state/zip for better geocoding, especially for intersections.
    """
    s = stop.strip()

    # normalize "&" spacing
    s = re.sub(r"\s*&\s*", " & ", s)

    # If already has city/state, keep
    if "," in s:
        return s

    if default_city_state_zip:
        return f"{s}, {default_city_state_zip}"

    return s

def extract_stops_from_lines(lines: List[str], default_city_state_zip: Optional[str] = "Verona, WI 53593") -> List[str]:
    """
    Main helper: feed it the PDF-extracted text split into lines.
    Returns cleaned + normalized stops in order.
    """
    stops: List[str] = []
    for raw in lines:
        if looks_like_stop(raw):
            cleaned = clean_stop_text(raw)
            normalized = normalize_stop(cleaned, default_city_state_zip)
            stops.append(normalized)

    # de-dup while preserving order (sometimes pdf text repeats)
    seen = set()
    unique: List[str] = []
    for s in stops:
        key = s.lower()
        if key not in seen:
            seen.add(key)
            unique.append(s)

    return unique

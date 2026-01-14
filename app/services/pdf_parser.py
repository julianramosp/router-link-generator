from pathlib import Path
from typing import List, Tuple
import re

import pdfplumber
import pandas as pd


# Navigation instructions (not stops)
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

# Header/label noise (not stops)
JUNK_PREFIXES = (
    "trip",
    "aide",
    "driver",
    "bus",
    "print date",
    "start time",
    "finish time",
    "total time",
    "distance",
    "students transported",
    "max student on bus",
    "stop",
    "time",
    "comment/location",
    "count",
    "student name",
    "school",
    "grade",
)

# Helps accept street-like lines even without a leading number
STREET_SUFFIX_RE = re.compile(
    r"\b(st|rd|dr|ln|ave|ct|cir|blvd|hwy|trl|pkwy|way|pl)\b",
    re.IGNORECASE,
)

# Row format like: "1 06:38 am Bus Garage" or "10 07:15 am Paoli St & S Nine Mound Rd"
ROW_RE = re.compile(
    r"^\s*(\d{1,2})\s+(\d{1,2}:\d{2}\s*(?:am|pm))\s+(.+)$",
    re.IGNORECASE,
)


def _looks_like_stop(line: str) -> bool:
    s = line.strip()
    if len(s) < 4:
        return False

    low = s.lower()

    # Ignore headers/labels
    for p in JUNK_PREFIXES:
        if low.startswith(p):
            return False

    # Ignore navigation instructions
    for p in NAV_PREFIXES:
        if low.startswith(p):
            return False

    # Ignore separators like "--- PICK UP ---"
    if low.startswith("---") or low.endswith("---"):
        return False

    # Accept intersection stops
    if "&" in s:
        return True

    # Accept numeric addresses
    if s[0].isdigit() and " " in s:
        return True

    # Accept non-numeric street-like lines
    if STREET_SUFFIX_RE.search(s):
        return True

    return False


def _normalize_location_text(s: str, default_city_state_zip: str) -> str:
    """
    Normalize a location string to be Google-Maps-friendly:
    - Remove leading numbering like "1.", "1)", "1 " (common in PDFs)
    - Normalize '&' spacing
    - Append city/state/zip if missing
    """
    s = s.strip()

    # Remove leading numbering like: "10. ", "10) ", "10 "
    s = re.sub(r"^\s*\d+\s*[\.\)]\s*", "", s)
    

    # Normalize '&' spacing
    s = re.sub(r"\s*&\s*", " & ", s)

    # Add context for better resolution in Google Maps, especially intersections
    if "," not in s and default_city_state_zip:
        s = f"{s}, {default_city_state_zip}"

    return s


def _parse_row_line(line: str) -> Tuple[int, str, str] | None:
    """
    If line looks like a First Student table row: "STOP TIME LOCATION",
    return (stop_no, time, location). Otherwise None.
    """
    m = ROW_RE.match(line)
    if not m:
        return None

    stop_no = int(m.group(1))
    t = m.group(2).strip()
    loc = m.group(3).strip()

    # Sometimes LOCATION starts with stop number again: "1 1871 County Hwy PB"
    loc = re.sub(rf"^\s*{stop_no}\s+", "", loc)

    return stop_no, t, loc


def parse_route_pdf(
    pdf_path: str,
    default_route_id: str = "A1",
    default_type: str = "PM",
    default_school: str = "",
) -> pd.DataFrame:
    """
    Parse a route PDF and return a DataFrame with the same structure
    expected by process_routes.

    Improved MVP for First Student:
    - Extract text lines from PDF.
    - Prefer parsing table rows: STOP + TIME + COMMENT/LOCATION
    - Extract COMMENT/LOCATION as the real address and TIME into 'time'
    - Keep fallback heuristic for older/simple PDFs
    """

    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_file}")

    lines: List[str] = []

    # 1) Extract all non-empty lines from every page
    with pdfplumber.open(str(pdf_file)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for raw_line in text.split("\n"):
                line = raw_line.strip()
                if line:
                    lines.append(line)

    default_city_state_zip = "Verona, WI 53593"

    rows: List[Tuple[int, str, str]] = []
    seen = set()

    # 2A) First pass: parse table rows (best quality)
    for line in lines:
        parsed = _parse_row_line(line)
        if not parsed:
            continue

        seq, t, loc_raw = parsed

        # Normalize location to clean address
        loc = _normalize_location_text(loc_raw, default_city_state_zip)
        key = loc.lower()

        if key in seen:
            continue
        seen.add(key)

        rows.append((seq, t, loc))

    # 2B) Fallback: if no rows were captured, use heuristic stop detection
    if not rows:
        sequence = 1
        for line in lines:
            if not _looks_like_stop(line):
                continue

            loc = _normalize_location_text(line, default_city_state_zip)
            key = loc.lower()

            if key in seen:
                continue
            seen.add(key)

            rows.append((sequence, "", loc))
            sequence += 1

    # 3) Build DataFrame in the same format expected by process_routes
    data = []
    for seq, t, addr in rows:
        data.append(
            {
                "route_id": default_route_id,
                "school": default_school,
                "type": default_type,
                "stop_name": addr,
                "address": addr,
                "notes": "",
                "time": t,
                "sequence": seq,
            }
        )

    df = pd.DataFrame(
        data,
        columns=[
            "route_id",
            "school",
            "type",
            "stop_name",
            "address",
            "notes",
            "time",
            "sequence",
        ],
    )

    return df

from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Optional, Tuple
import re
from collections import Counter

import pdfplumber
import pandas as pd


# =====================================================
# Patterns / constants
# =====================================================

TRIP_LINE_RE = re.compile(r"^\s*TRIP:\s*(.+?)\s*(?:\(|$)", re.IGNORECASE)
TIME_RE = re.compile(r"^\d{1,2}:\d{2}\s*(am|pm)$", re.IGNORECASE)

# Navigation verbs that pollute "Location"
NAV_VERBS = (
    "go", "turn", "continue", "merge", "head", "keep", "take",
    "slight", "sharp", "make", "bear", "toward"
)
NAV_START_RE = re.compile(r"^\s*(?:%s)\b" % "|".join(NAV_VERBS), re.IGNORECASE)
NAV_CUT_RE = re.compile(r"\b(?:%s)\b" % "|".join(NAV_VERBS), re.IGNORECASE)

# Street suffixes for validation
STREET_SUFFIX_RE = re.compile(
    r"\b(st|rd|dr|ln|ave|ct|cir|blvd|hwy|trl|pkwy|way|pl|pass)\b",
    re.IGNORECASE,
)

# Direction-only tokens like "(SW)" "(N)"
BARE_DIR_RE = re.compile(r"^\(\s*[NSEW]{1,2}\s*\)$", re.IGNORECASE)

# City, ST ZIP finder (tries to capture the full "City, ST 12345")
CITY_STATE_ZIP_FULL_RE = re.compile(r"\b([A-Za-z][A-Za-z\s]+,\s*[A-Z]{2}\s*\d{5})\b")

# Numeric address / intersection extractors
NUM_ADDR_RE = re.compile(
    r"\b(\d{2,6}\s+[A-Za-z0-9][A-Za-z0-9\s\.\-']+?\b(?:st|rd|dr|ln|ave|ct|cir|blvd|hwy|trl|pkwy|way|pl|pass)\b)",
    re.IGNORECASE,
)
INTERSECTION_RE = re.compile(
    r"\b([A-Za-z0-9][A-Za-z0-9\s\.\-']+?\s*&\s*[A-Za-z0-9][A-Za-z0-9\s\.\-']+)\b",
    re.IGNORECASE,
)

MILES_RE = re.compile(r"\b\d+(?:\.\d+)?\s*mi\.?\b", re.IGNORECASE)


# =====================================================
# Fragment merge helper (TOP LEVEL, only once)
# =====================================================

def _merge_fragment_rows(rows: list[dict]) -> list[dict]:
    """
    Merge OCR/parser fragment rows like:
      "(SW)" or "Trl (NE)" or "Dr"
    into the previous row's stop_name/address, then drop the fragment row.
    """
    SUFFIX = r"(st|rd|dr|ln|ave|ct|cir|blvd|hwy|trl|pkwy|way|pl|pass)"
    DIR = r"\(\s*[NSEW]{1,2}\s*\)"

    def is_fragment(text: str) -> bool:
        t = (text or "").strip()
        return (
            re.fullmatch(DIR, t, flags=re.I)
            or re.fullmatch(SUFFIX, t, flags=re.I)
            or re.fullmatch(rf"{SUFFIX}\s*{DIR}", t, flags=re.I)
        )

    merged: list[dict] = []
    for row in rows:
        addr = (row.get("address") or "").strip()
        name = (row.get("stop_name") or "").strip()
        token = addr or name

        if not merged:
            merged.append(row)
            continue

        if is_fragment(token):
            prev = merged[-1]
            prev_addr = (prev.get("address") or "").strip()
            prev_name = (prev.get("stop_name") or "").strip()

            # Merge fragment into previous
            prev["stop_name"] = f"{prev_name} {token}".strip()

            # Only extend address if previous has address; otherwise keep empty
            if prev_addr:
                prev["address"] = f"{prev_addr} {token}".strip()

            continue  # drop fragment row

        merged.append(row)

    return merged


# =====================================================
# Helpers: grouping words into lines
# =====================================================

def _cluster_words_to_lines(words: List[Dict], y_tolerance: float = 3.0) -> List[List[Dict]]:
    if not words:
        return []

    words = sorted(words, key=lambda w: (float(w.get("top", 0.0)), float(w.get("x0", 0.0))))
    lines: List[List[Dict]] = []
    current: List[Dict] = []
    current_y: Optional[float] = None

    for w in words:
        y = float(w.get("top", 0.0))
        if current_y is None:
            current_y = y
            current = [w]
            continue

        if abs(y - current_y) <= y_tolerance:
            current.append(w)
        else:
            lines.append(sorted(current, key=lambda ww: float(ww.get("x0", 0.0))))
            current_y = y
            current = [w]

    if current:
        lines.append(sorted(current, key=lambda ww: float(ww.get("x0", 0.0))))

    return lines


def _join_words(words: List[Dict]) -> str:
    return " ".join(
        (w.get("text") or "").strip()
        for w in words
        if (w.get("text") or "").strip()
    ).strip()


# =====================================================
# Trip / route inference
# =====================================================

def _extract_trip_name_from_lines(lines: List[str]) -> Optional[str]:
    for ln in lines:
        m = TRIP_LINE_RE.match(ln.strip())
        if m:
            return (m.group(1) or "").strip()
    return None


def _infer_route_id_and_type(trip_name: Optional[str], default_route_id: str, default_type: str) -> Tuple[str, str]:
    if not trip_name:
        return default_route_id, default_type

    upper = trip_name.upper()
    rtype = "AM" if "-AM" in upper else ("PM" if "-PM" in upper else default_type)

    rid = re.sub(r"-(AM|PM)\b.*$", "", trip_name, flags=re.IGNORECASE).strip()
    if not rid:
        rid = default_route_id

    return rid, rtype


def _infer_city_state_zip_from_text(lines: List[str], fallback: str = "Verona, WI 53593") -> str:
    hits: List[str] = []
    for ln in lines:
        m = CITY_STATE_ZIP_FULL_RE.search(ln)
        if m:
            hits.append(m.group(1).strip())

    if not hits:
        return fallback

    most_common = Counter(hits).most_common(1)[0][0]
    return most_common if len(most_common) >= 8 else fallback


# =====================================================
# Cleaning / validation
# =====================================================

def _extract_best_address(text: str) -> str:
    s = (text or "").strip()
    if not s:
        return ""

    if NAV_START_RE.match(s.lower()):
        return ""
    if MILES_RE.search(s) and not (NUM_ADDR_RE.search(s) or INTERSECTION_RE.search(s)):
        return ""

    m = NUM_ADDR_RE.search(s)
    if m:
        return m.group(1).strip()

    m = INTERSECTION_RE.search(s)
    if m:
        return m.group(1).strip()

    m = NAV_CUT_RE.search(s.lower())
    if m:
        left = s[:m.start()].strip()
        if _looks_like_address(left):
            return left
        return ""

    return s if _looks_like_address(s) else ""


def _looks_like_name_soup(text: str) -> bool:
    s = (text or "").strip()
    if not s:
        return False

    if any(ch.isdigit() for ch in s) or "&" in s or STREET_SUFFIX_RE.search(s):
        return False

    tokens = [t for t in re.split(r"\s+", s) if t]
    if len(tokens) < 6:
        return False

    cap_like = sum(1 for t in tokens if t[:1].isupper())
    return cap_like / max(len(tokens), 1) >= 0.75


def _looks_like_address(text: str) -> bool:
    s = (text or "").strip()
    if not s:
        return False

    if BARE_DIR_RE.match(s):
        return False

    if len(s) < 5:
        return False

    if _looks_like_name_soup(s):
        return False

    if "&" in s:
        return True

    if s[0].isdigit() and " " in s:
        return True

    if STREET_SUFFIX_RE.search(s):
        return True

    return False


def _normalize_location(text: str, city_state_zip: str) -> str:
    s = (text or "").strip()
    if not s:
        return ""

    s = re.sub(r"\s*&\s*", " & ", s)
    s = re.sub(r"\s{2,}", " ", s).strip()

    if city_state_zip and "," not in s:
        s = f"{s}, {city_state_zip}"

    return s


def _is_good_final_address(addr: str) -> bool:
    print("CHECK ADDRESS:", addr)

    if not addr:
        print("REJECTED: empty")
        return False

    s = addr.strip()
    if len(s) < 6:
        print("REJECTED: too_short")
        return False

    if _looks_like_name_soup(s):
        print("REJECTED: looks_like_name_soup")
        return False

    # SOLO evaluamos la parte antes de la coma (evita que el ZIP valide basura)
    head = s.split(",")[0].strip()

    if re.fullmatch(r"\(\s*[NSEW]{1,2}\s*\)", head, flags=re.IGNORECASE):
        print("REJECTED: bare_direction_only")
        return False

    if re.fullmatch(
        r"(st|rd|dr|ln|ave|ct|cir|blvd|hwy|trl|pkwy|way|pl|pass)\b",
        head,
        flags=re.IGNORECASE,
    ):
        print("REJECTED: suffix_only")
        return False

    if "&" in head:
        print("ACCEPTED: intersection")
        return True

    if head and head[0].isdigit():
        print("ACCEPTED: starts_with_digit")
        return True

    if any(ch.isdigit() for ch in head):
        print("ACCEPTED: has_digits_in_head")
        return True

    if STREET_SUFFIX_RE.search(head) and len(head.split()) >= 2:
        print("ACCEPTED: street_suffix")
        return True

    print("REJECTED: no_address_signals")
    return False

# =====================================================
# Extract rows from Trip Detail table (page 1)
# =====================================================

def _extract_rows_from_first_page(pdf_path: str) -> Tuple[List[Dict], List[str]]:
    rows: List[Dict] = []
    all_text_lines: List[str] = []

    with pdfplumber.open(pdf_path) as pdf:
        if not pdf.pages:
            return rows, all_text_lines

        page = pdf.pages[0]

        text_full = page.extract_text() or ""
        all_text_lines = [ln.strip() for ln in text_full.splitlines() if ln.strip()]

        words = page.extract_words(
            keep_blank_chars=False,
            use_text_flow=True,
            extra_attrs=["fontname", "size"],
        )

        line_groups = _cluster_words_to_lines(words, y_tolerance=3.0)

        w = float(page.width)

        x_stop_max = w * 0.14
        x_time_min = w * 0.14
        x_time_max = w * 0.30
        x_loc_min  = w * 0.34
        x_loc_max  = w * 0.72

        for line_words in line_groups:
            stop_words = [wd for wd in line_words if float(wd.get("x0", 0.0)) < x_stop_max]
            time_words = [wd for wd in line_words if x_time_min <= float(wd.get("x0", 0.0)) < x_time_max]
            loc_words  = [wd for wd in line_words if x_loc_min  <= float(wd.get("x0", 0.0)) < x_loc_max]

            stop_text = _join_words(stop_words)
            time_text = _join_words(time_words)
            loc_text  = _join_words(loc_words)

            seq = int(stop_text) if stop_text.isdigit() else None

            t = (time_text or "").strip()
            if t and not TIME_RE.match(t):
                if ":" in t and ("am" in t.lower() or "pm" in t.lower()):
                    pass
                else:
                    t = ""

            if seq is not None or loc_text:
                rows.append({"sequence": seq, "time": t, "raw_location": (loc_text or "").strip()})

    return rows, all_text_lines


# =====================================================
# Text extraction (all pages)
# =====================================================

def _extract_text_lines_all_pages(pdf_path: str) -> List[str]:
    lines: List[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for p in pdf.pages:
            txt = p.extract_text() or ""
            lines.extend([ln.strip() for ln in txt.splitlines() if ln.strip()])
    return lines


# =====================================================
# State machine to build stops
# =====================================================

def _state_machine_build_stops(extracted_rows: List[Dict], city_state_zip: str) -> List[Dict]:
    stops: List[Dict] = []
    current: Optional[Dict] = None

    def _finalize_current():
        nonlocal current
        if not current:
            return
        raw = " ".join(current["parts"]).strip()

        raw = _extract_best_address(raw)
        if not raw:
            current = None
            return

        addr = _normalize_location(raw, city_state_zip)
        if _is_good_final_address(addr):
            stops.append({"sequence": int(current["sequence"]), "time": current.get("time", ""), "address": addr})
        current = None

    for r in extracted_rows:
        seq = r.get("sequence", None)
        t = (r.get("time") or "").strip()
        loc = (r.get("raw_location") or "").strip()

        if not loc and seq is None:
            continue

        if re.match(r"^\d+\s+-{3,}", loc):
            continue
        if "PICK UP" in loc.upper() or "DROP OFF" in loc.upper():
            continue

        loc = re.sub(r"^\s*\d+\s+(?=[A-Za-z])", "", loc).strip()

        if _looks_like_name_soup(loc):
            continue

        loc = _extract_best_address(loc)
        if not loc:
            continue

        if BARE_DIR_RE.match(loc):
            continue

        if seq is not None:
            _finalize_current()
            current = {"sequence": seq, "time": t, "parts": []}
            if _looks_like_address(loc):
                current["parts"].append(loc)
            continue

        if current and loc:
            if _looks_like_address(loc) or (STREET_SUFFIX_RE.search(loc) and len(loc.split()) >= 2):
                current["parts"].append(loc)

    _finalize_current()

    seen = set()
    final: List[Dict] = []
    for s in sorted(stops, key=lambda x: x["sequence"]):
        key = s["address"].lower()
        if key in seen:
            continue
        seen.add(key)
        final.append(s)

    return final


# =====================================================
# Public API
# =====================================================
def parse_route_pdf(
    pdf_path: str,
    default_route_id: str = "A1",
    default_type: str = "PM",
    default_school: str = "",
) -> pd.DataFrame:
    """
    Parse First Student Trip Detail PDF (Trip Detail on page 1).
    """
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_file}")

    extracted_rows, _ = _extract_rows_from_first_page(str(pdf_file))
    text_lines = _extract_text_lines_all_pages(str(pdf_file))

    # Debug prints
    print("ROWS(page1):", len(extracted_rows))

    trip_name = _extract_trip_name_from_lines(text_lines)
    route_id, rtype = _infer_route_id_and_type(trip_name, default_route_id, default_type)
    city_state_zip = _infer_city_state_zip_from_text(text_lines, fallback="Verona, WI 53593")

    # 1) Primary approach: state machine over page-1 extracted rows
    stops = _state_machine_build_stops(extracted_rows, city_state_zip)
    print("STOPS(state_machine):", len(stops))

    # Fragment line regex (RAW STRING to avoid \s warning)
    FRAG_LINE_RE = re.compile(
        r"^(\([NSEW]{1,2}\)|"
        r"(Rd|St|Ave|Dr|Ln|Trl|Pass|Cir|Blvd|Hwy)(\s*\([NSEW]{1,2}\))?|"
        r"(School|Elementary|Middle))$",
        re.IGNORECASE,
    )

    # Decide if we should fallback:
    # expected stops ~= number of rows with a numeric sequence on page 1
    expected = sum(1 for r in extracted_rows if r.get("sequence") is not None)

    # Trigger fallback only if:
    # - no stops, OR
    # - we got a suspiciously low portion of expected (e.g., < 70%),
    #   AND expected is meaningful (>= 4)
    should_fallback = (len(stops) == 0) or (expected >= 4 and len(stops) < int(expected * 0.7))

    # 2) Text fallback (all pages)
    if should_fallback:
        STOP_RE = re.compile(
            r"^\s*(\d+)\s+(\d{1,2}:\d{2})\s*(am|pm)\s*(.*?)\s*$",
            re.IGNORECASE,
        )

        lines = [l.strip() for l in text_lines if l and l.strip()]
        fallback_stops: list[dict] = []

        i = 0
        while i < len(lines):
            line = lines[i]
            m = STOP_RE.match(line)
            if not m:
                i += 1
                continue

            seq = int(m.group(1))
            time = f"{m.group(2)} {m.group(3).lower()}"
            location = (m.group(4) or "").strip()

            # Attach continuation fragment lines
            k = i + 1
            while k < len(lines):
                nxt = lines[k].strip()

                if STOP_RE.match(nxt):
                    break

                if not nxt or "----" in nxt:
                    k += 1
                    continue

                if nxt.lower().startswith(("stop ", "go ", "turn ", "make ", "head ")):
                    break

                if FRAG_LINE_RE.match(nxt):
                    location = f"{location} {nxt}".strip()
                    k += 1
                    continue

                break

            if not location:
                i = k
                continue

            # filter junk
            if "----" in location:
                i = k
                continue
            if location.lower().startswith(("go ", "turn ", "make ", "head ")):
                i = k
                continue
            if location.strip().lower() in {"rd", "st", "ave", "dr", "blvd", "ln"}:
                i = k
                continue

            normalized = _normalize_location(location, city_state_zip)

            if not _is_good_final_address(normalized):
                fallback_stops.append({"sequence": seq, "time": time, "address": "", "stop_name": location})
            else:
                fallback_stops.append({"sequence": seq, "time": time, "address": normalized, "stop_name": location})

            i = k

        print("STOPS(fallback_text):", len(fallback_stops))

        # Keep the better result (more stops usually means better coverage)
        if len(fallback_stops) > len(stops):
            stops = fallback_stops

    # 3) Build final DataFrame (ALWAYS runs, ALWAYS inside function)
    data: list[dict] = []
    for s in stops:
        addr = (s.get("address") or "").strip()
        name = (s.get("stop_name") or "").strip() or addr

        data.append(
            {
                "route_id": route_id,
                "school": default_school,
                "type": rtype,
                "stop_name": name,
                "address": addr,
                "notes": "",
                "time": s.get("time", ""),
                "sequence": int(s.get("sequence", 0)),
            }
        )

    # keep this OFF while validating fallback output
    # data = _merge_fragment_rows(data)

    df = pd.DataFrame(
        data,
        columns=["route_id", "school", "type", "stop_name", "address", "notes", "time", "sequence"],
    )

    if not df.empty:
        df = df.sort_values("sequence").reset_index(drop=True)

    return df
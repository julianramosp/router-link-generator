"""
Utility functions for data cleaning, normalization, and list operations.
No I/O or external API calls should be here.
"""
import re
from typing import Iterable, List
from typing import List, Dict

# Regex pattern for collapsing extra whitespace
WS = re.compile(r"\s+")

def normalize_addresses(addresses: Iterable[str]) -> List[str]:
    """
    Cleans whitespace and separators in address strings.
    Example:
        '123  Main  St , Madison ' -> '123 Main St, Madison'
    """
    normalized = []
    for a in addresses:
        if not a:
            continue
        s = WS.sub(" ", a).strip()
        s = s.replace(" ,", ",")
        if s:
            normalized.append(s)
    return normalized

def dedupe_keep_order(items: Iterable[str]) -> List[str]:
    """
    Removes duplicates from a list while preserving the original order.
    Example:
        ['A', 'B', 'A', 'C'] -> ['A', 'B', 'C']
    """
    seen = set()
    unique_items = []
    for item in items:
        if item not in seen:
            unique_items.append(item)
            seen.add(item)
    return unique_items

from typing import Tuple, List, Dict

def clean_stops(parsed_stops: List[Dict]) -> Tuple[List[str], List[Dict]]:
    """
    Takes parsed stops (list of dicts with keys like 'address') and returns:
      - cleaned list of address strings (keeping original order)
      - dropped stops (original dicts) that had empty/invalid address strings
    """
    cleaned: List[str] = []
    dropped: List[Dict] = []

    for s in parsed_stops:
        addr = (s.get("address") or "").strip()
        if addr:
            cleaned.append(addr)
        else:
            dropped.append(s)

    return cleaned, dropped



FRAGMENT_ONLY_RE = re.compile(
    r"""^(
        \([NSEW]{1,2}\) |
        (Rd|St|Ave|Dr|Ln|Trl|Pass|Cir|Blvd|Hwy)(\s*\([NSEW]{1,2}\))? |
        School |
        Elementary |
        Middle
    )$""",
    re.IGNORECASE | re.VERBOSE,
)




DIR_ONLY = re.compile(r"^\(\s*[NSEW]{1,2}\s*\)$", re.I)
SUFFIX_START = re.compile(r"^(Rd|St|Ave|Dr|Ln|Trl|Pass|Cir|Blvd|Hwy)\b", re.I)
SCHOOL_WORD = re.compile(r"^(School|Elementary|Middle)\b", re.I)

# If a stop_name ends with these, it’s probably cut and the next fragment belongs to it
CUT_END = re.compile(r"\b(Red|New|Renaissance|Pawnee|Elementary)$", re.I)

def _is_fragment(name: str) -> bool:
    n = (name or "").strip()
    return bool(DIR_ONLY.match(n) or SUFFIX_START.match(n) or SCHOOL_WORD.match(n))

def _looks_cut(name: str) -> bool:
    n = (name or "").strip()
    # ends with connector words that commonly get continued in next line
    return bool(CUT_END.search(n))

def merge_fragment_stops(parsed_stops: List[Dict]) -> List[Dict]:
    """
    Merge only true fragments, and only into a neighbor that looks cut.
    This prevents collapsing many stops into one.
    """
    out: List[Dict] = []
    i = 0

    while i < len(parsed_stops):
        cur = parsed_stops[i]
        cur_name = (cur.get("stop_name") or "").strip()

        # If current is a fragment, try to attach it:
        if _is_fragment(cur_name):
            prev = out[-1] if out else None
            nxt = parsed_stops[i + 1] if i + 1 < len(parsed_stops) else None
            prev_name = (prev.get("stop_name") or "").strip() if prev else ""
            nxt_name = (nxt.get("stop_name") or "").strip() if nxt else ""

            # Prefer NEXT only if next looks cut (rare), otherwise prefer PREV only if prev looks cut.
            # This avoids wrong merges like (SW) into Rosenberry.
            if nxt and _looks_cut(nxt_name):
                nxt["stop_name"] = f"{nxt_name} {cur_name}".strip()
                nxt["address"] = f"{nxt['stop_name']}, Verona, WI 53593"
                i += 1
                continue

            if prev and _looks_cut(prev_name):
                prev["stop_name"] = f"{prev_name} {cur_name}".strip()
                prev["address"] = f"{prev['stop_name']}, Verona, WI 53593"
                i += 1
                continue

            # If we can't confidently attach it, DROP the fragment (don’t destroy route)
            i += 1
            continue

        out.append(cur)
        i += 1

    return out
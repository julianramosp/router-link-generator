"""
Utility functions for data cleaning, normalization, and list operations.
No I/O or external API calls should be here.
"""
import re
from typing import Iterable, List

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

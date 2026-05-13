"""
Matching engine: match old quote line items to current inventory by name.
Simple approach: exact match → normalized match → fuzzy top pick → no match.
No AI calls — fast, free, and predictable.
"""

import re
import logging
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# Patterns to strip when normalizing names for comparison
_YEAR_RE = re.compile(r"\s*\(\s*20\d{2}\s*\)\s*$")
_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


def _normalize(name: str) -> str:
    """Lowercase, strip year suffix, collapse non-alphanumeric to spaces."""
    name = _YEAR_RE.sub("", name).lower().strip()
    return _NORMALIZE_RE.sub(" ", name).strip()


def _fuzzy(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _build_index(inventory: list[dict]) -> dict[str, list[dict]]:
    """Index inventory by normalized name for fast lookup."""
    index: dict[str, list[dict]] = {}
    for item in inventory:
        key = _normalize(item.get("name") or "")
        if key:
            index.setdefault(key, []).append(item)
    return index


def match_item(old_item: dict, inventory: list[dict], name_index: dict) -> dict:
    old_name: str = old_item.get("name") or old_item.get("elementName") or old_item.get("description") or ""
    norm_old = _normalize(old_name)

    if not old_name or not inventory:
        return _no_match(old_item, "No item name or empty inventory")

    # 1. Exact normalized match
    if norm_old in name_index:
        candidates = name_index[norm_old]
        return {
            "old_item": old_item,
            "match": candidates[0],
            "confidence": 1.0,
            "reason": "Exact name match",
            "alternatives": candidates[1:4],
            "needs_review": False,
        }

    # 2. Fuzzy match — score all inventory items, take best
    scored = sorted(
        ((item, _fuzzy(norm_old, _normalize(item.get("name") or ""))) for item in inventory),
        key=lambda x: x[1],
        reverse=True,
    )
    best_item, best_score = scored[0]

    if best_score >= 0.85:
        return {
            "old_item": old_item,
            "match": best_item,
            "confidence": round(best_score, 2),
            "reason": f"Close name match ({best_score:.0%})",
            "alternatives": [x for x, _ in scored[1:4]],
            "needs_review": False,
        }

    if best_score >= 0.60:
        return {
            "old_item": old_item,
            "match": best_item,
            "confidence": round(best_score, 2),
            "reason": f"Possible match — please verify ({best_score:.0%})",
            "alternatives": [x for x, _ in scored[1:4]],
            "needs_review": True,
        }

    return _no_match(old_item, f"Best fuzzy score too low ({best_score:.0%}) — manual selection needed")


async def match_all_items(
    items: list[dict],
    inventory: list[dict],
    **kwargs,  # absorb openai_client / model if passed from route
) -> list[dict]:
    name_index = _build_index(inventory)
    logger.info("Built name index with %d unique normalized names from %d items", len(name_index), len(inventory))

    # Log a few inventory names so we can see what's in there
    sample_names = sorted(name_index.keys())[:10]
    logger.info("Sample inventory names (first 10 alpha): %s", sample_names)

    results = []
    for item in items:
        r = match_item(item, inventory, name_index)
        old_name = item.get("name") or ""
        logger.info("  '%s' → '%s' (%.0f%%)", old_name, r["match"].get("name") if r["match"] else "NO MATCH", r["confidence"] * 100)
        results.append(r)

    matched = sum(1 for r in results if r["match"])
    logger.info("Matched %d / %d items", matched, len(items))
    return results


def _no_match(old_item: dict, reason: str) -> dict:
    return {
        "old_item": old_item,
        "match": None,
        "confidence": 0.0,
        "reason": reason,
        "alternatives": [],
        "needs_review": True,
    }

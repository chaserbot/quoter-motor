"""
Matching engine: takes old quote line items and current Flex inventory,
returns AI-ranked match candidates with confidence scores.
"""

import json
import logging
from difflib import SequenceMatcher
from typing import Optional

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

LABOR_KEYWORDS = {
    "engineer", "technician", "tech", "stage hand", "stagehand",
    "hand", "operator", "director", "manager", "labor", "labour",
    "crew", "rigger", "driver", "loader", "pa ", " pa,",
}


def _fuzzy_score(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _is_labor(item: dict) -> bool:
    name = (item.get("name") or item.get("description") or "").lower()
    return any(kw in name for kw in LABOR_KEYWORDS)


def _top_candidates(old_name: str, inventory: list[dict], n: int = 20) -> list[dict]:
    """Return the N inventory items with the highest name similarity to old_name."""
    scored = [
        (item, _fuzzy_score(old_name, item.get("name") or ""))
        for item in inventory
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [item for item, _ in scored[:n]]


async def match_item(
    old_item: dict,
    inventory: list[dict],
    openai_client: AsyncOpenAI,
    model: str,
) -> dict:
    """
    Match a single old quote line item against the current inventory.

    Returns:
        {
            old_item, match, confidence, reason, alternatives, needs_review
        }
    """
    old_name: str = old_item.get("name") or old_item.get("elementName") or old_item.get("description") or ""
    old_desc: str = old_item.get("description") or ""

    if not inventory:
        return _no_match(old_item, "Inventory is empty")

    # Exact match short-circuit (case-insensitive)
    for item in inventory:
        if (item.get("name") or "").lower().strip() == old_name.lower().strip():
            return {
                "old_item": old_item,
                "match": item,
                "confidence": 1.0,
                "reason": "Exact name match",
                "alternatives": [],
                "needs_review": False,
            }

    candidates = _top_candidates(old_name, inventory, n=20)
    if not candidates:
        return _no_match(old_item, "No candidates found")

    # Build prompt
    item_type = "labor/personnel" if _is_labor(old_item) else "AV/event production equipment"
    candidates_text = "\n".join(
        f"{i + 1}. [ID:{c['id']}] {c.get('name', 'Unnamed')} — {c.get('description', '')[:80]}"
        for i, c in enumerate(candidates)
    )

    prompt = f"""You are an expert in {item_type} for live events and AV production.

Old quote item: "{old_name}"
Additional description: "{old_desc}"

Current inventory candidates (pre-sorted by name similarity):
{candidates_text}

Which current item BEST matches the old item? Consider:
- Direct upgrades within the same product line (e.g. "MAC Aura" → "MAC Aura XB")
- Functional equivalents (same role, possibly different brand/model)
- For labor: exact or near-exact job title match
- Prefer higher-numbered candidates ONLY if they are clearly better matches

Respond with ONLY valid JSON (no markdown, no explanation outside JSON):
{{
  "match_index": 1,
  "confidence": 0.95,
  "reason": "One sentence explanation",
  "alternative_indices": [2, 3]
}}

Rules:
- match_index is 1-based, matching the list above
- confidence: 0.95+ confident, 0.80-0.94 probable, 0.60-0.79 possible, <0.60 poor
- Set match_index to null and confidence to 0.0 if no reasonable match exists
"""

    try:
        response = await openai_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=200,
        )
        result = json.loads(response.choices[0].message.content)
    except Exception as e:
        logger.warning("OpenAI matching failed for '%s': %s", old_name, e)
        # Fall back to best fuzzy match
        return {
            "old_item": old_item,
            "match": candidates[0],
            "confidence": 0.4,
            "reason": f"AI unavailable — best fuzzy match (score: {_fuzzy_score(old_name, candidates[0].get('name', '')):.0%})",
            "alternatives": candidates[1:4],
            "needs_review": True,
        }

    idx = result.get("match_index")
    confidence = float(result.get("confidence", 0.0))

    if idx is None or not (1 <= idx <= len(candidates)):
        return _no_match(old_item, result.get("reason", "AI found no suitable match"))

    match = candidates[idx - 1]
    alt_indices = [
        i for i in result.get("alternative_indices", [])
        if isinstance(i, int) and 1 <= i <= len(candidates) and i != idx
    ]
    alternatives = [candidates[i - 1] for i in alt_indices[:3]]

    return {
        "old_item": old_item,
        "match": match,
        "confidence": confidence,
        "reason": result.get("reason", ""),
        "alternatives": alternatives,
        "needs_review": confidence < 0.85,
    }


async def match_all_items(
    items: list[dict],
    inventory: list[dict],
    openai_client: AsyncOpenAI,
    model: str,
) -> list[dict]:
    """Match every item in a quote concurrently (batched to avoid rate limits)."""
    import asyncio

    BATCH_SIZE = 10
    results: list[dict] = []
    for i in range(0, len(items), BATCH_SIZE):
        batch = items[i : i + BATCH_SIZE]
        batch_results = await asyncio.gather(
            *[match_item(item, inventory, openai_client, model) for item in batch]
        )
        results.extend(batch_results)

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

"""High-value owner questions for unresolved operational hypotheses (§20)."""

from __future__ import annotations

from typing import Any


QUESTION_TEMPLATES: dict[str, tuple[str, list[str], float]] = {
    "order_tier": (
        "Did the supplier or contract tier change this period?",
        ["smaller order tier", "new contract terms", "no change", "not sure"],
        0.8,
    ),
    "product_switch": (
        "Did you switch supplier, SKU, or product grade this period?",
        ["supplier", "SKU or grade", "no switch", "not sure"],
        0.8,
    ),
    "menu_change": (
        "Did a menu launch or removal change what customers ordered?",
        ["launch", "removal", "no menu change", "not sure"],
        0.8,
    ),
    "promo": (
        "Was a promotion running on the products whose mix changed?",
        ["yes", "no", "not sure"],
        0.8,
    ),
    "checkout_friction": (
        "Were there queue, POS, or staffing issues during peak hours?",
        ["queue", "POS", "staffing", "none", "not sure"],
        0.8,
    ),
    "equipment": (
        "Did any equipment fault or maintenance issue occur this period?",
        ["fault", "maintenance", "none", "not sure"],
        0.8,
    ),
    "hours": (
        "Were opening or staffed hours changed this period?",
        ["extended", "reduced", "unchanged", "not sure"],
        0.8,
    ),
    "waste": (
        "Was there a spoilage, portioning, or stock-build event?",
        ["spoilage", "portioning", "stock build", "none", "not sure"],
        0.8,
    ),
}


def candidate(
    *,
    hypothesis_id: str,
    leaf: str,
    cls: str,
    unexplained_dollars: float,
    recurring: bool,
) -> dict[str, Any] | None:
    spec = QUESTION_TEMPLATES.get(cls)
    if not spec:
        return None
    text, options, p_resolves = spec
    future_relevance = 1.0 if recurring else 0.5
    voi = abs(unexplained_dollars) * p_resolves * future_relevance
    if voi < 150:
        return None
    return {
        "id": f"q_{hypothesis_id}",
        "text": text,
        "options": options,
        "leaf": leaf,
        "class": cls,
        "voi_dollars": round(voi, 2),
    }


def select(candidates: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    """Return the highest-VOI non-duplicate questions."""
    seen: set[tuple[str, str]] = set()
    selected: list[dict[str, Any]] = []
    for item in sorted(candidates, key=lambda row: row["voi_dollars"], reverse=True):
        key = (item["leaf"], item["class"])
        if key in seen:
            continue
        seen.add(key)
        selected.append(item)
        if len(selected) == limit:
            break
    return selected

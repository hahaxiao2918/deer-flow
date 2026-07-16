"""Versioned external-data prices and deterministic estimates."""

from __future__ import annotations

from math import ceil

PRICING_VERSION = "zhihuiya-shanghai-electric-2026-07-16"
MAX_D114_BATCH = 100


def estimate_patent_cost(
    patent_count: int,
    *,
    search_calls: int = 0,
    include_basic: bool = False,
    include_text_bundle: bool = False,
    basic_count: int | None = None,
    text_bundle_count: int | None = None,
) -> dict:
    """Return an explainable quote; never performs a network call."""
    if patent_count < 0 or search_calls < 0 or (basic_count is not None and basic_count < 0) or (text_bundle_count is not None and text_bundle_count < 0):
        raise ValueError("counts and search_calls must be non-negative")

    lines: list[dict] = []
    if search_calls:
        lines.append({"api": "P002", "unit": "per_call", "unit_price": 0.20, "quantity": search_calls, "cost": round(search_calls * 0.20, 2)})
    basic_items = patent_count if basic_count is None else basic_count
    text_items = patent_count if text_bundle_count is None else text_bundle_count
    if include_basic and basic_items:
        lines.append({"api": "P012", "unit": "per_item", "unit_price": 0.02, "quantity": basic_items, "cost": round(basic_items * 0.02, 2)})
    if include_text_bundle and text_items:
        calls = ceil(text_items / MAX_D114_BATCH)
        lines.append({"api": "D114", "unit": "per_call_up_to_100_items", "unit_price": 0.20, "quantity": calls, "covered_items": text_items, "cost": round(calls * 0.20, 2)})

    return {
        "currency": "CNY",
        "pricing_version": PRICING_VERSION,
        "estimated_external_cost": round(sum(line["cost"] for line in lines), 2),
        "cost_basis": lines,
        "requires_confirmation": patent_count > MAX_D114_BATCH,
        "reason": "More than 100 records requires multiple D114 calls" if patent_count > MAX_D114_BATCH else "",
    }

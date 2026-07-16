"""MCP tools. They expose external facts and estimates, never LLM conclusions."""

from __future__ import annotations

import asyncio
from typing import Any

from .config import load_settings
from .ledger import BudgetLedger
from .normalize import clean_patent_numbers, normalize_d114_record, normalize_search_row
from .pricing import MAX_D114_BATCH, PRICING_VERSION, estimate_patent_cost
from .zhihuiya import ZhihuiyaClient


def _client() -> ZhihuiyaClient:
    return ZhihuiyaClient(load_settings())


def _ledger() -> BudgetLedger:
    settings = load_settings()
    return BudgetLedger(settings.state_path, settings.project_budgets_json)


async def data_capabilities() -> dict[str, Any]:
    """Return verified M1A capabilities and intentionally unavailable features."""
    return {
        "pricing_version": PRICING_VERSION,
        "capabilities": {
            "patent_search": {"api": "P002", "status": "verified_available", "max_results": 1000},
            "patent_basic": {"api": "P012", "status": "verified_available", "billing": "per_item"},
            "patent_text_bundle": {"api": "D114", "status": "verified_available", "max_batch": MAX_D114_BATCH, "billing": "per_call"},
            "literature_search": {"status": "feature_flag_disabled"},
            "legal_status": {"api": "P013", "status": "not_authorized"},
            "family": {"api": "P014", "status": "not_authorized"},
        },
    }


async def data_cost_estimate(
    project_id: str,
    patent_count: int,
    include_basic: bool = False,
    include_text_bundle: bool = False,
    search_calls: int = 0,
) -> dict[str, Any]:
    """Estimate P002/P012/D114 cost before any upstream request."""
    try:
        quote = estimate_patent_cost(patent_count, search_calls=search_calls, include_basic=include_basic, include_text_bundle=include_text_bundle)
        budget = _ledger().quote_budget(project_id, quote["estimated_external_cost"])
        quote["budget"] = {"ok": budget.ok, "reason": budget.reason, "limit": budget.budget_limit, "remaining": budget.budget_remaining}
        quote["requires_confirmation"] = quote["requires_confirmation"] or not budget.ok
        return quote
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}


async def patent_search(project_id: str, query_text: str, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    """Run confirmed P002 search and return normalized candidates with pn values."""
    if not query_text.strip():
        return {"ok": False, "error": "query_text is required"}
    if limit < 1 or limit > 1000 or offset < 0 or limit + offset > 20000:
        return {"ok": False, "error": "invalid limit or offset"}
    reservation = _ledger().reserve(project_id, "P002", 0.20)
    if not reservation.ok:
        return {"ok": False, "error": reservation.reason, "budget_limit": reservation.budget_limit, "budget_remaining": reservation.budget_remaining}
    shell = await _client().search(query_text, limit, offset)
    _ledger().complete(reservation.reservation_id, "success" if shell.get("status") else "upstream_error")
    if not shell.get("status"):
        return {"ok": False, "diagnostics": {"error_code": shell.get("error_code"), "error_msg": shell.get("error_msg")}}
    data = shell.get("data") or {}
    rows = [normalize_search_row(row) for row in (data.get("results") or [])]
    return {"ok": True, "query_text": query_text, "results": rows, "result_count": data.get("result_count", len(rows)), "total_search_result_count": data.get("total_search_result_count", 0), "provenance": {"source_api": "P002", "pricing_version": PRICING_VERSION}}


async def patent_get_records(
    project_id: str,
    patent_numbers: list[str],
    include_basic: bool = True,
    include_text_bundle: bool = True,
) -> dict[str, Any]:
    """Fetch up to 100 public numbers using P012 metadata and D114 batch text."""
    try:
        numbers = clean_patent_numbers(patent_numbers, maximum=MAX_D114_BATCH)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    if not include_basic and not include_text_bundle:
        return {"ok": False, "error": "select at least one field package"}

    settings = load_settings()
    ledger = _ledger()
    cached_text = {pn: ledger.get_cache(f"D114:{pn}") for pn in numbers} if include_text_bundle else {}
    cached_biblio = {pn: ledger.get_cache(f"P012:{pn}") for pn in numbers} if include_basic else {}
    missing_text = [pn for pn in numbers if include_text_bundle and not cached_text.get(pn)]
    missing_biblio = [pn for pn in numbers if include_basic and not cached_biblio.get(pn)]
    quote = estimate_patent_cost(max(len(missing_text), len(missing_biblio)), include_basic=bool(missing_biblio), include_text_bundle=bool(missing_text), basic_count=len(missing_biblio), text_bundle_count=len(missing_text))
    reservation = ledger.reserve(project_id, "P012+D114", quote["estimated_external_cost"]) if quote["estimated_external_cost"] else None
    if reservation is not None and not reservation.ok:
        return {"ok": False, "error": reservation.reason, "budget_limit": reservation.budget_limit, "budget_remaining": reservation.budget_remaining, "cost_estimate": quote}
    client = _client()
    tasks: list[Any] = []
    if missing_text:
        tasks.append(client.patent_info(missing_text))
    if missing_biblio:
        tasks.append(_fetch_bibliographies(client, missing_biblio))
    responses = await asyncio.gather(*tasks)

    text_shell: dict[str, Any] | None = None
    biblio_by_pn: dict[str, Any] = {}
    for response in responses:
        if isinstance(response, tuple):
            biblio_by_pn = response[0]
        else:
            text_shell = response
    if text_shell is not None and not text_shell.get("status"):
        ledger.complete(reservation.reservation_id if reservation else None, "upstream_error")
        return {"ok": False, "diagnostics": {"error_code": text_shell.get("error_code"), "error_msg": text_shell.get("error_msg")}}

    text_by_pn = {pn: value for pn, value in cached_text.items() if value}
    for row in ((text_shell or {}).get("data") or {}).get("data") or []:
        record = normalize_d114_record(row)
        if record["pn"]:
            text_by_pn[record["pn"]] = record
            ledger.put_cache(f"D114:{record['pn']}", record, settings.cache_ttl_seconds)
    for pn, value in biblio_by_pn.items():
        ledger.put_cache(f"P012:{pn}", value, settings.cache_ttl_seconds)
    biblio_by_pn = {pn: value for pn, value in cached_biblio.items() if value} | biblio_by_pn

    records = [text_by_pn[pn] for pn in numbers if pn in text_by_pn]
    if include_basic and not include_text_bundle:
        records = [{"pn": pn, "bibliography": biblio_by_pn.get(pn, {}), "source_api": "P012"} for pn in numbers]
    else:
        for record in records:
            record["bibliography"] = biblio_by_pn.get(record["pn"], {})

    ledger.complete(reservation.reservation_id if reservation else None, "success")
    return {"ok": True, "records": records, "requested_patent_numbers": numbers, "cost_estimate": quote, "cache": {"text_hits": len(numbers) - len(missing_text) if include_text_bundle else 0, "basic_hits": len(numbers) - len(missing_biblio) if include_basic else 0}, "provenance": {"source_apis": [api for api, active in (("P012", include_basic), ("D114", include_text_bundle)) if active], "pricing_version": PRICING_VERSION}}


async def _fetch_bibliographies(client: ZhihuiyaClient, numbers: list[str]) -> tuple[dict[str, Any]]:
    semaphore = asyncio.Semaphore(5)

    async def one(number: str) -> tuple[str, Any]:
        async with semaphore:
            response = await client.bibliography(number)
        data = response.get("data") or []
        return number, data[0].get("bibliographic_data", {}) if response.get("status") and data else {}

    pairs = await asyncio.gather(*(one(number) for number in numbers))
    return ({number: value for number, value in pairs},)

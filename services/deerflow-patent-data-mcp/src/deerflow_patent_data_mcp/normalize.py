"""Pure response normalization functions; safe to test without API access."""

from __future__ import annotations

from typing import Any


def clean_patent_numbers(patent_numbers: list[str], *, maximum: int = 100) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in patent_numbers:
        number = value.strip() if isinstance(value, str) else ""
        if not number:
            continue
        key = number.upper()
        if key not in seen:
            seen.add(key)
            cleaned.append(number)
    if not cleaned:
        raise ValueError("at least one non-empty patent_number is required")
    if len(cleaned) > maximum:
        raise ValueError(f"at most {maximum} patent numbers are allowed per request")
    return cleaned


def normalize_search_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "patent_id": row.get("patent_id", ""),
        "pn": row.get("pn", ""),
        "title": row.get("title", ""),
        "current_assignee": row.get("current_assignee", ""),
        "original_assignee": row.get("original_assignee", ""),
        "inventor": row.get("inventor", ""),
        "authority": row.get("authority", ""),
        "application_date": row.get("apdt", ""),
        "publication_date": row.get("pbdt", ""),
    }


def normalize_d114_record(row: dict[str, Any]) -> dict[str, Any]:
    """Keep the documented D114 text fields and preserve provenance."""
    return {
        "pn": row.get("id", ""),
        "title": row.get("title", ""),
        "abstract": row.get("abs", ""),
        "claims": row.get("cl", ""),
        "description": row.get("desc", ""),
        "original_title": row.get("original_title", ""),
        "original_abstract": row.get("original_abs", ""),
        "original_claims": row.get("original_cl", ""),
        "original_description": row.get("original_desc", ""),
        "english_title": row.get("en_title", ""),
        "english_abstract": row.get("en_abs", ""),
        "english_claims": row.get("en_cl", ""),
        "english_description": row.get("en_desc", ""),
        "source_api": "D114",
    }

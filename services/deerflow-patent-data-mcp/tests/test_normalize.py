import pytest

from deerflow_patent_data_mcp.config import load_settings
from deerflow_patent_data_mcp.normalize import clean_patent_numbers, normalize_d114_record


def test_clean_patent_numbers_deduplicates_case_and_whitespace():
    assert clean_patent_numbers([" CN1A ", "cn1a", "US2B"]) == ["CN1A", "US2B"]


def test_clean_patent_numbers_rejects_over_100():
    with pytest.raises(ValueError, match="at most 100"):
        clean_patent_numbers([f"CN{i}A" for i in range(101)])


def test_normalize_d114_keeps_provenance_and_text_fields():
    record = normalize_d114_record({"id": "CN1A", "title": "标题", "abs": "摘要", "cl": "权利要求", "desc": "说明书", "original_desc": "原文"})
    assert record["pn"] == "CN1A"
    assert record["description"] == "说明书"
    assert record["original_description"] == "原文"
    assert record["source_api"] == "D114"


def test_empty_budget_environment_falls_back_to_empty_object(monkeypatch):
    monkeypatch.setenv("DATA_MCP_PROJECT_BUDGETS_JSON", "")
    assert load_settings().project_budgets_json == "{}"

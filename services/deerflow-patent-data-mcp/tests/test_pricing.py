from deerflow_patent_data_mcp.pricing import estimate_patent_cost


def test_d114_cost_for_one_full_batch():
    quote = estimate_patent_cost(100, include_text_bundle=True)
    assert quote["estimated_external_cost"] == 0.20
    assert quote["cost_basis"][0]["api"] == "D114"
    assert quote["requires_confirmation"] is False


def test_d114_cost_splits_more_than_one_batch():
    quote = estimate_patent_cost(101, include_basic=True, include_text_bundle=True)
    assert quote["estimated_external_cost"] == 2.42
    assert quote["cost_basis"][0]["api"] == "P012"
    assert quote["cost_basis"][1]["quantity"] == 2
    assert quote["requires_confirmation"] is True


def test_cost_uses_separate_cache_miss_counts_per_api():
    quote = estimate_patent_cost(100, include_basic=True, include_text_bundle=True, basic_count=20, text_bundle_count=100)
    assert quote["estimated_external_cost"] == 0.60
    assert quote["cost_basis"][0]["quantity"] == 20

from deerflow_patent_data_mcp.ledger import BudgetLedger


def test_ledger_reserves_and_rejects_over_budget(tmp_path):
    ledger = BudgetLedger(str(tmp_path / "ledger.sqlite3"), '{"demo": 0.20}')
    first = ledger.reserve("demo", "P002", 0.20)
    assert first.ok is True
    ledger.complete(first.reservation_id, "success")
    assert ledger.reserve("demo", "D114", 0.01).reason == "budget_exceeded"


def test_ledger_fails_closed_without_configured_project(tmp_path):
    ledger = BudgetLedger(str(tmp_path / "ledger.sqlite3"), '{}')
    assert ledger.reserve("missing", "P002", 0.20).reason == "budget_unconfigured"


def test_cache_round_trip_and_expiry(tmp_path):
    ledger = BudgetLedger(str(tmp_path / "ledger.sqlite3"), '{}')
    ledger.put_cache("D114:CN1A", {"pn": "CN1A"}, ttl_seconds=60)
    assert ledger.get_cache("D114:CN1A") == {"pn": "CN1A"}
    ledger.put_cache("D114:expired", {"pn": "CN2A"}, ttl_seconds=0)
    assert ledger.get_cache("D114:expired") is None

"""Tests for the fastembed-based memory retrieval adapter.

The semantic tests run against a real (cached) fastembed model when the
``fastembed`` package is importable; otherwise they self-skip so environments
without the optional dependency still exercise the bookkeeping logic via the
fake-embedding path (which needs no model at all).
"""

from pathlib import Path

import pytest

from deerflow.memory_retrieval.fastembed_retrieval import (
    DEFAULT_MODEL_ID,
    FastembedRetrieval,
    create_retrieval,
)

try:
    import fastembed  # noqa: F401

    HAS_FASTEMBED = True
except ImportError:
    HAS_FASTEMBED = False


def _scope(user: str = "alice", agent: str | None = "agent-a") -> dict:
    return {"userId": user, "agentName": agent}


def _make_fake_store():
    from deerflow.memory_retrieval.fastembed_retrieval import FastembedVectorStore

    class FakeEmbedder:
        def embed(self, texts: list[str]) -> list[list[float]]:
            # deterministic mapping: char counts mod axis index
            return [[float((t.count(c) % 5) + 1) for c in "abc"] for t in texts]

    store = FastembedVectorStore.__new__(FastembedVectorStore)
    store._embedder = FakeEmbedder()
    store._vectors: dict[str, list[float]] = {}
    store._meta: dict[str, dict] = {}
    return store


class TestPureVectorStore:
    """FastembedVectorStore logic tested with fake embeddings (no model)."""

    def make_store(self):
        return _make_fake_store()

    def test_upsert_then_search_returns_fact(self):
        store = self.make_store()
        store.upsert("f1", [1.0, 0.0, 0.0], scope=_scope(), text="用户负责专利检索")
        results = store.search("专利", scopes=[_scope()], top_k=5)
        assert len(results) == 1
        assert results[0]["id"] == "f1"
        assert results[0]["score"] > 0

    def test_scope_isolation(self):
        store = self.make_store()
        store.upsert("f1", [1.0, 0.0, 0.0], scope=_scope(user="alice"), text="alice fact")
        store.upsert("f2", [1.0, 0.0, 0.0], scope=_scope(user="bob"), text="bob fact")
        assert [r["id"] for r in store.search("x", scopes=[_scope(user="alice")], top_k=5)] == ["f1"]
        assert [r["id"] for r in store.search("x", scopes=[_scope(user="bob")], top_k=5)] == ["f2"]

    def test_remove_deletes_entry(self):
        store = self.make_store()
        store.upsert("f1", [1.0, 0.0, 0.0], scope=_scope(), text="t")
        store.remove("f1", scope=_scope())
        assert store.search("x", scopes=[_scope()], top_k=5) == []

    def test_search_top_k_limits(self):
        store = self.make_store()
        for i in range(5):
            store.upsert(f"f{i}", [1.0, 0.0, 0.0], scope=_scope(), text=f"t{i}")
        assert len(store.search("x", scopes=[_scope()], top_k=3)) == 3

    def test_none_scope_wildcard_matches_all_users(self):
        store = self.make_store()
        store.upsert("f1", [1.0, 0.0, 0.0], scope=_scope(user="alice"), text="a")
        store.upsert("f2", [1.0, 0.0, 0.0], scope=_scope(user="bob"), text="b")
        got = {r["id"] for r in store.search("x", scopes=[{"userId": None, "agentName": None}], top_k=10)}
        assert got == {"f1", "f2"}


class TestRetrievalPortContract:
    def test_fact_dict_payload_roundtrip(self):
        retrieval = FastembedRetrieval(store=_make_fake_store())
        fact = {"id": "f1", "content": "用户负责专利检索", "confidence": 0.9}
        retrieval.upsert(fact, scope=_scope(), path="facts/f1.md")
        results = retrieval.search("专利检索", scopes=[_scope()], top_k=5, mode="hybrid", filters=None)
        assert results[0]["fact"]["content"] == "用户负责专利检索"
        retrieval.remove("f1", scope=_scope())
        assert retrieval.search("专利检索", scopes=[_scope()], top_k=5, mode="hybrid", filters=None) == []

    def test_fact_without_id_is_skipped(self):
        retrieval = FastembedRetrieval(store=_make_fake_store())
        retrieval.upsert({"content": "no id"}, scope=_scope(), path="")
        assert retrieval.search("x", scopes=[_scope()], top_k=5, mode="hybrid", filters=None) == []

    def test_factory_returns_singleton(self, monkeypatch):
        from deerflow.memory_retrieval import fastembed_retrieval as mod

        calls = []

        def fake_build(model_id, cache_dir):
            calls.append((model_id, cache_dir))
            return FastembedRetrieval(store=_make_fake_store())

        monkeypatch.setattr(mod, "_LAZY_SINGLETON", None)
        monkeypatch.setattr(mod.FastembedRetrieval, "_load_embedder", staticmethod(fake_build))
        cfg = type("C", (), {"retrieval_model": DEFAULT_MODEL_ID, "retrieval_cache_dir": ""})()
        first = create_retrieval(cfg)
        second = create_retrieval(cfg)
        assert first is second
        assert calls == [(DEFAULT_MODEL_ID, "")]

    def test_factory_missing_package_raises_actionable(self, monkeypatch):
        import builtins

        from deerflow.memory_retrieval import fastembed_retrieval as mod

        monkeypatch.setattr(mod, "_LAZY_SINGLETON", None)
        saved_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "fastembed":
                raise ModuleNotFoundError("No module named 'fastembed'")
            return saved_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        with pytest.raises(ValueError) as excinfo:
            create_retrieval(type("C", (), {"retrieval_model": DEFAULT_MODEL_ID, "retrieval_cache_dir": ""})())
        assert "fastembed" in str(excinfo.value)


@pytest.mark.skipif(not HAS_FASTEMBED, reason="fastembed not installed")
class TestSemanticMatching:
    def test_bge_zh_distinguishes_related_from_unrelated(self, tmp_path: Path):
        retrieval = FastembedRetrieval(cache_dir=str(tmp_path))
        retrieval.upsert({"id": "f1", "content": "用户负责专利检索业务"}, scope=_scope(), path="")
        retrieval.upsert({"id": "f2", "content": "用户喜欢吃辣"}, scope=_scope(), path="")
        results = retrieval.search("帮我构建检索式查专利", scopes=[_scope()], top_k=2, mode="hybrid", filters=None)
        assert len(results) == 2
        assert results[0]["fact"]["id"] == "f1"
        # related score clearly above unrelated score
        assert results[0]["score"] > results[1]["score"] + 0.1


def test_search_results_are_json_serializable():
    """Scores must be plain floats — numpy scalars break json.dumps in API responses."""
    import json

    class NumpyishEmbedder:
        """Mimics fastembed: real numpy vectors (np.float32 components)."""

        def embed(self, texts: list[str]):
            import numpy as np

            return [np.array([1.0, 0.0, 0.0], dtype=np.float32) for _ in texts]

    from deerflow.memory_retrieval.fastembed_retrieval import FastembedVectorStore

    store = FastembedVectorStore(NumpyishEmbedder())
    store.upsert("f1", [1.0, 0.0, 0.0], scope=_scope(), text="t")
    hits = store.search("x", scopes=[_scope()], top_k=1)
    assert isinstance(hits[0]["score"], float)
    json.dumps(hits)  # must not raise


class TestRestartBackfill:
    """Restart recovery: empty index + durable facts => search still finds them."""

    def test_search_triggers_backfill_for_empty_scope(self):
        retrieval = FastembedRetrieval(store=_make_fake_store())
        durable = [{"id": "f1", "content": "用户负责专利检索业务"}]
        calls = []

        def backfill(scope):
            calls.append(dict(scope))
            return list(durable)

        retrieval.set_backfill(backfill)
        results = retrieval.search("专利检索", scopes=[_scope()], top_k=5, mode="hybrid", filters=None)
        assert calls == [{"userId": "alice", "agentName": "agent-a"}]
        assert results[0]["fact"]["content"] == "用户负责专利检索业务"

    def test_backfill_runs_once_per_scope(self):
        retrieval = FastembedRetrieval(store=_make_fake_store())
        calls = []

        retrieval.set_backfill(lambda scope: (calls.append(1), [{"id": "f1", "content": "x"}])[1])
        retrieval.search("x", scopes=[_scope()], top_k=5, mode="hybrid", filters=None)
        retrieval.search("x", scopes=[_scope()], top_k=5, mode="hybrid", filters=None)
        assert len(calls) == 1

    def test_backfill_skipped_when_scope_already_indexed(self):
        retrieval = FastembedRetrieval(store=_make_fake_store())
        retrieval.upsert({"id": "f1", "content": "fresh"}, scope=_scope(), path="")
        calls = []
        retrieval.set_backfill(lambda scope: (calls.append(1), [])[1])
        retrieval.search("x", scopes=[_scope()], top_k=5, mode="hybrid", filters=None)
        assert calls == []

    def test_backfill_failure_does_not_break_search(self):
        retrieval = FastembedRetrieval(store=_make_fake_store())

        def boom(scope):
            raise RuntimeError("durable store unavailable")

        retrieval.set_backfill(boom)
        results = retrieval.search("x", scopes=[_scope()], top_k=5, mode="hybrid", filters=None)
        assert results == []

    def test_backfill_marks_scope_even_when_durable_empty(self):
        retrieval = FastembedRetrieval(store=_make_fake_store())
        calls = []
        retrieval.set_backfill(lambda scope: (calls.append(1), [])[1])
        retrieval.search("x", scopes=[_scope()], top_k=5, mode="hybrid", filters=None)
        retrieval.search("x", scopes=[_scope()], top_k=5, mode="hybrid", filters=None)
        assert len(calls) == 1  # second search does not retry the empty durable store


def test_create_storage_registers_backfill_for_restart_recovery(tmp_path):
    """E2E with real FileMemoryStorage + fake embedder: restart-empty index recovers from durable facts."""
    from deerflow.agents.memory.backends.deermem.deermem.config import DeerMemConfig
    from deerflow.agents.memory.backends.deermem.deermem.core.storage import create_storage

    cfg = DeerMemConfig(storage_path=str(tmp_path))
    # 直接走 create_storage 的注册分支:传入已构造好的 retrieval(等价 factory 产物)
    retrieval = FastembedRetrieval(store=_make_fake_store())
    storage = create_storage(cfg, retrieval=retrieval)
    assert retrieval._backfill is not None, "create_storage must register the backfill callback"

    # 写入两条事实(durable + 索引),然后模拟重启:新建空索引 retrieval + 新 storage
    doc = {
        "version": "1.0",
        "revision": 0,
        "lastUpdated": "2026-08-18T00:00:00Z",
        "user": {"workContext": {"summary": "", "updatedAt": ""}},
        "history": {"recentMonths": {"summary": "", "updatedAt": ""}},
        "facts": [{"id": "fact_R1", "content": "用户负责专利检索业务", "confidence": 0.9}],
    }
    storage.save(doc, "agent-a", user_id="alice")

    fresh_retrieval = FastembedRetrieval(store=_make_fake_store())
    fresh_storage = create_storage(cfg, retrieval=fresh_retrieval)
    assert len(fresh_retrieval._store) == 0  # restart: empty index
    hits = fresh_storage.search_facts("专利", scopes=[{"userId": "alice", "agentName": "agent-a"}], top_k=3)
    assert len(hits) == 1
    assert hits[0]["fact"]["content"] == "用户负责专利检索业务"
    assert len(fresh_retrieval._store) == 1  # backfilled from durable store

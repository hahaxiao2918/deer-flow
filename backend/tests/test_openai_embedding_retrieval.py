"""Tests for the OpenAI-compatible HTTP embedding retrieval adapter.

The adapter reuses :class:`FastembedRetrieval` (vector store, scope matching,
lazy backfill) with an HTTP embedder that calls an OpenAI-compatible
``POST {base_url}/embeddings`` endpoint — e.g. the Shanghai Electric private
``Qwen3-VL-Embedding`` service (1024-dim). Vectors are process-local and
rebuilt from the durable Markdown fact store after a restart, so switching
embedding models needs no vector migration.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from deerflow.memory_retrieval import openai_embedding_retrieval as mod


def _config(**overrides: Any) -> SimpleNamespace:
    """Build a DeermemConfig stand-in with the retrieval fields."""
    base = {
        "retrieval_model": "Qwen3-VL-Embedding",
        "retrieval_base_url": "https://ai.example.com/v1",
        "retrieval_api_key": "sk-test",
        "retrieval_dimensions": 1024,
        "retrieval_cache_dir": "",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        if "error" in self._payload:
            raise RuntimeError(self._payload["error"])

    def json(self) -> dict:
        return self._payload


class _RecordingClient:
    """httpx.Client stand-in: records requests, replies with fixed vectors.

    Each POST consumes ``len(input)`` vectors from the front of *vectors* and
    returns them deliberately shuffled — the adapter must sort by "index".
    """

    def __init__(self, *, vectors: list[list[float]] | None = None, error: Exception | None = None):
        self.requests: list[dict] = []
        self._remaining = list(vectors or [])
        self._error = error

    def post(self, url: str, *, json: dict, headers: dict, timeout: float):  # noqa: A002
        self.requests.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        if self._error is not None:
            raise self._error
        count = len(json.get("input") or [])
        batch, self._remaining = self._remaining[:count], self._remaining[count:]
        if batch:
            data = [{"index": i, "embedding": vec} for i, vec in reversed(list(enumerate(batch)))]
            return _FakeResponse({"data": data, "model": json.get("model"), "usage": {}})
        return _FakeResponse({"error": "boom"})


# ---------------------------------------------------------------------------
# Config surface: DeermemConfig carries the new adapter-only fields.
# ---------------------------------------------------------------------------


def test_deermem_config_has_openai_embedding_fields():
    from deerflow.agents.memory.backends.deermem.deermem.config import DeerMemConfig

    cfg = DeerMemConfig(retrieval_base_url="https://x/v1", retrieval_api_key="sk-1", retrieval_dimensions=1024)
    assert cfg.retrieval_base_url == "https://x/v1"
    assert cfg.retrieval_api_key == "sk-1"
    assert cfg.retrieval_dimensions == 1024
    # Defaults keep existing deployments (fastembed adapter) unchanged.
    default = DeerMemConfig()
    assert default.retrieval_base_url == ""
    assert default.retrieval_api_key == ""
    assert default.retrieval_dimensions == 0


# ---------------------------------------------------------------------------
# Embedder: request shape, ordering, dimensions handling.
# ---------------------------------------------------------------------------


def test_embedder_sends_model_dimensions_and_bearer():
    client = _RecordingClient(vectors=[[0.1, 0.2], [0.3, 0.4]])
    embedder = mod.OpenAIEmbeddingFunction(base_url="https://ai.example.com/v1", api_key="sk-test", model="Qwen3-VL-Embedding", dimensions=1024, client=client)
    out = embedder.embed(["a", "b"])
    assert out == [[0.1, 0.2], [0.3, 0.4]]  # sorted back by index
    req = client.requests[0]
    assert req["url"] == "https://ai.example.com/v1/embeddings"
    assert req["headers"]["Authorization"] == "Bearer sk-test"
    assert req["json"] == {"model": "Qwen3-VL-Embedding", "input": ["a", "b"], "dimensions": 1024}


def test_embedder_omits_dimensions_when_zero():
    client = _RecordingClient(vectors=[[0.5]])
    embedder = mod.OpenAIEmbeddingFunction(base_url="https://ai.example.com/v1", api_key="sk-test", model="m", dimensions=0, client=client)
    embedder.embed(["q"])
    assert client.requests[0]["json"] == {"model": "m", "input": ["q"]}


def test_embedder_raises_clear_error_on_http_failure():
    client = _RecordingClient()
    embedder = mod.OpenAIEmbeddingFunction(base_url="https://ai.example.com/v1", api_key="sk", model="m", client=client)
    with pytest.raises(RuntimeError, match="embedding endpoint"):
        embedder.embed(["q"])


# ---------------------------------------------------------------------------
# Factory: config plumbing, singleton, hard errors on missing wiring.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_singleton():
    mod._LAZY_SINGLETON = None
    yield
    mod._LAZY_SINGLETON = None


def test_factory_builds_retrieval_reusing_fastembed_store():
    client = _RecordingClient(vectors=[[1.0, 0.0], [0.0, 1.0], [0.9, 0.1]])
    retrieval = mod.create_retrieval(_config(), client=client)
    scope = {"agent_name": "lead"}
    retrieval.upsert({"id": "f1", "content": "用户偏好中文回复"}, scope=scope, path="")
    retrieval.upsert({"id": "f2", "content": "部署只走 gitea"}, scope=scope, path="")
    hits = retrieval.search("语言偏好", scopes=[scope], top_k=2)
    assert [h["fact"]["id"] for h in hits] == ["f1", "f2"]  # f1 closer to [1,0]
    assert hits[0]["matchType"] == "semantic"


def test_factory_requires_base_url_and_api_key():
    with pytest.raises(ValueError, match="retrieval_base_url"):
        mod.create_retrieval(_config(retrieval_base_url=""))
    with pytest.raises(ValueError, match="retrieval_api_key"):
        mod.create_retrieval(_config(retrieval_api_key=""))


def test_factory_is_singleton():
    client = _RecordingClient(vectors=[[0.1]])
    first = mod.create_retrieval(_config(), client=client)
    second = mod.create_retrieval(_config(retrieval_model="other"), client=client)
    assert first is second

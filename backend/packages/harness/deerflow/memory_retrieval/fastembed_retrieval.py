"""Fastembed-based semantic retrieval adapter for DeerMem memory facts.

Implements the DeerMem ``RetrievalPort`` protocol (``upsert`` / ``remove`` /
``search``) on top of ``fastembed`` ONNX embeddings — no external embedding
API, all inference is in-process. Chinese-optimized default model
``BAAI/bge-small-zh-v1.5`` (512-dim, ~30 MB quantized).

Wiring (config.yaml)::

    memory:
      backend_config:
        retrieval_adapter: deerflow.memory_retrieval.fastembed_retrieval:create_retrieval

The factory receives the parsed ``DeerMemConfig``, so ``retrieval_model`` and
``retrieval_cache_dir`` from ``memory.backend_config`` flow through unchanged.
Model weights are cached under the retrieval cache dir (default
``~/.cache/deerflow-memory-retrieval``); set ``HF_ENDPOINT=https://hf-mirror.com``
in the gateway environment for intranet-only hosts to download from the mirror.

The embedding model loads lazily on first use and is shared process-wide (one
instance; embedding is CPU-light). Search vectors live in memory keyed by
``(fact_id)`` with scope metadata, so a gateway restart re-indexes lazily from
the Markdown fact store via DeerMem's ``rebuild_index`` / migration notify
hooks. This is intentionally a simple linear scan: memory facts are bounded
(``memory.max_facts``, default 100 per agent bucket), so brute-force cosine
over a few hundred vectors is sub-millisecond and avoids any vector-index
dependency.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)

DEFAULT_MODEL_ID = "BAAI/bge-small-zh-v1.5"
DEFAULT_CACHE_DIR = "~/.cache/deerflow-memory-retrieval"


class EmbeddingFunction(Protocol):
    """Minimal embedder interface (fastembed TextEmbedding satisfies it)."""

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity, always returning a plain float.

    fastembed yields numpy scalars; without the ``float()`` coercion the score
    leaks into API responses / run records as ``np.float32``, which
    ``json.dumps`` cannot serialize.
    """
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return float(dot / (na**0.5 * nb**0.5))


def _scopes_match(entry_scope: dict[str, str | None], query_scope: dict[str, str | None]) -> bool:
    """Match when every non-None query field equals the entry's field."""
    for key, value in query_scope.items():
        if value is not None and entry_scope.get(key) != value:
            return False
    return True


class FastembedVectorStore:
    """In-memory vector store with scope-tagged entries (linear cosine scan)."""

    def __init__(self, embedder: EmbeddingFunction):
        self._embedder = embedder
        self._vectors: dict[str, list[float]] = {}
        self._meta: dict[str, dict[str, Any]] = {}

    def upsert(self, fact_id: str, vector: list[float], *, scope: dict[str, str | None], text: str) -> None:
        self._vectors[fact_id] = vector
        self._meta[fact_id] = {"scope": dict(scope), "text": text}

    def remove(self, fact_id: str, *, scope: dict[str, str | None] | None = None) -> None:
        # fact_id is globally unique (ULID); scope accepted for API symmetry
        # and ignored on purpose.
        self._vectors.pop(fact_id, None)
        self._meta.pop(fact_id, None)

    def search(self, query: str, *, scopes: list[dict[str, str | None]], top_k: int) -> list[dict[str, Any]]:
        if not query.strip() or top_k <= 0 or not self._vectors:
            return []
        query_vec = next(iter(self._embedder.embed([query])))
        wanted = [
            (fact_id, _cosine(query_vec, vec))
            for fact_id, vec in self._vectors.items()
            # entry matches when ANY query scope matches (OR across scopes)
            if any(_scopes_match(self._meta[fact_id]["scope"], s) for s in scopes)
        ]
        wanted.sort(key=lambda item: item[1], reverse=True)
        return [{"id": fact_id, "score": score, "scope": self._meta[fact_id]["scope"], "text": self._meta[fact_id]["text"]} for fact_id, score in wanted[:top_k]]

    def __len__(self) -> int:
        return len(self._vectors)


class FastembedRetrieval:
    """``RetrievalPort`` implementation over :class:`FastembedVectorStore`."""

    def __init__(
        self,
        store: FastembedVectorStore | None = None,
        model_id: str = DEFAULT_MODEL_ID,
        cache_dir: str = "",
    ):
        if store is not None:
            self._store = store
            self._owned_embedder = False
        else:
            self._embedder = self._load_embedder(model_id=model_id, cache_dir=cache_dir)
            self._store = FastembedVectorStore(self._embedder)
            self._owned_embedder = True

    @staticmethod
    def _load_embedder(model_id: str, cache_dir: str) -> EmbeddingFunction:
        try:
            from fastembed import TextEmbedding
        except ImportError as exc:
            raise ValueError(
                "memory retrieval_adapter requires the optional 'fastembed' package. Install it in the gateway image (uv add fastembed) or clear memory.backend_config.retrieval_adapter to fall back to substring search."
            ) from exc
        resolved_cache = str(Path(cache_dir or DEFAULT_CACHE_DIR).expanduser())
        Path(resolved_cache).mkdir(parents=True, exist_ok=True)
        return TextEmbedding(model_name=model_id, cache_dir=resolved_cache)

    # ── RetrievalPort ────────────────────────────────────────────────────

    def upsert(self, fact: dict[str, Any], *, scope: dict[str, str | None], path: str) -> None:
        fact_id = fact.get("id")
        content = fact.get("content")
        if not isinstance(fact_id, str) or not fact_id or not isinstance(content, str) or not content.strip():
            return
        vector = next(iter(self._store._embedder.embed([content])))
        self._store.upsert(fact_id, vector, scope=scope, text=content)

    def remove(self, fact_id: str, *, scope: dict[str, str | None]) -> None:
        self._store.remove(fact_id)

    def search(
        self,
        query: str,
        *,
        scopes: list[dict[str, str | None]],
        top_k: int = 10,
        mode: str = "hybrid",
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        hits = self._store.search(query, scopes=scopes, top_k=top_k)
        results: list[dict[str, Any]] = []
        for hit in hits:
            results.append({"fact": {"id": hit["id"], "content": hit["text"]}, "score": hit["score"], "matchType": "semantic"})
            if filters:
                results[-1]["filters"] = filters
        return results


# ── Factory (dotted path target) ────────────────────────────────────────────

_LAZY_SINGLETON: FastembedRetrieval | None = None
_SINGLETON_LOCK = threading.Lock()


def create_retrieval(config: Any) -> FastembedRetrieval:
    """Dotted-factory entry: ``deerflow.memory_retrieval.fastembed_retrieval:create_retrieval``.

    Receives the parsed ``DeerMemConfig``; reads ``retrieval_model`` and
    ``retrieval_cache_dir`` from it. The embedding model is process-expensive
    to construct, so the adapter is a singleton per process (config changes
    need a gateway restart — memory is not a hot-reload field for the adapter).
    """
    global _LAZY_SINGLETON
    if _LAZY_SINGLETON is not None:
        return _LAZY_SINGLETON
    with _SINGLETON_LOCK:
        if _LAZY_SINGLETON is None:
            model_id = getattr(config, "retrieval_model", DEFAULT_MODEL_ID) or DEFAULT_MODEL_ID
            cache_dir = getattr(config, "retrieval_cache_dir", "") or ""
            logger.info("Loading memory retrieval adapter (model=%s, cache=%s)", model_id, cache_dir or DEFAULT_CACHE_DIR)
            _LAZY_SINGLETON = FastembedRetrieval(model_id=model_id, cache_dir=cache_dir)
        return _LAZY_SINGLETON

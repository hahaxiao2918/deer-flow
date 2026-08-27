"""OpenAI-compatible HTTP embedding retrieval adapter for DeerMem memory facts.

Implements the DeerMem ``RetrievalPort`` on top of an OpenAI-compatible
``POST {base_url}/embeddings`` endpoint instead of local ONNX inference —
built for privately deployed embedding services (e.g. the Shanghai Electric
``Qwen3-VL-Embedding`` model behind ``https://ai.nebula-starlink.shanghai-electric.com/v1``,
1024-dim). Everything except the embedder — in-memory vector store, scope
matching, lazy backfill from the durable Markdown fact store — is reused from
:class:`deerflow.memory_retrieval.fastembed_retrieval.FastembedRetrieval`, so
the two adapters stay behaviourally identical and no vector migration is
needed when switching models (vectors are process-local and rebuilt lazily
after a restart).

Wiring (config.yaml)::

    memory:
      backend_config:
        retrieval_adapter: deerflow.memory_retrieval.openai_embedding_retrieval:create_retrieval
        retrieval_model: Qwen3-VL-Embedding
        retrieval_base_url: https://ai.example.com/v1
        retrieval_api_key: $MY_EMBEDDING_API_KEY
        retrieval_dimensions: 1024

``$VAR`` values are resolved centrally by ``AppConfig.resolve_env_variables``.
``retrieval_dimensions`` is sent as the OpenAI ``dimensions`` request field
only when > 0 (the endpoint's default dimensionality applies otherwise).

Backfill note: after a gateway restart the first search in a scope re-embeds
that scope's facts one request at a time (bounded by ``memory.max_facts``,
default 100), then never again — a few hundred milliseconds of LAN latency.
"""

from __future__ import annotations

import logging
import threading
from operator import itemgetter
from typing import Any

from deerflow.memory_retrieval.fastembed_retrieval import FastembedRetrieval, FastembedVectorStore

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 15.0


class OpenAIEmbeddingFunction:
    """``EmbeddingFunction`` protocol over an OpenAI-compatible embeddings API."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        dimensions: int = 0,
        timeout: float = _DEFAULT_TIMEOUT_SECONDS,
        client: Any = None,
    ) -> None:
        base_url = (base_url or "").rstrip("/")
        if not base_url:
            raise ValueError("retrieval_base_url is required for the openai_embedding_retrieval adapter")
        if not api_key:
            raise ValueError("retrieval_api_key is required for the openai_embedding_retrieval adapter")
        self._endpoint = f"{base_url}/embeddings"
        self._api_key = api_key
        self._model = model
        self._dimensions = int(dimensions or 0)
        self._timeout = timeout
        if client is not None:
            self._client = client
        else:
            import httpx

            self._client = httpx.Client(timeout=timeout)

    def embed(self, texts: list[str]) -> list[list[float]]:
        payload: dict[str, Any] = {"model": self._model, "input": texts}
        if self._dimensions > 0:
            payload["dimensions"] = self._dimensions
        try:
            response = self._client.post(
                self._endpoint,
                json=payload,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=self._timeout,
            )
            response.raise_for_status()
            body = response.json()
        except Exception as exc:
            raise RuntimeError(f"memory embedding endpoint {self._endpoint} failed: {exc}") from exc
        data = body.get("data")
        if not isinstance(data, list) or len(data) != len(texts):
            raise RuntimeError(f"memory embedding endpoint returned {len(data) if isinstance(data, list) else 'malformed'} results for {len(texts)} inputs")
        # The API may return embeddings out of order; "index" restores it.
        return [item["embedding"] for item in sorted(data, key=itemgetter("index"))]


# ── Factory (dotted path target) ────────────────────────────────────────────

_LAZY_SINGLETON: FastembedRetrieval | None = None
_SINGLETON_LOCK = threading.Lock()


def create_retrieval(config: Any, *, client: Any = None) -> FastembedRetrieval:
    """Dotted-factory entry: ``deerflow.memory_retrieval.openai_embedding_retrieval:create_retrieval``.

    Receives the parsed ``DeerMemConfig``; reads ``retrieval_model`` (API model
    name), ``retrieval_base_url``, ``retrieval_api_key`` and
    ``retrieval_dimensions`` from it. Like the fastembed adapter this is a
    process singleton — config changes need a gateway restart.
    """
    global _LAZY_SINGLETON
    if _LAZY_SINGLETON is not None:
        return _LAZY_SINGLETON
    with _SINGLETON_LOCK:
        if _LAZY_SINGLETON is None:
            model = getattr(config, "retrieval_model", "") or ""
            base_url = getattr(config, "retrieval_base_url", "") or ""
            api_key = getattr(config, "retrieval_api_key", "") or ""
            dimensions = int(getattr(config, "retrieval_dimensions", 0) or 0)
            embedder = OpenAIEmbeddingFunction(
                base_url=base_url,
                api_key=api_key,
                model=model,
                dimensions=dimensions,
                client=client,
            )
            logger.info("Loading memory retrieval adapter (openai-http, model=%s, base_url=%s, dims=%s)", model, base_url, dimensions or "default")
            _LAZY_SINGLETON = FastembedRetrieval(store=FastembedVectorStore(embedder))
        return _LAZY_SINGLETON

"""Gracefully cap long runs before LangGraph's hard recursion limit kills them.

LangGraph raises ``GraphRecursionError`` when a run exceeds ``recursion_limit``
super-steps. For tool-heavy workflows (e.g. patent search-query composition
with many calibration probes) the error routinely fires when the run is one or
two steps from finishing — deliverables written, final answer already in
state — yet the run surfaces as *failed*. Observed 2026-07-26 in live smoke
runs: a completed conversation killed at step ~248/250.

This middleware converts that hard death into a natural finish, following the
same pattern as ``LoopDetectionMiddleware`` / ``TokenBudgetMiddleware``:

1. Track a per-run estimate of consumed super-steps. Measured on LangGraph
   (``stream_mode="updates"``), each model cycle costs: ``model`` node (1) +
   one node per middleware implementing ``before_model``/``after_model`` +
   ``tools`` node (1, when the response calls tools — parallel calls share one
   node). The builders (lead-agent / factory) count the chain's hook nodes and
   inject them via ``set_extra_hook_nodes``; the guard's own ``after_model``
   node is always accounted (baseline 2 = model + self).
2. At ``warn_ratio * limit``: queue a wrap-up reminder, injected at the next
   model call via ``wrap_model_call`` — never between ``AIMessage.tool_calls``
   and their ``ToolMessage`` responses (pairing validators reject that).
3. At ``limit - hard_margin``: strip ``tool_calls`` from the response so the
   agent loop terminates naturally with a final answer, and record
   ``stop_reason=recursion_capped`` for the caller to surface. The margin must
   cover the post-strip hook nodes before END (~2-5 steps) plus occasional
   summarization passes.

The guard reads the run's effective limit from
``runtime.context["recursion_limit"]`` (plumbed by the Gateway run-config
builder and the embedded client). When the key is absent or invalid the guard
is **inactive** — un-plumbed run paths keep the previous behaviour.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime

from deerflow.agents.middlewares._bounded_dict import BoundedDict
from deerflow.agents.middlewares.loop_detection_middleware import LoopDetectionMiddleware

if TYPE_CHECKING:
    from deerflow.config.recursion_guard_config import RecursionGuardConfig

logger = logging.getLogger(__name__)

_DEFAULT_WARN_RATIO = 0.75
_DEFAULT_HARD_MARGIN = 10

_WARN_MSG = (
    "<system_reminder>\n"
    "Step budget warning: this run is approaching its step limit. Stop exploring now — "
    "write deliverables once with fixed filenames, present them once, then give your final "
    "text answer. Do not start new probes, re-read references, or rewrite files.\n"
    "</system_reminder>"
)

_HARD_STOP_MSG = "Step budget exhausted: the run was closed early by the recursion guard. Deliverables produced so far are preserved."

# Reuse loop-detection's battle-tested text-append / tool-call-strip helpers:
# identical semantics (content may be str or list blocks; tool-call metadata
# must be cleared so the forced message serializes as plain assistant text).
_append_text = LoopDetectionMiddleware._append_text
_build_hard_stop_update = LoopDetectionMiddleware._build_hard_stop_update


class RecursionGuardMiddleware(AgentMiddleware[AgentState]):
    """Force a graceful finish before LangGraph's recursion limit raises."""

    def __init__(self, *, warn_ratio: float = _DEFAULT_WARN_RATIO, hard_margin: int = _DEFAULT_HARD_MARGIN) -> None:
        super().__init__()
        if not 0.0 < warn_ratio < 1.0:
            raise ValueError(f"warn_ratio must be in (0, 1), got {warn_ratio!r}")
        if hard_margin < 1:
            raise ValueError(f"hard_margin must be >= 1, got {hard_margin!r}")
        self._warn_ratio = warn_ratio
        self._hard_margin = hard_margin
        # Hook nodes contributed by OTHER middleware in the chain (set by the
        # agent builders once the full chain is assembled). Baseline cycle
        # cost already accounts for this guard's own after_model node.
        self._extra_hook_nodes = 0
        self._lock = threading.Lock()
        # Per-run estimated step cost, keyed by (thread_id, run_id).
        self._costs: BoundedDict[tuple[str, str], int] = BoundedDict(1000)
        self._warned: BoundedDict[tuple[str, str], bool] = BoundedDict(1000)
        self._pending_warnings: BoundedDict[tuple[str, str], bool] = BoundedDict(1000)
        self._stop_reason: BoundedDict[str, str] = BoundedDict(1000)

    @classmethod
    def from_config(cls, config: RecursionGuardConfig) -> RecursionGuardMiddleware:
        return cls(warn_ratio=config.warn_ratio, hard_margin=config.hard_margin)

    def set_extra_hook_nodes(self, count: int) -> None:
        """Record how many before/after-model hook nodes the rest of the chain
        adds per model cycle (counted by the agent builders post-assembly)."""
        self._extra_hook_nodes = max(0, int(count))

    @staticmethod
    def count_model_hook_nodes(chain: list, *, exclude: AgentMiddleware | None = None) -> int:
        """Count middleware in *chain* that add a graph node per model cycle.

        A middleware adds a node when it overrides ``before_model`` or
        ``after_model`` (sync or async variants). ``wrap_model_call`` /
        ``wrap_tool_call`` compose inside the model/tools nodes and add nothing.
        """
        from langchain.agents.middleware import AgentMiddleware as _Base

        count = 0
        for mw in chain:
            if exclude is not None and mw is exclude:
                continue
            t = type(mw)
            if t.before_model is not _Base.before_model or t.abefore_model is not _Base.abefore_model:
                count += 1
            if t.after_model is not _Base.after_model or t.aafter_model is not _Base.aafter_model:
                count += 1
        return count

    # ------------------------------------------------------------------
    # Run identity / limit resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _key(runtime: Runtime) -> tuple[str, str]:
        context = getattr(runtime, "context", None)
        if isinstance(context, dict):
            thread_id = str(context.get("thread_id") or "unknown-thread")
            run_id = str(context.get("run_id") or context.get("run_attempt_id") or id(runtime))
            return thread_id, run_id
        return "unknown-thread", str(id(runtime))

    def _get_run_id(self, runtime: Runtime) -> str:
        return self._key(runtime)[1]

    @staticmethod
    def _read_limit(runtime: Runtime) -> int | None:
        """Read the run's effective recursion limit from runtime context.

        Returns ``None`` (guard inactive) when the key is missing or invalid.
        """
        context = getattr(runtime, "context", None)
        if not isinstance(context, dict):
            return None
        value = context.get("recursion_limit")
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            return None
        return value

    def _thresholds(self, limit: int) -> tuple[int, int]:
        warn_at = max(1, int(limit * self._warn_ratio))
        hard_at = max(warn_at + 1, limit - self._hard_margin)
        return warn_at, hard_at

    def _clear(self, runtime: Runtime) -> None:
        key = self._key(runtime)
        with self._lock:
            self._costs.pop(key, None)
            self._warned.pop(key, None)
            self._pending_warnings.pop(key, None)

    def consume_stop_reason(self, run_id: str | None) -> str | None:
        """Return and clear the recorded stop reason for *run_id* (once)."""
        if run_id is None:
            return None
        with self._lock:
            return self._stop_reason.pop(run_id, None)

    # ------------------------------------------------------------------
    # Cost accounting + hard stop (after_model)
    # ------------------------------------------------------------------

    def _apply(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        limit = self._read_limit(runtime)
        if limit is None:
            return None
        messages = list(state.get("messages") or [])
        if not messages or not isinstance(messages[-1], AIMessage):
            return None

        last = messages[-1]
        n_tools = len(last.tool_calls or [])
        invalid = getattr(last, "invalid_tool_calls", None)
        if invalid:
            n_tools += len(invalid)

        # Cycle cost (measured, see module docstring): model node (1) + this
        # guard's own after_model node (1) + other middleware hook nodes +
        # tools node (1) when the response calls tools. Parallel tool calls
        # share one tools node, so batch size does not change the cost.
        cycle_cost = 2 + self._extra_hook_nodes + (1 if n_tools > 0 else 0)

        key = self._key(runtime)
        warn_at, hard_at = self._thresholds(limit)
        with self._lock:
            cost = self._costs.get(key, 0) + cycle_cost
            self._costs[key] = cost
            queue_warn = warn_at <= cost < hard_at and not self._warned.get(key)
            if queue_warn:
                self._warned[key] = True
                self._pending_warnings[key] = True

        if cost < hard_at or n_tools == 0:
            # n_tools == 0: the model is producing its final answer (possibly
            # after a hard strip) — never rewrite it, even past the threshold.
            return None

        run_id = self._get_run_id(runtime)
        with self._lock:
            self._stop_reason[run_id] = "recursion_capped"
        # Also write to runtime.context so the worker can read it without a
        # reference to this middleware instance (mirrors loop_detection #4176).
        ctx = getattr(runtime, "context", None)
        if isinstance(ctx, dict):
            ctx["stop_reason"] = "recursion_capped"
        logger.warning(
            "recursion guard hard stop: estimated cost=%d >= hard_at=%d (limit=%d), thread=%s run=%s",
            cost,
            hard_at,
            limit,
            key[0],
            run_id,
        )
        # Strip tool_calls: once removed, the AIMessage no longer requires
        # matching ToolMessage responses, so mutating it here is safe for
        # provider pairing validators — same reasoning as loop_detection.
        content = _append_text(last.content, _HARD_STOP_MSG)
        stripped_msg = last.model_copy(update=_build_hard_stop_update(last, content))
        return {"messages": [stripped_msg]}

    @override
    def after_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        return self._apply(state, runtime)

    @override
    async def aafter_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        return self._apply(state, runtime)

    # ------------------------------------------------------------------
    # Warn injection (wrap_model_call, pairing-safe)
    # ------------------------------------------------------------------

    def _augment_request(self, request: ModelRequest) -> ModelRequest:
        key = self._key(request.runtime)
        with self._lock:
            pending = self._pending_warnings.pop(key, None)
        if not pending:
            return request
        reminder = HumanMessage(
            content=_WARN_MSG,
            name="recursion_guard_warning",
            additional_kwargs={"hide_from_ui": True},
        )
        return request.override(messages=[*request.messages, reminder])

    @override
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelCallResult:
        return handler(self._augment_request(request))

    @override
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelCallResult:
        return await handler(self._augment_request(request))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @override
    def before_agent(self, state: AgentState, runtime: Runtime) -> dict | None:
        self._clear(runtime)
        return None

    @override
    async def abefore_agent(self, state: AgentState, runtime: Runtime) -> dict | None:
        self._clear(runtime)
        return None

    @override
    def after_agent(self, state: AgentState, runtime: Runtime) -> dict | None:
        self._clear(runtime)
        return None

    @override
    async def aafter_agent(self, state: AgentState, runtime: Runtime) -> dict | None:
        self._clear(runtime)
        return None

"""Tests for RecursionGuardMiddleware.

The guard converts LangGraph's hard ``GraphRecursionError`` death into a
natural finish: it estimates consumed super-steps per model cycle (model node
+ own after_model node + builder-injected extra hook nodes + tools node when
the response calls tools — parallel calls share one node), injects a wrap-up
reminder at the warn ratio, and strips ``tool_calls`` at the hard threshold so
the agent loop terminates with a final answer. It reads the run's effective
limit from ``runtime.context["recursion_limit"]`` and is inactive when the key
is absent.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import tool as as_tool
from pydantic import PrivateAttr

from deerflow.agents.middlewares.recursion_guard_middleware import (
    _HARD_STOP_MSG,
    RecursionGuardMiddleware,
)


def _make_runtime(thread_id: str = "t-thread", run_id: str = "t-run", limit: Any = 20):
    """Build a minimal Runtime mock with context."""
    runtime = MagicMock()
    context: dict[str, Any] = {"thread_id": thread_id, "run_id": run_id}
    if limit is not None:
        context["recursion_limit"] = limit
    runtime.context = context
    return runtime


def _tc(name: str = "echo", call_id: str = "c1", args: dict | None = None):
    return {"name": name, "args": args or {}, "id": call_id, "type": "tool_call"}


def _state_with_ai(tool_calls: list | None = None, content: str = ""):
    return {"messages": [AIMessage(content=content, tool_calls=tool_calls or [])]}


def _make_request(messages, runtime):
    """Build a minimal ModelRequest stand-in for wrap_model_call tests."""
    request = MagicMock()
    request.messages = list(messages)
    request.runtime = runtime
    request.override = lambda **updates: _override_request(request, updates)
    return request


def _override_request(request, updates):
    new = MagicMock()
    new.messages = updates.get("messages", request.messages)
    new.runtime = updates.get("runtime", request.runtime)
    new.override = lambda **u: _override_request(new, u)
    return new


def _capture_handler():
    captured: list = []

    def handler(req):
        captured.append(req)
        return MagicMock()

    return captured, handler


# ---------------------------------------------------------------------------
# Activation gate: the guard only runs when a valid limit is plumbed.
# ---------------------------------------------------------------------------


def test_inactive_without_limit_in_context():
    mw = RecursionGuardMiddleware()
    runtime = _make_runtime(limit=None)
    assert mw.after_model(_state_with_ai([_tc()]), runtime) is None
    assert not mw._costs


@pytest.mark.parametrize("bad_limit", [0, -5, "abc", 10.5, True])
def test_inactive_with_invalid_limit(bad_limit):
    mw = RecursionGuardMiddleware()
    runtime = _make_runtime(limit=bad_limit)
    assert mw.after_model(_state_with_ai([_tc()]), runtime) is None
    assert not mw._costs


def test_inactive_when_last_message_not_ai():
    mw = RecursionGuardMiddleware()
    runtime = _make_runtime(limit=20)
    state = {"messages": [HumanMessage(content="hi")]}
    assert mw.after_model(state, runtime) is None
    assert not mw._costs


# ---------------------------------------------------------------------------
# Cost accounting: 1 + len(tool_calls) per model response.
# ---------------------------------------------------------------------------


def test_cost_accounting_counts_tool_calls():
    """Cycle cost = model(1) + own after_model node(1) + tools node(1 if any).

    Parallel tool calls share one tools node, so batch size is irrelevant.
    """
    mw = RecursionGuardMiddleware()
    runtime = _make_runtime(limit=100)
    key = ("t-thread", "t-run")

    mw.after_model(_state_with_ai([_tc(call_id="a"), _tc(call_id="b"), _tc(call_id="c")]), runtime)
    assert mw._costs[key] == 3  # 2 + 1 (one tools node despite 3 calls)

    mw.after_model(_state_with_ai([], content="thinking"), runtime)
    assert mw._costs[key] == 5  # + 2 (no tools node)

    mw.after_model(_state_with_ai([_tc(call_id="d"), _tc(call_id="e")]), runtime)
    assert mw._costs[key] == 8  # + 3


def test_cost_accounting_includes_extra_hook_nodes():
    """Builders inject the chain's other hook nodes; each adds 1 per cycle."""
    mw = RecursionGuardMiddleware()
    mw.set_extra_hook_nodes(4)
    runtime = _make_runtime(limit=100)
    mw.after_model(_state_with_ai([_tc()]), runtime)
    assert mw._costs[("t-thread", "t-run")] == 2 + 4 + 1
    mw.after_model(_state_with_ai([], content="text"), runtime)
    assert mw._costs[("t-thread", "t-run")] == 2 + 4 + 1 + 2 + 4


def test_count_model_hook_nodes():
    """Only before/after-model overrides count; wrap hooks add no node."""
    from langchain.agents.middleware import AgentMiddleware

    class _BeforeAfter(AgentMiddleware):
        def before_model(self, state, runtime): ...
        def after_model(self, state, runtime): ...

    class _WrapOnly(AgentMiddleware):
        def wrap_model_call(self, request, handler):
            return handler(request)

    class _Plain(AgentMiddleware):
        pass

    chain = [_BeforeAfter(), _WrapOnly(), _Plain()]
    assert RecursionGuardMiddleware.count_model_hook_nodes(chain) == 2
    assert RecursionGuardMiddleware.count_model_hook_nodes(chain, exclude=chain[0]) == 0


def test_cost_isolated_per_run():
    mw = RecursionGuardMiddleware()
    r1 = _make_runtime(thread_id="t1", run_id="r1", limit=100)
    r2 = _make_runtime(thread_id="t1", run_id="r2", limit=100)
    mw.after_model(_state_with_ai([_tc()]), r1)
    assert mw._costs[("t1", "r1")] == 3
    assert ("t1", "r2") not in mw._costs
    mw.after_model(_state_with_ai([_tc()]), r2)
    assert mw._costs[("t1", "r2")] == 3


# ---------------------------------------------------------------------------
# Warn path: reminder injected once, appended after tool messages.
# ---------------------------------------------------------------------------


def test_warn_injected_once_at_ratio_threshold():
    mw = RecursionGuardMiddleware()
    runtime = _make_runtime(limit=20)  # warn_at=15, hard_at=16
    # 5 responses x (1 + 2 tool calls) = cost 15 -> warn queued after the 5th.
    for i in range(5):
        assert mw.after_model(_state_with_ai([_tc(call_id=f"a{i}"), _tc(call_id=f"b{i}")]), runtime) is None

    captured, handler = _capture_handler()
    request = _make_request(
        [
            HumanMessage(content="go"),
            AIMessage(content="", tool_calls=[_tc(call_id="a4")]),
            ToolMessage(content="ok", tool_call_id="a4"),
        ],
        runtime,
    )
    mw.wrap_model_call(request, handler)
    injected = captured[0].messages[-1]
    assert isinstance(injected, HumanMessage)
    assert "Step budget warning" in injected.content
    assert injected.additional_kwargs.get("hide_from_ui") is True
    # Pairing safety: reminder lands after the ToolMessage, never between
    # tool_calls and their responses.
    assert isinstance(captured[0].messages[-2], ToolMessage)

    # Second model call: no duplicate reminder.
    captured2, handler2 = _capture_handler()
    mw.wrap_model_call(_make_request([HumanMessage(content="go")], runtime), handler2)
    assert captured2[0].messages[-1].content == "go"


def test_no_warn_below_threshold():
    mw = RecursionGuardMiddleware()
    runtime = _make_runtime(limit=100)  # warn_at=75
    for i in range(3):
        mw.after_model(_state_with_ai([_tc(call_id=f"x{i}")]), runtime)  # cost 6
    captured, handler = _capture_handler()
    mw.wrap_model_call(_make_request([HumanMessage(content="go")], runtime), handler)
    assert captured[0].messages[-1].content == "go"


# ---------------------------------------------------------------------------
# Hard stop: strip tool_calls, force a natural finish, record stop_reason.
# ---------------------------------------------------------------------------


def _drive_to_hard(mw: RecursionGuardMiddleware, runtime, responses: int = 8):
    """8 responses x (1 + 1 tool call) = cost 16 >= hard_at(16) for limit=20."""
    result = None
    for i in range(responses):
        msg = AIMessage(
            content="working",
            tool_calls=[_tc(call_id=f"h{i}")],
            response_metadata={"finish_reason": "tool_calls"},
        )
        result = mw.after_model({"messages": [msg]}, runtime)
    return result


def test_hard_strip_forces_natural_finish():
    mw = RecursionGuardMiddleware()
    runtime = _make_runtime(limit=20)  # hard_at = max(16, 20-6) = 16
    update = _drive_to_hard(mw, runtime)

    assert update is not None
    stripped = update["messages"][0]
    assert stripped.tool_calls == []
    assert _HARD_STOP_MSG in stripped.content
    assert "tool_calls" not in stripped.additional_kwargs
    # finish_reason normalized so the message serializes as plain text.
    assert stripped.response_metadata.get("finish_reason") == "stop"
    # stop_reason surfaced both ways.
    assert runtime.context["stop_reason"] == "recursion_capped"
    assert mw.consume_stop_reason("t-run") == "recursion_capped"
    assert mw.consume_stop_reason("t-run") is None  # consumed once


def test_hard_stop_skips_warn():
    """Cost jumps straight past warn into hard: no reminder is ever queued."""
    mw = RecursionGuardMiddleware()
    runtime = _make_runtime(limit=20)  # warn_at=15, hard_at=16
    # 4 tool responses (+3 each) = 12, then a text-only response (+2) = 14
    # (< warn_at), then one more tool response = 17 (>= hard_at) — the warn
    # threshold was never crossed without also crossing hard.
    update = None
    for i in range(4):
        update = mw.after_model(_state_with_ai([_tc(call_id=f"a{i}")]), runtime)
    assert update is None
    update = mw.after_model(_state_with_ai([], content="thinking"), runtime)
    assert update is None
    update = mw.after_model(_state_with_ai([_tc(call_id="final")]), runtime)
    assert update is not None
    assert update["messages"][0].tool_calls == []
    captured, handler = _capture_handler()
    mw.wrap_model_call(_make_request([HumanMessage(content="go")], runtime), handler)
    assert captured[0].messages[-1].content == "go"  # no pending warn


def test_final_answer_after_strip_is_not_rewritten():
    """Once the model answers with plain text (no tool calls), the guard must
    not append the hard-stop note again, even though cost stays >= hard_at."""
    mw = RecursionGuardMiddleware()
    runtime = _make_runtime(limit=20)
    _drive_to_hard(mw, runtime)
    # Model now produces the final answer: no tool calls.
    final = AIMessage(content="All done. Deliverables are in outputs.")
    assert mw.after_model({"messages": [final]}, runtime) is None


# ---------------------------------------------------------------------------
# End-to-end: a run that would hit LangGraph's recursion limit finishes clean.
# ---------------------------------------------------------------------------


class _ToolCallingFakeModel(FakeMessagesListChatModel):
    """Fake chat model returning pre-built responses (bind_tools passthrough)."""

    _seen_messages: list[list[Any]] = PrivateAttr(default_factory=list)

    @property
    def seen_messages(self) -> list[list[Any]]:
        return self._seen_messages

    def bind_tools(self, tools: Any, *, tool_choice: Any = None, **kwargs: Any) -> Runnable:
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self._seen_messages.append(list(messages))
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


@as_tool
def echo(text: str = "x") -> str:
    """Echo the input text."""
    return text


def test_e2e_run_terminates_gracefully_before_langgraph_recursion_error():
    responses = [AIMessage(content="", tool_calls=[{"name": "echo", "args": {"text": str(i)}, "id": f"call-{i}"}]) for i in range(30)]
    model = _ToolCallingFakeModel(responses=responses)
    mw = RecursionGuardMiddleware()
    agent = create_agent(model, tools=[echo], middleware=[mw])

    context = {"thread_id": "e2e-t", "run_id": "e2e-r", "recursion_limit": 30}
    result = agent.invoke(
        {"messages": [HumanMessage(content="start")]},
        config={"recursion_limit": 30},
        context=context,
    )

    # No GraphRecursionError was raised; the last AI message is a stripped,
    # plain-text finish carrying the hard-stop note.
    last = result["messages"][-1]
    assert isinstance(last, AIMessage)
    assert not last.tool_calls
    assert _HARD_STOP_MSG in last.content
    assert context.get("stop_reason") == "recursion_capped"
    assert mw.consume_stop_reason("e2e-r") == "recursion_capped"


def test_e2e_short_run_untouched_by_guard():
    """A short run below the warn threshold is completely unaffected."""
    responses = [
        AIMessage(content="", tool_calls=[{"name": "echo", "args": {"text": "a"}, "id": "c-a"}]),
        AIMessage(content="final answer"),
    ]
    model = _ToolCallingFakeModel(responses=responses)
    mw = RecursionGuardMiddleware()
    agent = create_agent(model, tools=[echo], middleware=[mw])

    context = {"thread_id": "e2e-t2", "run_id": "e2e-r2", "recursion_limit": 100}
    result = agent.invoke(
        {"messages": [HumanMessage(content="start")]},
        config={"recursion_limit": 100},
        context=context,
    )
    last = result["messages"][-1]
    assert last.content == "final answer"
    assert "stop_reason" not in context
    # The model never saw a guard reminder.
    for seen in model.seen_messages:
        assert not any(getattr(m, "name", None) == "recursion_guard_warning" for m in seen)


# ---------------------------------------------------------------------------
# Gateway plumbing: build_run_config surfaces the clamped limit into context.
# ---------------------------------------------------------------------------


@pytest.fixture
def _stub_app_config():
    from deerflow.config.app_config import AppConfig, reset_app_config, set_app_config

    set_app_config(AppConfig.model_validate({"sandbox": {"use": "deerflow.sandbox.local:LocalSandboxProvider"}}))
    try:
        yield
    finally:
        reset_app_config()


def test_gateway_run_config_plumbs_default_limit_into_context(_stub_app_config):
    from app.gateway.services import build_run_config

    config = build_run_config("thread-9", None, None)
    assert config["recursion_limit"] == 250
    assert config["context"]["recursion_limit"] == 250
    assert config["context"]["thread_id"] == "thread-9"


def test_gateway_run_config_plumbs_clamped_limit_into_context(_stub_app_config):
    from app.gateway.services import build_run_config

    config = build_run_config("thread-9", {"recursion_limit": 250}, None)
    assert config["recursion_limit"] == 250
    assert config["context"]["recursion_limit"] == 250


def test_gateway_run_config_caller_context_preserved_with_limit(_stub_app_config):
    from app.gateway.services import build_run_config

    config = build_run_config("thread-9", {"context": {"secrets": {"K": "v"}}}, None)
    assert config["context"]["secrets"] == {"K": "v"}
    assert config["context"]["recursion_limit"] == 250

"""Tests for SkillToolPolicyMiddleware."""

import posixpath
from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain_core.tools import tool as as_tool

from deerflow.agents.middlewares.skill_tool_policy_middleware import SkillToolPolicyMiddleware
from deerflow.runtime.secret_context import _SLASH_SECRET_SOURCE_KEY
from deerflow.skills.tool_policy import ALWAYS_AVAILABLE_BUILTIN_TOOL_NAMES
from deerflow.skills.types import Skill


@as_tool
def web_search(x: str) -> str:
    """Search the web."""
    return x


@as_tool
def bash(x: str) -> str:
    """Run a shell command."""
    return x


@as_tool
def read_file(x: str) -> str:
    """Read a file."""
    return x


@as_tool
def review_skill_package(x: str) -> str:
    """Review a skill package."""
    return x


@as_tool
def custom_skill_tool(x: str) -> str:
    """A skill-specific tool."""
    return x


@as_tool
def tool_search(x: str) -> str:
    """Discover deferred tool schemas."""
    return x


@as_tool
def patent_data_patent_search(x: str) -> str:
    """Search patents."""
    return x


ALL_TOOLS = [web_search, bash, read_file, review_skill_package, custom_skill_tool, tool_search, patent_data_patent_search]


def _make_skill(name: str, *, allowed_tools: list[str] | None = None, enabled: bool = True) -> Skill:
    return Skill(
        name=name,
        description=f"Description for {name}",
        license="MIT",
        skill_dir=Path(f"/tmp/{name}"),
        skill_file=Path(f"/tmp/{name}/SKILL.md"),
        relative_path=Path(name),
        category="public",
        allowed_tools=tuple(allowed_tools) if allowed_tools is not None else None,
        enabled=enabled,
    )


class _FakeStorage:
    def __init__(self, skills: list[Skill], container_root: str = "/mnt/skills") -> None:
        self._skills = skills
        self._container_root = container_root

    def load_skills(self, *, enabled_only: bool = False) -> list[Skill]:
        return self._skills

    def get_container_root(self) -> str:
        return self._container_root


def _make_middleware(skills: list[Skill], *, available_skills: set[str] | None = None) -> SkillToolPolicyMiddleware:
    """Build middleware with an in-memory registry so tests stay hermetic.

    Patches the instance's registry loader rather than module-level storage
    factories; this avoids the fragility where restoring a module patch in a
    ``finally`` block happens before the test actually exercises the middleware.
    """
    mw = SkillToolPolicyMiddleware(available_skills=available_skills)
    container_root = "/mnt/skills"
    registry = {posixpath.normpath(skill.get_container_file_path(container_root)): skill for skill in skills}
    mw._load_registry_by_path = lambda: registry
    return mw


class _ModelReq:
    def __init__(self, tools: list, state: dict | None = None, runtime_context: dict | None = None):
        self.tools = tools
        self.state = state or {}
        self.runtime = SimpleNamespace(context=runtime_context)
        self.overridden = None

    def override(self, *, tools: list):
        self.overridden = tools
        return self


class _ToolReq:
    def __init__(self, name: str, state: dict | None = None, runtime_context: dict | None = None):
        self.tool_call = {"name": name, "id": "tc1"}
        self.state = state or {}
        self.runtime = SimpleNamespace(context=runtime_context)


def _names(tools: list) -> list[str]:
    return [getattr(t, "name", None) for t in tools]


def test_no_active_skills_leaves_tools_unchanged():
    mw = _make_middleware([_make_skill("reviewer", allowed_tools=["review_skill_package"])])
    req = _ModelReq(ALL_TOOLS)
    out = mw._filter_tools(req)
    assert out is req
    assert req.overridden is None


def _skill_path(name: str) -> str:
    return f"/mnt/skills/public/{name}/SKILL.md"


def test_slash_activation_restricts_to_allowed_plus_builtins():
    reviewer = _make_skill("reviewer", allowed_tools=["review_skill_package"])
    mw = _make_middleware([reviewer])
    req = _ModelReq(
        ALL_TOOLS,
        runtime_context={_SLASH_SECRET_SOURCE_KEY: {"path": _skill_path("reviewer")}},
    )
    out = mw._filter_tools(req)
    assert set(_names(out.overridden)) == {"review_skill_package", "read_file", "tool_search"}


def test_tool_search_remains_available_but_promoted_disallowed_schema_is_hidden():
    reviewer = _make_skill("reviewer", allowed_tools=["review_skill_package"])
    mw = _make_middleware([reviewer])
    req = _ModelReq(
        ALL_TOOLS,
        runtime_context={_SLASH_SECRET_SOURCE_KEY: {"path": _skill_path("reviewer")}},
    )

    out = mw._filter_tools(req)

    assert "tool_search" in _names(out.overridden)
    assert "patent-data_patent_search" not in _names(out.overridden)


def test_promoted_disallowed_schema_is_rejected_at_execution_time():
    reviewer = _make_skill("reviewer", allowed_tools=["review_skill_package"])
    mw = _make_middleware([reviewer])
    req = _ToolReq(
        "patent-data_patent_search",
        runtime_context={_SLASH_SECRET_SOURCE_KEY: {"path": _skill_path("reviewer")}},
    )

    result = mw._blocked_tool_message(req)

    assert result is not None
    assert result.status == "error"
    assert "patent-data_patent_search" in result.content


def test_skill_context_restricts_to_allowed_plus_builtins():
    skill = _make_skill("data-skill", allowed_tools=["custom_skill_tool", "bash"])
    mw = _make_middleware([skill])
    req = _ModelReq(
        ALL_TOOLS,
        state={"skill_context": [{"name": "data-skill", "path": _skill_path("data-skill"), "description": "d", "loaded_at": 1}]},
    )
    out = mw._filter_tools(req)
    assert set(_names(out.overridden)) == {"bash", "custom_skill_tool", "read_file", "review_skill_package", "tool_search"}


def test_multiple_active_skills_union_allowed_tools():
    skill_a = _make_skill("skill-a", allowed_tools=["custom_skill_tool"])
    skill_b = _make_skill("skill-b", allowed_tools=["bash"])
    mw = _make_middleware([skill_a, skill_b])
    req = _ModelReq(
        ALL_TOOLS,
        state={
            "skill_context": [
                {"name": "skill-a", "path": _skill_path("skill-a"), "description": "a", "loaded_at": 1},
                {"name": "skill-b", "path": _skill_path("skill-b"), "description": "b", "loaded_at": 2},
            ]
        },
    )
    out = mw._filter_tools(req)
    assert set(_names(out.overridden)) == {"bash", "custom_skill_tool", "read_file", "review_skill_package", "tool_search"}


def test_disabled_skill_in_context_is_ignored():
    skill = _make_skill("data-skill", allowed_tools=["custom_skill_tool"], enabled=False)
    mw = _make_middleware([skill])
    req = _ModelReq(
        ALL_TOOLS,
        state={"skill_context": [{"name": "data-skill", "path": _skill_path("data-skill"), "description": "d", "loaded_at": 1}]},
    )
    out = mw._filter_tools(req)
    assert out is req


def test_skill_not_in_available_skills_is_ignored():
    skill = _make_skill("data-skill", allowed_tools=["custom_skill_tool"])
    mw = _make_middleware([skill], available_skills={"other-skill"})
    req = _ModelReq(
        ALL_TOOLS,
        state={"skill_context": [{"name": "data-skill", "path": _skill_path("data-skill"), "description": "d", "loaded_at": 1}]},
    )
    out = mw._filter_tools(req)
    assert out is req


def test_legacy_active_skill_allows_all_tools():
    skill = _make_skill("legacy", allowed_tools=None)
    mw = _make_middleware([skill])
    req = _ModelReq(
        ALL_TOOLS,
        runtime_context={_SLASH_SECRET_SOURCE_KEY: {"path": _skill_path("legacy")}},
    )
    out = mw._filter_tools(req)
    assert out is req


def test_empty_allowed_tools_leaves_only_builtins():
    skill = _make_skill("locked-down", allowed_tools=[])
    mw = _make_middleware([skill])
    req = _ModelReq(
        ALL_TOOLS,
        runtime_context={_SLASH_SECRET_SOURCE_KEY: {"path": _skill_path("locked-down")}},
    )
    out = mw._filter_tools(req)
    assert set(_names(out.overridden)) == set(ALWAYS_AVAILABLE_BUILTIN_TOOL_NAMES)


def test_registry_load_failure_fails_open():
    mw = SkillToolPolicyMiddleware()
    req = _ModelReq(
        ALL_TOOLS,
        runtime_context={_SLASH_SECRET_SOURCE_KEY: {"path": _skill_path("reviewer")}},
    )
    out = mw._filter_tools(req)
    assert out is req


def test_blocked_tool_call_returns_error():
    reviewer = _make_skill("reviewer", allowed_tools=["review_skill_package"])
    mw = _make_middleware([reviewer])
    req = _ToolReq(
        "bash",
        runtime_context={_SLASH_SECRET_SOURCE_KEY: {"path": _skill_path("reviewer")}},
    )
    result = mw._blocked_tool_message(req)
    assert result is not None
    assert result.status == "error"
    assert "bash" in result.content
    assert "review_skill_package" in result.content


def test_allowed_tool_call_not_blocked():
    reviewer = _make_skill("reviewer", allowed_tools=["review_skill_package"])
    mw = _make_middleware([reviewer])
    req = _ToolReq(
        "read_file",
        runtime_context={_SLASH_SECRET_SOURCE_KEY: {"path": _skill_path("reviewer")}},
    )
    assert mw._blocked_tool_message(req) is None


def test_no_active_skills_no_blocked_message():
    mw = _make_middleware([_make_skill("reviewer", allowed_tools=["review_skill_package"])])
    req = _ToolReq("bash")
    assert mw._blocked_tool_message(req) is None


def test_wrap_model_call_passes_filtered_tools():
    reviewer = _make_skill("reviewer", allowed_tools=["review_skill_package"])
    mw = _make_middleware([reviewer])
    req = _ModelReq(
        ALL_TOOLS,
        runtime_context={_SLASH_SECRET_SOURCE_KEY: {"path": _skill_path("reviewer")}},
    )

    def handler(r: _ModelReq):
        return SimpleNamespace(result=[r])

    result = mw.wrap_model_call(req, handler)
    passed = result.result[0]
    assert set(_names(passed.overridden)) == {"review_skill_package", "read_file", "tool_search"}


@pytest.mark.anyio
async def test_awrap_model_call_offloads_filtering():
    reviewer = _make_skill("reviewer", allowed_tools=["review_skill_package"])
    mw = _make_middleware([reviewer])
    req = _ModelReq(
        ALL_TOOLS,
        runtime_context={_SLASH_SECRET_SOURCE_KEY: {"path": _skill_path("reviewer")}},
    )

    async def handler(r: _ModelReq):
        return SimpleNamespace(result=[r])

    result = await mw.awrap_model_call(req, handler)
    passed = result.result[0]
    assert set(_names(passed.overridden)) == {"review_skill_package", "read_file", "tool_search"}


def test_wrap_tool_call_blocks_disallowed_tool():
    reviewer = _make_skill("reviewer", allowed_tools=["review_skill_package"])
    mw = _make_middleware([reviewer])
    req = _ToolReq(
        "bash",
        runtime_context={_SLASH_SECRET_SOURCE_KEY: {"path": _skill_path("reviewer")}},
    )

    def handler(r: _ToolReq):
        return SimpleNamespace(content="should not run")

    result = mw.wrap_tool_call(req, handler)
    assert result.status == "error"


@pytest.mark.anyio
async def test_awrap_tool_call_blocks_disallowed_tool():
    reviewer = _make_skill("reviewer", allowed_tools=["review_skill_package"])
    mw = _make_middleware([reviewer])
    req = _ToolReq(
        "bash",
        runtime_context={_SLASH_SECRET_SOURCE_KEY: {"path": _skill_path("reviewer")}},
    )

    async def handler(r: _ToolReq):
        return SimpleNamespace(content="should not run")

    result = await mw.awrap_tool_call(req, handler)
    assert result.status == "error"

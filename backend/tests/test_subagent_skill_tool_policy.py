"""Regression tests for subagent skill-tool policy alignment with the lead agent.

Covers the fix for the issue where enabled skills (especially skill-reviewer
and its eval fixtures) collapsed the general-purpose subagent tool surface at
build time. After the fix:

- evals/fixtures directories are not discovered as standalone skills;
- subagents bind the full tool surface by default;
- skill allowed-tools are enforced only at runtime and only for actually
  active skills (slash activation or captured skill_context), matching the
  lead-agent semantics from #72d9b21.
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from deerflow.skills.storage.local_skill_storage import LocalSkillStorage
from deerflow.skills.storage.user_scoped_skill_storage import UserScopedSkillStorage
from deerflow.skills.types import Skill, SkillCategory

# ---------------------------------------------------------------------------
# Fixture exclusion
# ---------------------------------------------------------------------------


def _write_skill_md(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\nname: fixture-skill\ndescription: fixture\nallowed-tools:\n  - bash\n---\n",
        encoding="utf-8",
    )


def test_local_skill_storage_excludes_evals_fixtures():
    """Skills under evals/fixtures must not be discovered as ordinary skills."""
    root = Path(__file__).parent / ".tmp-test-fixtures"
    try:
        root.mkdir(exist_ok=True)
        _write_skill_md(root / "public" / "skill-reviewer" / "evals" / "fixtures" / "prompt-injection" / "SKILL.md")
        _write_skill_md(root / "public" / "skill-reviewer" / "evals" / "fixtures" / "publish-candidate" / "SKILL.md")
        _write_skill_md(root / "public" / "real-skill" / "SKILL.md")

        storage = LocalSkillStorage(host_path=str(root))
        files = list(storage._iter_skill_files())
        names = {p.parent.name for _, _, p in files}

        assert "prompt-injection" not in names
        assert "publish-candidate" not in names
        assert "real-skill" in names
        assert len(files) == 1
    finally:
        # Best-effort cleanup
        import shutil

        shutil.rmtree(root, ignore_errors=True)


def test_user_scoped_storage_excludes_evals_fixtures():
    """UserScopedSkillStorage must also ignore evals/fixtures in public skills."""
    host_root = Path(__file__).parent / ".tmp-test-user-fixtures"
    try:
        host_root.mkdir(exist_ok=True)
        _write_skill_md(host_root / "public" / "skill-reviewer" / "evals" / "fixtures" / "prompt-injection" / "SKILL.md")
        _write_skill_md(host_root / "public" / "real-skill" / "SKILL.md")

        storage = UserScopedSkillStorage(
            user_id="test-user",
            host_path=str(host_root),
        )
        files = list(storage._iter_skill_files())
        names = {p.parent.name for _, _, p in files}

        assert "prompt-injection" not in names
        assert "real-skill" in names
        assert len(files) == 1
    finally:
        import shutil

        shutil.rmtree(host_root, ignore_errors=True)


# ---------------------------------------------------------------------------
# Subagent build-time tool policy removal
# ---------------------------------------------------------------------------


def _make_skill(name: str, allowed_tools: list[str] | None = None, enabled: bool = True) -> Skill:
    return Skill(
        name=name,
        description=f"Description for {name}",
        license="MIT",
        skill_dir=Path(f"/tmp/{name}"),
        skill_file=Path(f"/tmp/{name}/SKILL.md"),
        relative_path=Path(name),
        category=SkillCategory.PUBLIC,
        allowed_tools=tuple(allowed_tools) if allowed_tools is not None else None,
        enabled=enabled,
    )


def _runtime_app_config():
    from deerflow.config.app_config import AppConfig
    from deerflow.config.sandbox_config import SandboxConfig

    return AppConfig(sandbox=SandboxConfig(use="deerflow.sandbox.local:LocalSandboxProvider"))


def test_subagent_runtime_middlewares_include_skill_tool_policy():
    """build_subagent_runtime_middlewares must include SkillToolPolicyMiddleware."""
    from deerflow.agents.middlewares.skill_tool_policy_middleware import SkillToolPolicyMiddleware
    from deerflow.agents.middlewares.tool_error_handling_middleware import build_subagent_runtime_middlewares

    middlewares = build_subagent_runtime_middlewares(app_config=_runtime_app_config())
    assert any(isinstance(m, SkillToolPolicyMiddleware) for m in middlewares)


def test_subagent_skill_runtime_middleware_order_is_activation_then_durable_then_policy():
    from deerflow.agents.middlewares.durable_context_middleware import DurableContextMiddleware
    from deerflow.agents.middlewares.skill_activation_middleware import SkillActivationMiddleware
    from deerflow.agents.middlewares.skill_tool_policy_middleware import SkillToolPolicyMiddleware
    from deerflow.agents.middlewares.tool_error_handling_middleware import build_subagent_runtime_middlewares

    middlewares = build_subagent_runtime_middlewares(app_config=_runtime_app_config())
    activation_idx = next(i for i, middleware in enumerate(middlewares) if isinstance(middleware, SkillActivationMiddleware))
    durable_idx = next(i for i, middleware in enumerate(middlewares) if isinstance(middleware, DurableContextMiddleware))
    policy_idx = next(i for i, middleware in enumerate(middlewares) if isinstance(middleware, SkillToolPolicyMiddleware))

    assert activation_idx < durable_idx < policy_idx


# ---------------------------------------------------------------------------
# Runtime skill-tool policy behavior
# ---------------------------------------------------------------------------


class _FakeStorage:
    def __init__(self, skills: list[Skill]) -> None:
        self._skills = skills

    def load_skills(self, *, enabled_only: bool = False) -> list[Skill]:
        return self._skills

    def get_container_root(self) -> str:
        return "/mnt/skills"


def _patch_storage(skills: list[Skill]):
    """Patch SkillToolPolicyMiddleware storage factories for the scope of the test."""
    from deerflow.agents.middlewares import skill_tool_policy_middleware as policy_module

    storage = _FakeStorage(skills)

    def _get_storage(*args, **kwargs):
        return storage

    return (
        patch.object(policy_module, "get_or_new_skill_storage", _get_storage),
        patch.object(policy_module, "get_or_new_user_skill_storage", lambda user_id, **kwargs: storage),
    )


class _ModelReq:
    def __init__(self, tools: list, state: dict | None = None, runtime_context: dict | None = None):
        self.tools = tools
        self.state = state or {}
        self.runtime = SimpleNamespace(context=runtime_context)
        self.overridden = None

    def override(self, *, tools: list):
        self.overridden = tools
        return self


def test_runtime_skill_tool_policy_no_active_skills_allows_all_tools():
    """Without active skills, the subagent middleware must leave all tools visible."""
    from deerflow.agents.middlewares.skill_tool_policy_middleware import SkillToolPolicyMiddleware

    class Tool:
        def __init__(self, name: str):
            self.name = name

    all_tools = [Tool("bash"), Tool("web_search"), Tool("review_skill_package")]
    p1, p2 = _patch_storage([_make_skill("skill-reviewer", allowed_tools=["review_skill_package"])])
    with p1, p2:
        mw = SkillToolPolicyMiddleware()
        req = _ModelReq(all_tools)
        out = mw._filter_tools(req)
    assert out is req
    assert req.overridden is None


def test_runtime_skill_tool_policy_active_skill_restricts_tools():
    """When a skill is active in skill_context, only its allowed tools remain."""
    from deerflow.agents.middlewares.skill_tool_policy_middleware import SkillToolPolicyMiddleware

    class Tool:
        def __init__(self, name: str):
            self.name = name

    all_tools = [Tool("bash"), Tool("web_search"), Tool("read_file"), Tool("review_skill_package")]
    p1, p2 = _patch_storage([_make_skill("skill-reviewer", allowed_tools=["review_skill_package"])])
    with p1, p2:
        mw = SkillToolPolicyMiddleware()
        req = _ModelReq(
            all_tools,
            state={
                "skill_context": [
                    {
                        "name": "skill-reviewer",
                        "path": "/mnt/skills/public/skill-reviewer/SKILL.md",
                        "description": "reviewer",
                        "loaded_at": 1,
                    }
                ]
            },
        )
        out = mw._filter_tools(req)
    assert out.overridden is not None
    assert {t.name for t in out.overridden} == {"read_file", "review_skill_package"}

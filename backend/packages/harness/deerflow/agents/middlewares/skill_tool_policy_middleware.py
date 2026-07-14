"""Middleware to enforce skill ``allowed-tools`` only for currently active skills.

A skill is considered active for the current turn when:

- the user explicitly slash-activated it this run (recorded on the runtime context
  by ``SkillActivationMiddleware``); or
- the model loaded its ``SKILL.md`` earlier in the thread (captured in
  ``ThreadState.skill_context`` by ``DurableContextMiddleware``).

Only active skills' ``allowed-tools`` declarations are unioned and applied.
When no active skill declares ``allowed-tools``, all tools remain available.
This replaces the previous compile-time behavior that restricted the agent
whenever an *enabled* skill declared ``allowed-tools``.
"""

from __future__ import annotations

import asyncio
import logging
import posixpath
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command

from deerflow.runtime.secret_context import _SLASH_SECRET_SOURCE_KEY
from deerflow.skills.storage import get_or_new_skill_storage, get_or_new_user_skill_storage
from deerflow.skills.tool_policy import ALWAYS_AVAILABLE_BUILTIN_TOOL_NAMES, allowed_tool_names_for_skills
from deerflow.skills.types import Skill

if TYPE_CHECKING:
    from deerflow.config.app_config import AppConfig

logger = logging.getLogger(__name__)


class SkillToolPolicyMiddleware(AgentMiddleware[AgentState]):
    """Runtime filter for ``request.tools`` based on actually-active skills.

    This middleware is intentionally separate from ``SkillActivationMiddleware``:
    activation injects skill content and records slash state, while this
    middleware independently computes the tool-policy union from that state.
    Keeping them separate means either can be updated or disabled without
    affecting the other's security-critical logic.
    """

    def __init__(
        self,
        *,
        available_skills: set[str] | None = None,
        app_config: AppConfig | None = None,
        user_id: str | None = None,
    ) -> None:
        super().__init__()
        self._available_skills = set(available_skills) if available_skills is not None else None
        self._app_config = app_config
        self._user_id = user_id

    def _storage(self):
        if self._user_id is not None:
            return get_or_new_user_skill_storage(self._user_id, app_config=self._app_config)
        if self._app_config is not None:
            return get_or_new_skill_storage(app_config=self._app_config)
        return get_or_new_skill_storage()

    def _load_registry_by_path(self) -> dict[str, Skill] | None:
        """Load the live skill registry keyed by normalized container file path.

        Reloaded every call on purpose: an operator disabling a skill must stop
        its tool-policy restrictions on the very next model call. If loading
        fails, return ``None`` so the caller can fail open (allow all tools)
        rather than accidentally restricting everything.
        """
        try:
            storage = self._storage()
            skills = storage.load_skills(enabled_only=False)
            container_root = storage.get_container_root()
        except Exception:
            logger.exception("Failed to load skills for runtime tool policy")
            return None
        return {posixpath.normpath(skill.get_container_file_path(container_root)): skill for skill in skills}

    @staticmethod
    def _run_context(request: ModelRequest | ToolCallRequest) -> dict | None:
        runtime = getattr(request, "runtime", None)
        context = getattr(runtime, "context", None)
        return context if isinstance(context, dict) else None

    def _active_skill_paths(self, request: ModelRequest | ToolCallRequest) -> set[str]:
        """Collect normalized container paths of skills active this turn."""
        paths: set[str] = set()

        # 1) Explicit slash activation for this run.
        run_context = self._run_context(request)
        if run_context is not None:
            slash_source = run_context.get(_SLASH_SECRET_SOURCE_KEY)
            if isinstance(slash_source, dict):
                slash_path = slash_source.get("path")
                if isinstance(slash_path, str) and slash_path:
                    paths.add(posixpath.normpath(slash_path))

        # 2) Skills the model loaded in-context earlier in the thread.
        state = getattr(request, "state", None) or {}
        try:
            entries = state.get("skill_context") or []
        except AttributeError:
            entries = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            path = entry.get("path")
            if isinstance(path, str) and path:
                paths.add(posixpath.normpath(path))

        return paths

    def _resolve_active_skills(self, request: ModelRequest | ToolCallRequest) -> list[Skill] | None:
        """Resolve active skill paths to enabled, allowlisted Skill objects.

        Returns ``[]`` when there are no active skills. Returns ``None`` when the
        registry could not be loaded, signalling "fail open".
        """
        paths = self._active_skill_paths(request)
        if not paths:
            return []

        registry = self._load_registry_by_path()
        if registry is None:
            return None

        skills: list[Skill] = []
        seen: set[str] = set()
        for path in paths:
            skill = registry.get(path)
            if skill is None or not skill.enabled:
                continue
            if self._available_skills is not None and skill.name not in self._available_skills:
                continue
            if skill.name in seen:
                continue
            seen.add(skill.name)
            skills.append(skill)
        return skills

    def _allowed_tool_names(self, request: ModelRequest | ToolCallRequest) -> set[str] | None:
        """Return the set of tool names allowed this turn, or ``None`` for allow-all.

        ``None`` means no active skill declared ``allowed-tools``, so every tool
        bound to the agent remains visible.
        """
        skills = self._resolve_active_skills(request)
        if skills is None:
            # Registry load failure: fail open rather than lock the agent out.
            return None
        allowed = allowed_tool_names_for_skills(skills)
        if allowed is None:
            return None
        return allowed | ALWAYS_AVAILABLE_BUILTIN_TOOL_NAMES

    def _filter_tools(self, request: ModelRequest) -> ModelRequest:
        allowed = self._allowed_tool_names(request)
        if allowed is None:
            return request
        active = [t for t in request.tools if getattr(t, "name", None) in allowed]
        if len(active) < len(request.tools):
            hidden = {getattr(t, "name", None) for t in request.tools} - allowed
            logger.debug(
                "SkillToolPolicyMiddleware filtered %d tool schema(s) from model binding; hidden: %s",
                len(request.tools) - len(active),
                sorted(name for name in hidden if name is not None),
            )
        return request.override(tools=active)

    def _blocked_tool_message(self, request: ToolCallRequest) -> ToolMessage | None:
        allowed = self._allowed_tool_names(request)
        if allowed is None:
            return None
        name = str(request.tool_call.get("name") or "")
        if not name or name in allowed:
            return None
        tool_call_id = str(request.tool_call.get("id") or "missing_tool_call_id")
        return ToolMessage(
            content=(f"Error: Tool '{name}' is not available under the current active skill's allowed-tools policy. Allowed tools: {sorted(allowed)}"),
            tool_call_id=tool_call_id,
            name=name,
            status="error",
        )

    @override
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelCallResult:
        return handler(self._filter_tools(request))

    @override
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelCallResult:
        filtered = await asyncio.to_thread(self._filter_tools, request)
        return await handler(filtered)

    @override
    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        blocked = self._blocked_tool_message(request)
        if blocked is not None:
            return blocked
        return handler(request)

    @override
    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        blocked = await asyncio.to_thread(self._blocked_tool_message, request)
        if blocked is not None:
            return blocked
        return await handler(request)

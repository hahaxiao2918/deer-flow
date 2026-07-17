"""Configuration for the unchanged built-in lead-agent entry point."""

from pydantic import BaseModel, Field


class DefaultAgentConfig(BaseModel):
    """Optional capability filters for DeerFlow's default lead agent.

    Every list uses three-state semantics: ``None`` preserves the historical
    all-enabled behavior, ``[]`` enables none, and an explicit list is a
    whitelist.  The profile intentionally does not include identity, SOUL,
    memory, or thread settings.
    """

    skills: list[str] | None = Field(default=None, description="Skill whitelist (None=all, []=none).")
    subagents: list[str] | None = Field(default=None, description="Subagent whitelist (None=all, []=none).")
    tool_groups: list[str] | None = Field(default=None, description="Tool-group whitelist (None=all, []=none).")

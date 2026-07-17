"""Shared explicit Skill resolution rules for lead and subagent runtimes."""

from deerflow.skills.types import Skill


def resolve_explicit_skills(
    discovered: list[Skill],
    requested: list[str] | None,
    *,
    strict: bool,
    owner: str,
) -> list[Skill]:
    """Resolve an optional whitelist, failing deterministically in strict mode."""
    # Storage returns real Skill objects; permissive default keeps lightweight
    # embedded/test registry entries backward compatible.
    enabled_by_name = {skill.name: skill for skill in discovered if getattr(skill, "enabled", True)}
    if requested is None:
        return list(enabled_by_name.values())

    unresolved = [name for name in requested if name not in enabled_by_name]
    if strict and unresolved:
        joined = ", ".join(unresolved)
        raise ValueError(f"Strict skill resolution failed for {owner}: unavailable skills: {joined}")

    return [enabled_by_name[name] for name in requested if name in enabled_by_name]

"""Strict explicit-skill resolution is fail-fast and backward compatible."""

from pathlib import Path

import pytest

from deerflow.skills.resolution import resolve_explicit_skills
from deerflow.skills.types import Skill


def _skill(name: str, *, enabled: bool = True) -> Skill:
    return Skill(
        name=name,
        description=name,
        license="MIT",
        skill_dir=Path(f"/tmp/{name}"),
        skill_file=Path(f"/tmp/{name}/SKILL.md"),
        relative_path=Path(name),
        category="public",
        enabled=enabled,
    )


def test_non_strict_resolution_keeps_legacy_silent_filtering():
    resolved = resolve_explicit_skills([_skill("present")], ["present", "missing"], strict=False, owner="agent:test")
    assert [skill.name for skill in resolved] == ["present"]


def test_strict_resolution_rejects_missing_or_disabled_skill():
    with pytest.raises(ValueError, match=r"agent:test.*missing, disabled"):
        resolve_explicit_skills(
            [_skill("present"), _skill("disabled", enabled=False)],
            ["present", "missing", "disabled"],
            strict=True,
            owner="agent:test",
        )


def test_strict_resolution_preserves_explicit_order():
    resolved = resolve_explicit_skills([_skill("b"), _skill("a")], ["a", "b"], strict=True, owner="agent:test")
    assert [skill.name for skill in resolved] == ["a", "b"]

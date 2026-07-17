"""Contracts for the checked-in patent-research deployment profile."""

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]

COMMON_SKILLS = [
    "deep-research",
    "data-analysis",
    "chart-visualization",
    "systematic-literature-review",
    "academic-paper-review",
    "consulting-analysis",
    "ppt-generation",
]
PATENT_SKILLS = [
    "applicant-tech-patent-retrieval",
    "evidence-based-labeling",
    "technology-insight-analysis",
    "tech-evolution-analysis",
    "black-swan-tech-radar",
]
SUBAGENT_SKILLS = {
    "patent-retriever": "applicant-tech-patent-retrieval",
    "evidence-labeler": "evidence-based-labeling",
    "technology-insight-analyst": "technology-insight-analysis",
    "tech-evolution-analyst": "tech-evolution-analysis",
    "black-swan-radar": "black-swan-tech-radar",
}


def test_config_example_default_agent_exposes_only_common_capabilities():
    config = yaml.safe_load((ROOT / "config.example.yaml").read_text(encoding="utf-8"))

    assert config["default_agent"] == {
        "skills": COMMON_SKILLS,
        "subagents": ["general-purpose", "bash"],
        "tool_groups": None,
    }


def test_config_example_defines_five_single_skill_patent_subagents():
    config = yaml.safe_load((ROOT / "config.example.yaml").read_text(encoding="utf-8"))
    custom_agents = config["subagents"]["custom_agents"]

    assert set(custom_agents) == set(SUBAGENT_SKILLS)
    for name, skill in SUBAGENT_SKILLS.items():
        agent = custom_agents[name]
        assert agent["skills"] == [skill]
        assert agent["model"] == "inherit"
        assert agent["tools"] is None
        assert agent["disallowed_tools"] == ["task"]
        assert agent["max_turns"] == 80
        assert agent["timeout_seconds"] == 900


def test_patent_research_agent_profile_combines_common_and_patent_capabilities():
    profile_path = ROOT / "docs" / "examples" / "patent-research-agent" / "config.yaml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))

    assert profile["name"] == "patent-research"
    assert profile["skills"] == COMMON_SKILLS + PATENT_SKILLS
    assert profile["subagents"] == ["general-purpose", "bash", *SUBAGENT_SKILLS]


def test_extensions_example_declares_all_common_and_patent_skills():
    extensions = json.loads((ROOT / "extensions_config.example.json").read_text(encoding="utf-8"))

    assert set(COMMON_SKILLS + PATENT_SKILLS).issubset(extensions["skills"])

"""Contracts for the checked-in patent-research deployment profile."""

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

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
        assert agent["strict_skill_resolution"] is True


def test_patent_research_agent_profile_combines_common_and_patent_capabilities():
    profile_path = ROOT / "docs" / "examples" / "patent-research-agent" / "config.yaml"
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))

    assert profile["name"] == "patent-research"
    assert profile["skills"] == COMMON_SKILLS + PATENT_SKILLS
    assert profile["subagents"] == ["general-purpose", "bash", *SUBAGENT_SKILLS]
    assert profile["strict_skill_resolution"] is True


def test_extensions_example_declares_all_common_and_patent_skills():
    extensions = json.loads((ROOT / "extensions_config.example.json").read_text(encoding="utf-8"))

    assert set(COMMON_SKILLS + PATENT_SKILLS).issubset(extensions["skills"])


def test_patent_skills_are_canonical_v2_packages_with_exact_structure():
    for name in PATENT_SKILLS:
        root = ROOT / "skills" / "public" / name
        files = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
        assert files == {"SKILL.md", "agents/openai.yaml", "references/methodology.md", "references/output.schema.json"}
        body = (root / "SKILL.md").read_text(encoding="utf-8")
        assert "contract_version: patent-research.v2" in body
        assert "patent-data_patent_get_passages" in body
        schema = json.loads((root / "references" / "output.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        assert schema["$schema"].endswith("2020-12/schema")
        assert "corpus_id" in schema["properties"]


def test_only_retriever_can_discover_patents():
    retriever = (ROOT / "skills" / "public" / PATENT_SKILLS[0] / "SKILL.md").read_text(encoding="utf-8")
    assert "patent-data_patent_search" in retriever
    assert "patent-data_patent_validate_query" in retriever
    for name in PATENT_SKILLS[1:]:
        body = (ROOT / "skills" / "public" / name / "SKILL.md").read_text(encoding="utf-8")
        assert "  - patent-data_patent_search" not in body
        assert "  - patent-data_patent_validate_query" not in body
        assert "search_gap_request" in body


def test_complete_fake_pipeline_artifacts_validate_against_each_skill_schema():
    fixtures = ROOT / "backend" / "tests" / "fixtures" / "patent_pipeline"
    artifact_files = ["retrieval.json", "labels.json", "routes.json", "timeline.json", "signals.json"]
    for skill_name, artifact_file in zip(PATENT_SKILLS, artifact_files, strict=True):
        schema = json.loads((ROOT / "skills" / "public" / skill_name / "references" / "output.schema.json").read_text(encoding="utf-8"))
        artifact = json.loads((fixtures / artifact_file).read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(artifact)

import hashlib
import json
from pathlib import Path

import yaml

from deerflow.skills.parser import parse_skill_file
from deerflow.skills.types import SkillCategory


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = REPO_ROOT / "skills" / "public"
CONTRACT_ROOT = REPO_ROOT / "contracts" / "patent_skill_runtime"
PATENT_SKILLS = {
    "applicant-tech-patent-retrieval",
    "evidence-based-labeling",
    "technology-insight-analysis",
    "tech-evolution-analysis",
    "black-swan-tech-radar",
}


def test_patent_skills_are_in_discoverable_public_layout():
    for name in PATENT_SKILLS:
        skill_file = SKILLS_ROOT / name / "SKILL.md"
        parsed = parse_skill_file(skill_file, SkillCategory.PUBLIC, Path(name))
        assert parsed is not None
        assert parsed.name == name
        assert parsed.allowed_tools is not None


def test_patent_skill_descriptions_route_by_distinct_deliverables():
    descriptions = {}
    for name in PATENT_SKILLS:
        skill_file = SKILLS_ROOT / name / "SKILL.md"
        frontmatter = yaml.safe_load(skill_file.read_text(encoding="utf-8").split("---", 2)[1])
        descriptions[name] = frontmatter["description"]

    assert "candidate list" in descriptions["applicant-tech-patent-retrieval"]
    assert "per-document" in descriptions["evidence-based-labeling"]
    assert "technical route map" in descriptions["technology-insight-analysis"]
    assert "chronology" in descriptions["tech-evolution-analysis"]
    assert "early-warning signal register" in descriptions["black-swan-tech-radar"]


def test_business_skills_do_not_require_runtime_or_vendor_internals():
    forbidden = ("project_id", "P002", "P012", "D114")
    for name in PATENT_SKILLS:
        body = (SKILLS_ROOT / name / "SKILL.md").read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in body


def test_all_patent_skills_support_clarification_and_artifact_handoff():
    required_tools = {"ask_clarification", "write_file", "str_replace", "present_files"}
    for name in PATENT_SKILLS:
        parsed = parse_skill_file(SKILLS_ROOT / name / "SKILL.md", SkillCategory.PUBLIC, Path(name))
        assert parsed is not None
        assert required_tools <= set(parsed.allowed_tools or ())
        body = parsed.skill_file.read_text(encoding="utf-8")
        assert "schema_version" in body
        assert "schema_version: 2.0.0" in body
        assert "analysis_id" in body
        assert "status" in body

    labeling = (SKILLS_ROOT / "evidence-based-labeling" / "SKILL.md").read_text(encoding="utf-8")
    assert "do not use numeric confidence" in labeling


def test_runtime_manifest_and_schema_are_version_aligned():
    manifest = json.loads((CONTRACT_ROOT / "manifest.json").read_text(encoding="utf-8"))
    schema = json.loads((CONTRACT_ROOT / "v2" / "runtime-contract.schema.json").read_text(encoding="utf-8"))

    assert manifest["release"] == "2.0.0"
    assert manifest["runtime_contract"] == "2.0.0"
    assert set(manifest["skills"]) == PATENT_SKILLS
    assert schema["properties"]["schema_version"]["const"] == "2.0.0"
    assert manifest["runtime_policy"]["general_subagent_delegation"] is False

    for name, release in manifest["skills"].items():
        content = (SKILLS_ROOT / name / "SKILL.md").read_bytes()
        assert release["version"] == "2.0.0"
        assert release["sha256"] == hashlib.sha256(content).hexdigest()

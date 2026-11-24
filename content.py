"""Load the editable YAML catalog: roles, rubric, methods, sources, templates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from models import METHODS, ROLES

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

REQUIRED_BEAT_KEYS = (
    "stakeholder",
    "stakes_sentence",
    "question",
    "alternatives",
    "baseline",
    "heavier",
    "drop_rule",
    "assumption",
    "limitation",
    "action",
    "more_resources",
    "sample_plan",
    "cleaning",
    "skills_sentence",
)

IDEA_READY_BEATS = (
    "stakeholder",
    "stakes_sentence",
    "alternatives",
    "baseline",
    "heavier",
    "limitation",
    "action",
    "sample_plan",
)


def _read(name: str) -> Any:
    path = DATA / name
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_catalog() -> dict[str, Any]:
    roles_doc = _read("roles.yaml")
    rubric = _read("rubric.yaml")
    methods_doc = _read("methods.yaml")
    sources_doc = _read("sources.yaml")
    templates_doc = _read("templates.yaml")

    roles = {role["id"]: role for role in roles_doc["roles"]}
    sources = sources_doc["sources"]
    templates = templates_doc["templates"]
    catalog = {
        "roles": roles,
        "role_order": [role["id"] for role in roles_doc["roles"]],
        "criteria": rubric["criteria"],
        "spider_fields": rubric["spider_fields"],
        "acts": rubric["acts"],
        "pitfalls": rubric["pitfalls"],
        "dataset_checks": rubric["dataset_checks"],
        "methods": methods_doc["methods"],
        "methods_by_id": {method["id"]: method for method in methods_doc["methods"]},
        "groups": sources_doc["groups"],
        "sources": sources,
        "sources_by_id": {source["id"]: source for source in sources},
        "avoid_sources": [source for source in sources if source.get("avoid")],
        "templates": templates,
        "templates_by_id": {template["id"]: template for template in templates},
    }
    validate_catalog(catalog)
    return catalog


def validate_catalog(catalog: dict[str, Any]) -> None:
    if tuple(catalog["role_order"]) != ROLES:
        raise ValueError(f"V1 roles must be exactly {ROLES}.")
    criterion_ids = [item["id"] for item in catalog["criteria"]]
    if len(criterion_ids) != 8 or len(set(criterion_ids)) != 8:
        raise ValueError("The rubric needs exactly 8 criteria.")
    if [method["id"] for method in catalog["methods"]] != list(METHODS):
        raise ValueError(f"Methods must be {METHODS}.")

    for role_id, role in catalog["roles"].items():
        total = sum(int(role["weights"][key]) for key in criterion_ids)
        if total != 100:
            raise ValueError(f"{role_id} weights sum to {total}, not 100.")
        missing = [key for key in criterion_ids if key not in role["weights"]]
        if missing:
            raise ValueError(f"{role_id} is missing weights for {missing}.")
        unknown = [key for key in role["priority_criteria"] if key not in criterion_ids]
        if unknown:
            raise ValueError(f"{role_id} has unknown priority criteria {unknown}.")
        for key in REQUIRED_BEAT_KEYS:
            if not (role.get("defaults") or {}).get(key):
                raise ValueError(f"{role_id} defaults are missing {key}.")

    if len(catalog["templates"]) != 6:
        raise ValueError("V1 ships exactly six templates.")
    for role_id in ROLES:
        owned = [item for item in catalog["templates"] if item["role"] == role_id]
        if len(owned) != 2:
            raise ValueError(f"{role_id} should have 2 templates, found {len(owned)}.")
        for template in owned:
            source = catalog["sources_by_id"].get(template["dataset_id"])
            if source is None:
                raise ValueError(f"Template {template['id']} points at an unknown dataset.")
            if role_id not in source["suits_roles"]:
                raise ValueError(f"Template {template['id']} dataset does not suit {role_id}.")
            for letter in (
                "summary_impact",
                "problem_space",
                "investigation_insights",
                "data",
                "execution",
                "results_recommendations",
                "act1",
                "act2",
                "act3",
            ):
                if not (template.get("prompts") or {}).get(letter):
                    raise ValueError(f"Template {template['id']} is missing the {letter} prompt.")

    from scoring import extract_row_estimates

    for source in catalog["sources"]:
        for role_id in source.get("suits_roles") or []:
            if role_id not in ROLES:
                raise ValueError(f"{source['id']} is tagged with a non-v1 role: {role_id}.")
        if source.get("avoid") and source.get("idea_ready"):
            raise ValueError(f"Avoid source {source['id']} cannot be idea-ready.")
        idea_roles = source.get("idea_roles") or []
        for role_id in idea_roles:
            if role_id not in (source.get("suits_roles") or []):
                raise ValueError(f"{source['id']} idea_roles includes {role_id}, which is not in suits_roles.")
        if source.get("idea_ready"):
            beats = source.get("beats") or {}
            missing = [key for key in IDEA_READY_BEATS if not beats.get(key)]
            if missing:
                raise ValueError(f"{source['id']} is idea-ready but missing beats: {missing}.")
            if not source.get("example_question") or not source.get("project_title"):
                raise ValueError(f"{source['id']} needs example_question and project_title.")
            estimates = extract_row_estimates(beats["sample_plan"])
            in_range = [value for value in estimates if 10_000 <= value <= 10_000_000]
            if source.get("size_rule") != "in_range" and not in_range:
                raise ValueError(f"{source['id']} sample_plan needs an in-range row count.")

    import re

    for item in catalog["pitfalls"]["overused"]["datasets"]:
        re.compile(item["pattern"])
    for source in catalog["avoid_sources"]:
        if source.get("mention_pattern"):
            re.compile(source["mention_pattern"])

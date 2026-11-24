"""Fill the blank README template from a scored brief."""

from __future__ import annotations

from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
TEMPLATE_PATH = ROOT / "templates" / "readme_blank.md"


def load_blank_template() -> str:
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def _bullets(items: list[str], empty: str = "None") -> str:
    cleaned = [item.strip() for item in items if item and item.strip()]
    if not cleaned:
        return f"- {empty}"
    return "\n".join(f"- {item}" for item in cleaned)


def _check_line(checks: list[dict[str, Any]], check_id: str) -> str:
    for check in checks:
        if check["id"] == check_id:
            status = "Pass" if check["passed"] else "Fail"
            return f"{status}. {check['detail']}"
    return "Not run."


def render_readme(
    profile: dict[str, Any],
    idea: dict[str, Any],
    dataset: dict[str, Any],
    brief: dict[str, Any],
    evaluation: dict[str, Any],
) -> str:
    scorecard = evaluation["scorecard"]
    flags = evaluation["flags"]
    checks = evaluation["dataset_checks"]
    rows = []
    for score in scorecard["scores"]:
        evidence = (score["evidence"] or "").replace("|", "/")
        rows.append(f"| {score['criterion']} | {score['level']} | {evidence} |")
    skills = idea.get("skills") or profile.get("must_have_skills") or []
    skill_lines = _bullets([str(skill) for skill in skills], empty="Not stated yet")
    gaps = scorecard.get("priority_gaps") or []
    open_items = list(flags.get("pitfalls") or []) + list(flags.get("dataset_flags") or [])
    more = (brief.get("more_resources") or "").strip() or "Not stated yet."
    mapping = {
        "project_title": idea.get("title") or "Untitled portfolio project",
        "role": profile.get("target_role") or "",
        "method": idea.get("method") or "",
        "dataset_name": (dataset or {}).get("name") or "Unspecified dataset",
        "dataset_url": (dataset or {}).get("source_url") or "",
        "summary_impact": (brief.get("summary_impact") or "").strip(),
        "problem_space": (brief.get("problem_space") or "").strip(),
        "investigation_insights": (brief.get("investigation_insights") or "").strip(),
        "data": (brief.get("data") or "").strip(),
        "execution": (brief.get("execution") or "").strip(),
        "results_recommendations": (brief.get("results_recommendations") or "").strip(),
        "act1": (brief.get("act1") or "").strip(),
        "act2": (brief.get("act2") or "").strip(),
        "act3": (brief.get("act3") or "").strip(),
        "size_check": _check_line(checks, "size"),
        "business_check": _check_line(checks, "business"),
        "showcase_check": _check_line(checks, "showcase"),
        "story_check": _check_line(checks, "story"),
        "skills_bullets": skill_lines,
        "scorecard_rows": "\n".join(rows),
        "pass_bar": "met" if scorecard.get("pass_bar_met") else "not met",
        "priority_gaps": ", ".join(gaps) if gaps else "none",
        "open_flags": _bullets(open_items),
        "more_resources": more,
    }
    text = load_blank_template()
    for key, value in mapping.items():
        text = text.replace("{{" + key + "}}", value)
    return text.strip() + "\n"

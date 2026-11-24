"""Deterministic rubric, pitfall, and dataset checks.

Levels come from tunable token lists in data/rubric.yaml. A template prompt
that is still sitting unchanged in a field does not count as evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

LO = 10_000
HI = 10_000_000
RANK = {"weak": 0, "developing": 1, "ready": 2}
POINTS = {"weak": 0.0, "developing": 0.5, "ready": 1.0}

SAMPLE_RE = re.compile(
    r"\b(sample|sampled|sampling|filter|filtered|slice|one month|one borough|one category|subset)\b",
    re.I,
)
WINDOW_RE = re.compile(r"10\s*k|10,000|10\s*million|10\s*m\b", re.I)
RANGE_PHRASE_RE = re.compile(
    r"10\s*k\s*(?:[\u2013\u2014\-]|to)\s*10\s*m",
    re.I,
)
ROW_WORD_RE = re.compile(
    r"rows|records|orders|reviews|complaints|trips|passengers|flights|applications|ratings|inspections|reports",
    re.I,
)


def pattern_to_regex(token: str) -> str:
    token = token.strip()
    if token.endswith("*"):
        return rf"\b{re.escape(token[:-1])}\w*"
    return rf"\b{re.escape(token)}\b"


def text_has(token: str, text: str) -> bool:
    return re.search(pattern_to_regex(token), text or "", re.I) is not None


def count_tokens(tokens: list[str], text: str) -> int:
    return sum(1 for token in tokens if text_has(token, text))


def group_hits(groups: list[list[str]], text: str) -> int:
    hits = 0
    for group in groups:
        if any(text_has(token, text) for token in group):
            hits += 1
    return hits


def _field_text(brief: dict[str, Any], fields: list[str]) -> str:
    return "\n".join((brief.get(field) or "") for field in fields)


def substantive_brief(brief: dict[str, Any], template: dict[str, Any] | None) -> dict[str, Any]:
    """Drop fields that are still the untouched template prompt."""
    prompts = (template or {}).get("prompts") or {}
    cleaned = dict(brief)
    for key, value in list(cleaned.items()):
        prompt = (prompts.get(key) or "").strip()
        if prompt and (value or "").strip() == prompt:
            cleaned[key] = ""
    return cleaned


def echoed_fields(brief: dict[str, Any], template: dict[str, Any] | None) -> list[str]:
    prompts = (template or {}).get("prompts") or {}
    echoed = []
    for key, prompt in prompts.items():
        if prompt and (brief.get(key) or "").strip() == prompt.strip():
            echoed.append(key)
    return echoed


def extract_row_estimates(text: str) -> list[int]:
    """Pull stated row counts. Ignores the bare 10k–10M rule phrase and bare years."""
    if not text:
        return []
    scrubbed = RANGE_PHRASE_RE.sub(" ", text)
    found: list[int] = []
    for match in re.finditer(
        r"(\d+(?:\.\d+)?)\s*(billion|million|k\b|m\b)",
        scrubbed,
        re.I,
    ):
        number = float(match.group(1))
        unit = match.group(2).lower()
        multiplier = {"billion": 1_000_000_000, "million": 1_000_000, "k": 1_000, "m": 1_000_000}[unit]
        found.append(int(number * multiplier))
    for match in re.finditer(r"\b(\d{1,3}(?:,\d{3})+|\d{2,9})\b", scrubbed):
        raw = match.group(1)
        value = int(raw.replace(",", ""))
        if value < 10:
            continue
        if "," not in raw and value < LO:
            window = scrubbed[max(0, match.start() - 40) : match.end() + 40]
            if not ROW_WORD_RE.search(window):
                continue
        found.append(value)
    # Preserve order, drop duplicates.
    seen: set[int] = set()
    unique: list[int] = []
    for value in found:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


def commits_to_window(text: str, estimates: list[int]) -> bool:
    if any(LO <= value <= HI for value in estimates):
        return True
    return bool(SAMPLE_RE.search(text or "") and WINDOW_RE.search(text or ""))


def _size_from_estimates(estimates: list[int], text: str) -> tuple[bool, str] | None:
    if not estimates:
        return None
    in_range = [value for value in estimates if LO <= value <= HI]
    over = [value for value in estimates if value > HI]
    under = [value for value in estimates if value < LO]
    if in_range:
        shown = in_range[0]
        return True, f"About {shown:,} rows, inside 10k–10M."
    if over and commits_to_window(text, estimates):
        return True, "The brief commits to a 10k–10M sample of a larger source."
    if over:
        return (
            False,
            f"About {over[0]:,} rows is above 10M. Sample or filter into 10k–10M, and state the sample size.",
        )
    if under:
        return (
            False,
            f"About {under[0]:,} rows is under 10k. Combine files or pick a larger extract.",
        )
    return None


def check_size(dataset: dict[str, Any], brief: dict[str, Any]) -> dict[str, Any]:
    text = f"{brief.get('data') or ''}\n{brief.get('summary_impact') or ''}"
    estimates = extract_row_estimates(text)
    stated = _size_from_estimates(estimates, text)
    if stated is not None:
        passed, detail = stated
        return {"id": "size", "name": "Size (10k–10M)", "passed": passed, "detail": detail}

    rule = dataset.get("size_rule") or "unknown"
    typical = (dataset.get("typical_rows") or "").strip()
    if rule == "in_range":
        detail = "Catalog size sits inside 10k–10M if you follow the source note."
        if typical:
            detail = f"{detail} {typical}"
        return {"id": "size", "name": "Size (10k–10M)", "passed": True, "detail": detail}
    if rule == "must_sample":
        if commits_to_window(text, estimates):
            return {
                "id": "size",
                "name": "Size (10k–10M)",
                "passed": True,
                "detail": "The brief commits to a sample inside 10k–10M.",
            }
        return {
            "id": "size",
            "name": "Size (10k–10M)",
            "passed": False,
            "detail": f"This source is too large to use whole. Sample into 10k–10M. {typical}".strip(),
        }
    if rule == "too_small":
        return {
            "id": "size",
            "name": "Size (10k–10M)",
            "passed": False,
            "detail": f"This source is under 10k rows on its own. Stack or join it into range. {typical}".strip(),
        }
    return {
        "id": "size",
        "name": "Size (10k–10M)",
        "passed": False,
        "detail": "Row count is unknown. State an estimate inside 10k–10M, or name the slice you will keep.",
    }


def has_business_context(text: str, catalog: dict[str, Any]) -> bool:
    spec = catalog["pitfalls"]["no_business_context"]
    return count_tokens(spec["who_tokens"], text) > 0 and count_tokens(spec["why_tokens"], text) > 0


def business_text(brief: dict[str, Any]) -> str:
    return "\n".join(
        brief.get(key) or ""
        for key in ("summary_impact", "problem_space", "act1", "results_recommendations")
    )


def check_business(brief: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    if has_business_context(business_text(brief), catalog):
        return {
            "id": "business",
            "name": "Business relevance",
            "passed": True,
            "detail": "A stakeholder and the stakes are both in the brief.",
        }
    return {
        "id": "business",
        "name": "Business relevance",
        "passed": False,
        "detail": "Name who cares and the cost, risk, or decision that changes if the work is ignored.",
    }


def check_showcase(
    brief: dict[str, Any],
    role: dict[str, Any],
    idea: dict[str, Any],
    catalog: dict[str, Any],
) -> dict[str, Any]:
    keywords = role.get("showcase_keywords") or []
    skills = ", ".join(idea.get("skills") or [])
    text = "\n".join(
        [
            brief.get("execution") or "",
            brief.get("data") or "",
            brief.get("summary_impact") or "",
            skills,
        ]
    )
    hits = [token for token in keywords if text_has(token, text)]
    viz_tokens = catalog["pitfalls"]["visualization_only"]["viz_tokens"]
    viz_hits = count_tokens(viz_tokens, text)
    if hits and viz_hits < 2:
        return {
            "id": "showcase",
            "name": "Technical showcase",
            "passed": True,
            "detail": f"Can show {hits[0].rstrip('*')} for this role.",
        }
    if hits and viz_hits >= 2:
        # Charts are fine when a real skill is also present.
        return {
            "id": "showcase",
            "name": "Technical showcase",
            "passed": True,
            "detail": f"Can show {hits[0].rstrip('*')} for this role, beyond the charts.",
        }
    examples = ", ".join(role.get("emphasized_skills") or []) or "a must-have skill for this role"
    return {
        "id": "showcase",
        "name": "Technical showcase",
        "passed": False,
        "detail": f"Add a must-have skill for this role beyond a single chart. For example: {examples}.",
    }


def check_story(brief: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    spec = catalog["dataset_checks"]["story"]
    acts = [brief.get("act1") or "", brief.get("act2") or "", brief.get("act3") or ""]
    min_chars = int(spec.get("min_chars", 60))
    long_enough = all(len(act.strip()) >= min_chars for act in acts)
    beats = [
        count_tokens(spec["act1_tokens"], acts[0]) > 0,
        count_tokens(spec["act2_tokens"], acts[1]) > 0,
        count_tokens(spec["act3_tokens"], acts[2]) > 0,
    ]
    if long_enough and all(beats):
        return {
            "id": "story",
            "name": "Story test",
            "passed": True,
            "detail": "Act 1 has stakes, Act 2 has a journey, and Act 3 has an action.",
        }
    return {
        "id": "story",
        "name": "Story test",
        "passed": False,
        "detail": "Write all three acts: stakes, what you will try and drop, and the action a stakeholder takes.",
    }


def extra_dataset_flags(brief: dict[str, Any], dataset: dict[str, Any], catalog: dict[str, Any]) -> list[str]:
    blob = " ".join(
        [
            brief.get("data") or "",
            brief.get("summary_impact") or "",
            dataset.get("name") or "",
            dataset.get("notes") or "",
        ]
    )
    flags = []
    for item in catalog.get("avoid_sources") or []:
        if not item.get("flag_message"):
            continue
        if item.get("counts_as_overused_pitfall"):
            continue
        pattern = item.get("mention_pattern")
        if pattern and re.search(pattern, blob, re.I):
            flags.append(item["flag_message"])
    return flags


def dataset_checks(
    brief: dict[str, Any],
    dataset: dict[str, Any],
    role: dict[str, Any],
    idea: dict[str, Any],
    catalog: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        check_size(dataset, brief),
        check_business(brief, catalog),
        check_showcase(brief, role, idea, catalog),
        check_story(brief, catalog),
    ]


def overused_hits(text: str, catalog: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    for item in catalog["pitfalls"]["overused"]["datasets"]:
        if re.search(item["pattern"], text or "", re.I):
            if item["label"] not in labels:
                labels.append(item["label"])
    return labels


def has_new_angle(text: str, catalog: dict[str, Any]) -> bool:
    lowered = (text or "").lower()
    return any(phrase in lowered for phrase in catalog["pitfalls"]["overused"]["new_angle_phrases"])


def detect_pitfalls(
    brief: dict[str, Any],
    idea: dict[str, Any],
    dataset: dict[str, Any],
    catalog: dict[str, Any],
) -> list[str]:
    pitfalls = catalog["pitfalls"]
    brief_blob = "\n".join(str(brief.get(key) or "") for key in brief)
    project_blob = "\n".join(
        [
            brief_blob,
            idea.get("title") or "",
            idea.get("one_liner") or "",
            idea.get("problem") or "",
            idea.get("data_angle") or "",
            dataset.get("name") or "",
        ]
    )
    found: list[str] = []

    viz = pitfalls["visualization_only"]
    if count_tokens(viz["viz_tokens"], brief_blob) >= int(viz.get("min_viz", 1)) and count_tokens(
        viz["substance_tokens"], brief_blob
    ) == 0:
        found.append(
            "Visualization-only: charts or EDA with no why, drivers, or next steps."
        )

    labels = overused_hits(project_blob, catalog)
    if labels and not has_new_angle(project_blob, catalog):
        joined = ", ".join(labels)
        found.append(
            f"Overused dataset, no new angle: {joined} without a genuinely new question. "
            "Pick a shortlist dataset, or state the new angle in the brief."
        )

    business = pitfalls["no_business_context"]
    if not has_business_context(business_text(brief), catalog):
        found.append(
            "No business context: the brief never answers who cares, why it matters, or what decision changes."
        )

    tutorial = pitfalls["tutorial_clone"]
    clone_hit = any(text_has(token, brief_blob) for token in tutorial["clone_tokens"])
    original_hit = any(text_has(token, brief_blob) for token in tutorial["originality_tokens"])
    if clone_hit and not original_hit:
        found.append(
            "Tutorial clone: polished walkthrough shape with no record of an original decision or what you dropped."
        )

    # `business` is referenced so a mis-edited rubric key fails loudly in tests.
    if not business.get("label"):
        raise ValueError("no_business_context.label missing from rubric")
    return found


def _criterion_level(spec: dict[str, Any], text: str) -> str:
    stripped = text.strip()
    if len(stripped) < int(spec.get("weak_below_chars", 80)):
        return "weak"
    hits = group_hits(spec.get("groups") or [], stripped)
    if hits >= int(spec.get("ready_min_groups", 2)) and len(stripped) >= int(spec.get("ready_min_chars", 140)):
        return "ready"
    if hits >= 1 or len(stripped) >= int(spec.get("developing_min_chars", 80)):
        return "developing"
    return "weak"


def _evidence(spec: dict[str, Any], level: str, text: str) -> str:
    base = (spec.get("evidence") or {}).get(level) or level
    snippet = ""
    if text.strip() and level != "weak":
        snippet = text.strip().split(".")[0][:140].strip()
    if snippet:
        return f'{base} Seen in: "{snippet}."'
    return base


def score_criterion(spec: dict[str, Any], brief: dict[str, Any], role: dict[str, Any]) -> dict[str, Any]:
    text = _field_text(brief, spec.get("fields") or [])
    level = _criterion_level(spec, text)
    criterion_id = spec["id"]
    return {
        "criterion_id": criterion_id,
        "criterion": spec["name"],
        "level": level,
        "evidence": _evidence(spec, level, text),
        "weight": float(role["weights"][criterion_id]),
        "priority": criterion_id in role["priority_criteria"],
    }


def pass_bar_met(scores: list[dict[str, Any]]) -> bool:
    if any(score["level"] == "weak" for score in scores):
        return False
    return sum(score["level"] == "ready" for score in scores) >= 6


def priority_gap_names(scores: list[dict[str, Any]]) -> list[str]:
    return [score["criterion"] for score in scores if score.get("priority") and score["level"] != "ready"]


def weighted_score(scores: list[dict[str, Any]]) -> float:
    return sum(float(score["weight"]) * POINTS[score["level"]] for score in scores)


def finish_scorecard(scores: list[dict[str, Any]], role_id: str, weights: dict[str, float]) -> dict[str, Any]:
    return {
        "scores": scores,
        "role": role_id,
        "weights": weights,
        "pass_bar_met": pass_bar_met(scores),
        "priority_gaps": priority_gap_names(scores),
        "weighted": weighted_score(scores),
        "ready_count": sum(score["level"] == "ready" for score in scores),
        "weak_count": sum(score["level"] == "weak" for score in scores),
    }


def score_brief(brief: dict[str, Any], role: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    scores = [score_criterion(spec, brief, role) for spec in catalog["criteria"]]
    return finish_scorecard(scores, role["id"], dict(role["weights"]))


def evaluate(
    profile: dict[str, Any],
    idea: dict[str, Any],
    brief: dict[str, Any],
    dataset: dict[str, Any],
    catalog: dict[str, Any],
) -> dict[str, Any]:
    role = catalog["roles"][profile["target_role"]]
    template = None
    if idea.get("template_id"):
        template = catalog["templates_by_id"].get(idea["template_id"])
    cleaned = substantive_brief(brief, template)
    scorecard = score_brief(cleaned, role, catalog)
    checks = dataset_checks(cleaned, dataset or {}, role, idea, catalog)
    pitfalls = detect_pitfalls(cleaned, idea, dataset or {}, catalog)
    dataset_flags = [f"{check['name']}: {check['detail']}" for check in checks if not check["passed"]]
    dataset_flags.extend(extra_dataset_flags(cleaned, dataset or {}, catalog))
    clear = bool(scorecard["pass_bar_met"]) and not pitfalls and not dataset_flags
    return {
        "scorecard": scorecard,
        "flags": {
            "pitfalls": pitfalls,
            "dataset_flags": dataset_flags,
            "clear_to_export": clear,
        },
        "dataset_checks": checks,
    }


def merge_scores(local_scores: list[dict[str, Any]], remote_scores: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Keep the stricter level. Polished AI notes cannot raise a weak rubric score."""
    if not remote_scores:
        return local_scores
    by_id = {item.get("criterion_id"): item for item in remote_scores if item.get("criterion_id")}
    by_name = {str(item.get("criterion", "")).strip().lower(): item for item in remote_scores}
    merged: list[dict[str, Any]] = []
    for local in local_scores:
        remote = by_id.get(local["criterion_id"]) or by_name.get(local["criterion"].lower())
        remote_level = (remote or {}).get("level", "")
        remote_level = str(remote_level).strip().lower()
        evidence = str((remote or {}).get("evidence") or "").strip()
        if remote_level not in RANK or not evidence:
            merged.append(local)
            continue
        chosen = dict(local)
        if RANK[remote_level] < RANK[local["level"]]:
            chosen["level"] = remote_level
            chosen["evidence"] = evidence
        elif RANK[remote_level] == RANK[local["level"]]:
            chosen["evidence"] = evidence
        else:
            chosen["evidence"] = (
                local["evidence"] + " A draft AI note was more generous, so the rubric level stands."
            )
        merged.append(chosen)
    return merged


def merge_pitfalls(local: list[str], remote: list[str] | None) -> list[str]:
    merged = list(local)
    for item in remote or []:
        text = str(item).strip()
        if not text:
            continue
        lowered = text.lower()
        if any(lowered in current.lower() or current.lower() in lowered for current in merged):
            continue
        merged.append(text)
    return merged


def apply_remote_evaluation(local: dict[str, Any], remote: dict[str, Any] | None) -> dict[str, Any]:
    if not remote:
        return local
    remote_card = remote.get("scorecard") or {}
    remote_flags = remote.get("flags") or {}
    scores = merge_scores(local["scorecard"]["scores"], remote_card.get("scores"))
    # Recompute weights and the pass bar from the merged levels. Never trust the model boolean.
    role_id = local["scorecard"]["role"]
    weights = local["scorecard"]["weights"]
    # priority flags already live on the local scores and are copied by merge_scores.
    scorecard = finish_scorecard(scores, role_id, weights)
    pitfalls = merge_pitfalls(local["flags"]["pitfalls"], remote_flags.get("pitfalls"))
    dataset_flags = list(local["flags"]["dataset_flags"])
    clear = bool(scorecard["pass_bar_met"]) and not pitfalls and not dataset_flags
    return {
        "scorecard": scorecard,
        "flags": {
            "pitfalls": pitfalls,
            "dataset_flags": dataset_flags,
            "clear_to_export": clear,
        },
        "dataset_checks": local["dataset_checks"],
    }


def fingerprint(brief: dict[str, Any], dataset: dict[str, Any] | None, idea_id: str | None) -> str:
    dataset = dataset or {}
    payload = {
        "brief": {key: brief.get(key, "") for key in (
            "summary_impact",
            "problem_space",
            "investigation_insights",
            "data",
            "execution",
            "results_recommendations",
            "act1",
            "act2",
            "act3",
            "more_resources",
        )},
        "dataset": {
            "id": dataset.get("id"),
            "name": dataset.get("name"),
            "source_url": dataset.get("source_url"),
            "typical_rows": dataset.get("typical_rows"),
            "size_rule": dataset.get("size_rule"),
        },
        "idea_id": idea_id,
    }
    encoded = json.dumps(payload, sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def weak_example() -> tuple[dict[str, str], dict[str, Any]]:
    """A deliberately poor brief used to demo every pitfall."""
    brief = {
        "summary_impact": "I will make dashboards and heatmaps of the Titanic dataset.",
        "problem_space": "It is a famous dataset from a tutorial.",
        "investigation_insights": "The charts show who survived.",
        "data": "Titanic, about 891 rows.",
        "execution": "I followed a kaggle kernel and made plots.",
        "results_recommendations": "The graphs look good.",
        "act1": "The ship sank.",
        "act2": "I plotted the charts.",
        "act3": "See the dashboard.",
        "more_resources": "",
    }
    dataset = {
        "id": "custom",
        "name": "Titanic",
        "source_url": "https://www.kaggle.com/c/titanic",
        "domain": "Tutorial",
        "typical_rows": "891 passengers",
        "suits_roles": ["data_analyst"],
        "notes": "Classic tutorial set.",
        "size_rule": "unknown",
        "avoid": True,
        "group": "avoid",
    }
    return brief, dataset

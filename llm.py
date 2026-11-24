"""Four structured LLM calls, with a template fallback when no API key is set."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from ideas import draft_local, generate_local, public_dataset
from models import Dataset, ProjectIdea, SPIDERBrief
from scoring import apply_remote_evaluation, evaluate

ROOT = Path(__file__).resolve().parent
SYSTEM_PROMPT_PATH = ROOT / "prompts" / "system.md"

AI_OFF_NOTE = (
    "AI generation is off. Ideas, drafts, and scores use the built-in templates "
    "and the deterministic rubric. Set OPENAI_API_KEY to turn AI on. "
    "OPENAI_MODEL and OPENAI_BASE_URL are optional."
)

ROLE_LABELS = {
    "data_analyst": "data analyst",
    "product_data_scientist": "product data scientist",
    "algorithm_data_scientist": "algorithm data scientist",
}


def _read_secrets() -> dict[str, str]:
    try:
        from streamlit.runtime.secrets import secrets_singleton

        if not secrets_singleton.load_if_toml_exists():
            return {}
        data = secrets_singleton.to_dict()
        return {str(key): str(value) for key, value in data.items() if isinstance(value, (str, int, float))}
    except Exception:
        return {}


def resolve_settings() -> dict[str, str]:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    model = os.environ.get("OPENAI_MODEL", "").strip()
    base = os.environ.get("OPENAI_BASE_URL", "").strip()
    if not (key and model and base):
        secrets = _read_secrets()
        key = key or str(secrets.get("OPENAI_API_KEY", "")).strip()
        model = model or str(secrets.get("OPENAI_MODEL", "")).strip()
        base = base or str(secrets.get("OPENAI_BASE_URL", "")).strip()
    return {"api_key": key, "model": model or "gpt-4o-mini", "base_url": base}


def ai_status() -> dict[str, Any]:
    settings = resolve_settings()
    return {
        "enabled": bool(settings["api_key"]),
        "model": settings["model"],
        "base_url": settings["base_url"],
    }


def system_prompt() -> str:
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def sanitize_error(exc: Exception) -> str:
    text = str(exc)
    text = re.sub(r"sk-[A-Za-z0-9_\-]+", "sk-…", text)
    text = re.sub(r"Bearer\s+[A-Za-z0-9._\-]+", "Bearer …", text)
    if len(text) > 280:
        text = text[:280] + "…"
    return text or exc.__class__.__name__


def _parse_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw).strip()
        raw = re.sub(r"```$", "", raw).strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end <= start:
            raise
        parsed = json.loads(raw[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Model response was not a JSON object.")
    return parsed


def _complete(user: str, temperature: float) -> str:
    from openai import OpenAI

    settings = resolve_settings()
    kwargs: dict[str, Any] = {"api_key": settings["api_key"]}
    if settings["base_url"]:
        kwargs["base_url"] = settings["base_url"]
    client = OpenAI(**kwargs)
    messages = [
        {"role": "system", "content": system_prompt()},
        {"role": "user", "content": user},
    ]
    base = {
        "model": settings["model"],
        "temperature": temperature,
        "messages": messages,
        "max_tokens": 3000,
    }
    try:
        response = client.chat.completions.create(**base, response_format={"type": "json_object"})
    except Exception:
        response = client.chat.completions.create(**base)
    content = response.choices[0].message.content or ""
    if not content.strip():
        raise ValueError("The model returned an empty response.")
    return content


def _coerce_role(value: Any, catalog: dict[str, Any]) -> str | None:
    text = str(value or "").strip()
    if text in catalog["roles"]:
        return text
    labels = {role["label"].lower(): role["id"] for role in catalog["roles"].values()}
    return labels.get(text.lower())


def _source_menu(catalog: dict[str, Any], role_id: str) -> list[dict[str, str]]:
    menu = []
    for source in catalog["sources"]:
        if source.get("avoid") or role_id not in source.get("suits_roles", []):
            continue
        if not source.get("idea_ready"):
            continue
        menu.append(
            {
                "id": source["id"],
                "name": source["name"],
                "source_url": source.get("source_url", ""),
                "typical_rows": source.get("typical_rows", ""),
                "size_rule": source.get("size_rule", ""),
                "example_question": source.get("example_question", ""),
            }
        )
    return menu


def _enrich_dataset(dataset: dict[str, Any] | None, catalog: dict[str, Any]) -> dict[str, Any] | None:
    if not dataset:
        return None
    name = dataset.get("name") or ""
    source_id = dataset.get("id")
    source = catalog["sources_by_id"].get(source_id) if source_id else None
    if source is None and name:
        lowered = name.lower()
        for candidate in catalog["sources"]:
            if candidate["name"].lower() == lowered or candidate["id"].lower() == lowered:
                source = candidate
                break
    if source is None:
        dataset.setdefault("size_rule", "unknown")
        dataset.setdefault("suits_roles", [])
        return dataset
    merged = public_dataset(source)
    for key in ("name", "source_url", "domain", "typical_rows", "notes"):
        if dataset.get(key):
            merged[key] = dataset[key]
    return merged


def _normalize_ideas(raw_ideas: list[Any], profile: dict[str, Any], method: str, inputs: dict[str, Any], catalog: dict[str, Any]) -> list[dict[str, Any]]:
    role_id = profile["target_role"]
    angle = _user_has_angle(profile, inputs, catalog)
    normalized: list[dict[str, Any]] = []
    for item in raw_ideas:
        if not isinstance(item, dict):
            continue
        item = dict(item)
        item["role"] = role_id
        item["method"] = method
        item.setdefault("id", f"llm-{len(normalized) + 1}")
        item.setdefault("skills", [])
        item.setdefault("one_liner", item.get("title") or "")
        item.setdefault("problem", "")
        item.setdefault("data_angle", "")
        suggested = item.get("suggested_dataset")
        if isinstance(suggested, dict):
            try:
                item["suggested_dataset"] = Dataset.model_validate(suggested).model_dump()
            except Exception:
                item["suggested_dataset"] = suggested
        item["suggested_dataset"] = _enrich_dataset(item.get("suggested_dataset"), catalog)
        template_id = item.get("template_id")
        template = catalog["templates_by_id"].get(template_id) if template_id else None
        if template is None or template["role"] != role_id:
            item["template_id"] = None
        elif item["suggested_dataset"] is None:
            item["suggested_dataset"] = public_dataset(catalog["sources_by_id"][template["dataset_id"]])
        try:
            idea = ProjectIdea.model_validate(item).model_dump()
        except Exception:
            continue
        blob = " ".join([idea["title"], idea["data_angle"], (idea.get("suggested_dataset") or {}).get("name") or ""])
        from scoring import overused_hits

        if overused_hits(blob, catalog) and not angle:
            continue
        dataset = idea.get("suggested_dataset") or {}
        if dataset and dataset.get("suits_roles") and role_id not in dataset["suits_roles"] and not dataset.get("avoid"):
            continue
        normalized.append(idea)
        if len(normalized) >= 5:
            break
    return normalized


def _user_has_angle(profile: dict[str, Any], inputs: dict[str, Any], catalog: dict[str, Any]) -> bool:
    from scoring import has_new_angle

    blob = "\n".join(
        [profile.get("background") or "", " ".join(str(value) for value in inputs.values())]
    )
    return has_new_angle(blob, catalog)


def _pad_ideas(ideas: list[dict[str, Any]], profile: dict[str, Any], method: str, inputs: dict[str, Any], catalog: dict[str, Any]) -> list[dict[str, Any]]:
    if len(ideas) >= 3:
        return ideas[:5]
    local, _notes = generate_local(profile, method, inputs, catalog)
    seen = {idea["title"].lower() for idea in ideas}
    for idea in local:
        if idea["title"].lower() in seen:
            continue
        ideas.append(idea)
        seen.add(idea["title"].lower())
        if len(ideas) >= 4:
            break
    for index, idea in enumerate(ideas, start=1):
        idea["id"] = idea.get("id") or f"{profile['target_role']}-{method}-{index}"
    return ideas[:5]


def run_generate(profile: dict[str, Any], method: str, inputs: dict[str, Any], catalog: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    local_ideas, notes = generate_local(profile, method, inputs, catalog)
    if not ai_status()["enabled"]:
        return local_ideas, {"source": "template", "message": AI_OFF_NOTE, "notes": notes, "model": None}
    payload = {
        "call": "generate_ideas",
        "profile": profile,
        "method": method,
        "method_inputs": inputs,
        "role_sources": _source_menu(catalog, profile["target_role"]),
        "template_ids": [item["id"] for item in catalog["templates"] if item["role"] == profile["target_role"]],
        "output_shape": {
            "ideas": [
                {
                    "id": "idea_1",
                    "title": "",
                    "method": method,
                    "role": profile["target_role"],
                    "one_liner": "",
                    "problem": "",
                    "data_angle": "",
                    "skills": [],
                    "template_id": None,
                    "suggested_dataset": {
                        "name": "",
                        "source_url": "",
                        "domain": "",
                        "typical_rows": "",
                        "suits_roles": [profile["target_role"]],
                        "notes": "",
                    },
                }
            ]
        },
    }
    try:
        parsed = _parse_json(
            _complete(
                "Return 4 ideas for this call. Use only the selected method and role. "
                "Prefer the role_sources list. Do not recommend Titanic, Iris, or Boston Housing "
                "unless the user text states a genuinely new angle.\n\n"
                + json.dumps(payload, indent=2),
                temperature=0.4,
            )
        )
        ideas = _normalize_ideas(parsed.get("ideas") or [], profile, method, inputs, catalog)
        ideas = _pad_ideas(ideas, profile, method, inputs, catalog)
        if len(ideas) < 3:
            raise ValueError("The model returned fewer than 3 usable ideas.")
        return ideas, {
            "source": "llm",
            "message": f"Ideas drafted with {resolve_settings()['model']}.",
            "notes": notes,
            "model": resolve_settings()["model"],
        }
    except Exception as exc:
        return local_ideas, {
            "source": "template",
            "message": f"AI request failed ({sanitize_error(exc)}). Showing built-in ideas instead.",
            "notes": notes,
            "model": None,
        }


def _brief_from_payload(payload: dict[str, Any]) -> dict[str, str]:
    raw = payload.get("brief") or payload
    brief = SPIDERBrief.model_validate(raw).model_dump()
    return {key: str(value or "") for key, value in brief.items()}


def run_draft(profile: dict[str, Any], idea: dict[str, Any], dataset: dict[str, Any], catalog: dict[str, Any]) -> tuple[dict[str, str], dict[str, Any]]:
    local = draft_local(profile, idea, dataset, catalog)
    if not ai_status()["enabled"]:
        return local, {"source": "template", "message": AI_OFF_NOTE, "model": None}
    template = catalog["templates_by_id"].get(idea.get("template_id") or "")
    payload = {
        "call": "draft_brief",
        "profile": profile,
        "idea": {key: idea.get(key) for key in ("title", "method", "role", "one_liner", "problem", "data_angle", "skills", "template_id")},
        "dataset": dataset,
        "template_prompts": (template or {}).get("prompts"),
    }
    try:
        parsed = _parse_json(
            _complete(
                "Draft a SPIDER brief and Three-Act outline as a plan, not a finished analysis. "
                "Fill summary_impact, problem_space, investigation_insights, data, execution, "
                "results_recommendations, act1, act2, act3, and more_resources. "
                "Keep the dataset inside 10k–10M rows.\n\n"
                + json.dumps({"output_shape": {"brief": local}, **payload}, indent=2),
                temperature=0.3,
            )
        )
        brief = _brief_from_payload(parsed)
        if not brief["summary_impact"] or not brief["problem_space"]:
            raise ValueError("The draft was missing Summary or Problem.")
        return brief, {"source": "llm", "message": f"Brief drafted with {resolve_settings()['model']}.", "model": resolve_settings()["model"]}
    except Exception as exc:
        return local, {
            "source": "template",
            "message": f"AI request failed ({sanitize_error(exc)}). Showing a starter draft from the templates instead.",
            "model": None,
        }


def _normalize_remote_scores(raw: Any, catalog: dict[str, Any]) -> list[dict[str, Any]]:
    scores = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("criterion") or "").strip()
        level = str(item.get("level") or "").strip().lower()
        evidence = str(item.get("evidence") or "").strip()
        match = next((spec for spec in catalog["criteria"] if spec["name"].lower() == name.lower() or spec["id"] == item.get("criterion_id")), None)
        if match is None or level not in {"weak", "developing", "ready"}:
            continue
        scores.append(
            {
                "criterion_id": match["id"],
                "criterion": match["name"],
                "level": level,
                "evidence": evidence,
            }
        )
    return scores


def run_evaluate(profile: dict[str, Any], idea: dict[str, Any], brief: dict[str, Any], dataset: dict[str, Any], catalog: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    local = evaluate(profile, idea, brief, dataset, catalog)
    if not ai_status()["enabled"]:
        return local, {"source": "template", "message": AI_OFF_NOTE, "model": None}
    payload = {
        "call": "evaluate",
        "profile": profile,
        "idea": idea,
        "brief": brief,
        "dataset": dataset,
        "weights": catalog["roles"][profile["target_role"]]["weights"],
        "priority_criteria": catalog["roles"][profile["target_role"]]["priority_criteria"],
    }
    try:
        parsed = _parse_json(
            _complete(
                "Score all 8 criteria as weak, developing, or ready. "
                "Return scorecard.scores with criterion, level, and evidence, plus flags.pitfalls. "
                "Do not claim the pass bar yourself; the app recomputes it.\n\n"
                + json.dumps(payload, indent=2),
                temperature=0.2,
            )
        )
        remote_scores = _normalize_remote_scores((parsed.get("scorecard") or {}).get("scores"), catalog)
        remote_flags = parsed.get("flags") or {}
        merged = apply_remote_evaluation(
            local,
            {"scorecard": {"scores": remote_scores}, "flags": {"pitfalls": remote_flags.get("pitfalls") or []}},
        )
        return merged, {
            "source": "llm",
            "message": f"Scored with the rubric and {resolve_settings()['model']}. The stricter level is kept.",
            "model": resolve_settings()["model"],
        }
    except Exception as exc:
        return local, {
            "source": "template",
            "message": f"AI request failed ({sanitize_error(exc)}). Scored with the deterministic rubric instead.",
            "model": None,
        }


def run_revise(
    profile: dict[str, Any],
    idea: dict[str, Any],
    brief: dict[str, Any],
    dataset: dict[str, Any],
    notes: str,
    catalog: dict[str, Any],
) -> tuple[dict[str, str], dict[str, Any], dict[str, Any]]:
    if not ai_status()["enabled"]:
        evaluation, meta = run_evaluate(profile, idea, brief, dataset, catalog)
        meta = {
            "source": "template",
            "message": "AI revise is off. Your current text was re-scored with the rubric. Edit the fields yourself, then score again.",
            "model": None,
        }
        return brief, evaluation, meta
    payload = {
        "call": "revise_brief",
        "profile": profile,
        "idea": idea,
        "brief": brief,
        "dataset": dataset,
        "revision_notes": notes,
    }
    try:
        parsed = _parse_json(
            _complete(
                "Revise the brief using the user's notes. Return brief (all SPIDER and act fields) "
                "and scorecard.scores. Do not write analysis code.\n\n"
                + json.dumps(payload, indent=2),
                temperature=0.3,
            )
        )
        revised = _brief_from_payload(parsed)
        for key, value in brief.items():
            if not str(revised.get(key) or "").strip():
                revised[key] = value
        evaluation, eval_meta = run_evaluate(profile, idea, revised, dataset, catalog)
        message = f"Revised with {resolve_settings()['model']}. {eval_meta['message']}"
        return revised, evaluation, {"source": "llm", "message": message, "model": resolve_settings()["model"]}
    except Exception as exc:
        evaluation = evaluate(profile, idea, brief, dataset, catalog)
        return brief, evaluation, {
            "source": "template",
            "message": f"AI request failed ({sanitize_error(exc)}). The current text was re-scored locally.",
            "model": None,
        }


def coerce_profile_role(value: Any, catalog: dict[str, Any]) -> str | None:
    return _coerce_role(value, catalog)

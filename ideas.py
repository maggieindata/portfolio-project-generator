"""Deterministic ideas and SPIDER drafts from the catalog."""

from __future__ import annotations

import re
from typing import Any

from scoring import has_new_angle, overused_hits

METHOD_SHORT = {
    "inventory_first": "Upgrade path for work you already have.",
    "skill_first": "Scoped to must-have skills from a target job description.",
    "problem_first": "Starts from a problem this role would own.",
    "data_first": "Starts from the dataset, then the question.",
}

METHOD_LINES = {
    "inventory_first": "This upgrades work I can already show, aimed at the gaps for this role.",
    "skill_first": "I chose the scope so it shows the must-have skills in the job description I am targeting.",
    "problem_first": "The problem and the stakes come first, and the dataset has to serve that decision.",
    "data_first": "I am starting from this dataset and keeping only a question that can carry a full story.",
}

VOICE_LINES = {
    "analyst": "The deliverable is a decision memo a stakeholder can use, not a gallery of charts and not a model showcase.",
    "product": "The deliverable is a ship, stop, or target decision a product lead can defend, including who is unaffected.",
    "algorithm": "The deliverable is a method choice against a baseline, with the error trade-off made explicit. I will not treat a leaderboard score as the decision.",
}

EXCERPT_KEYS = {
    "inventory_first": "existing_work",
    "skill_first": "job_description",
    "problem_first": "problem",
    "data_first": "why_interesting",
}


def public_dataset(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": source["id"],
        "name": source["name"],
        "source_url": source.get("source_url") or "",
        "domain": source.get("domain") or "",
        "typical_rows": source.get("typical_rows") or "",
        "suits_roles": list(source.get("suits_roles") or []),
        "notes": source.get("notes") or "",
        "size_rule": source.get("size_rule") or "unknown",
        "group": source.get("group") or "",
        "avoid": bool(source.get("avoid", False)),
    }


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        cleaned = (item or "").strip()
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        ordered.append(cleaned)
    return ordered


def clip(text: str, limit: int) -> str:
    squashed = " ".join((text or "").split())
    if len(squashed) <= limit:
        return squashed
    return squashed[: limit - 1].rstrip() + "…"


def user_blob(profile: dict[str, Any], inputs: dict[str, Any]) -> str:
    parts = [
        profile.get("background") or "",
        profile.get("target_industry") or "",
        " ".join(str(value) for value in (inputs or {}).values()),
    ]
    return "\n".join(parts)


def generation_notes(profile: dict[str, Any], inputs: dict[str, Any], catalog: dict[str, Any]) -> list[str]:
    blob = user_blob(profile, inputs)
    notes: list[str] = []
    for source in catalog["avoid_sources"]:
        pattern = source.get("mention_pattern")
        note = source.get("generation_note")
        if pattern and note and re.search(pattern, blob, re.I):
            notes.append(note)
    return notes


def _excerpt(method: str, inputs: dict[str, Any], catalog: dict[str, Any]) -> str:
    raw = inputs.get(EXCERPT_KEYS[method]) or ""
    text = " ".join(str(raw).split())
    if not text:
        return ""
    if overused_hits(text, catalog) and not has_new_angle(text, catalog):
        return ""
    return clip(text, 240)


def fill_beats(
    source: dict[str, Any] | None,
    role: dict[str, Any],
    template: dict[str, Any] | None = None,
) -> dict[str, str]:
    beats = dict(role["defaults"])
    if source:
        beats.update({key: value for key, value in (source.get("beats") or {}).items() if value})
        if source.get("example_question"):
            beats["question"] = source["example_question"].rstrip("?")
        if source.get("beats", {}).get("sample_plan"):
            beats["sample_plan"] = source["beats"]["sample_plan"]
    if template and template.get("beats"):
        beats.update({key: value for key, value in template["beats"].items() if value})
    for key, value in list(beats.items()):
        beats[key] = str(value).strip()
    return beats


def idea_skills(
    source: dict[str, Any],
    template: dict[str, Any] | None,
    role: dict[str, Any],
    method: str,
    inputs: dict[str, Any],
    profile: dict[str, Any],
) -> list[str]:
    if template and template.get("skills"):
        skills = list(template["skills"])
    else:
        skills = list(source.get("skills") or role["emphasized_skills"])
    for skill in role["emphasized_skills"]:
        if skill not in skills:
            skills.append(skill)
    if method == "skill_first":
        blob = f"{inputs.get('job_description') or ''} {inputs.get('skills_to_prove') or ''}"
        front: list[str] = []
        for skill in list(profile.get("must_have_skills") or []) + [
            piece.strip() for piece in (inputs.get("skills_to_prove") or "").split(",")
        ]:
            if skill and skill.lower() in blob.lower():
                front.append(skill)
        skills = front + skills
    return _unique(skills)[:8]


def build_idea(
    source: dict[str, Any],
    role: dict[str, Any],
    method: str,
    profile: dict[str, Any],
    inputs: dict[str, Any],
    catalog: dict[str, Any],
    template: dict[str, Any] | None = None,
) -> dict[str, Any]:
    beats = fill_beats(source, role, template)
    title = template["title"] if template else source["project_title"]
    question = beats["question"].rstrip("?")
    excerpt = _excerpt(method, inputs, catalog)
    problem = (
        f"The stakeholder is {beats['stakeholder']}. {beats['stakes_sentence']} "
        f"The question: {question}."
    )
    if excerpt:
        problem += f" Starting point: {excerpt}"
    skills = idea_skills(source, template, role, method, inputs, profile)
    return {
        "id": "",
        "title": title,
        "method": method,
        "role": role["id"],
        "one_liner": f"{question}? {METHOD_SHORT[method]}",
        "problem": problem,
        "data_angle": f"{source['name']}: {source.get('typical_rows') or beats['sample_plan']}",
        "skills": skills,
        "suggested_dataset": public_dataset(source),
        "template_id": template["id"] if template else None,
    }


def _match_source(query: str, sources: list[dict[str, Any]]) -> dict[str, Any] | None:
    import re

    raw = " ".join((query or "").lower().split())
    if len(raw) < 3:
        return None
    exact = [
        source
        for source in sources
        if source["id"].lower() == raw or source["name"].lower() == raw
    ]
    if exact:
        return exact[0]
    hits = []
    for source in sources:
        name = source["name"].lower()
        ident = source["id"].lower().replace("_", " ")
        if len(name) >= 6 and name in raw:
            hits.append(source)
        elif len(ident) >= 3 and re.search(rf"\b{re.escape(ident)}\b", raw):
            hits.append(source)
    if not hits:
        return None
    return max(hits, key=lambda source: len(source["name"]))


def generate_local(
    profile: dict[str, Any],
    method: str,
    inputs: dict[str, Any] | None,
    catalog: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    inputs = inputs or {}
    role = catalog["roles"][profile["target_role"]]
    notes = generation_notes(profile, inputs, catalog)
    templates = [item for item in catalog["templates"] if item["role"] == role["id"]]
    pool = []
    for source in catalog["sources"]:
        if not source.get("idea_ready") or source.get("avoid"):
            continue
        if role["id"] not in source.get("suits_roles", []):
            continue
        idea_roles = source.get("idea_roles")
        if idea_roles is not None and role["id"] not in idea_roles:
            continue
        pool.append(source)
    pool.sort(key=lambda source: (int(source.get("idea_rank", 1000)), source["id"]))

    ideas: list[dict[str, Any]] = []
    used: set[str] = set()
    for template in templates:
        source = catalog["sources_by_id"][template["dataset_id"]]
        ideas.append(build_idea(source, role, method, profile, inputs, catalog, template))
        used.add(source["id"])
    for source in pool:
        if source["id"] in used:
            continue
        ideas.append(build_idea(source, role, method, profile, inputs, catalog, None))
        used.add(source["id"])
        if len(ideas) >= 4:
            break

    hint = (inputs.get("dataset_hint") or "").strip()
    if method == "data_first" and hint:
        hinted = _match_source(hint, [source for source in catalog["sources"] if not source.get("avoid")])
        if hinted and role["id"] in hinted.get("suits_roles", []):
            existing = next((idea for idea in ideas if idea["suggested_dataset"]["id"] == hinted["id"]), None)
            if existing:
                ideas = [existing] + [idea for idea in ideas if idea is not existing]
            else:
                template = next(
                    (item for item in templates if item["dataset_id"] == hinted["id"]),
                    None,
                )
                ideas = [build_idea(hinted, role, method, profile, inputs, catalog, template)] + ideas
            notes.append(f"Put {hinted['name']} first because you named it.")
        elif overused_hits(hint, catalog) and not has_new_angle(hint, catalog):
            notes.append(
                "That dataset was not used. Add a genuinely new angle if you want it considered, "
                "and expect the size check to fail if the extract stays under 10k rows."
            )
        else:
            notes.append("No shortlist dataset matched that hint. Showing role-matched starters instead.")

    # Drop anything that still names an overused set unless the user supplied the angle.
    allowed_angle = has_new_angle(user_blob(profile, inputs), catalog)
    if not allowed_angle:
        kept = []
        for idea in ideas:
            blob = " ".join(
                [
                    idea["title"],
                    idea["data_angle"],
                    idea["suggested_dataset"]["name"],
                ]
            )
            if overused_hits(blob, catalog):
                continue
            kept.append(idea)
        ideas = kept

    ideas = ideas[:5]
    for index, idea in enumerate(ideas, start=1):
        idea["id"] = f"{role['id']}-{method}-{index}"
    return ideas, notes


def assemble_brief(
    profile: dict[str, Any],
    idea: dict[str, Any],
    dataset: dict[str, Any],
    beats: dict[str, str],
    catalog: dict[str, Any],
) -> dict[str, str]:
    role = catalog["roles"][profile["target_role"]]
    skills = ", ".join(idea.get("skills") or role["emphasized_skills"])
    method_line = METHOD_LINES[idea["method"]]
    voice_line = VOICE_LINES[role["voice"]]
    extra = ""
    industry = (profile.get("target_industry") or "").strip()
    background = (profile.get("background") or "").strip()
    if industry:
        extra += f" Industry context: {industry}."
    if background and (not overused_hits(background, catalog) or has_new_angle(background, catalog)):
        extra += f" Background I bring: {clip(background, 160).rstrip('.')}."
    source_name = dataset.get("name") or "the dataset"
    source_url = dataset.get("source_url") or "the publisher page"
    question = beats["question"].strip().rstrip("?")

    summary = (
        f"{idea['title']} gives {beats['stakeholder']} a decision they can act on. "
        f"{beats['stakes_sentence']} "
        f"I will use {source_name} ({beats['sample_plan']}). "
        f"I will compare {beats['baseline']} with {beats['heavier']}. "
        f"The decision I will hand them is {beats['action']}. "
        f"{voice_line} {method_line}{extra}"
    )
    problem = (
        f"The stakeholder is {beats['stakeholder']}. {beats['stakes_sentence']} "
        f"If this work is ignored, the cost of a wrong call sits with that stakeholder. "
        f"The question I will answer: {question}?"
    )
    investigation = (
        f"I will investigate this question: {question}? "
        f"I start there because a first pattern is rarely the driver. "
        f"I will check alternative explanations: {beats['alternatives']}. "
        f"The pattern I keep is the one that changes the decision, not a chart that only redescribes the data."
    )
    data = (
        f"I will source {source_name} from {source_url}. "
        f"Size plan: {beats['sample_plan']}. "
        f"Cleaning and handling: {beats['cleaning']}. "
        f"Limitation: {beats['limitation']}"
    )
    execution = (
        f"I will compare {beats['baseline']} with {beats['heavier']}. "
        f"The trade-off is speed versus accuracy, and simple versus complex. "
        f"I will record what I dropped and why I chose the option that changes the decision. "
        f"Drop rule: {beats['drop_rule']}. "
        f"This is my own plan, not a tutorial clone. "
        f"Skills I will show: {skills}."
    )
    results = (
        f"I will recommend {beats['action']}. "
        f"Assumption: {beats['assumption']}. "
        f"If that assumption is wrong, the recommendation overstates what the public data can prove. "
        f"Limitation: {beats['limitation']} "
        f"With more resources I would {beats['more_resources']}. "
        f"Next step is a short stakeholder readout, a note on how to reproduce the extract, and a refresh check."
    )
    act1 = f"{beats['stakes_sentence']} The person who has to act is {beats['stakeholder']}."
    act2 = (
        f"I will compare {beats['baseline']} with {beats['heavier']}, then drop the heavier work if it does not change the decision. "
        f"Alternative causes I will test: {beats['alternatives']}."
    )
    act3 = f"The action is {beats['action']}. Uncertainty stays visible: {beats['limitation']}"
    return {
        "summary_impact": summary,
        "problem_space": problem,
        "investigation_insights": investigation,
        "data": data,
        "execution": execution,
        "results_recommendations": results,
        "act1": act1,
        "act2": act2,
        "act3": act3,
        "more_resources": beats["more_resources"],
    }


def draft_local(
    profile: dict[str, Any],
    idea: dict[str, Any],
    dataset: dict[str, Any],
    catalog: dict[str, Any],
) -> dict[str, str]:
    role = catalog["roles"][profile["target_role"]]
    template = catalog["templates_by_id"].get(idea.get("template_id") or "")
    source = catalog["sources_by_id"].get((dataset or {}).get("id") or "")
    if template and source and template.get("dataset_id") != source.get("id"):
        # The user swapped datasets. Follow the dataset they picked.
        template_for_beats = None
    else:
        template_for_beats = template
    if source is None:
        beats = dict(role["defaults"])
        typed = (dataset or {}).get("typical_rows") or ""
        if typed:
            beats["sample_plan"] = typed
        question = (idea.get("data_angle") or beats["question"]).rstrip("?")
        beats["question"] = question
    else:
        beats = fill_beats(source, role, template_for_beats)
    return assemble_brief(profile, idea, dataset or {}, beats, catalog)


def template_prompt_brief(template: dict[str, Any]) -> dict[str, str]:
    prompts = template.get("prompts") or {}
    brief = {key: "" for key in (
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
    )}
    for key in brief:
        if prompts.get(key):
            brief[key] = prompts[key]
    if not brief["more_resources"]:
        brief["more_resources"] = "Say what you would add with more time, data, or a collaborator."
    return brief

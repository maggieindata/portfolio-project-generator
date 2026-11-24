"""Screen 3 — dataset check, SPIDER editor, scorecard, pitfalls."""

from __future__ import annotations

import streamlit as st

from content import load_catalog
from ideas import draft_local, template_prompt_brief
from llm import run_draft, run_evaluate, run_revise
from scoring import dataset_checks, echoed_fields, fingerprint, substantive_brief, weak_example
from state import current_evaluation, profile_for_engine, read_brief, selected_idea, store_evaluation, write_brief
from ui.components import ai_banner, boot, render_checks, render_pitfalls, render_scorecard, require_role, sidebar, stepper

boot()
catalog = load_catalog()
sidebar(catalog, 3)
stepper(3)
profile = require_role()
role = catalog["roles"][profile["target_role"]]
idea = selected_idea()
ai_banner()

st.markdown('<p class="eyebrow">Brief and review</p>', unsafe_allow_html=True)
st.title("Structure the brief, then stress-test it")

if idea is None:
    st.info("Pick an idea or a template first. The brief is written for one project at a time.")
    st.page_link("ui/page_ideas.py", label="Go to method and ideas")
    st.stop()

template = catalog["templates_by_id"].get(idea.get("template_id") or "")
pending = st.session_state.pop("pending_action", None)
if pending:
    write_brief(pending["brief"])
    pending_dataset = pending.get("dataset")
    if pending_dataset:
        st.session_state.dataset = pending_dataset
        if pending_dataset.get("id") == "custom":
            st.session_state.dataset_choice = "custom"
            st.session_state.custom_name = pending_dataset.get("name") or ""
            st.session_state.custom_url = pending_dataset.get("source_url") or ""
            st.session_state.custom_rows = pending_dataset.get("typical_rows") or ""
        else:
            st.session_state.dataset_choice = pending_dataset["id"]
    store_evaluation(pending["evaluation"], pending["meta"], pending["fingerprint"])
    if "draft_dataset_id" in pending:
        st.session_state.draft_dataset_id = pending["draft_dataset_id"]

st.write(f"**{idea['title']}**")
st.caption(idea["one_liner"])
if template:
    st.caption("Emphasize: " + ", ".join(template["criteria_to_emphasize"]))
    st.caption("Watch-outs: " + template["pitfalls_to_avoid"])

selectable = [
    source
    for source in catalog["sources"]
    if not source.get("avoid") and profile["target_role"] in source.get("suits_roles", [])
]
suggested_id = (idea.get("suggested_dataset") or {}).get("id")
option_ids = []
if suggested_id in catalog["sources_by_id"]:
    option_ids.append(suggested_id)
option_ids.extend(source["id"] for source in selectable if source["id"] not in option_ids)
option_ids.append("custom")
labels = {source["id"]: source["name"] for source in selectable}
labels["custom"] = "A dataset I will name"

if "dataset_choice" not in st.session_state:
    st.session_state.dataset_choice = suggested_id if suggested_id in labels else "custom"

choice = st.selectbox(
    "Dataset",
    option_ids,
    format_func=lambda item: labels.get(item, item),
    key="dataset_choice",
)
if choice == "custom":
    st.text_input("Dataset name", key="custom_name", placeholder="Name the extract you will actually use")
    st.text_input("Source URL", key="custom_url", placeholder="https://")
    st.text_input("Row-count plan", key="custom_rows", placeholder="about 200,000 rows after the filter")
    dataset = {
        "id": "custom",
        "name": st.session_state.get("custom_name") or "Untitled dataset",
        "source_url": st.session_state.get("custom_url") or "",
        "domain": profile.get("target_industry") or "Unspecified",
        "typical_rows": st.session_state.get("custom_rows") or "",
        "suits_roles": [profile["target_role"]],
        "notes": "Named by the user.",
        "size_rule": "unknown",
        "avoid": False,
        "group": "",
    }
else:
    source = catalog["sources_by_id"][choice]
    dataset = {
        "id": source["id"],
        "name": source["name"],
        "source_url": source.get("source_url") or "",
        "domain": source.get("domain") or "",
        "typical_rows": source.get("typical_rows") or "",
        "suits_roles": list(source.get("suits_roles") or []),
        "notes": source.get("notes") or "",
        "size_rule": source.get("size_rule") or "unknown",
        "avoid": False,
        "group": source.get("group") or "",
    }
    if dataset["source_url"]:
        st.markdown(f"[{dataset['name']}]({dataset['source_url']})")
    st.caption(dataset["typical_rows"])
    if source.get("notes"):
        st.caption(source["notes"])
st.session_state.dataset = dataset

with st.expander("Verified shortlist for this role"):
    for group in catalog["groups"]:
        rows = [
            source
            for source in catalog["sources"]
            if source.get("group") == group["id"]
            and (source.get("avoid") or profile["target_role"] in source.get("suits_roles", []))
        ]
        if not rows:
            continue
        st.markdown(f"**{group['label']}**")
        st.caption(group["caption"])
        for source in rows:
            flag = " · avoid" if source.get("avoid") else ""
            st.markdown(f"- {source['name']}{flag} — {source.get('typical_rows', '')}")

st.subheader("SPIDER and the three acts")
st.caption(
    "I is Investigation & Insights. D is data sourcing, cleaning, and handling. "
    "Template prompts are questions. They do not count as evidence until you replace them."
)
if template and template.get("prompts", {}).get("three_act"):
    st.caption("Three-act outline from the template: " + " ".join(template["prompts"]["three_act"].split()))

field_meta = {item["id"]: item for item in catalog["spider_fields"]}
field_meta.update({item["id"]: item for item in catalog["acts"]})
prompts = (template or {}).get("prompts") or {}
stored = st.session_state.brief
for key, meta in ((item["id"], item) for item in catalog["spider_fields"] + catalog["acts"]):
    widget_key = f"field_{key}"
    if widget_key not in st.session_state:
        st.session_state[widget_key] = stored.get(key, "")
    label = f"{meta['letter']} · {meta['name']}"
    st.caption(meta["include"])
    if prompts.get(key):
        st.caption("Template prompt: " + " ".join(prompts[key].split()))
    st.text_area(label, key=widget_key, height=140)

if "field_more_resources" not in st.session_state:
    st.session_state.field_more_resources = stored.get("more_resources", "")
st.text_area(
    "What I would do differently with more resources",
    key="field_more_resources",
    height=90,
)
st.text_area("Revision notes for the next pass", key="revision_notes", height=80, placeholder="What should change, in your words.")

brief = read_brief()
echoed = echoed_fields(brief, template)
if echoed:
    st.warning(
        "These fields are still the template prompt, so the scorecard ignores them: "
        + ", ".join(echoed)
        + "."
    )

if any(value.strip() for value in brief.values()):
    st.subheader("Dataset check")
    render_checks(dataset_checks(substantive_brief(brief, template), dataset, role, idea, catalog))
else:
    st.caption("Dataset checks appear once the brief has text. Size, business relevance, a role skill, and a three-act story all have to pass.")

draft_col, prompt_col, weak_col = st.columns(3)
score_col, revise_col = st.columns(2)


def _score(current_brief: dict, meta_message: str | None = None) -> None:
    evaluation, meta = run_evaluate(profile_for_engine(), idea, current_brief, dataset, catalog)
    if meta_message:
        meta = dict(meta)
        meta["message"] = meta_message
    store_evaluation(evaluation, meta, fingerprint(current_brief, dataset, idea["id"]))


def _queue(brief_text: dict, evaluation: dict, meta: dict, queued_dataset: dict, draft_dataset_id: str | None = None) -> None:
    st.session_state.pending_action = {
        "brief": brief_text,
        "evaluation": evaluation,
        "meta": meta,
        "dataset": queued_dataset,
        "fingerprint": fingerprint(brief_text, queued_dataset, idea["id"]),
        "draft_dataset_id": draft_dataset_id,
    }
    st.rerun()


with draft_col:
    if st.button("Draft a starter brief", type="primary", use_container_width=True):
        drafted, meta = run_draft(profile_for_engine(), idea, dataset, catalog)
        evaluation, eval_meta = run_evaluate(profile_for_engine(), idea, drafted, dataset, catalog)
        eval_meta = dict(eval_meta)
        eval_meta["message"] = meta["message"]
        _queue(drafted, evaluation, eval_meta, dataset, dataset.get("id"))
with prompt_col:
    if st.button("Fill template prompts", use_container_width=True, disabled=template is None):
        prompted = template_prompt_brief(template)
        evaluation, meta = run_evaluate(profile_for_engine(), idea, prompted, dataset, catalog)
        meta = dict(meta)
        meta["message"] = "Template prompts do not count as evidence. Replace them or draft a starter brief."
        _queue(prompted, evaluation, meta, dataset)
with weak_col:
    if st.button("Load a weak example", use_container_width=True):
        weak_brief, weak_dataset = weak_example()
        evaluation, meta = run_evaluate(profile_for_engine(), idea, weak_brief, weak_dataset, catalog)
        _queue(weak_brief, evaluation, meta, weak_dataset)

with score_col:
    if st.button("Score this brief", use_container_width=True):
        _score(brief)
        st.rerun()
with revise_col:
    if st.button("Revise and re-score", use_container_width=True):
        revised, evaluation, meta = run_revise(
            profile_for_engine(),
            idea,
            brief,
            dataset,
            st.session_state.get("revision_notes") or "",
            catalog,
        )
        _queue(revised, evaluation, meta, dataset)

if st.session_state.draft_dataset_id and st.session_state.draft_dataset_id != dataset.get("id"):
    st.caption("The starter draft was written for a different dataset. Draft again if you changed the source.")

evaluation = current_evaluation()
current_fp = fingerprint(brief, dataset, idea["id"])
stale = bool(st.session_state.evaluated_fingerprint) and st.session_state.evaluated_fingerprint != current_fp
if stale:
    st.warning("The brief or dataset changed after the last score. Score it again before export.")

if evaluation:
    st.subheader("Scorecard")
    if st.session_state.evaluation_meta.get("message"):
        st.caption(st.session_state.evaluation_meta["message"])
    render_scorecard(evaluation["scorecard"])
    st.subheader("Pitfalls")
    render_pitfalls(evaluation["flags"]["pitfalls"])
    if evaluation["flags"]["clear_to_export"] and not stale:
        st.success("Clear to export.")
        if st.button("Continue to export", type="primary"):
            st.switch_page("ui/page_export.py")
    else:
        st.error("Export stays blocked until the pass bar is met, every pitfall is clear, and the dataset checks pass.")
        st.page_link("ui/page_export.py", label="Open export to see the block in writing")
else:
    st.caption("Score the brief when you want the pass bar. A starter draft is the fastest way to see a full scorecard.")

with st.expander("What the levels mean"):
    for spec in catalog["criteria"]:
        levels = spec["levels"]
        st.markdown(f"**{spec['name']}.** Weak: {levels['weak']}. Developing: {levels['developing']}. Ready: {levels['ready']}.")

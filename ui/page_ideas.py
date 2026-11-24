"""Screen 2 — one method, then 3–5 role-matched ideas or a template."""

from __future__ import annotations

import streamlit as st

from content import load_catalog
from ideas import build_idea
from llm import run_generate
from models import empty_brief
from state import profile_for_engine
from ui.components import ai_banner, boot, require_role, sidebar, stepper


def _select(idea: dict) -> None:
    st.session_state.selected_idea_id = idea["id"]
    dataset = idea.get("suggested_dataset") or {}
    st.session_state.dataset = dataset
    st.session_state.dataset_choice = dataset.get("id") or "custom"
    st.session_state.brief = empty_brief()
    st.session_state.scorecard = None
    st.session_state.flags = None
    st.session_state.dataset_checks = None
    st.session_state.evaluated_fingerprint = None
    for key in empty_brief():
        st.session_state.pop(f"field_{key}", None)

boot()
catalog = load_catalog()
sidebar(catalog, 2)
stepper(2)
profile = require_role()
role = catalog["roles"][profile["target_role"]]
ai_banner()

st.markdown('<p class="eyebrow">Method and ideas</p>', unsafe_allow_html=True)
st.title(f"Ideas for a {role['label']}")
st.write(
    "Pick one method for this session. Inventory, skill, problem, and data-first "
    "are not mixed in a single generation. You can also start from one of the two templates for this role."
)

method_ids = [item["id"] for item in catalog["methods"]]
if "method_radio" not in st.session_state and st.session_state.get("method") in method_ids:
    st.session_state.method_radio = st.session_state.method
method = st.radio(
    "Method",
    method_ids,
    format_func=lambda item: catalog["methods_by_id"][item]["label"],
    horizontal=True,
    index=None,
    key="method_radio",
)

columns = st.columns(4)
for column, spec in zip(columns, catalog["methods"]):
    with column:
        with st.container(border=True):
            st.markdown(f"**{spec['label']}**")
            st.caption(spec["summary"])

inputs: dict[str, str] = {}
if method:
    st.session_state.method = method
    st.subheader(catalog["methods_by_id"][method]["label"])
    bucket = st.session_state.setdefault("method_input_bucket", {})
    saved_inputs = bucket.get(method) or {}
    for field in catalog["methods_by_id"][method]["inputs"]:
        key = f"in_{method}_{field['id']}"
        if key not in st.session_state and saved_inputs.get(field["id"]):
            st.session_state[key] = saved_inputs[field["id"]]
        if field["type"] == "text_area":
            inputs[field["id"]] = st.text_area(field["label"], key=key, placeholder=field.get("placeholder", ""), height=110)
        else:
            inputs[field["id"]] = st.text_input(field["label"], key=key, placeholder=field.get("placeholder", ""))
    bucket[method] = inputs
    st.session_state.method_inputs = inputs

generate = st.button("Generate ideas", type="primary", disabled=method is None)
if generate and method:
    with st.spinner("Generating ideas…"):
        ideas, meta = run_generate(profile_for_engine(), method, inputs, catalog)
    st.session_state.ideas = ideas
    st.session_state.generation_meta = meta
    st.session_state.generation_notes = meta.get("notes") or []
    st.session_state.selected_idea_id = None
    st.rerun()

for note in st.session_state.generation_notes:
    st.warning(note)

visible = [
    idea
    for idea in st.session_state.ideas
    if idea["role"] == profile["target_role"] and (method is None or idea["method"] == method)
]
if st.session_state.ideas and not visible:
    st.info("Those ideas were for a different method. Generate again to replace them.")
elif not visible:
    st.info("Generate 3–5 ideas, or start from a template below. Nothing is saved after you close the tab.")
else:
    source = (st.session_state.generation_meta or {}).get("source")
    st.subheader(f"{len(visible)} ideas")
    st.caption("Built-in templates and the shortlist." if source != "llm" else "Drafted with the model, then checked against the shortlist.")
    for idea in visible:
        with st.container(border=True):
            st.markdown(f"### {idea['title']}")
            st.write(idea["one_liner"])
            st.write(idea["problem"])
            dataset = idea.get("suggested_dataset") or {}
            if dataset.get("source_url"):
                st.markdown(f"Data: [{dataset['name']}]({dataset['source_url']})")
            else:
                st.write(f"Data: {dataset.get('name', 'Not set')}")
            st.caption(idea["data_angle"])
            st.write("Skills: " + ", ".join(idea["skills"]))
            template = catalog["templates_by_id"].get(idea.get("template_id") or "")
            if template:
                st.caption(f"Template · {template['label']}. Watch-outs: {template['pitfalls_to_avoid']}")
            picked = st.session_state.selected_idea_id == idea["id"]
            if st.button("Selected" if picked else "Use this idea", key=f"use_{idea['id']}", type="primary" if picked else "secondary"):
                _select(idea)
                st.switch_page("ui/page_brief.py")

st.divider()
st.subheader("Or start from a template")
st.caption("Templates prefill SPIDER prompts. The starter draft on the next screen turns them into a plan you can score.")
template_cols = st.columns(2)
role_templates = [item for item in catalog["templates"] if item["role"] == profile["target_role"]]
for column, template in zip(template_cols, role_templates):
    source = catalog["sources_by_id"][template["dataset_id"]]
    with column:
        with st.container(border=True):
            st.markdown(f"**{template['title']}**")
            st.caption(template["label"])
            st.write(source["example_question"])
            st.caption(source["typical_rows"])
            if st.button("Use this template", key=f"tpl_{template['id']}", disabled=method is None):
                idea = build_idea(source, role, method, profile_for_engine(), inputs, catalog, template)
                idea["id"] = f"{profile['target_role']}-{method}-template"
                st.session_state.ideas = [idea] + [
                    existing for existing in st.session_state.ideas if existing.get("template_id") != template["id"]
                ]
                _select(idea)
                st.switch_page("ui/page_brief.py")
if method is None:
    st.caption("Choose a method before using a template, so the brief knows which starting point you are in.")

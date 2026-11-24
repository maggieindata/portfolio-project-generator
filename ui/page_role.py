"""Screen 1 — pick one of the three v1 roles and a short profile."""

from __future__ import annotations

import streamlit as st

from content import load_catalog
from state import choose_role
from ui.components import ai_banner, boot, sidebar, stepper, weight_line

boot()
catalog = load_catalog()
sidebar(catalog, 1)
stepper(1)
ai_banner()

st.markdown('<p class="eyebrow">Portfolio Project Generator</p>', unsafe_allow_html=True)
st.title("Choose the role you want to be hired for")
st.write(
    "Everything after this screen follows that choice: the ideas, the templates, "
    "the datasets, the skills the brief has to show, and which scorecard gaps get called out. "
    "There are three roles in v1."
)

selected = st.session_state.profile.get("target_role")
columns = st.columns(3)
for column, role_id in zip(columns, catalog["role_order"]):
    role = catalog["roles"][role_id]
    with column:
        with st.container(border=True):
            st.markdown(f"### {role['label']}")
            st.write(role["good_looks_like"])
            st.markdown("**Priority criteria**")
            names = {item["id"]: item["name"] for item in catalog["criteria"]}
            for criterion_id in role["priority_criteria"]:
                st.markdown(f"- {names[criterion_id]}")
            st.markdown("**Skills to show**")
            st.write(", ".join(role["emphasized_skills"]))
            st.markdown(f'<p class="weight-line">{weight_line(role, catalog)}</p>', unsafe_allow_html=True)
            label = "Selected" if selected == role_id else "Choose this role"
            if st.button(label, key=f"pick_{role_id}", type="primary" if selected == role_id else "secondary", use_container_width=True):
                choose_role(role_id, catalog)
                st.rerun()

st.divider()
if not selected:
    st.info("Pick a role to unlock background, skills, and the rest of the brief.")
    st.button("Continue to method and ideas", disabled=True)
    st.stop()

role = catalog["roles"][selected]
st.subheader(f"Profile for a {role['label']} brief")
st.caption("Background and industry are optional. Skills start from the role and you can edit them.")

profile = st.session_state.profile
if "skills_pick" not in st.session_state:
    st.session_state.skills_pick = list(profile.get("must_have_skills") or role["emphasized_skills"])
if "skills_extra" not in st.session_state:
    st.session_state.skills_extra = profile.get("skills_extra") or ""
if "background_input" not in st.session_state:
    st.session_state.background_input = profile.get("background") or ""
if "industry_input" not in st.session_state:
    st.session_state.industry_input = profile.get("target_industry") or ""

options = list(dict.fromkeys(list(role["emphasized_skills"]) + list(st.session_state.skills_pick)))
st.multiselect("Must-have skills", options=options, key="skills_pick")
st.text_input("Other skills, comma-separated", key="skills_extra", placeholder="A/B testing, looker, experiment readouts")
st.text_area(
    "Background",
    key="background_input",
    height=120,
    placeholder="Career switcher from operations, finishing a data bootcamp, comfortable with SQL.",
)
st.text_input("Target industry (optional)", key="industry_input", placeholder="Marketplaces, hospitals, city operations")

profile["must_have_skills"] = list(st.session_state.skills_pick)
profile["skills_extra"] = st.session_state.skills_extra
profile["background"] = st.session_state.background_input
profile["target_industry"] = st.session_state.industry_input

if st.button("Continue to method and ideas", type="primary"):
    st.switch_page("ui/page_ideas.py")

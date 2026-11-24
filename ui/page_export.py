"""Screen 4 — copy or download the README brief."""

from __future__ import annotations

import re

import streamlit as st

from content import load_catalog
from export import render_readme
from scoring import fingerprint
from state import current_evaluation, profile_for_engine, read_brief, selected_idea
from ui.components import ai_banner, boot, require_role, sidebar, stepper

boot()
catalog = load_catalog()
sidebar(catalog, 4)
stepper(4)
profile = require_role()
ai_banner()

st.markdown('<p class="eyebrow">Export</p>', unsafe_allow_html=True)
st.title("README brief")
st.write(
    "The file follows the SPIDER outline: role, method, dataset, the six sections, "
    "the three acts, dataset checks, the scorecard, and anything still open."
)

idea = selected_idea()
evaluation = current_evaluation()
if idea is None or evaluation is None:
    st.info("Evaluate a brief before export. The download stays off until a score exists.")
    st.page_link("ui/page_brief.py", label="Go to brief and review")
    st.stop()

brief = read_brief()
dataset = st.session_state.dataset or idea.get("suggested_dataset") or {}
current = fingerprint(brief, dataset, idea["id"])
stale = st.session_state.evaluated_fingerprint != current
flags = evaluation["flags"]
reasons = []
if stale:
    reasons.append("The brief changed after the last score. Re-score it on the brief screen.")
if not evaluation["scorecard"]["pass_bar_met"]:
    reasons.append("The pass bar is not met (no Weak scores, and at least 6 of 8 Ready).")
reasons.extend(flags.get("pitfalls") or [])
reasons.extend(flags.get("dataset_flags") or [])
can_download = bool(flags.get("clear_to_export")) and not stale

markdown = render_readme(profile_for_engine(), idea, dataset, brief, evaluation)
slug = re.sub(r"[^a-z0-9]+", "-", (idea.get("title") or "portfolio-brief").lower()).strip("-") or "portfolio-brief"

if can_download:
    st.success("Clear to export. This is a plan, not a finished analysis.")
else:
    st.error("Download is blocked until the brief is clear.")
    for reason in reasons:
        st.markdown(f"- {reason}")

st.download_button(
    "Download README.md",
    data=markdown,
    file_name=f"{slug}-README.md",
    mime="text/markdown",
    type="primary",
    disabled=not can_download,
)
st.page_link("ui/page_brief.py", label="Back to the brief")

st.subheader("Preview")
st.markdown(markdown)
with st.expander("Raw markdown"):
    st.code(markdown, language="markdown")

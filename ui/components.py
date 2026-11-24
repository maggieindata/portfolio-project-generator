"""Shared layout for the four screens."""

from __future__ import annotations

from typing import Any

import streamlit as st

from llm import AI_OFF_NOTE, ai_status
from state import init_state, profile_for_engine, selected_idea

CSS = """
<style>
.block-container { padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1080px; }
h1 { letter-spacing: -0.03em; font-weight: 640; }
.eyebrow { letter-spacing: 0.14em; text-transform: uppercase; font-size: 0.75rem; color: #5C564C; margin-bottom: 0.2rem; }
.stepper { display: flex; gap: 0.5rem; flex-wrap: wrap; margin: 0.2rem 0 1rem; }
.step { border: 1px solid #DDD6C8; border-radius: 999px; padding: 0.2rem 0.7rem; color: #5C564C; font-size: 0.85rem; }
.step.active { background: #0F6E56; color: #F6F3EC; border-color: #0F6E56; }
.pill { display: inline-block; border-radius: 999px; padding: 0.1rem 0.55rem; font-size: 0.78rem; font-weight: 650; letter-spacing: 0.02em; }
.pill-ready { background: #E5F4EF; color: #0F6E56; }
.pill-developing { background: #F8F0DC; color: #8A5A00; }
.pill-weak { background: #F8E8E4; color: #8C3A32; }
.pill-priority { background: #1F1A14; color: #F6F3EC; margin-left: 0.35rem; }
.weight-line { color: #5C564C; font-size: 0.82rem; line-height: 1.4; }
section[data-testid="stSidebar"] { background: #1F1A14; }
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] a { color: #F6F3EC !important; }
@media (max-width: 800px) {
  [data-testid="stHorizontalBlock"] { flex-direction: column; }
  [data-testid="column"] { width: 100% !important; flex: 1 1 100% !important; }
}
</style>
"""


def boot() -> None:
    init_state()
    st.markdown(CSS, unsafe_allow_html=True)


def stepper(active: int) -> None:
    labels = ["1 · Role", "2 · Ideas", "3 · Brief", "4 · Export"]
    chips = []
    for index, label in enumerate(labels, start=1):
        kind = "step active" if index == active else "step"
        chips.append(f'<span class="{kind}">{label}</span>')
    st.markdown(f'<div class="stepper">{"".join(chips)}</div>', unsafe_allow_html=True)


def sidebar(catalog: dict[str, Any], active: int) -> None:
    status = ai_status()
    profile = st.session_state.profile
    role = catalog["roles"].get(profile.get("target_role") or "")
    with st.sidebar:
        st.markdown("**Portfolio Project Generator**")
        st.caption("A hire-worthy brief for one target role, before you write code.")
        if status["enabled"]:
            st.markdown(f"AI on · `{status['model']}`")
        else:
            st.markdown("AI generation is off. Templates and the rubric are running.")
        st.divider()
        if role:
            st.markdown(f"**{role['label']}**")
        else:
            st.markdown("No role yet")
        idea = selected_idea()
        if idea:
            st.caption(idea["title"])
        st.divider()
        st.page_link("ui/page_role.py", label="Role and profile")
        st.page_link("ui/page_ideas.py", label="Method and ideas")
        st.page_link("ui/page_brief.py", label="Brief and review")
        st.page_link("ui/page_export.py", label="Export")
        st.caption("Pass bar: no Weak scores, and at least 6 of 8 Ready.")
        _ = active


def ai_banner() -> None:
    status = ai_status()
    meta = st.session_state.get("generation_meta") or {}
    eval_meta = st.session_state.get("evaluation_meta") or {}
    if not status["enabled"]:
        st.info(AI_OFF_NOTE)
    else:
        st.caption(f"AI generation is on · {status['model']}. The rubric still has the last word on the pass bar.")
    for message in (meta.get("message"), eval_meta.get("message")):
        if message and message != AI_OFF_NOTE and "failed" in message.lower():
            st.warning(message)


def require_role() -> dict[str, Any]:
    profile = profile_for_engine()
    if not profile.get("target_role"):
        st.warning("Choose a target role on the first screen. The other steps wait for that.")
        st.page_link("ui/page_role.py", label="Go to role and profile")
        st.stop()
    return profile


def level_pill(level: str, priority: bool = False) -> str:
    label = {"weak": "Weak", "developing": "Developing", "ready": "Ready"}.get(level, level)
    extra = '<span class="pill pill-priority">Priority</span>' if priority else ""
    return f'<span class="pill pill-{level}">{label}</span>{extra}'


def render_checks(checks: list[dict[str, Any]]) -> None:
    left, right = st.columns(2)
    for index, check in enumerate(checks):
        column = left if index % 2 == 0 else right
        with column:
            text = f"**{check['name']}.** {check['detail']}"
            if check["passed"]:
                st.success(text)
            else:
                st.error(text)


def render_pitfalls(pitfalls: list[str]) -> None:
    names = [
        ("Visualization-only", "Charts or EDA with no why, drivers, or next steps."),
        ("Overused dataset, no new angle", "Titanic, Iris, Boston Housing, and similar sets without a new question."),
        ("No business context", "No one named, no stakes, no decision."),
        ("Tutorial clone", "A walkthrough with no original decision and nothing dropped."),
    ]
    for name, detail in names:
        hit = next((item for item in pitfalls if item.lower().startswith(name.lower())), None)
        if hit:
            st.error(hit)
        else:
            st.success(f"{name} is clear. {detail}")


def render_scorecard(scorecard: dict[str, Any]) -> None:
    if scorecard["pass_bar_met"]:
        st.success(
            f"Pass bar met · {scorecard['ready_count']} of 8 Ready, {scorecard['weak_count']} Weak. "
            f"Weighted guide {scorecard['weighted']:.0f} / 100."
        )
    else:
        st.error(
            f"Pass bar not met. You need no Weak scores and at least 6 Ready "
            f"({scorecard['ready_count']} Ready, {scorecard['weak_count']} Weak now). "
            f"Weighted guide {scorecard['weighted']:.0f} / 100."
        )
    if scorecard["priority_gaps"]:
        st.warning("Priority gaps for this role: " + ", ".join(scorecard["priority_gaps"]))
    else:
        st.caption("No priority-criterion gaps for this role.")
    for score in scorecard["scores"]:
        with st.container(border=True):
            st.markdown(
                f"**{score['criterion']}** · weight {score['weight']:.0f} {level_pill(score['level'], score['priority'])}",
                unsafe_allow_html=True,
            )
            st.write(score["evidence"])


def weight_line(role: dict[str, Any], catalog: dict[str, Any]) -> str:
    shorts = {item["id"]: item["short"] for item in catalog["criteria"]}
    parts = [f"{shorts[key]} {role['weights'][key]}" for key in (item["id"] for item in catalog["criteria"])]
    return " · ".join(parts)

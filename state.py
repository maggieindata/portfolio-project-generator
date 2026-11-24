"""Streamlit session helpers. Kept out of the scoring tests."""

from __future__ import annotations

from typing import Any

import streamlit as st

from models import empty_brief

BRIEF_FIELDS = (
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
)


def init_state() -> None:
    st.session_state.setdefault(
        "profile",
        {
            "target_role": None,
            "background": "",
            "must_have_skills": [],
            "target_industry": "",
        },
    )
    st.session_state.setdefault("ideas", [])
    st.session_state.setdefault("generation_notes", [])
    st.session_state.setdefault("generation_meta", {})
    st.session_state.setdefault("selected_idea_id", None)
    st.session_state.setdefault("dataset", None)
    st.session_state.setdefault("brief", empty_brief())
    st.session_state.setdefault("scorecard", None)
    st.session_state.setdefault("flags", None)
    st.session_state.setdefault("dataset_checks", None)
    st.session_state.setdefault("evaluated_fingerprint", None)
    st.session_state.setdefault("evaluation_meta", {})
    st.session_state.setdefault("draft_dataset_id", None)


def profile_for_engine() -> dict[str, Any]:
    profile = st.session_state.profile
    if "background_input" in st.session_state:
        profile["background"] = st.session_state.background_input
    if "industry_input" in st.session_state:
        profile["target_industry"] = st.session_state.industry_input
    skills = list(st.session_state.get("skills_pick") or profile.get("must_have_skills") or [])
    if "skills_extra" in st.session_state:
        extra = st.session_state.skills_extra or ""
    else:
        extra = profile.get("skills_extra") or ""
    for piece in extra.split(","):
        cleaned = piece.strip()
        if cleaned and cleaned not in skills:
            skills.append(cleaned)
    profile["must_have_skills"] = skills
    industry = (profile.get("target_industry") or "").strip()
    return {
        "target_role": profile.get("target_role"),
        "background": (profile.get("background") or "").strip(),
        "must_have_skills": skills,
        "target_industry": industry or None,
    }


def selected_idea() -> dict[str, Any] | None:
    idea_id = st.session_state.get("selected_idea_id")
    for idea in st.session_state.get("ideas") or []:
        if idea["id"] == idea_id:
            return idea
    return None


def clear_downstream() -> None:
    st.session_state.ideas = []
    st.session_state.generation_notes = []
    st.session_state.generation_meta = {}
    st.session_state.selected_idea_id = None
    st.session_state.dataset = None
    st.session_state.brief = empty_brief()
    st.session_state.scorecard = None
    st.session_state.flags = None
    st.session_state.dataset_checks = None
    st.session_state.evaluated_fingerprint = None
    st.session_state.evaluation_meta = {}
    st.session_state.draft_dataset_id = None
    st.session_state.pop("dataset_choice", None)
    for key in BRIEF_FIELDS:
        st.session_state.pop(f"field_{key}", None)


def choose_role(role_id: str, catalog: dict[str, Any]) -> None:
    profile = st.session_state.profile
    if profile.get("target_role") == role_id:
        return
    profile["target_role"] = role_id
    skills = list(catalog["roles"][role_id]["emphasized_skills"])
    profile["must_have_skills"] = skills
    st.session_state.skills_pick = skills
    clear_downstream()


def read_brief() -> dict[str, str]:
    brief = {}
    stored = st.session_state.get("brief") or empty_brief()
    for key in BRIEF_FIELDS:
        widget_key = f"field_{key}"
        if widget_key in st.session_state:
            brief[key] = st.session_state[widget_key]
        else:
            brief[key] = stored.get(key, "")
    st.session_state.brief = brief
    return brief


def write_brief(brief: dict[str, str]) -> None:
    full = empty_brief()
    full.update(brief)
    st.session_state.brief = full
    for key, value in full.items():
        st.session_state[f"field_{key}"] = value


def store_evaluation(evaluation: dict[str, Any], meta: dict[str, Any], fingerprint: str) -> None:
    st.session_state.scorecard = evaluation["scorecard"]
    st.session_state.flags = evaluation["flags"]
    st.session_state.dataset_checks = evaluation["dataset_checks"]
    st.session_state.evaluated_fingerprint = fingerprint
    st.session_state.evaluation_meta = meta


def current_evaluation() -> dict[str, Any] | None:
    if not st.session_state.get("scorecard"):
        return None
    return {
        "scorecard": st.session_state.scorecard,
        "flags": st.session_state.flags,
        "dataset_checks": st.session_state.dataset_checks,
    }

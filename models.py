"""Pydantic contracts for the v1 session objects."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["data_analyst", "product_data_scientist", "algorithm_data_scientist"]
Method = Literal["inventory_first", "skill_first", "problem_first", "data_first"]
ScoreLevel = Literal["weak", "developing", "ready"]

ROLES: tuple[Role, ...] = (
    "data_analyst",
    "product_data_scientist",
    "algorithm_data_scientist",
)
METHODS: tuple[Method, ...] = (
    "inventory_first",
    "skill_first",
    "problem_first",
    "data_first",
)


class UserProfile(BaseModel):
    target_role: Role
    background: str = ""
    must_have_skills: list[str] = Field(default_factory=list)
    target_industry: str | None = None


class Dataset(BaseModel):
    name: str
    source_url: str = ""
    domain: str = ""
    typical_rows: str = ""
    suits_roles: list[Role] = Field(default_factory=list)
    notes: str = ""
    id: str | None = None
    size_rule: str | None = None
    group: str | None = None
    avoid: bool = False


class ProjectIdea(BaseModel):
    id: str
    title: str
    method: Method
    role: Role
    one_liner: str = ""
    problem: str = ""
    data_angle: str = ""
    skills: list[str] = Field(default_factory=list)
    suggested_dataset: Dataset | None = None
    template_id: str | None = None


class SPIDERBrief(BaseModel):
    summary_impact: str = ""
    problem_space: str = ""
    investigation_insights: str = ""
    data: str = ""
    execution: str = ""
    results_recommendations: str = ""
    act1: str = ""
    act2: str = ""
    act3: str = ""
    more_resources: str = ""


class CriterionScore(BaseModel):
    criterion: str
    level: ScoreLevel
    evidence: str
    criterion_id: str = ""
    weight: float = 0
    priority: bool = False


class Scorecard(BaseModel):
    scores: list[CriterionScore]
    role: Role
    weights: dict[str, float]
    pass_bar_met: bool
    priority_gaps: list[str] = Field(default_factory=list)
    weighted: float = 0
    ready_count: int = 0
    weak_count: int = 0


class Flags(BaseModel):
    pitfalls: list[str] = Field(default_factory=list)
    dataset_flags: list[str] = Field(default_factory=list)
    clear_to_export: bool = False


BRIEF_KEYS: tuple[str, ...] = (
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


def empty_brief() -> dict[str, str]:
    return {key: "" for key in BRIEF_KEYS}

"""Pass bar, weights, and scorecard behavior."""

from content import load_catalog
from ideas import draft_local, generate_local, template_prompt_brief
from scoring import (
    evaluate,
    merge_scores,
    pass_bar_met,
    priority_gap_names,
    weighted_score,
)

CATALOG = load_catalog()


def _score(level: str, criterion_id: str, name: str, weight: float, priority: bool) -> dict:
    return {
        "criterion_id": criterion_id,
        "criterion": name,
        "level": level,
        "evidence": "Evidence.",
        "weight": weight,
        "priority": priority,
    }


def test_catalog_has_three_roles_and_eight_criteria():
    assert CATALOG["role_order"] == [
        "data_analyst",
        "product_data_scientist",
        "algorithm_data_scientist",
    ]
    assert len(CATALOG["criteria"]) == 8
    assert len(CATALOG["templates"]) == 6


def test_weights_sum_to_100_and_priorities_are_real():
    ids = {item["id"] for item in CATALOG["criteria"]}
    for role in CATALOG["roles"].values():
        assert sum(role["weights"].values()) == 100
        assert set(role["priority_criteria"]) <= ids


def test_pass_bar_rules():
    ready = [_score("ready", "a", "A", 10, False) for _ in range(8)]
    assert pass_bar_met(ready)
    six = [_score("ready", str(i), str(i), 10, False) for i in range(6)]
    six += [_score("developing", "d1", "D1", 10, False), _score("developing", "d2", "D2", 10, False)]
    assert pass_bar_met(six)
    five = [_score("ready", str(i), str(i), 10, False) for i in range(5)]
    five += [_score("developing", str(i), str(i), 10, False) for i in range(3)]
    assert not pass_bar_met(five)
    seven = [_score("ready", str(i), str(i), 10, False) for i in range(7)]
    seven.append(_score("weak", "w", "W", 10, True))
    assert not pass_bar_met(seven)


def test_priority_gaps_ignore_non_priority_developing():
    scores = [
        _score("developing", "industry_relevance", "Industry relevance", 15, True),
        _score("developing", "independence", "Independent work capability", 10, False),
        _score("ready", "depth_of_analysis", "Depth of analysis", 20, True),
    ]
    assert priority_gap_names(scores) == ["Industry relevance"]


def test_weighted_score_uses_half_credit_for_developing():
    scores = [
        _score("ready", "depth_of_analysis", "Depth of analysis", 20, True),
        _score("developing", "industry_relevance", "Industry relevance", 20, True),
        _score("weak", "implementation", "Implementation & planning", 10, True),
    ]
    assert weighted_score(scores) == 30


def test_remote_score_cannot_inflate_a_weak_rubric_level():
    local = [_score("weak", "tradeoffs", "Understanding trade-offs", 20, True)]
    remote = [{"criterion_id": "tradeoffs", "criterion": "Understanding trade-offs", "level": "ready", "evidence": "Sounds polished."}]
    merged = merge_scores(local, remote)
    assert merged[0]["level"] == "weak"
    assert "more generous" in merged[0]["evidence"]


def test_remote_score_can_lower_a_level_when_it_has_evidence():
    local = [_score("ready", "tradeoffs", "Understanding trade-offs", 20, True)]
    remote = [{"criterion": "Understanding trade-offs", "level": "developing", "evidence": "Names a trade-off and stops."}]
    merged = merge_scores(local, remote)
    assert merged[0]["level"] == "developing"
    assert merged[0]["evidence"].startswith("Names a trade-off")


def test_prompt_echo_does_not_meet_the_pass_bar():
    template = CATALOG["templates_by_id"]["tlc_demand"]
    source = CATALOG["sources_by_id"][template["dataset_id"]]
    profile = {"target_role": "data_analyst", "background": "", "must_have_skills": [], "target_industry": None}
    ideas, _notes = generate_local(profile, "data_first", {}, CATALOG)
    idea = next(item for item in ideas if item["template_id"] == "tlc_demand")
    brief = template_prompt_brief(template)
    result = evaluate(profile, idea, brief, source, CATALOG)
    assert result["scorecard"]["pass_bar_met"] is False
    assert result["flags"]["clear_to_export"] is False


def test_starter_drafts_have_evidence_on_every_score():
    profile = {"target_role": "data_analyst", "background": "Bootcamp grad.", "must_have_skills": ["SQL"], "target_industry": "transit"}
    ideas, _notes = generate_local(profile, "problem_first", {}, CATALOG)
    idea = ideas[0]
    brief = draft_local(profile, idea, idea["suggested_dataset"], CATALOG)
    result = evaluate(profile, idea, brief, idea["suggested_dataset"], CATALOG)
    assert len(result["scorecard"]["scores"]) == 8
    assert all(score["evidence"] for score in result["scorecard"]["scores"])
    assert result["scorecard"]["pass_bar_met"] is True

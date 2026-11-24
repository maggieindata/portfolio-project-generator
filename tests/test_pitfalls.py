"""Pitfall and dataset-check behavior."""

from content import load_catalog
from ideas import draft_local, generate_local
from scoring import check_size, evaluate, extract_row_estimates, weak_example

CATALOG = load_catalog()


def _profile(role: str = "data_analyst") -> dict:
    return {"target_role": role, "background": "", "must_have_skills": [], "target_industry": None}


def _anchor_idea(role: str = "data_analyst") -> dict:
    ideas, _notes = generate_local(_profile(role), "data_first", {}, CATALOG)
    return ideas[0]


def test_weak_example_trips_all_four_pitfalls_and_blocks_export():
    brief, dataset = weak_example()
    idea = _anchor_idea()
    result = evaluate(_profile(), idea, brief, dataset, CATALOG)
    pitfalls = result["flags"]["pitfalls"]
    assert any(item.startswith("Visualization-only") for item in pitfalls)
    assert any(item.startswith("Overused dataset") for item in pitfalls)
    assert any(item.startswith("No business context") for item in pitfalls)
    assert any(item.startswith("Tutorial clone") for item in pitfalls)
    assert any(not check["passed"] for check in result["dataset_checks"] if check["id"] == "size")
    assert result["flags"]["clear_to_export"] is False


def test_charts_with_a_driver_are_not_visualization_only():
    idea = _anchor_idea()
    brief, dataset = weak_example()
    brief["investigation_insights"] = (
        "The chart is not the point, because the driver is zone imbalance rather than a citywide average. "
        "I will recommend a staffing change."
    )
    brief["results_recommendations"] = "Next step is a readout for the stakeholder, with a baseline comparison."
    result = evaluate(_profile(), idea, brief, dataset, CATALOG)
    assert not any(item.startswith("Visualization-only") for item in result["flags"]["pitfalls"])


def test_titanic_with_a_new_angle_clears_the_overused_pitfall_but_not_size():
    idea = _anchor_idea()
    brief, dataset = weak_example()
    brief["summary_impact"] = (
        "A genuinely new angle: this is not the survival tutorial. The stakeholder is a museum lead, "
        "and the cost is a bad exhibit decision. I will use a fresh question about crew process, about 891 rows."
    )
    brief["problem_space"] = "The stakeholder is a museum lead. The cost is telling the wrong operational story."
    brief["execution"] = "This is my own plan, not a tutorial clone. I dropped the leaderboard framing."
    result = evaluate(_profile(), idea, brief, dataset, CATALOG)
    assert not any(item.startswith("Overused dataset") for item in result["flags"]["pitfalls"])
    size = next(check for check in result["dataset_checks"] if check["id"] == "size")
    assert size["passed"] is False


def test_tutorial_language_with_an_original_decision_is_not_a_clone():
    profile = _profile("algorithm_data_scientist")
    ideas, _notes = generate_local(profile, "skill_first", {}, CATALOG)
    idea = ideas[0]
    brief = draft_local(profile, idea, idea["suggested_dataset"], CATALOG)
    brief["execution"] += " I looked at a kaggle kernel and then dropped it. This is my own plan, not a tutorial clone."
    result = evaluate(profile, idea, brief, idea["suggested_dataset"], CATALOG)
    assert not any(item.startswith("Tutorial clone") for item in result["flags"]["pitfalls"])


def test_instacart_is_a_dataset_flag_not_a_silent_pass():
    profile = _profile("product_data_scientist")
    ideas, _notes = generate_local(profile, "data_first", {}, CATALOG)
    idea = ideas[0]
    brief = draft_local(profile, idea, idea["suggested_dataset"], CATALOG)
    brief["data"] += " I wish I could use the instacart market basket file."
    result = evaluate(profile, idea, brief, idea["suggested_dataset"], CATALOG)
    assert any("Instacart" in flag for flag in result["flags"]["dataset_flags"])
    assert result["flags"]["clear_to_export"] is False


def test_row_boundaries():
    assert extract_row_estimates("about 9,999 rows") == [9999]
    assert extract_row_estimates("about 10,000 rows") == [10000]
    assert extract_row_estimates("about 10,000,000 rows") == [10000000]
    assert extract_row_estimates("about 10,000,001 rows") == [10000001]
    assert 2026 not in extract_row_estimates("checked in 2026 before modeling")
    dataset = {"size_rule": "unknown", "typical_rows": ""}

    def size(text: str) -> bool:
        return check_size(dataset, {"data": text, "summary_impact": ""})["passed"]

    assert size("about 9,999 rows") is False
    assert size("about 10,000 rows") is True
    assert size("about 10,000,000 rows") is True
    assert size("about 10,000,001 rows") is False
    assert size("I will use all 25,000,000 rows") is False
    assert size("I will sample down into the 10k–10M window from 25,000,000 rows") is True


def test_starter_draft_has_no_pitfalls():
    for role in CATALOG["role_order"]:
        profile = _profile(role)
        ideas, _notes = generate_local(profile, "inventory_first", {}, CATALOG)
        idea = next(item for item in ideas if item["template_id"])
        brief = draft_local(profile, idea, idea["suggested_dataset"], CATALOG)
        result = evaluate(profile, idea, brief, idea["suggested_dataset"], CATALOG)
        assert result["flags"]["pitfalls"] == [], idea["title"]
        assert result["flags"]["clear_to_export"] is True

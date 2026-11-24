"""Each v1 role can generate ideas, draft a brief, and export a README."""

from content import load_catalog
from export import render_readme
from ideas import draft_local, generate_local
from scoring import evaluate, overused_hits

CATALOG = load_catalog()
METHODS = ["inventory_first", "skill_first", "problem_first", "data_first"]


def _profile(role: str) -> dict:
    return {
        "target_role": role,
        "background": "Switching from operations into this role.",
        "must_have_skills": list(CATALOG["roles"][role]["emphasized_skills"]),
        "target_industry": "public services",
    }


def test_every_role_and_method_exports_a_clear_brief():
    for role in CATALOG["role_order"]:
        profile = _profile(role)
        for method in METHODS:
            ideas, _notes = generate_local(profile, method, {"dataset_hint": "", "existing_work": "A class dashboard."}, CATALOG)
            assert 3 <= len(ideas) <= 5, (role, method, len(ideas))
            assert len({idea["template_id"] for idea in ideas if idea["template_id"]}) >= 1
            for idea in ideas:
                assert idea["role"] == role
                assert idea["method"] == method
                dataset = idea["suggested_dataset"]
                assert role in dataset["suits_roles"]
                assert not dataset["avoid"]
                idea_roles = CATALOG["sources_by_id"][dataset["id"]].get("idea_roles")
                if idea_roles is not None:
                    assert role in idea_roles
                assert overused_hits(idea["title"] + idea["data_angle"] + dataset["name"], CATALOG) == []
                for skill in CATALOG["roles"][role]["emphasized_skills"]:
                    assert skill in idea["skills"]
                brief = draft_local(profile, idea, dataset, CATALOG)
                result = evaluate(profile, idea, brief, dataset, CATALOG)
                assert result["flags"]["clear_to_export"], (idea["title"], result["flags"], result["scorecard"]["priority_gaps"], [score["criterion"] + ":" + score["level"] for score in result["scorecard"]["scores"]])
                readme = render_readme(profile, idea, dataset, brief, result)
                assert "{{" not in readme
                assert idea["title"] in readme
                assert role in readme
                assert method in readme
                for criterion in CATALOG["criteria"]:
                    assert criterion["name"] in readme
                assert "Pass bar" in readme
                assert "Three-Act story" in readme
                assert "does not generate notebooks" in readme


def test_data_first_hint_puts_the_named_source_first():
    profile = _profile("algorithm_data_scientist")
    ideas, notes = generate_local(profile, "data_first", {"dataset_hint": "CFPB complaints"}, CATALOG)
    assert ideas[0]["suggested_dataset"]["id"] == "cfpb"
    assert any("CFPB" in note for note in notes)


def test_titanic_hint_is_rejected_without_a_new_angle():
    profile = _profile("data_analyst")
    ideas, notes = generate_local(profile, "data_first", {"dataset_hint": "Titanic survival"}, CATALOG)
    blob = " ".join(idea["title"] + idea["suggested_dataset"]["name"] for idea in ideas)
    assert overused_hits(blob, CATALOG) == []
    assert any("not used" in note.lower() or "Titanic" in note for note in notes)


def test_new_angle_does_not_invent_a_titanic_idea_by_default():
    profile = _profile("data_analyst")
    ideas, _notes = generate_local(
        profile,
        "problem_first",
        {"problem": "A genuinely new angle on Titanic crew logistics."},
        CATALOG,
    )
    names = [idea["suggested_dataset"]["name"] for idea in ideas]
    assert all("Titanic" not in name for name in names)


def test_each_role_has_two_templates_in_the_default_set():
    for role in CATALOG["role_order"]:
        ideas, _notes = generate_local(_profile(role), "skill_first", {}, CATALOG)
        template_ids = {idea["template_id"] for idea in ideas if idea["template_id"]}
        owned = {item["id"] for item in CATALOG["templates"] if item["role"] == role}
        assert template_ids == owned

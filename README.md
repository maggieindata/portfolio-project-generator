# Portfolio Project Generator

A Streamlit app that helps career switchers and new grads write a hire-worthy data science portfolio brief before they build anything. Pick one target role. The ideas, templates, datasets, skills, and scorecard weights follow that choice.

V1 roles:

- Data Analyst
- Product Data Scientist
- Algorithm Data Scientist

The brief uses the SPIDER framework (Summary, Problem, Investigation & Insights, Data, Execution, Results) and a three-act story. A scorecard checks eight hiring-manager criteria. A pitfall checker flags visualization-only work, overused datasets (Titanic, Iris, Boston Housing, and close cousins), missing business context, and tutorial clones. Dataset checks cover size (about 10k–10M rows), business relevance, a skill this role needs to show, and whether the story has stakes, a journey, and an action.

This is a plan, not an analysis. The app does not generate notebooks or code.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Python 3.11 or newer. The app opens in the browser on Streamlit's default port.

## AI, and running without a key

Idea generation, drafting, and revision can call an OpenAI-compatible chat API. Scoring always recomputes the pass bar locally, and a model note cannot raise a rubric level.

```bash
export OPENAI_API_KEY="sk-..."
export OPENAI_MODEL="gpt-4o-mini"          # optional, this is the default
export OPENAI_BASE_URL="https://api.openai.com/v1"  # optional, for compatible servers
streamlit run app.py
```

On Streamlit Community Cloud, put the same keys in the app secrets (`OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_BASE_URL`).

With no key, the app still runs. Ideas and starter drafts come from the built-in templates and shortlist, scores come from the deterministic rubric, and each screen says that AI generation is off.

## Screens

1. **Role and profile** — pick one of the three roles, then background, skills, and an optional industry.
2. **Method and ideas** — one of Inventory-First, Skill-First, Problem-First, or Data-First. Generate 3–5 ideas, or start from a role template.
3. **Brief and review** — dataset check, SPIDER editor, scorecard, and pitfall flags. Draft a starter brief, or load a weak example to see the flags.
4. **Export** — download a README-style markdown brief. Download stays off while a pitfall is open, the pass bar fails, a dataset check fails, or the brief changed after the last score.

Pass bar: no Weak scores, and at least 6 of 8 criteria at Ready. Role weights change which gaps are marked priority. They do not change the bar.

## Tune the content

Edit these files and rerun. No code change is required.

| File | What it controls |
| --- | --- |
| `data/roles.yaml` | Role copy, priority criteria, weights, skills, default brief beats |
| `data/rubric.yaml` | The 8 criteria, token rules, pitfall phrases, story-test tokens |
| `data/methods.yaml` | The four methods and their inputs |
| `data/sources.yaml` | The public-data shortlist, size rules, and project beats |
| `data/templates.yaml` | The six SPIDER templates and their prompts |
| `templates/readme_blank.md` | The exported README structure |
| `prompts/system.md` | The system prompt for the four LLM calls |

I is Investigation & Insights. D is sourcing, cleaning, and handling. That split is the v1 assumption from the playbook plan.

## Tests

```bash
pytest
```

The tests cover the pass bar, priority gaps, the rule that an AI note cannot inflate a weak score, all four pitfalls, dataset size boundaries, and a full generate → draft → score → README path for every role and method.

## Deploy on Streamlit Community Cloud

1. Push this project to GitHub.
2. Open [share.streamlit.io](https://share.streamlit.io) and create an app from the repo.
3. Set the main file to `app.py`.
4. Under App settings → Secrets, add:

```toml
OPENAI_API_KEY = "sk-..."
OPENAI_MODEL = "gpt-4o-mini"
```

`OPENAI_BASE_URL` is optional. Leave the secrets empty and the deployed app still runs on templates and the rubric.

5. Deploy. Community Cloud installs `requirements.txt` and runs `streamlit run app.py`.

## Out of v1

Accounts, saved history, generated analysis code, live Kaggle or GitHub integrations, and the later roles (Business Analyst, ML Engineer, Analytics Engineer, Data Engineer) are not in this version. Activation logging is also deferred.

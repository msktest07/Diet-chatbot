# Diet Chatbot — manual evaluation edition

A small diet and nutrition chatbot (OpenAI `gpt-4o-mini`, Streamlit UI) set up for
end-to-end testing **without any evaluation library**. The code produces the answers
and the tracking data; people score the answers with rubrics in the Excel workbook
that comes with the lab.

## What changed from the starter

| Area | Starter | This edition |
|---|---|---|
| Prompt | One prompt | `v1` (original) and `v2` (adds safety, tone, security and format rules), switchable |
| Tracking | None | Every answer logged to `logs/chat_log.csv` with run ID, case ID, prompt version, model, temperature, latency, tokens and cost |
| UI | Chat only | Tester panel: prompt version, test case ID, latency/tokens per answer, log download |
| Dataset | 8 question/answer pairs | `eval/goldens.csv`: 30 goldens in 8 categories with key facts, must-include and must-avoid rules |
| Evaluation | DeepEval metrics | `eval/run_goldens.py` runs the goldens and applies plain-Python checks; people score the rest in Excel |
| Tests | DeepEval test file | `tests/test_checks.py` tests the checkers themselves; `tests/test_scope_live.py` checks refusals on the live model |

## Setup

Create and activate a virtual environment, then install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

On macOS/Linux, activate it with `source .venv/bin/activate` and copy the template
with `cp .env.example .env`. Add your `OPENAI_API_KEY` to `.env` before running
the chatbot.

## Run the chatbot

```bash
streamlit run app.py     # web UI with the tester panel
python chatbot.py        # command line
```

## Run the golden dataset

```bash
python -m eval.run_goldens --prompt v1            # baseline: the original prompt
python -m eval.run_goldens --prompt v2            # after the fix
python -m eval.run_goldens --lab                  # only the 10 lab-set cases
python -m eval.run_goldens --ids D22 D24 --repeat 3   # same question 3 times: how much do answers vary?
python -m eval.run_goldens --replay eval/sample_run_v1.csv --prompt v1   # no API key needed
```

Each run writes `results/<run_id>.csv`. Paste its `actual_output` and `latency_ms`
columns into the workbook's run sheet (rows are in the same order as the goldens),
then score each answer with the rubrics.

`eval/sample_run_v1.csv` holds illustrative answers written for teaching, so the
scoring can be practised without an API key. Replace it with a real run before
drawing conclusions about the bot.

## Run the tests

```bash
pytest -q
```

`test_checks.py` needs no key. `test_scope_live.py` calls the model and is skipped
when `OPENAI_API_KEY` is not set.

## Project layout

```
chatbot.py               ask() + prompts v1/v2 + tracking log + CLI
app.py                   Streamlit UI with the tester panel
eval/goldens.csv         the golden dataset (30 cases)
eval/checks.py           programmatic checks: exact refusal, keywords, forbidden phrases, length, percentile
eval/run_goldens.py      runs the goldens, applies the checks, writes results/<run_id>.csv
eval/sample_run_v1.csv   illustrative answers for practising the scoring
tests/                   tests for the checkers and live scope tests
```

## Deploying to Streamlit Community Cloud

Repo: https://github.com/msktest07/Diet-chatbot

1. Go to https://share.streamlit.io and sign in with GitHub.
2. Click "New app", pick the repo, branch `main`, main file path `app.py`.
3. In **Settings → Secrets** add `OPENAI_API_KEY = "sk-..."`.
4. Deploy and share the `*.streamlit.app` URL with the cohort. The tester panel lets
   everyone switch between prompt v1 and v2.

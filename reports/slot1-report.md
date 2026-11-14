# Slot 1 report: AutoDocs

One row per run worth keeping. Every number comes from a real run.

| Session | Goal | Model | Steps | Input tokens | Output tokens | Cost (USD) | Stop | Notes |
|---|---|---|---|---|---|---|---|---|
| S1 | List the functions `feat/coupon-stacking` adds (diff attached) | gemini-3.5-flash-lite | 1 | 2,485 | 14 | 0.00078 | done | The counting call said 2,449; the extra 36 is the system prompt |
| S2 | Line counts for `app/*` and `data/sample.csv` (practice tools) | gemini-3.5-flash-lite | 3 | 876 | 124 | 0.00057 | done | Two tool calls per turn, both results in one message |
| S2 | The same two counts with one result dropped (planted failure) | gemini-3.5-flash-lite | 3 | 792 | 85 | 0.00045 | done | No error; the model re-asked for the lost result: one extra step vs the 2-step, $0.00037 run |

## S3: v1, the contract (gemini-3.5-flash-lite, 2026-11-14)

Three class branches, run with `python -m autodocs <branch> --repo <ShopLite>` at `s03-b`; table from `python -m autodocs.report`.

| Branch | Model | Stop | Steps | Tool calls | Input tokens | Output tokens | Cost (USD) | Changed functions covered | Docstrings edited | Could not determine |
|---|---|---|---|---|---|---|---|---|---|---|
| `feat/coupon-stacking` | gemini-3.5-flash-lite | done | 2 | 1 | 3,591 | 524 | 0.00239 | 4/4 | 0 | 0 |
| `feat/review-moderation` | gemini-3.5-flash-lite | done | 3 | 2 | 11,285 | 800 | 0.00539 | 7/7 | 0 | 0 |
| `fix/stock-race` | gemini-3.5-flash-lite | done | 3 | 3 | 9,207 | 594 | 0.00425 | 4/4 | 0 | 0 |

Total **$0.01203**; **15 of 15** changed functions covered. Judged against the faculty answer keys, nothing was invented on any of the three branches (the endpoint path came out right: `POST /reviews/<id>/flag`). `score_review_text` is marked `(empty)`.

The planted failure (`score_review_text`'s docstring deleted, branch `feat/review-moderation`, two runs each):

| Contract | What the write-up said about `score_review_text` | Could not determine | Cost (USD) |
|---|---|---|---|
| No `body` field (`s03-a`), run 1 | "Placeholder function for scoring review text using a moderation model." | Nothing | 0.00564 |
| No `body` field (`s03-a`), run 2 | "Stub function for scoring review text with a moderation model." | Nothing | 0.00811 |
| `body` field (`s03-b`), run 1 | `(empty)` with no description | Nothing | 0.00356 |
| `body` field (`s03-b`), run 2 | `(empty)` "Placeholder function for scoring review text with a moderation model." | Nothing | 0.00364 |

Without the field, the only signal was a word in a sentence; with it, code can check `body == "empty"`.

## S4: surviving failures (gemini-3.5-flash-lite, 2026-11-14)

**The broken branch** (`chore/reports-refactor`: `shoplite/services/reports/stock.py` does not parse):

| Version | `low_stock` (in the broken file) | Could not determine | Corrected by code | Cost (USD) |
|---|---|---|---|---|
| v1 (`s03-b`), 2 runs | `implemented`, described as working code | Nothing | — | 0.00288 each |
| `s04-a`, 2 runs | `file does not parse` | The file, plus the reason added by code | 1 each | 0.00274, 0.00413 |

**Retrying a 400** (a tool name with a space, rejected as `400 INVALID_ARGUMENT`):

| How | Result | Time |
|---|---|---|
| One call, no retry | 400 | 0.15–0.5 s |
| The SDK told to retry 400, 4 attempts | The same 400, after 3 retries (back-off 1.1, 2.7, 4.2 s) | 9.5 s |

Nothing improved, and nothing was billed. 16 rejected requests in a minute did not use the free tier's 15-a-minute quota: the 17th, a good request, succeeded.

**Scenarios** (`runs/s4-*`, from `python -m autodocs.report`):

| Scenario | Stop | Steps | Tool calls (errors) | Cost (USD) | Covered | What happened |
|---|---|---|---|---|---|---|
| `AUTODOCS_FAIL_TOOL_CALLS=1` | done | 3 | 2 (1) | 0.00287 | 4/4 | Called `read_diff` again and recovered |
| `AUTODOCS_FAIL_TOOL_CALLS=every` | done | 3 | 2 (2) | 0.00101 | 0/4 | After the nudge (2 failed rounds) it answered and recorded the failure, but still wrote a summary from the branch name alone; coverage shows 0/4 |
| `--budget-tokens 5000` | token budget of 5,000 spent | 2 | 3 (0) | 0.00196 | 0/7 | The hard stop fired; the advisory line didn't make it finish early |

## S5: the same loop on LangChain (gemini-3.5-flash-lite; hand loop 2026-11-14, LangChain re-run 2026-11-15 on langgraph 1.2.22)

Both engines at `s05-b`, the same tools and contract; hand / langchain (`runs/s5-hand`, `runs/s5-langchain`).

| Branch | Steps | Tool calls | Input tokens | Cost (USD) | Covered |
|---|---|---|---|---|---|
| `feat/coupon-stacking` | 2 / 4 | 1 / 5 | 3,775 / 13,129 | 0.00244 / 0.00589 | 4/4 / 4/4 |
| `feat/review-moderation` | 2 / 2 | 1 / 1 | 5,830 / 5,600 | 0.00357 / 0.00356 | 7/7 / 7/7 |
| `fix/stock-race` | 2 / 2 | 1 / 1 | 3,860 / 3,630 | 0.00250 / 0.00237 | 4/4 / 4/4 |

Equal cost on two branches; on `feat/coupon-stacking` the LangChain run opened both changed files and called `write_docstring` twice (5 tool calls), and cost 2.4× as much. Coverage was 15/15 for both.

What the framework path does not do that the hand loop does (read from `langchain_agent.py`): no token budget line or budget stop, no time limit, no give-up guard, no failure injection, although the banner prints the limits. What it chose for us: native structured output (no extra tool call for the answer), and `langchain-google-genai` reads `GOOGLE_API_KEY` before `GEMINI_API_KEY` when no key is passed.

A breaking framework change, rehearsed: in a throwaway environment with `langchain<1` (0.3.30), `from langchain.agents import create_agent` raises `ImportError` and `langchain.agents.middleware` does not exist. LangChain's v1 migration guide explains: `create_agent` replaces `langgraph.prebuilt.create_react_agent`, hooks became middleware, and Python 3.10+ is required.


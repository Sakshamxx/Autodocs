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


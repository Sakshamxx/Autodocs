# Slot 1 report: AutoDocs

One row per run worth keeping. Every number comes from a real run.

| Session | Goal | Model | Steps | Input tokens | Output tokens | Cost (USD) | Stop | Notes |
|---|---|---|---|---|---|---|---|---|
| S1 | List the functions `feat/coupon-stacking` adds (diff attached) | gemini-3.5-flash-lite | 1 | 2,485 | 14 | 0.00078 | done | The counting call said 2,449; the extra 36 is the system prompt |
| S2 | Line counts for `app/*` and `data/sample.csv` (practice tools) | gemini-3.5-flash-lite | 3 | 876 | 124 | 0.00057 | done | Two tool calls per turn, both results in one message |
| S2 | The same two counts with one result dropped (planted failure) | gemini-3.5-flash-lite | 3 | 792 | 85 | 0.00045 | done | No error; the model re-asked for the lost result: one extra step vs the 2-step, $0.00037 run |

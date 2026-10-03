# Trimmed AI build record

Tool used: OpenAI Codex in ChatGPT Work. This document summarizes this actual session; it is not a fabricated Claude/Cursor transcript. No external LLM API was called by the delivered application.

1. User instruction: “let's finish the following assignment,” with business context, exercise brief, and invoice CSV attached.
2. Codex read the exercise/business context and profiled categories: 5,125 rows, 5,000 distinct invoice IDs. It selected Track B because aggregates and business rules dominate the questions.
3. Before implementation, Codex wrote `specs/model.md`, `specs/evaluation.md`, and `AGENTS.md`, then committed them. These artifacts directed the subsequent implementation.
4. Implementation followed the spec: Decimal currency parsing, alias maps, flagged date assumptions, deterministic dedup, SQLite ledger, latest-invoice account snapshots, and six query intents. No claim is made that the customer approved the assumptions.
5. First full-data run exposed two negative amounts labeled paid in conflicting invoice candidates, and 977 accounts with inconsistent plan/region/churn/seats/discount. The implementation quarantined those two candidates and documented snapshot uncertainty.
6. Review identified a risk in broad keyword matching: an extra filter could be ignored. Codex replaced it with full-match supported question patterns, added unsupported-filter tests, and retained an explicit narrow-scope limitation.
7. Codex created an independent small golden fixture with hand-calculated USD amounts and account-level metrics. Thirteen tests ran: twelve passed, one intentionally expected failure for predictive churn. Full CSV integration produced six answers and lineage.

Human involvement: the user supplied the assignment and requested completion. All assumptions, generated code and evaluation were chosen by Codex; this record does not invent human interventions. Before submission, the candidate should review the code and confirm they can explain and defend its assumptions.

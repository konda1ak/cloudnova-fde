# Validation recorded during build

- `python -m unittest discover -s evals -v`: 13 cases; 12 pass, 1 expected failure (unsupported predictive churn). Full output: `eval_output.txt`.
- `python -m app`: six stakeholder questions execute successfully on the provided dataset. Reproducible output: `sample_answers.json`.
- Full-data checks: 5,000 invoices, 3,815 unique account snapshots; 977 snapshot conflict flags; input-row accounting balances (5,125 = 5,000 + 123 + 2).
- Both quarantined invoice IDs have a valid retained candidate. Quarantine reason: negative amount with paid status.
- Read-only guard rejects DELETE. Unsupported filters and injection-like question text are rejected before query execution.

Expected values in unit evals are hand-calculated from the fixture, not generated from production SQL. Full-data observed answers are integration evidence, not independently reconciled financial totals. No cloud deployment or GitHub publishing was performed.

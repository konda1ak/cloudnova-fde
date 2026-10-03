# Suggested 3–5 minute walkthrough

1. Explain the finance ask and why Track B makes aggregates reproducible.
2. Show the spec-first commit and the MRR/revenue/dedup rules.
3. Run `python -m app`; show paid revenue, account-level MRR and churn.
4. Show SQL, source hash, lineage and audit outputs.
5. Run `python -m unittest discover -s evals -v`; explain the intentional prediction failure.
6. Explain the 977 account attribute conflicts, unsupported NL wording, and which assumptions require finance confirmation.

Be clear that Codex implemented the system under the recorded spec; review each module before presenting it as your submission.

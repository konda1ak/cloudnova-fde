# CloudNova — trustworthy invoice answers

**Track B: spec-driven pipeline + constrained natural-language query agent.** Cleans the provided ledger and answers all six finance questions, showing the exact SQL, parameters, source hash and row lineage. Everything runs locally without dependencies or an API key.

## Setup and demo

Python **3.11+** is required. From the repository directory:

```bash
python -m app
```

This single command rebuilds `output/ledger.sqlite`, writes quality/dedup/quarantine reports and answers, and prints all six questions with their results.

```bash
python -m app --ask 'What was our total recognized revenue in USD for paid invoices in 2024?'
python -m app --ask 'net revenue in 2024'
python -m app --input data/cloudnova_invoices.csv --output output
python -m unittest discover -s evals -v
```

No setup installation is needed. No credentials are required or committed. Output and `.env` are ignored. `--input`, `--output`, and `--ask` configure the application.

## Spec and business choices

The [model spec](specs/model.md) and [eval spec](specs/evaluation.md) were committed before implementation. [AGENTS.md](AGENTS.md) contains Codex instructions; [the AI build record](docs/ai-build-log.md) records the actual decisions and correction. [Architecture](docs/architecture.md) matches the code.

- Paid-only revenue is separate from **net recognized revenue** (paid plus negative refunds). Local amounts are authoritative; discount is not reapplied. EUR/GBP use the briefing's fixed FX; monetary parsing/calculation uses Decimal and integer cents.
- Conflicting invoice IDs use refunded > paid > void > failed > pending, then earliest CSV row. This is an assumption in the absence of update timestamps. Every discarded record is audited; invalid candidates are quarantined.
- MRR and churn use one latest-invoice snapshot per account. Active means not churned. Annual MRR uses the monthly list-price formula, not annual invoice amount divided by 12. Churn is cumulative snapshot churn, not monthly cohort churn.
- Slash numeric dates use month/day/year; hyphen numeric dates use day/month/year. Ambiguity is flagged. Nullable CSAT remains unknown, never silently low or high.

## Observed results

Full-data results under those assumptions; not externally reconciled accounting truth:

| Question | Result |
|---|---:|
| Paid-only recognized revenue in 2024 | $32,686,371.20 |
| Highest average MRR per active account | APAC: $6,147.30 (753 accounts) |
| Refunds, all time | $8,925,163.84 |
| Enterprise vs Starter snapshot churn | 21.92% vs 18.81% |
| Pending/failed exposure | 894 invoices; $28,983,255.97 |

The top-five account results and exact queries are in [sample answers](docs/sample_answers.json). Source: 5,125 rows → 5,000 cleaned invoices, 123 discarded duplicate candidates, 2 quarantined invalid candidates; 3,815 accounts. See [quality report](docs/quality_report.json). The two quarantined rows are negative amounts marked paid; valid versions of both IDs remain in the ledger.

## Query contract and trade-offs

This is a **deterministic natural-language intent router**, not a general-purpose LLM text-to-SQL system. It recognizes the six exact stakeholder questions from the briefing (case/punctuation insensitive), plus aliases: `paid revenue in 2024`, `net revenue in 2024`, `refunds`, `churn rate Enterprise vs Starter`, `top 5 accounts by revenue`, and `pending/failed exposure`. Revenue aliases accept an explicit four-digit year. Other filters and wording are rejected; nothing is silently ignored. Answers are machine-readable JSON rather than generated prose.

Reviewed SQL templates provide reproducible calculations and avoid model hallucinations, arbitrary SQL and API costs. SQLite and the standard library keep setup small and fit this dataset; no orchestration/framework or cloud deployment is needed. Account and invoice query grains are explicit. The read-only connection/authorizer and strict templates are the primary hardening touch; CI also runs the evals and demo.

Each response contains contributing-record count, up to ten CSV source-row samples and a lineage query for **all** contributing records. The top-account CSAT comes from `accounts` (latest snapshot); its source can be found via `SELECT account_id, source_row FROM accounts`. Sample citations are not a complete list. The SHA-256 binds answers to the input bytes.

## Evaluation and known limits

Run the eval command above. **12 passing tests + 1 expected failure** cover golden revenue/net/refund calculations, FX, MRR, churn grain, CSAT, exposure, parsing, dedup/audit, quarantine, read-only execution and rejected filters. The expected failure asks for future churn prediction: the agent abstains because the data has no future labels or reliable lifecycle history. These tests prove a narrow slice; they do not establish finance approval of assumptions. See [validation report](docs/validation.md).

**977 accounts have inconsistent modeled attributes** across invoices. Their latest-invoice snapshots may misrepresent present-day subscription state. There is no reliable event timestamp for invoice correction precedence, subscription lifecycle, churn date, invoice payment date or historical CSAT. Date ambiguity can alter year-boundary membership. Revenue is attributed by invoice issue date per the question, not payment date or GAAP service-period recognition. Fixed FX is not historical FX. Amounts are not reconciled to expected pricing, and integer monetary totals eventually use SQLite rounding for display; this is suitable for the supplied scale, not arbitrary-precision warehousing.

The interface supports documented questions, not arbitrary natural language, follow-ups, forecasts or user-selected dimensions. Input validation is in the pipeline; SQLite is not a public write API. The output directory is single-writer; concurrent builds are unsupported. Audit JSON sidecars are not transactional with the database. The pipeline and query layer are a local demo, not an authenticated multi-tenant service.

## Another day

Confirm dedup/date/active-account definitions with finance; obtain invoice update timestamps and subscription lifecycle events; measure answer sensitivity to alternate dedup policies; reconcile pricing and FX; add account-level conflict review; expand evals with null/unknown-category edge cases. Then add an LLM **structured intent** adapter that must satisfy this same validated contract, rather than executing unrestricted model SQL.

## Submission and walkthrough

The repository has small real commits. It has not yet been pushed to GitHub; create an empty repository and push this history:

```bash
git remote add origin https://github.com/YOUR_USERNAME/cloudnova-fde.git
git branch -M main
git push -u origin main
```

A 3–5 minute walkthrough can follow [docs/walkthrough.md](docs/walkthrough.md). This is a compact build with explicit limitations; no claim is made that active work duration was measured to exactly one hour.

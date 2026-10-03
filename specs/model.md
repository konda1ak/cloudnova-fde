# Build spec — Track B (written before implementation)

## Scope and contract
Python 3.11+ standard library; CSV → validated invoice rows → SQLite → constrained natural-language intent → parameterized SELECT → JSON with SQL and provenance. No API key. Support the six stakeholder question families; reject unsupported questions rather than guess. This is a deterministic query agent, not an LLM translator.

## Clean schema and validation
Invoice grain: unique invoice_id. Retain account_id/name, normalized region/plan/cycle/status/currency/payment_method, nullable contact_email/industry/csat, integer seats/support_tickets, numeric discount, ISO signup/invoice dates, boolean churned, local and USD amounts in integer cents, USD MRR in cents, input CSV source row (header = row 1), flags. Required IDs nonempty; plan Starter/Pro/Enterprise; cycle monthly/annual; status paid/pending/failed/refunded/void; currency USD/EUR/GBP; region NA/EMEA/APAC/LATAM; seats positive; discount 0–100; CSAT null or 1–5; support tickets nonnegative. Invalid rows go to quarantine with reason and original record, never silent coercion.

Aliases include Start/Tier 1 → Starter, Professional/Tier 2 → Pro, ENT/Tier 3 → Enterprise. Case/space insensitive. Status and cycle aliases follow briefing. Blank optional text → null. Repair `_at_` in emails, flag repair; malformed remaining emails → null + flag.
Dates: ISO/slash year-first, English abbreviated month, slash month/day/year, hyphen day/month/year. Ambiguous numeric dates flagged. This is an explicit assumption, not recovered source truth.
Amounts: strip known currency symbols, comma grouping, matching currency suffix; Decimal with half-up cent rounding. Fixed FX USD=1 EUR=1.08 GBP=1.27. Refunded amounts must be negative; other amounts must be nonnegative. Invoice amounts are authoritative (do not apply discount twice).
MRR = USD list price × seats × (1−discount/100); annual incentive does not change MRR.

## Dedup and account modeling
Validate candidates first. Full duplicates removed (all original fields equal). For conflicting valid invoice IDs: refunded > paid > void > failed > pending, then smallest source row. Preserve every loser, reason, and winning source row in dedup audit. No update timestamps exist: priority is a documented assumption and may discard a correction. Invalid candidate remains quarantined even if its ID has a valid winner.
One account snapshot: latest invoice_date, then invoice_id lexicographically descending. Attributes and churn come from that one row; flag accounts whose invoice attributes disagree. Active means snapshot churned=false; ledger has no subscription lifecycle events. MRR averages include each active account once, regardless of latest payment status. Churn rate uses all account snapshots per plan, not invoices, and is cumulative observed churn, not period churn.

## Metric semantics
Paid revenue for requested year = paid USD amount sum, date-filtered. Net recognized revenue = paid + negative refunded. Refunds displayed as positive magnitude. Top 5 = all-time net revenue by account with snapshot CSAT ≤2 flag. Exposure = pending/failed invoice count and USD amount. Regional MRR = average active account snapshot MRR. Results include SQL/parameters, source hash, qualifying record count, and sample source rows; samples are not exhaustive citations.

## Safety and operations
Only known SELECT templates, bound parameters, read-only query connection, SQLite authorizer blocks writes, and row cap. Pipeline builds temporary DB then atomic replacement. Output artifacts ignored by git. Input path configurable; no secrets. Unknown NL filters, multiple intents, or missing/ambiguous years rejected. Demo single command: python -m app.

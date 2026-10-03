# Implemented architecture

```mermaid
flowchart TD
    A[Raw invoice CSV] --> B[Validate and normalize]
    B --> C[Quarantine JSON]
    B --> D[Resolve duplicate invoice IDs]
    D --> E[Dedup audit JSON]
    D --> F[SQLite invoices and account snapshots]
    Q[Natural language question] --> R[Restricted intent and SQL templates]
    R --> S[Read only parameterized query]
    F --> S
    S --> T[JSON answer with SQL and source lineage]
```

`app.pipeline.build` creates the store and audit artifacts. `app.query.plan` maps explicitly supported question wording to reviewed SQL; `ask` executes it through a read-only authorized SQLite connection. `python -m app` rebuilds the store and prints six answers (or one `--ask` answer). No vector store, external LLM, web service, or frontend is implied.

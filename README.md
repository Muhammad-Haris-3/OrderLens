# OrderLens — Marketplace Operations Analytics

> **Which operational failures cost the most revenue, and what should be fixed first?**

An end-to-end analytics engagement on ~100k real marketplace orders: from nine
raw CSVs, through a tested dimensional warehouse, to a controlled statistical
estimate of what a late delivery actually costs — ending in a costed
recommendation a business could act on.

**The deliverable is a decision, not an app.** The pipeline exists to make that
decision trustworthy and reproducible.

> 🚧 **In progress.** M0 (Foundation) complete. Headline findings land at M5;
> dashboard and decision memo at M7. See [milestones](#milestones).

---

## Why this project exists

Most analytics portfolios stop at "here are some charts." This one is built to
answer the question a business actually asks — *what should we do?* — and to
survive being challenged on it:

- **Analysis happens in SQL**, not pandas. Transformation, aggregation and
  cohorting are dbt models; Python is reserved for statistics and modelling.
- **Every test reports an effect size**, not just a p-value. Significance
  without magnitude is not a finding.
- **The causal claim is defended.** Delay-to-satisfaction is estimated with
  controls, and the limits of an observational design are stated explicitly
  rather than glossed.
- **Negative results ship.** If delay turns out not to drive satisfaction once
  confounders are handled, that is the finding (SRS NFR-8).

---

## Architecture

```
9 source CSVs (~120 MB)
        │  Python loader — idempotent, COPY-based, row-count reconciled
        ▼
   RAW layer      untyped text, source fidelity preserved
        │  dbt
   STAGING layer  typed, renamed, deduplicated
        │  dbt
   MARTS layer    star schema — facts + dimensions, tested grain
        │
        ├──────────────► Python: hypothesis tests, regression, classifier
        └──────────────► Tableau Public: interactive dashboard
                                    │
                                    ▼
                            Decision memo
```

**Why raw is untyped:** typing at load time would reject malformed rows, hiding
the exact anomalies the M2 data-quality audit exists to find. Casting happens in
staging where a failure is visible and testable.

---

## Stack

| Layer | Technology | Why |
|---|---|---|
| Warehouse | PostgreSQL (Neon) | Free, persistent, remotely reachable by Tableau |
| Transformation | dbt-core | Lineage, testing and docs as first-class citizens |
| Statistics | scipy, statsmodels | Regression *with inference*, which scikit-learn omits |
| Modelling | scikit-learn | Classifier with cost-based thresholding |
| Dashboard | Tableau Public | Free public publishing; signals analyst, not developer |
| CI | GitHub Actions | ruff + pytest on every push |

---

## Getting started

```bash
python -m venv venv && venv/Scripts/activate      # Windows
pip install -r requirements.txt
cp .env.example .env                               # then fill in Neon credentials
```

Obtain the dataset — see [data/raw/README.md](data/raw/README.md) — then:

```bash
python scripts/load_raw.py --check
```

Verifies all nine files are present with the expected headers, without touching
the database. Then create the schema and load:

```bash
psql "$DATABASE_URL" -f sql/raw_schema.sql
python scripts/load_raw.py
```

The loader truncates and reloads every table, reconciles file row counts against
landed row counts, records both in `raw.load_log`, and **fails rather than
warns** on any mismatch.

---

## Testing

```bash
pytest -q          # config-integrity tests (no data or DB required)
ruff check .       # lint
```

The current suite guards a specific silent failure: if a column is added to
`sql/raw_schema.sql` but not to the loader's expected header, `COPY` shifts
every subsequent column by one and lands a fully populated, entirely wrong
table. dbt data-quality tests join the suite at M3.

---

## Milestones

| # | Milestone | Delivers | Status |
|---|---|---|---|
| M0 | Foundation — repo, warehouse DDL, loader, CI, data dictionary | Reproducible skeleton | ✅ [Summary](OrderLens_M0_Summary.md) |
| M1 | Ingestion — raw layer loaded, row counts reconciled | FR-1 | ⬜ |
| M2 | Data-quality audit — anomalies found and adjudicated | FR-4 | ⬜ |
| M3 | Dimensional model — staging + marts, tests green | FR-2, FR-3 | ⬜ |
| M4 | Descriptive — delivery, cohorts, RFM, revenue concentration | FR-5–8 | ⬜ |
| M5 | Inferential — effect sizes, controlled regression | FR-9–13 | ⬜ |
| M6 | Predictive — cost-optimised classifier | FR-14–17 | ⬜ |
| M7 | Communication — dashboard, decision memo, A/B design | FR-18–21 | ⬜ |

---

## Documentation

| Document | Contents |
|---|---|
| [SRS v1.0](OrderLens_SRS_v1.0.md) | Requirements, feasibility, architecture decisions, analysis plan, risks |
| [Data Dictionary](docs/data_dictionary.md) | Source fields and — more importantly — every derived measure's formula |


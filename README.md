# OrderLens — Marketplace Operations Analytics

> **Which operational failures cost the most revenue, and what should be fixed first?**

An end-to-end analytics engagement on ~100k real marketplace orders: from nine
raw CSVs, through a tested dimensional warehouse, to a controlled statistical
estimate of what a late delivery actually costs — ending in a costed
recommendation a business could act on.

**The deliverable is a decision, not an app.** The pipeline exists to make that
decision trustworthy and reproducible.

> 🚧 **In progress.** M3 (Dimensional model) complete — the warehouse is loaded,
> audited and modelled, with 156 dbt tests green. Headline findings land at M5;
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
psql "$DATABASE_URL" -f sql/raw_indexes.sql
```

The loader truncates and reloads every table, reconciles file row counts against
landed row counts, records both in `raw.load_log`, and **fails rather than
warns** on any mismatch. The indexes are on join keys only — an index asserts
nothing about the data, so raw keeps its source fidelity while the audit and the
M3 builds stop scanning a million rows at a time.

---

## The data-quality audit

```bash
python scripts/run_audit.py          # run all 30 checks, regenerate the evidence
python scripts/run_audit.py --list   # list the checks; no database needed
```

Thirty committed queries in [`sql/audit/`](sql/audit) interrogate the raw layer.
The runner executes them in a **read-only** session — the audit cannot alter what
it measures — and writes every returned row to
[`docs/data_quality_audit_results.md`](docs/data_quality_audit_results.md).

The findings are adjudicated in
[`docs/data_quality_audit.md`](docs/data_quality_audit.md), where every figure
cites the check that produced it. The most consequential one:
`order_estimated_delivery_date` is a date stored at midnight while
`order_delivered_customer_date` is a real timestamp, so the obvious subtraction
counts **1,292 on-time deliveries as late** — understating the project's central
estimate by 14%.

---

## Building the warehouse

```bash
python scripts/run_dbt.py deps
python scripts/run_dbt.py build
```

`build` runs all 17 models then all 139 data tests. The wrapper loads `.env` and
invokes dbt through `python -m dbt.cli.main`, so the same two commands work on
any shell whether or not the virtualenv is activated (NFR-1).

Three layers, each with one job:

| Layer | Schema | Materialised as | Job |
|---|---|---|---|
| Raw | `raw` | Tables (Python loader) | Source fidelity. Untyped text, no constraints |
| Staging | `analytics_staging` | Views | Type, rename, deduplicate. One source each, **no joins** |
| Marts | `analytics_marts` | Tables | The star schema Tableau and the analysis query |

Full rebuild takes **1m 50s** on free-tier Neon.

### The tests that matter

Most of the 139 are schema tests — uniqueness, not-null, referential integrity,
accepted values. Seven are not, and those are the ones worth reading:

| Test | Catches |
|---|---|
| `assert_repeat_customers_exist` | `dim_customers` keyed on the per-order id. The key is still unique, so **no schema test can see this** — it just reports a 100% first-time customer base |
| `assert_delay_days_is_whole_days` | `delay_days` reverting to timestamp arithmetic, which returns a valid number for every order and shrinks the headline effect by 14% |
| `assert_fct_orders_grain_preserved` | Any fan-out. Joining raw geolocation inflates the fact table **151.7×** while producing perfectly valid rows |
| `assert_durations_are_never_negative` | Backwards timestamps clamped to zero instead of nulled, silently pulling segment means down |
| `assert_centroids_inside_brazil` | One out-of-hemisphere coordinate dragging a ZIP prefix — and every distance from it — off the map |
| `assert_delivery_measures_respect_eligibility` | A status-only filter admitting 8 orders with no delivery timestamp, or a timestamp-only filter admitting 6 cancelled ones |
| `assert_order_value_reconciles_to_items` | The two fact grains disagreeing about money — a dashboard whose total contradicts its own drill-down |

Every one of these guards a failure that is **structurally valid and
semantically wrong**. Each was verified against the wrong implementation to
confirm it actually fires; a test that cannot fail is decoration.

---

## Testing

```bash
pytest -q          # 36 tests — no data or database required
ruff check .       # lint
```

The suite guards specific silent failures rather than exercising code paths:

- **Loader vs DDL drift** — a column added to `sql/raw_schema.sql` but not to the
  loader's expected header makes `COPY` shift every subsequent column by one and
  land a fully populated, entirely wrong table.
- **Audit integrity** — check ids contiguous, filenames matching ids, no audit
  query containing a write or DDL keyword, every `A-nn` cited in the audit
  document resolving to a query that exists, all five deferred design decisions
  covered.
- **`_sources.yml`** — parses, matches the loader's table list, and its
  `accepted_values` still match what the audit measured.
- **dbt structural rules** — staging models never join, marts never read `raw`
  directly, `delay_days` is still computed on `::date`, `dim_customers` is still
  keyed on the person, and every bespoke test still exists by name.

`dbt build` needs the loaded warehouse and ~120 MB of uncommitted CSV, so CI runs
`dbt parse` instead — which compiles every model, test and macro without
connecting — plus the structural tests above.

---

## Milestones

| # | Milestone | Delivers | Status |
|---|---|---|---|
| M0 | Foundation — repo, warehouse DDL, loader, CI, data dictionary | Reproducible skeleton | ✅ [Summary](OrderLens_M0_Summary.md) |
| M1 | Ingestion — raw layer loaded, row counts reconciled | FR-1 | ✅ [Summary](OrderLens_M1_Summary.md) |
| M2 | Data-quality audit — anomalies found and adjudicated | FR-4 | ✅ [Summary](OrderLens_M2_Summary.md) |
| M3 | Dimensional model — staging + marts, tests green | FR-2, FR-3 | ✅ [Summary](OrderLens_M3_Summary.md) |
| M4 | Descriptive — delivery, cohorts, RFM, revenue concentration | FR-5–8 | ⬜ |
| M5 | Inferential — effect sizes, controlled regression | FR-9–13 | ⬜ |
| M6 | Predictive — cost-optimised classifier | FR-14–17 | ⬜ |
| M7 | Communication — dashboard, decision memo, A/B design | FR-18–21 | ⬜ |

---

## Documentation

Everything is documented as it's built — what was decided, why, and what broke
along the way.

### Specification and design

| Document | Contents |
|---|---|
| [SRS v1.0](OrderLens_SRS_v1.0.md) | 21 functional + 8 non-functional requirements, feasibility study, architecture decisions with rejected alternatives, analysis plan, 7 risks |
| [Design Phase v1.1](OrderLens_Design_Phase_v1.0.md) | Every model, its grain, its tests, and why it's shaped that way — layer architecture, star schema, test strategy, leakage rules. Amended by the M2 audit; no open decisions |
| [Data Dictionary](docs/data_dictionary.md) | Source fields, and every derived measure's exact formula |
| [Data-Quality Audit](docs/data_quality_audit.md) | 17 findings graded and adjudicated, five deferred design decisions resolved — the M2 deliverable |
| [Audit Results](docs/data_quality_audit_results.md) | Generated evidence: the exact rows every one of the 30 audit queries returned |

Model-level documentation lives with the models:
[staging](dbt_orderlens/models/staging/_staging_models.yml),
[marts](dbt_orderlens/models/marts/_marts_models.yml).

### Milestone record

Each summary documents what was built, how it was verified, and the problems
found — including the ones that were caught before they did damage.

| # | Milestone | Notable finding |
|---|---|---|
| [M0](OrderLens_M0_Summary.md) | Foundation | Two dataset traps documented as risks *before* being hit |
| [M1](OrderLens_M1_Summary.md) | Ingestion | A UTF-8 BOM that would have silently broken every category join |
| [M2](OrderLens_M2_Summary.md) | Data-quality audit | A unit mismatch between the delivery promise and the delivery measurement, understating the project's central estimate by 14% |
| [M3](OrderLens_M3_Summary.md) | Dimensional model | The geolocation fan-out is 151.7× on the join that matters, not the 52.6× the average suggested |


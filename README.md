# OrderLens — Marketplace Operations Analytics

> **Which operational failures cost the most revenue, and what should be fixed first?**

An end-to-end analytics engagement on ~100k real marketplace orders: from nine
raw CSVs, through a tested dimensional warehouse, to a controlled statistical
estimate of what a late delivery actually costs — ending in a costed
recommendation a business could act on.

**The deliverable is a decision, not an app.** The pipeline exists to make that
decision trustworthy and reproducible.

> ✅ **Complete — all seven milestones, all 21 requirements delivered.**
>
> **The finding:** customers do not punish slow delivery. They punish **broken
> promises**. Orders that take the *same* time to arrive score a full point lower
> when they miss the quoted date.
>
> 📊 **[Live dashboard](https://public.tableau.com/app/profile/muhammad.haris2276/viz/OrderLens/Dashboard1)**
> · 📄 **[Decision memo](docs/decision_memo.md)** (2 pages, no technical background needed)

---

## The answer

**Customers do not punish us for slow delivery. They punish us for broken
promises.**

Orders that took the same time to arrive score a full review point lower when
they missed the quoted date. The effect survives controlling for the actual wait
(−1.56 of a 5-point scale), and it is the *threshold* that costs, not the
overshoot — being one day late does nearly all the damage.

**Recommendation:** extend the quoted date only on routes that demonstrably miss
it. Touches 19% of orders, cuts broken promises from 8.8% to 7.0%, and prevents
~560 bad reviews a year. It is free to run; the risk is conversion, which this
data cannot measure — so the deliverable is a costed A/B test, not a rollout.

**Two honest bounds:** two-thirds of bad reviews are on orders that arrived *on
time*, so this addresses about a third of the problem; and with a 2.24% repeat
rate, the case cannot rest on retention.

→ **[The decision memo](docs/decision_memo.md)** (2 pages, no technical background needed)
→ **[The dashboard](https://public.tableau.com/app/profile/muhammad.haris2276/viz/OrderLens/Dashboard1)** (Tableau Public — delivery performance, impact, and where to fix it first)

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

`--data-dir` and `--schema` exist so a sample load can never overwrite a real raw
layer by pointing at the wrong database. CI uses both; so does
`scripts/make_sample.py`, which regenerates the committed CI fixture:

```bash
python scripts/make_sample.py
```

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

## Running the analysis

```bash
python analysis/descriptive.py     # M4 — regenerates docs/descriptive_results.md
python analysis/inferential.py     # M5 — regenerates docs/inferential_results.md
python analysis/predictive.py      # M6 — regenerates docs/predictive_results.md
python analysis/decision.py        # M7 — regenerates docs/decision_results.md
```

**Aggregation happens in SQL, not in Python.** Every count, sum, rate and ranking
published in M4 is a `select` against one of five analysis marts
(`mart_delivery_monthly`, `mart_delay_buckets`, `mart_cohort_retention`,
`mart_customer_rfm`, `mart_revenue_concentration`). The script computes the Gini
coefficients, the top-N share curve and the review-timing sensitivity — three
things that are genuinely statistics — and nothing else.

That is not stylistic. Because the numbers live in marts, the M7 dashboard reads
the same definitions rather than a parallel set that will eventually disagree
with them. A test enforces it: anything in `analysis/` that reaches into `raw` or
`analytics_staging` fails the suite.

---

## Testing

```bash
pytest -q          # 52 tests — no data or database required
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
- **The M6 leakage rule** — no post-delivery column is declared as a model
  feature, the feature mart projects none, and the seller track record is still
  computed as-of the purchase timestamp. Training on `is_late` would look superb
  and be worthless; these tests run without a database so a leak cannot reach
  `main` even if nobody runs the model.

### What CI actually runs

`ruff`, the 52 Python tests, **and the full `dbt build`** — all 24 models and all
193 data tests — on every push.

The dbt tests need a loaded warehouse, and the source dataset is ~120 MB of CSV
that is deliberately not committed. So CI stands up a throwaway Postgres and
loads [a committed sample fixture](tests/fixtures/raw_sample/README.md) instead:
~1.5 MB, **grown outward** from a stratified seed of orders until every foreign
key resolves.

Grown, not sampled row by row — independent sampling produces items whose order
does not exist, and then every `relationships` test fails for reasons that have
nothing to do with the code under test. The fixture deliberately preserves all
eight order statuses, 194 repeat customers, and more than one geolocation row per
ZIP prefix. Each of those, if lost, would silently disable a test while leaving
CI green; the repeat customers matter most, because without them
`assert_repeat_customers_exist` — the risk R-1 guard — cannot be satisfied at any
threshold, and the tempting fix is to stop running it.

CI does **not** verify any figure in the milestone documents. Those come from the
full warehouse. The fixture proves the pipeline is correct, not that the numbers
reproduce.

---

## Milestones

| # | Milestone | Delivers | Status |
|---|---|---|---|
| M0 | Foundation — repo, warehouse DDL, loader, CI, data dictionary | Reproducible skeleton | ✅ [Summary](OrderLens_M0_Summary.md) |
| M1 | Ingestion — raw layer loaded, row counts reconciled | FR-1 | ✅ [Summary](OrderLens_M1_Summary.md) |
| M2 | Data-quality audit — anomalies found and adjudicated | FR-4 | ✅ [Summary](OrderLens_M2_Summary.md) |
| M3 | Dimensional model — staging + marts, tests green | FR-2, FR-3 | ✅ [Summary](OrderLens_M3_Summary.md) |
| M4 | Descriptive — delivery, cohorts, RFM, revenue concentration | FR-5–8 | ✅ [Summary](OrderLens_M4_Summary.md) |
| M5 | Inferential — effect sizes, controlled regression | FR-9–13 | ✅ [Summary](OrderLens_M5_Summary.md) |
| M6 | Predictive — cost-optimised classifier | FR-14–17 | ✅ [Summary](OrderLens_M6_Summary.md) |
| M7 | Communication — dashboard, decision memo, A/B design | FR-18–21 | ✅ [Summary](OrderLens_M7_Summary.md) |

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
| [Descriptive Findings](docs/descriptive_findings.md) | Delivery performance, retention, RFM and revenue concentration interpreted — the M4 deliverable |
| [Descriptive Results](docs/descriptive_results.md) | Generated evidence for the above, straight from the analysis marts |
| [Inferential Findings](docs/inferential_findings.md) | The controlled estimate, and **the FR-12 limitations statement** — what the number is and is not worth |
| [Inferential Results](docs/inferential_results.md) | Generated evidence: every test statistic, confidence interval and p-value |
| [Predictive Findings](docs/predictive_findings.md) | The classifier, its cost-based threshold, and why its ceiling matters more than its score |
| [Predictive Results](docs/predictive_results.md) | Generated evidence: baselines, thresholds, importances, calibration |
| **[Decision Memo](docs/decision_memo.md)** | **Two pages, plain language — the deliverable this project exists to produce** |
| [Decision Results](docs/decision_results.md) | Generated evidence: mechanism test, policy simulation, break-even, A/B power |
| [Dashboard Spec](docs/dashboard_spec.md) | Three views, fields, colourblind-safe encodings, and what the dashboard must not imply |
| **[Live Dashboard](https://public.tableau.com/app/profile/muhammad.haris2276/viz/OrderLens/Dashboard1)** | **Published on Tableau Public** |

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
| [M4](OrderLens_M4_Summary.md) | Descriptive analysis | Review timing is *caused by* the delay — 96% of late orders were reviewed before arrival, which overturned an M2 handling decision |
| [M5](OrderLens_M5_Summary.md) | Inferential analysis | BQ-3's premise is false: there is no per-day price. Breaching the promise costs 1.71 review points; the next 113 days cost as much again |
| [M6](OrderLens_M6_Summary.md) | Predictive model | Two-thirds of bad reviews are on orders that arrived *on time* — so fixing delivery entirely reaches at most a third of the problem |
| [M7](OrderLens_M7_Summary.md) | Communication | The damage is the broken promise, not the wait — and the obvious fix (recalculating quotes from route history) makes things measurably worse |


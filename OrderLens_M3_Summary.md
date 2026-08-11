# OrderLens — M3 (Dimensional Model) Milestone Summary

**Date:** 2026-08-11
**Status:** Complete
**Maps to:** SRS FR-2 (documented dimensional model with declared grain) and
FR-3 (data-quality tests on every model)

---

## 1. Scope

Turn the audited raw layer into the star schema the analysis and the dashboard
query — nine staging views, five dimensions, three facts — with every grain
declared and tested, and every M2 decision encoded in SQL rather than in a
document.

The Design Phase was written to make this milestone *typing, not deciding*
(v1.1, §Purpose). It largely was: no design decision was reopened, and the only
changes below are consequences of decisions M2 had already taken.

---

## 2. What was built

**17 models. 139 dbt data tests. All green.**

| Layer | Schema | Materialisation | Models |
|---|---|---|---|
| Staging | `analytics_staging` | Views | 9 |
| Marts | `analytics_marts` | Tables | 8 |

### Staging — one source each, no joins

| Model | Rows | Note |
|---|---|---|
| `stg_orders` | 99,441 | `estimated_delivery_date` typed as **DATE**, which is what the source stores |
| `stg_order_items` | 112,650 | |
| `stg_order_payments` | 103,886 | |
| **`stg_order_reviews`** | **98,673** | Deduplicated from 99,224 — grain is `order_id` (D-1) |
| `stg_customers` | 99,441 | Per-order key; **not** collapsed to the person here |
| `stg_sellers` | 3,095 | |
| `stg_products` | 32,951 | Source misspellings corrected; 4 zero weights nulled |
| `stg_product_categories` | 71 | Straight passthrough — the gap is handled in `dim_products` |
| **`stg_geolocation`** | **19,010** | Aggregated from 1,000,163. This model kills risk R-2 |

### Marts — the star schema

| Model | Grain | Rows |
|---|---|---|
| `dim_customers` | one **person** (`customer_unique_id`) | 96,096 |
| `dim_products` | one product | 32,951 |
| `dim_sellers` | one seller | 3,095 |
| `dim_geography` | one ZIP prefix | 19,010 |
| `dim_dates` | one calendar day, **generated** | 800 |
| **`fct_orders`** | one order — **all** of them | **99,441** |
| `fct_order_items` | (order_id, order_item_id) | 112,650 |
| `fct_payments` | (order_id, payment_sequential) | 103,886 |

Full rebuild: **1 minute 50 seconds** on free-tier Neon, against NFR-4's
10-minute budget.

---

## 3. The marts reproduce the audit exactly

The point of M2 was to decide what the model should say. This is the check that
it says it — every figure below was produced by M2 against the *raw* layer and
re-derived here from the *marts*, independently:

| Figure | M2 audit | `analytics_marts` |
|---|---|---|
| Orders | 99,441 | 99,441 ✅ |
| Delivery-eligible orders | 96,470 | 96,470 ✅ |
| Late orders (calendar-day rule) | 6,534 | 6,534 ✅ |
| **Late rate** | **6.77%** | **6.77%** ✅ |
| Mean review score, late | 2.270 | 2.270 ✅ |
| Mean review score, on time | 4.290 | 4.290 ✅ |
| **Delay-to-satisfaction gap** | **2.020** | **2.020** ✅ |
| `delay_days` min / median / max | −147 / −12 / 188 | −147 / −12 / 188 ✅ |
| People (not customer_ids) | 96,096 | 96,096 ✅ |
| Repeat customers | 2,997 | 2,997 ✅ |
| Orders with no items | 775 | 775, `order_value` **null** ✅ |
| Category coverage | 32,328 / 13 / 610 | 32,328 / 13 / 610 ✅ |
| Negative durations | 165 + 23 | **0** — nulled as decided ✅ |

One number reconciles in a way worth spelling out. `fct_orders` totals
**R$15,843,553.24** of order value. A-24 measured **R$15,843,409.78** across
orders that have *both* payments and items. The difference is **R$143.46** —
exactly the value of the single order in the dataset with no payment record
(M2 F-04). The two figures were never meant to match, and the amount by which
they don't is the thing that explains why.

---

## 4. Where the marts legitimately differ from the audit

Two figures moved, and neither is an error. Both are consequences of decisions
M2 took, showing up where they were supposed to.

### `stg_geolocation` has 19,010 prefixes, not 19,015

M2 decided (F-13) to discard the 42 coordinates outside Brazil *before*
averaging. **Five ZIP prefixes consisted entirely of out-of-bounds points** and
disappeared with them.

That is a cost the audit did not quantify, so it was quantified here: of the
five, four are referenced by nobody. The fifth is used by **one customer**. The
customer-without-coordinates count therefore moves from 278 to **279**, and
seller coverage is unchanged at 7.

One customer against 42 impossible coordinates is a trade worth making, but it
is a trade, and it is now on the record rather than absorbed silently.

### Reviews answered before delivery: 4,653, not 4,795

A-27 counted **review rows**; `fct_orders` counts **orders**, after the D-1
deduplication. The chain reconciles exactly:

| Step | Count |
|---|---|
| Review rows answered before delivery (A-27) | 4,795 |
| Distinct orders those rows belong to | 4,769 |
| Less orders whose *latest* review came after delivery | −115 |
| Less one cancelled-but-delivered order, now ineligible (F-03) | −1 |
| **Orders flagged `reviewed_before_delivery`** | **4,653** |

115 orders carry reviews on *both* sides of delivery. Keeping the latest picks
the one written with the parcel in hand, which is the more informative of the
two — a small, unplanned benefit of the D-1 rule.

---

## 5. The bespoke tests, and proof they can fail

Schema tests confirm structure. The Design Phase (§7) argues that the failures
that actually threaten this project are **structurally valid and semantically
wrong**, and that only assertions about meaning catch them.

Seven such tests were written. A test that passes but *cannot* fail is
decoration, so each was checked against the wrong implementation:

| Test | Guards | Under the wrong implementation |
|---|---|---|
| `assert_repeat_customers_exist` | Risk R-1 | Keyed on `customer_id`: **0** repeat customers → fires |
| `assert_delay_days_is_whole_days` | M2 F-01 | Timestamp arithmetic: **96,470** fractional rows → fires |
| `assert_fct_orders_grain_preserved` | Risk R-2 | Raw geolocation join: **15,083,455** rows → fires |
| `assert_durations_are_never_negative` | M2 F-08 | Unclamped: 188 negative durations → fires |
| `assert_centroids_inside_brazil` | M2 F-13 | Unfiltered: 21 prefixes off the map → fires |
| `assert_delivery_measures_respect_eligibility` | M2 F-03 | Status-only filter: 8 orders with null delay in the denominator → fires |
| `assert_order_value_reconciles_to_items` | Cross-grain agreement | Any drift between the two fact grains → fires |

The R-2 number is worth a second look. The audit measured the geolocation
fan-out at **52.6× on average**. Joined through the actual customer ZIP
prefixes, the realised inflation is **151.7×** — 15.08 million rows from 99,441
orders — because customers concentrate in dense urban prefixes, which are
exactly the prefixes carrying the most geolocation rows. The average understates
the damage by a factor of three.

---

## 6. Structural rules enforced without a warehouse

`dbt build` needs the loaded warehouse and ~120 MB of uncommitted CSV, so CI
cannot run it. Nine Python tests enforce what *can* be checked from the files,
and they run on every push:

- **Staging models never join** (Design Phase §1.2). Break this and lineage stops
  being readable: when a mart is wrong, the fault could be anywhere upstream
  rather than in one identifiable model.
- **Staging reads sources, marts read refs.** A mart reaching into `raw` directly
  bypasses the review dedup and the geolocation aggregation — including the one
  that kills R-2.
- **`delay_days` is computed on `::date`.** The dbt test guarding F-01 needs a
  warehouse; this one does not, so a reversion cannot reach `main` unnoticed.
- **`fct_orders` LEFT JOINs its items**, and **`dim_customers` is keyed on the
  person**.
- **Every bespoke test still exists**, by name. Deleting one is precisely the
  change that must not pass review.
- **Every model is documented** (NFR-5).

CI's `dbt parse` step also stops swallowing failures. It was written as
`|| echo "::warning::"` because no models existed before M3; they exist now, so
a broken `ref` or an unparseable model fails the build.

---

## 7. How it was verified

| Check | Result |
|---|---|
| `python scripts/run_dbt.py build` | **156/156** — 17 models, 139 data tests |
| Full rebuild time | 1m 50s (NFR-4 budget: 10 min) |
| `pytest -q` | **36 passed** (27 at M2) |
| `ruff check .` | clean |
| `dbt parse` with no warehouse | passes — as CI runs it |
| Marts vs M2 audit | 13 headline figures reproduced exactly (§3) |
| Bespoke tests vs wrong implementation | all 7 fire (§5) |

---

## 8. Problems hit while building this

**The bounding box was nearly written twice.** `stg_geolocation` filters on it and
`assert_centroids_inside_brazil` checks it. Two copies of four numbers is two
copies that will eventually disagree, and the disagreement would be silent in the
worst way — the test would pass on data the model should have rejected. Both now
read the same `dbt_project.yml` vars. The anchor date and trend window are
declared there for the same reason.

**The centroid test failed on first run** — it selected `source_point_count`,
which `dim_geography` renames to `centroid_point_count`. Caught by `dbt build` in
seconds, which is the argument for having written it at all.

**A `>` at the start of a YAML description.** `description: >1 on 1,278 orders`
is a block-scalar indicator, not a greater-than sign, and it took down parsing
for the entire project. Fixed by quoting.

**dbt was not installed.** `requirements.txt` pinned dbt-core and dbt-postgres
since M0, but the local venv only ever had the subset M0–M2 needed. Installing
them surfaced a second gap: the documented command sequence differed per shell,
because dbt reads discrete `DBT_*` environment variables while the credentials
live in `.env`. `scripts/run_dbt.py` loads `.env` and invokes dbt through
`python -m dbt.cli.main`, so NFR-1's "one documented command sequence" is one
sequence on any platform, activated venv or not.

---

## 9. Definition of Done

| Criterion | Status |
|---|---|
| Artefacts committed | ✅ |
| Automated tests pass | ✅ 156 dbt + 36 pytest, lint clean |
| Every figure traceable to a committed query or model | ✅ §3 reproduces the audit from the marts |
| Assumptions and limitations recorded | ✅ §4 records both legitimate divergences |
| Milestone summary written, including problems found | ✅ this document, §8 |

---

## 10. Next: M4 — Descriptive analysis

The warehouse is built and tested. M4 reads **marts only** — never `raw`, never
`staging` (Design Phase §8) — and delivers FR-5 to FR-8:

- Delivery performance: on-time rate, delay distribution, trend over
  2017-01 to 2018-08 (`in_trend_window` is already on `dim_dates`)
- Cohort retention on `customer_unique_id` (`cohort_month` is already on
  `dim_customers`)
- RFM segmentation against the 2018-08-31 anchor (`recency_days` is already
  computed)
- Revenue concentration by category, seller and geography — seller ranking from
  `fct_order_items` filtered on `is_single_seller` (M2 F-12)

Every column those analyses need exists in a mart. If one turns out not to, the
fix is a new mart column rather than a bespoke query in a script — that is what
keeps NFR-2 true.

---

## Document control

| Field | Value |
|---|---|
| Milestone | M3 — Dimensional model |
| SRS version | 1.0 |
| Design Phase version | 1.1 |
| Previous | `OrderLens_M2_Summary.md` |
| Next document | `OrderLens_M4_Summary.md` |

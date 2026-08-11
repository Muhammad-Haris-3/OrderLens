# OrderLens — M2 (Data-Quality Audit) Milestone Summary

**Date:** 2026-08-11
**Status:** Complete
**Maps to:** SRS FR-4 — *produce a data-quality audit documenting every anomaly
found and the handling decision taken, with justification*

---

## 1. Scope

Interrogate the loaded raw layer, quantify every anomaly, decide how each is
handled, and resolve the five design decisions M0/M1 deliberately deferred until
the data had been looked at.

The SRS chose iterative over waterfall for exactly this reason (§4): *"committing
to a full analysis design before seeing the data would be dishonest sequencing."*
M2 is where that sequencing pays off — or fails to.

It paid off. The audit overturned a definition the Design Phase had already
settled, and that definition was understating the project's central estimate by
14%.

---

## 2. What was built

| Artefact | Purpose |
|---|---|
| `sql/audit/` — 30 committed queries | Every audit figure traces to a re-runnable query (NFR-2) |
| `scripts/run_audit.py` | Runs them in a **read-only** session, renders the evidence file |
| `docs/data_quality_audit_results.md` | Generated evidence — the exact rows every check returned |
| `docs/data_quality_audit.md` | **The FR-4 deliverable** — 17 findings adjudicated, D-1 to D-5 resolved |
| `sql/raw_indexes.sql` | Join-key indexes; the audit's geolocation checks were minutes, now seconds |
| `tests/test_audit_queries.py` | 12 tests guarding the audit's integrity |
| `tests/test_sources_yml.py` | 6 tests guarding `_sources.yml`, which CI was not really checking |

**Design decision — the audit is SQL, not a notebook.** An audit whose numbers
come from an unsaved console session is an assertion. Thirty committed files
mean any figure in the write-up can be re-run by anyone, and a test asserts that
every check id cited in the document resolves to a query that still exists.

The runner opens the connection with `readonly=True`, and a test rejects any
audit query containing a write or DDL keyword. **The audit cannot alter what it
is measuring.**

---

## 3. The headline finding: `is_late` was measured in the wrong unit

This is the one worth reading. Full working in
[`docs/data_quality_audit.md` F-01](docs/data_quality_audit.md).

### The setup

`order_estimated_delivery_date` is a **date**, stored at midnight — all 96,470
delivered orders, no exceptions. `order_delivered_customer_date` is a real
timestamp, and **not one delivery in the dataset lands at exactly midnight**.

The Design Phase defined `delay_days = delivered_at − estimated_delivery_at`.
That is the obvious formula. It is also wrong: it classifies an order as late if
it arrives at *any* hour of the day it was promised, because every hour of that
day is after the midnight the promise is stored at.

Deliveries cluster in the evening — 67.9% land between 15:00 and 23:00 — so the
affected group is not a rounding-error minority.

### The size

**1,292 orders were delivered on the day they were promised and counted late.**

| Rule | Late orders | Late rate |
|---|---|---|
| Timestamp | 7,826 | 8.11% |
| Calendar day | 6,534 | **6.77%** |

1.3% of delivered orders. Easy to wave away — until you look at which orders
they are.

### The cost

| Group | Orders | Mean review score |
|---|---|---|
| Late — timestamp rule | 7,661 | 2.565 |
| On time — timestamp rule | 88,163 | 4.294 |
| **Late — calendar-day rule** | **6,381** | **2.270** |
| **On time — calendar-day rule** | **89,443** | **4.290** |
| *Boundary group* | *1,280* | ***4.034*** |

The misclassified orders score **4.03**. They behave like on-time deliveries,
because they *were* on-time deliveries. Filing them under "late" pulls that
group's mean from 2.270 up to 2.565:

| | Gap in mean review score |
|---|---|
| Timestamp rule | 1.729 |
| Calendar-day rule | **2.020** |

**The timestamp rule understates the delay-to-satisfaction gap by 0.29 review
points — 14.4%.**

That gap is the number this entire project exists to estimate (BQ-2, BQ-3) and
the number the M7 recommendation is costed from. A 14% understatement would have
propagated into the M5 regression coefficient, the M6 target definition, and the
projected return of the intervention — and it would have arrived looking
completely reasonable.

### Why it would never have been caught later

Nothing fails. No null appears, no row count changes, no test goes red. The
formula returns a valid signed number for every delivered order. The only symptom
is that the answer is 14% too small, and there is nothing to compare it against.

**Fix:** `delay_days = delivered_at::date − estimated_delivery_at::date`. The
promise made to the customer was a *day*; the comparison is made at the
granularity the promise was made at. `delivery_days`, `seller_handover_days` and
`carrier_transit_days` keep full timestamp precision — they compare a measurement
to another measurement, so no unit mismatch exists there.

**Guarded:** a dbt test asserts `delay_days` is a whole number of days, so a
reversion cannot happen silently.

---

## 4. The five deferred decisions, resolved

| # | Question | Resolution |
|---|---|---|
| **D-1** | How duplicated is `review_id`? | Grain is **`order_id`**, not `review_id`. Keep latest by `review_answer_timestamp`, tie-break `review_id`. `review_id` never tested for uniqueness — it is genuinely not unique and a permanently failing test is one everybody learns to ignore. |
| **D-2** | Which statuses are eligible for delivery analysis? | `order_status = 'delivered' AND delivered_at IS NOT NULL` — **both**, giving 96,470 orders. All 99,441 retained in `fct_orders` with null delivery measures outside that set. |
| **D-3** | How are unmapped-category products labelled? | English → Portuguese → `'uncategorised'`, with a `category_source` enum recording which step fired. |
| **D-4** | Orders with no items, or reviews with no order? | 775 item-less orders — a real business state, so `LEFT JOIN` with **null** order value, not 0. Zero orphans in any child-to-parent direction. |
| **D-5** | What is the analysis anchor date? | **2018-08-31**, not the maximum timestamp. Trend window 2017-01 to 2018-08. |

D-1 is worth a note on honesty. The dedup rule barely moves anything — mean
review score 4.0864 keeping the latest against 4.0872 keeping the earliest. The
audit says so plainly rather than dressing the decision up as consequential. It
still had to be made, because leaving it unmade weights 551 orders twice in every
join, and an *unstated* weighting is worse than a stated one that happens not to
matter.

---

## 5. Other findings that changed the build

Seventeen findings in total; these are the ones that moved something.

| # | Finding | What changed |
|---|---|---|
| **F-02** | 547 orders carry several reviews, **202 disagreeing on the score** | `stg_order_reviews` grain is `order_id` after dedup |
| **F-03** | 8 orders are `delivered` with no timestamp; 6 `canceled` orders **have** one | Eligibility needs both conditions; materialised as `is_delivery_eligible` |
| **F-04** | 775 orders have no items — 603 `unavailable`, 164 `canceled` | `LEFT JOIN` to items; `order_value` NULL, not 0 |
| **F-05** | 623 products never reach an English category | Inner join would delete **R$185,049.76** across **1,473 orders** |
| **F-06** | 2018-09/10 carry 20 orders, **none ever delivered**; **November 2016 is missing entirely** | Anchor 2018-08-31; gapless `dim_dates` spine |
| **F-07** | Geolocation fans out **52.6×**; 157 customer ZIP prefixes have no coordinates at all | Aggregate before joining; geography joins are `LEFT JOIN` |
| **F-08** | 165 orders handed to carrier **before** the customer ordered | Handover/transit measures null rather than negative |
| **F-09** | **4,795 reviews were answered before the parcel arrived** | Flagged; excluded from M6 training; M5 sensitivity |
| **F-13** | 42 geolocation points fall outside Brazil | Filtered before averaging — the one place a row is discarded |

**F-09 is the one that constrains interpretation rather than code.** The
satisfaction survey is triggered at dispatch, not delivery, so 4.98% of reviews
on delivered orders were written before the customer had the parcel. Those
reviews cannot be a response to the delivery experience. No amount of cleaning
fixes that — it is a property of the measurement instrument, and FR-12's
limitations statement has to say so.

---

## 6. What the audit did *not* find

Stated because absence of evidence is a result, and because a report listing only
problems invites the question of what was skipped:

- **No corruption.** Zero orphan rows in any child-to-parent direction — no items,
  payments or reviews without a parent order; no order without a customer; no
  item referencing an unknown product or seller.
- **No row loss.** All nine tables still reconcile to their source files.
- **No duplicate rows.** Every declared grain holds except reviews.
- **No impossible values.** No negative or zero prices, no negative freight or
  payments, no out-of-range review scores, no malformed state codes.

The dataset is clean. What it is not is **self-explanatory** — every blocking
finding is a place where a correct-looking rule produces a wrong answer with
nothing failing to warn you.

---

## 7. A supporting change: raw-layer indexes

The geolocation coverage checks joined 1,000,163 rows against customers and
sellers with no index, and the first audit run did not finish inside two minutes.

`sql/raw_indexes.sql` adds indexes on the join keys. **An index is not a
constraint** — it asserts nothing and rejects nothing, so the raw layer's source
fidelity (`sql/raw_schema.sql`) is untouched. What changes is time: the full
30-check audit now runs in seconds, and the same keys are hit by every dbt model
in M3, so the cost is paid once and recovered on every build (NFR-4, risk R-4).

A test asserts the file contains nothing but `CREATE INDEX IF NOT EXISTS`, so it
cannot quietly become a place where data gets changed.

---

## 8. How it was verified

| Check | Result |
|---|---|
| `pytest -q` | **27 passed** (was 8 at M1) |
| `ruff check .` | clean |
| `python scripts/run_audit.py` | 30/30 checks executed, evidence regenerated |
| `python scripts/run_audit.py --list` | works with no database — CI-safe |
| Audit ids contiguous, filenames match ids | enforced by test |
| No audit query contains a write or DDL keyword | enforced by test |
| Every `A-nn` cited in the audit document exists | enforced by test |
| All five D-decisions covered by a query | enforced by test |
| `_sources.yml` parses; accepted values match what A-06/A-25 measured | enforced by test |

Every figure in the audit and in this summary comes from a committed query run
against the loaded warehouse. None is quoted from a console session.

---

## 9. Problems hit while building this

**The report was truncating its own questions.** The header parser took only the
first line of a wrapped `-- question:` field, so multi-line questions rendered as
half a sentence — which reads as a typo rather than as the parsing bug it was.
Fixed with an explicit continuation rule and a regression test.

**A-11 was double-counting.** The first version joined reviews to orders
directly, so the 547 multi-review orders were counted twice — while measuring
whether the review dedup rule mattered. It was measuring two things at once.
Rewritten to apply the D-1 rule first; the numbers moved slightly (7,826 → 7,661
late orders) and the comparison became clean.

**The midnight claim had no committed query behind it.** The first draft of the
audit asserted that the estimated delivery date is always stored at midnight,
having verified it in an ad-hoc session. That is exactly the traceability failure
NFR-2 exists to prevent, so the check was added to A-10 as two columns:
96,470 of 96,470 promises at midnight, 0 of 96,470 deliveries at midnight.

---

## 10. Definition of Done

| Criterion | Status |
|---|---|
| Artefacts committed | ✅ |
| Automated tests pass | ✅ 27/27, lint clean |
| Every figure traceable to a committed query | ✅ 30 queries, enforced by test |
| Assumptions and limitations recorded | ✅ 17 findings, each with a graded decision |
| Milestone summary written, including problems found | ✅ this document, §9 |

---

## 11. Next: M3 — Dimensional model

The Design Phase is now amended to v1.1 with no open decisions, and every model
definition it carries has been checked against the data rather than assumed. M3
should be typing, not deciding:

- Nine staging views, one per source, no joins
- `dim_customers` (keyed on `customer_unique_id`), `dim_products`, `dim_sellers`,
  `dim_dates`, `dim_geography`
- `fct_orders`, `fct_order_items`, `fct_payments`
- Schema, referential, domain and **bespoke** tests — the bespoke ones being
  repeat customers exist (R-1), row count preserved across joins (R-2),
  `delay_days` is whole days (F-01), durations null-not-negative (F-08),
  centroids inside Brazil (F-13)

---

## Document control

| Field | Value |
|---|---|
| Milestone | M2 — Data-quality audit |
| SRS version | 1.0 |
| Design Phase version | 1.1 (amended by this milestone) |
| Previous | `OrderLens_M1_Summary.md` |
| Next document | `OrderLens_M3_Summary.md` |

# OrderLens — M4 (Descriptive Analysis) Milestone Summary

**Date:** 2026-08-11
**Status:** Complete
**Maps to:** SRS FR-5 (delivery performance), FR-6 (cohort retention), FR-7
(RFM segmentation), FR-8 (revenue concentration)

---

## 1. Scope

Describe what actually happens in this marketplace: how late deliveries are and
when, whether customers come back, who the valuable customers are, and where the
revenue and the failures concentrate.

No causal claim is made anywhere in M4. That is M5's job, and the distinction is
kept sharp on purpose — the 2.020-point gap between late and on-time orders is a
difference between two groups that were not randomly assigned, and calling it an
effect before applying controls would be the exact error FR-12 exists to prevent.

---

## 2. What was built

**Five analysis marts. 34 new dbt tests. One analysis script.**

| Artefact | Delivers |
|---|---|
| `mart_delivery_monthly` | FR-5 — on-time rate, delay and the handover/transit split by month |
| `mart_delay_buckets` | FR-5 — the delay distribution and what each band costs |
| `mart_cohort_retention` | FR-6 — retention by first-purchase month, on `customer_unique_id` |
| `mart_customer_rfm` | FR-7 — RFM per person, with the frequency degeneracy exposed |
| `mart_revenue_concentration` | FR-8 — revenue ranked by category, seller and state with cumulative share |
| `analysis/descriptive.py` | Gini, top-N shares, the review-timing sensitivity → `docs/descriptive_results.md` |
| `docs/descriptive_findings.md` | The interpretation — the FR-5 to FR-8 deliverable |

**Aggregation stayed in SQL.** Every count, sum, rate and ranking published in
M4 is a `select` against one of those five models; the Python script computes
three things that are genuinely statistics and nothing else. That is the
deliberate constraint in SRS §9.2, and it has a practical consequence: because
the numbers live in marts, the M7 dashboard reads the same definitions rather
than a parallel set that will eventually disagree.

A test enforces it — `test_analysis_scripts_read_marts_only` fails if anything
in `analysis/` reaches into `raw` or `analytics_staging`.

---

## 3. The headline finding: review timing is a consequence of the delay

**This overturns a decision M2 took, and it is the reason M4 exists before M5
rather than after it.**

### What M2 knew

M2 (finding F-09) measured that 4,795 reviews were answered before the parcel
arrived, because the satisfaction survey fires at dispatch rather than delivery.
Its handling decision: flag them, run M5 with and without, **exclude them from
M6 training**.

### What M4 measured

Not *how many* there are, but *where they are*:

| Delay band | % reviewed before delivery |
|---|---|
| 15+ days early | 0.2% |
| 8–14 days early | 0.2% |
| 1–7 days early | 0.2% |
| On the promised day | 0.6% |
| **1–7 days late** | **49.1%** |
| **8–14 days late** | **96.1%** |
| **15–30 days late** | **98.8%** |
| **More than 30 days late** | **97.9%** |

Near-zero for every on-time band. Near-total for every late one. The survey goes
out on a fixed schedule after dispatch, so a parcel that has not arrived by then
gets reviewed in its absence. **Whether a review was written before delivery is
very nearly determined by whether the delivery was late.**

### Why the M2 decision could not stand

| Population | On-time | Late | Mean (on time) | Mean (late) | Gap |
|---|---|---|---|---|---|
| All reviews | 89,443 | 6,381 | 4.290 | 2.271 | **2.020** |
| After-delivery reviews only | 89,263 | 1,908 | 4.291 | 3.720 | **0.572** |

Excluding pre-delivery reviews keeps **99.8% of on-time orders and 29.9% of late
ones**, and shrinks the headline effect by 72%.

The tempting reading is that 0.572 is the clean number with a nuisance removed.
It is not. Review timing is a **post-treatment variable** — caused by the delay,
not confounding it. Conditioning on it does not remove bias; it selects the late
orders where the customer waited long enough to receive the parcel before
responding, which is a non-random and much better-behaved subset. The 0.572 is
not a more careful measurement of the same quantity, it is a measurement of a
different population.

### Revised

- **M5** uses **all reviews** for the headline. The after-delivery figure is
  published as a **stated selection bound**, labelled as conditioning on a
  post-treatment variable.
- **M6** no longer excludes them from training. Doing so would remove 70% of
  late orders and most of the low scores the classifier exists to predict.
- `docs/data_quality_audit.md` and the Design Phase carry the amendment inline,
  with the superseded text struck through rather than deleted. The M2 decision
  was reasonable on the evidence M2 had; the record should show why it changed.

The non-monotonic ">30 days late" band — mean 2.058, *better* than the two bands
before it — is the same effect surfacing as an anomaly. Nothing improves past
thirty days. The composition of who responds changes.

---

## 4. FR-5 — Delivery performance

**6.77% late. Median delay −12 days.** The typical order arrives nearly two weeks
before it was promised, because the promise is padded: 22.7 to 28.3 days
promised against 7.7 to 17.0 delivered.

**The rate is far less stable than the average.** It ranges from 1.16%
(2018-06) to 18.96% (2018-03) — sixteen-fold. Two failure episodes: Black Friday
2017 and a sustained February–March 2018 breakdown.

**Both are carrier-side.** Across the spikes carrier transit doubles from 6.7 to
13.4 days while seller handover stays between 2.5 and 4.1. Overall the carrier
owns **74.2% of the wait** and effectively all of its variance.

**The cost of lateness is a cliff, not a slope:**

| Band | Mean review | % low score |
|---|---|---|
| On the promised day | 4.034 | 12.42% |
| **1–7 days late** | **2.714** | **49.39%** |
| 8–14 days late | 1.671 | 80.15% |
| 15–30 days late | 1.614 | 81.81% |

Crossing from on-time to one week late costs 1.32 review points and quadruples
the low-score rate. The next three weeks cost 1.10 points combined. **Most of the
damage happens immediately**, which means the intervention worth paying for
prevents lateness rather than limiting it.

Being early buys almost nothing: 15+ days early scores 4.323 against 4.201 for
1–7 days early — 0.12 of a point for two extra weeks of buffer. The padding in
the promise is not purchasing satisfaction, and it has a competitive price M7
should account for.

---

## 5. FR-6 — Retention, and a question the project cannot answer

| Measure | Value |
|---|---|
| People | 96,096 |
| Placed 2+ orders | 2,997 (3.12%) |
| **Shopped on 2+ distinct days** | **2,149 (2.24%)** |

The gap between those two rows is a finding in itself: **897 of the 2,997 repeat
customers placed their second order on the same day as the first** — a split
basket, one shopping occasion. `mart_cohort_retention` counts shopping days
rather than orders for exactly that reason.

Pooled retention is a floor, not a curve: 0.480% at month 1, decaying to 0.186%
by month 6. Per-cohort figures wander between 0.1% and 0.7% with no pattern; at
these counts that is sampling noise and reading a trend into it would be
inventing one.

**BQ-3 asks what one day of delay is worth "in review score and repeat-purchase
terms". The repeat-purchase half is unanswerable.** There is no repeat-purchase
signal large enough to detect a delay effect within, and a model claiming to find
one would be fitting noise. Reported rather than worked around (NFR-8).

This constrains M7 directly: **the business case cannot rest on retained
customers, because this marketplace does not retain customers.** It has to rest
on revenue at risk within the order, on acquisition cost wasted on a customer
whose only experience was bad, or on the platform rating.

Recorded as a limitation rather than a fact about the business: a 2.24% two-year
repeat rate is unusual, and `customer_unique_id` may simply fail to follow a
person who re-registered. Untestable with the fields available.

---

## 6. FR-7 — RFM, with the frequency dimension called out

96.88% of people placed exactly one order. Textbook RFM scores each dimension
into quintiles; `NTILE(5)` on that column would cut five slices through the value
1 and hand back five segments that differ in nothing — while looking exactly like
a normal RFM output.

`mart_customer_rfm` scores F on its actual distribution (1 / 2 / 3+) and segments
on R and M, carrying `f_score` into the output so the degeneracy is visible.

**32.1% of customers carry 60.2% of revenue** — Champions (16.62% of people,
30.95% of revenue) and "At risk, high value" (15.48%, 29.26%).

The labels need reading with care, and the findings document says so plainly:
with F degenerate, "Champions" does not mean loyal repeat buyers — **94% of them
bought exactly once**. It means recent, high-value, single-purchase customers.
"At risk, high value" is not a churn warning; those customers have already gone
and most were never coming back. Value here is driven by **basket size on one
order**, not relationship depth.

---

## 7. FR-8 — Concentration, and where the damage actually is

| Dimension | Members | Reaching 80% of revenue | Gini |
|---|---|---|---|
| Category | 74 | 18 (24.3%) | 0.713 |
| Seller | 3,095 | 562 (18.2%) | **0.785** |
| Customer state | 27 | 7 (25.9%) | 0.703 |

Sellers follow Pareto almost exactly, and the top is sharper still: **31 sellers
— the top 1% — produce 25.6% of all revenue.**

Category late rates sit in a narrow 5.0–8.0% band across the top 15, which is a
useful negative result: **lateness is not a category phenomenon.** It rules out
product handling as the primary driver and points at geography.

**Damage concentrates differently from revenue, and that is the BQ-4 answer:**

| State | % of revenue | % of late-order revenue | Late rate | Mean review |
|---|---|---|---|---|
| SP | 37.39% | 23.70% | 4.49% | 4.195 |
| **RJ** | **13.44%** | **22.98%** | **12.11%** | 3.893 |
| MG | 11.71% | 7.57% | 4.58% | 4.154 |
| MA | 0.96% | 2.35% | **17.36%** | 3.774 |

**Rio de Janeiro is the target.** 13.4% of revenue absorbing 23.0% of the revenue
on late orders — 1.7× over-represented — at nearly three times São Paulo's
failure rate. The northeastern states fail harder (Maranhão 17.36%) but each is
around 1% of revenue. High volume *and* high failure rate coincide in exactly one
place, and RJ's mean review score confirms customers notice.

---

## 8. How it was verified

| Check | Result |
|---|---|
| `python scripts/run_dbt.py build` | **195/195** — 22 models, 173 data tests (2m 15s) |
| `pytest -q` | **37 passed** (36 at M3) |
| `ruff check .` | clean |
| `python analysis/descriptive.py` | regenerates `docs/descriptive_results.md` |
| Every published figure traceable to a mart | ✅ — the script aggregates nothing |
| Analysis reads marts only | ✅ enforced by test |

Two new bespoke tests: `assert_cumulative_share_reaches_100` (the Pareto
arithmetic must actually reach 100% per dimension — a mis-partitioned window
function still produces a plausible-looking curve against the wrong denominator)
and `assert_cohort_month_zero_is_complete` (month 0 must be exactly 100%, or the
cohort definition and the activity months disagree and every later period is
rescaled against the wrong base).

---

## 9. Problems hit while building this

**The pooled retention denominator was wrong, and the error flattered the
result.** `mart_cohort_retention` only holds rows where a cohort had at least one
active customer, so summing `cohort_customers` per period silently dropped every
cohort that retained nobody — removing the zeros from the denominator. Month 3
read 0.261% instead of 0.226%, month 6 read 0.231% instead of 0.186%. Fixed by
generating the cohort × period grid and left-joining the mart onto it, which also
excludes periods a cohort could not yet have reached so right-censoring cannot
masquerade as churn.

Small numbers in absolute terms. But it is exactly the class of error that makes
a retention curve look like it has a floor when it has a slope, and it was found
by asking why the denominator changed between periods rather than by a test.

**The `>30 days late` band scored better than the two bands before it**, which
read like a data error and turned out to be the review-timing selection effect
(§3) surfacing as an anomaly. Chasing it is what produced the milestone's main
finding.

**`test_all_expected_models_exist` failed on the five new marts**, which is the
test doing its job — the model list is meant to be an explicit inventory, so
adding a mart is a deliberate edit rather than something that happens quietly.

---

## 10. Definition of Done

| Criterion | Status |
|---|---|
| Artefacts committed | ✅ |
| Automated tests pass | ✅ 195 dbt + 37 pytest, lint clean |
| Every figure traceable to a committed query or model | ✅ five marts + one script |
| Assumptions and limitations recorded | ✅ five, in `descriptive_findings.md` |
| Milestone summary written, including problems found | ✅ this document, §9 |

---

## 11. Next: M5 — Inferential analysis

M4 describes; M5 tests and controls. FR-9 to FR-13:

- Mann-Whitney U on review score by late/on-time with rank-biserial effect size —
  rank-based because A-28 measured the distribution as bimodal, not because
  rank tests are fashionable
- Kruskal-Wallis across categories and states with Benjamini-Hochberg correction
- Regression of review score on `delay_days` controlling for price, freight,
  category, seller state, customer state and season
- **FR-12's limitations statement**, which now has to carry the review-timing
  problem: the outcome measure partly reflects *waiting* rather than *having
  received a late parcel*, and no analysis choice separates the two

The 2.020-point gap is the number M5 has to defend. M4's job was to establish it
honestly and to say clearly that it is not yet an effect.

---

## Document control

| Field | Value |
|---|---|
| Milestone | M4 — Descriptive analysis |
| SRS version | 1.0 |
| Design Phase version | 1.1 (§8.1 amended by this milestone) |
| Amends | M2 finding F-09's handling decision |
| Previous | `OrderLens_M3_Summary.md` |
| Next document | `OrderLens_M5_Summary.md` |

# OrderLens — Descriptive Findings

**Milestone:** M4
**Satisfies:** SRS FR-5 (delivery performance), FR-6 (cohort retention), FR-7
(RFM segmentation), FR-8 (revenue concentration)
**Date:** 2026-08-11

---

## How to read this document

Every figure here comes from one of five dbt models —
`mart_delivery_monthly`, `mart_delay_buckets`, `mart_cohort_retention`,
`mart_customer_rfm`, `mart_revenue_concentration` — and the exact tables they
produced are in [`descriptive_results.md`](descriptive_results.md), regenerated
by `python analysis/descriptive.py`.

Aggregation happens in SQL, not in this script (SRS §9.2). Python computes the
Gini coefficients, the top-N share curve, and the review-timing sensitivity, and
nothing else.

This document is the interpretation.

---

## Summary — four findings

| # | Finding | Consequence |
|---|---|---|
| **D-1** | The delay→satisfaction relationship is a **cliff, not a slope**. Being 1–7 days late costs more than the next three weeks of lateness combined | Prevention beats recovery. The intervention must stop the first week of lateness |
| **D-2** | **Review timing is a consequence of the delay.** 96%+ of late orders were reviewed before the parcel arrived, against 0.2% of on-time ones | **Overturns the M2 F-09 handling decision.** Excluding those reviews collapses the measured effect from 2.020 to 0.572 — not by removing bias but by removing 70% of the late orders |
| **D-3** | There is **almost no repeat business to lose**: 2.24% of customers ever shop on a second day | BQ-3's repeat-purchase leg is unanswerable. The business case for M7 cannot rest on retention |
| **D-4** | Damage concentrates far more sharply than revenue. **Rio de Janeiro carries 23.0% of late-order revenue on 13.4% of revenue** | BQ-4 has a target: RJ, at 12.11% late against São Paulo's 4.49% |

---

# FR-5 — Delivery performance

## The headline numbers

6,534 of 96,470 delivered orders arrived late — **6.77%**, on the calendar-day
rule settled in M2. Median delay is **−12 days**: the typical order arrives
nearly two weeks *before* it was promised.

That second number explains the first. Across the trend window the platform
promised between **22.7 and 28.3 days** and delivered in between **7.7 and 17.0**
(`mart_delivery_monthly`). The estimate is padded by roughly a factor of two, and
the 6.77% late rate is a rate against a deliberately soft target. An order has to
go substantially wrong to breach it.

## The on-time rate is far less stable than the average suggests

| Month | Late rate | Carrier transit (days) | Seller handover (days) | Mean review |
|---|---|---|---|---|
| 2018-06 | **1.16%** | 6.68 | 2.57 | 4.307 |
| 2017-11 | 12.40% | 11.09 | 4.07 | 3.989 |
| 2018-02 | 14.13% | 13.38 | 3.56 | 3.881 |
| 2018-03 | **18.96%** | 12.97 | 3.33 | 3.813 |

A sixteen-fold range between the best and worst months. Two distinct failure
episodes: November 2017 (Black Friday) and a sustained February–March 2018
breakdown that is the worst in the dataset.

**Both are carrier-side.** Across the spikes, carrier transit runs from 6.7 days
to 13.4 — it doubles. Seller handover moves between 2.5 and 4.1 days and is
essentially flat. Whatever went wrong in early 2018 happened after the parcel
left the seller.

## Where the wait goes

| | Days | Share of the wait |
|---|---|---|
| Seller handover | 3.23 | **25.8%** |
| Carrier transit | 9.29 | **74.2%** |
| Total | 12.51 | |

The carrier owns three quarters of the wait *and* all of the variance. This is
the split that makes a recommendation actionable: "deliveries are late" is not
something a business can act on, and on this evidence "sellers are slow" would be
the wrong thing to act on.

## The cost of lateness is a cliff

| Delay band | Orders | % of delivered | Mean review | % low score (≤2) |
|---|---|---|---|---|
| 15+ days early | 34,939 | 36.22% | 4.323 | 9.04% |
| 8–14 days early | 36,364 | 37.69% | 4.311 | 8.91% |
| 1–7 days early | 17,341 | 17.98% | 4.201 | 10.24% |
| On the promised day | 1,292 | 1.34% | 4.034 | 12.42% |
| **1–7 days late** | **3,672** | **3.81%** | **2.714** | **49.39%** |
| 8–14 days late | 1,478 | 1.53% | 1.671 | 80.15% |
| 15–30 days late | 1,039 | 1.08% | 1.614 | 81.81% |
| More than 30 days late | 345 | 0.36% | 2.058 | 67.78% |

Two things stand out.

**The damage arrives immediately.** Crossing from "on the promised day" to "1–7
days late" costs 1.32 review points and quadruples the low-score rate from 12.4%
to 49.4%. The next three weeks of lateness cost a further 1.10 points combined.
Most of the harm is done in the first week — which means the intervention worth
paying for is one that prevents lateness, not one that limits how late.

**Being early is worth very little.** 15+ days early scores 4.323 against 4.201
for 1–7 days early — 0.12 of a point for two extra weeks of buffer. The padding
in the delivery estimate is buying almost no satisfaction. That is a cost
question for M7: a promise this conservative has a competitive price.

Late orders carry **R$1,150,892** of the R$15,418,395 delivered through the
window — **7.46% of revenue** sitting in the bands where half to four-fifths of
customers leave a 1 or 2.

---

# The review-timing problem

**This is the finding that changes what M5 and M6 are allowed to do, and it
overturns a decision M2 took.**

## What was found

M2 (finding F-09) recorded that 4,795 reviews were answered before the parcel
arrived, because the satisfaction survey fires at dispatch rather than delivery.
Its handling decision was to flag them, run M5 both with and without, and
**exclude them from M6 training**.

M4 measured how they are distributed. They are not spread evenly:

| Delay band | % reviewed before delivery |
|---|---|
| 15+ days early | 0.2% |
| 8–14 days early | 0.2% |
| 1–7 days early | 0.2% |
| On the promised day | 0.6% |
| 1–7 days late | **49.1%** |
| 8–14 days late | **96.1%** |
| 15–30 days late | **98.8%** |
| More than 30 days late | **97.9%** |

The share is near-zero for every on-time band and near-total for every late one.
That is mechanical: the survey is sent on a fixed schedule after dispatch, so a
parcel that has not arrived by then is reviewed in its absence. **Whether a
review was written before delivery is determined by whether the delivery was
late.**

## Why the M2 decision could not stand

| Population | On-time orders | Late orders | Mean (on time) | Mean (late) | Gap |
|---|---|---|---|---|---|
| All reviews | 89,443 | 6,381 | 4.290 | 2.271 | **2.020** |
| Reviews written after delivery only | 89,263 | 1,908 | 4.291 | 3.720 | **0.572** |

Excluding pre-delivery reviews retains **99.8% of on-time orders and 29.9% of
late ones**, and shrinks the headline effect by 72%.

It is tempting to read the 0.572 as the "clean" estimate with a nuisance removed.
It is not. Review timing is a **post-treatment variable** — a consequence of the
delay, not a confounder of it. Conditioning on it does not remove bias, it
introduces selection: the late orders that survive the filter are precisely the
ones where the customer waited long enough to receive the parcel before
responding, which is a non-random subset of late orders and a much
better-behaved one.

The 0.572 figure is not a more careful measurement of the same thing. It is a
measurement of a different, self-selected population.

## Revised handling

> **The M2 F-09 decision is amended.**
>
> **M5:** the headline estimate uses **all reviews**. The after-delivery-only
> figure is reported as a **stated selection bound**, explicitly labelled as
> conditioning on a post-treatment variable, not as an alternative estimate. FR-12's
> limitations statement records that the outcome measure partly reflects *waiting*
> rather than *having received a late parcel* — the two cannot be separated with
> this instrument.
>
> **M6:** pre-delivery reviews are **no longer excluded from training**. Excluding
> them would remove 70% of late orders and most of the low scores the classifier
> exists to predict, leaving a model trained on a population that does not
> resemble the one it would be deployed against.

The non-monotonic ">30 days late" band — 2.058, better than the two bands before
it — is the same effect surfacing again. Nothing improves past thirty days; the
composition of who responds changes.

---

# FR-6 — Cohort retention

## There is almost nothing to retain

| Measure | Value |
|---|---|
| People | 96,096 |
| Placed 2+ orders | 2,997 (3.12%) |
| **Shopped on 2+ distinct days** | **2,149 (2.24%)** |

The two rows differ because **897 of the 2,997 repeat customers placed their
second order on the same day as their first** — a split basket, one shopping
occasion. `mart_cohort_retention` counts shopping days for exactly this reason:
counting orders would book those people as retained when they never came back.

## The curve is a floor

Pooled across the twenty cohorts of 500+ customers, with cohorts that retained
nobody kept in the denominator and periods a cohort could not yet have reached
excluded:

| Months since first order | Customers | Active | Retention |
|---|---|---|---|
| 0 | 95,764 | 95,764 | 100% |
| 1 | 95,764 | 460 | **0.480%** |
| 2 | 95,764 | 289 | 0.302% |
| 3 | 89,493 | 202 | 0.226% |
| 4 | 83,422 | 186 | 0.223% |
| 5 | 77,482 | 143 | 0.185% |
| 6 | 70,860 | 132 | 0.186% |

This is not a retention curve with a steep drop. It is a floor of roughly two
customers in a thousand per month, indistinguishable across cohorts. Per-cohort
figures move between 0.1% and 0.7% with no pattern — at these counts the
month-to-month variation is sampling noise, and reading a trend into it would be
inventing one.

## What this costs the project

**BQ-3 asks what one day of delay is worth "in review score and repeat-purchase
terms". The repeat-purchase half of that question cannot be answered.** With
2.24% of customers ever returning, there is no repeat-purchase signal large
enough to detect a delay effect within — and a model that claimed to find one
would be fitting noise.

This is reported rather than worked around (SRS NFR-8), and it constrains M7
directly: **the business case for fixing delivery cannot rest on retained
customers, because this marketplace does not retain customers.** It has to rest
on revenue at risk within the order, on the acquisition cost of a customer whose
first and only experience was bad, or on the platform rating — none of which is
a retention argument.

The finding is also a caution about the dataset rather than the business. A
marketplace with a 2.24% repeat rate over two years is unusual, and the more
likely explanation is that `customer_unique_id` under-identifies people who
re-registered. That cannot be tested with the fields available, and it is
recorded as a limitation rather than asserted as a fact.

---

# FR-7 — RFM segmentation

## The frequency dimension does not exist

| Orders placed | People | Share |
|---|---|---|
| 1 | 93,099 | **96.881%** |
| 2 | 2,745 | 2.857% |
| 3+ | 252 | 0.262% |

Textbook RFM scores each dimension into quintiles. Applied here, `NTILE(5)` would
cut five slices through a column that is the value 1 for nineteen people in
twenty and hand back five segments that differ in nothing — while looking exactly
like a normal RFM output.

`mart_customer_rfm` therefore scores F on its actual distribution (1 / 2 / 3+ →
1 / 3 / 5) and segments on R and M, which do vary. `f_score` is carried into the
output so the degeneracy is visible rather than buried in a label.

## Segments

| Segment | People | % of people | Revenue | % of revenue | Mean spend | Returned later |
|---|---|---|---|---|---|---|
| Champions | 15,970 | 16.62% | R$4,904,356 | **30.95%** | R$307 | 942 |
| At risk, high value | 14,877 | 15.48% | R$4,636,492 | **29.26%** | R$312 | 469 |
| Needs attention | 7,591 | 7.90% | R$2,158,100 | 13.62% | R$284 | 326 |
| Hibernating | 19,200 | 19.98% | R$1,647,607 | 10.40% | R$86 | 155 |
| Recent, promising | 15,046 | 15.66% | R$1,345,861 | 8.49% | R$89 | 192 |
| Lost, low value | 15,989 | 16.64% | R$863,166 | 5.45% | R$54 | 47 |
| Recent, low value | 7,423 | 7.72% | R$287,971 | 1.82% | R$39 | 18 |

**32.1% of customers carry 60.2% of revenue.**

The labels need reading with care, and this is worth stating plainly because a
standard RFM deck would not. With F degenerate, "Champions" does not mean *loyal
repeat buyers* — 94% of them bought exactly once. It means **recent, high-value,
single-purchase customers**. "At risk, high value" is not a churn warning: those
customers are not at risk of leaving, they have already gone, and most were never
going to return.

Read correctly, the segmentation says something simpler than it appears to: value
here is driven almost entirely by **basket size on a single order**, not by
relationship depth. That is a different business to run and a different one to
fix.

---

# FR-8 — Revenue concentration

## All three dimensions are highly concentrated

| Dimension | Members | Members reaching 80% of revenue | Share of members | Gini |
|---|---|---|---|---|
| Category | 74 | 18 | 24.3% | **0.713** |
| Seller | 3,095 | 562 | 18.2% | **0.785** |
| Customer state | 27 | 7 | 25.9% | **0.703** |

Sellers follow Pareto almost exactly — 18.2% of them produce 80% of revenue — and
the top of the distribution is sharper still:

| Tier | Sellers | Share of revenue |
|---|---|---|
| Top 1% | 31 | **25.62%** |
| Top 5% | 155 | 52.51% |
| Top 10% | 310 | 66.76% |
| Top 20% | 619 | 82.06% |

Thirty-one sellers out of three thousand produce a quarter of all revenue. Any
seller-side intervention has an obvious first cohort.

Categories are led by `health_beauty` (9.10%), `watches_gifts` (8.24%) and
`bed_bath_table` (7.84%), with no category above 10%. Category late rates sit in
a narrow band of 5.0% to 8.0% across the top 15 — **lateness is not a category
phenomenon**, which is a useful negative result: it rules out product handling as
the primary driver and points at geography instead.

## Damage concentrates differently from revenue

This is the BQ-4 answer, and it is not the same ranking as revenue.

| State | % of all revenue | % of all late-order revenue | Late rate | Mean review |
|---|---|---|---|---|
| SP | 37.39% | 23.70% | **4.49%** | 4.195 |
| **RJ** | **13.44%** | **22.98%** | **12.11%** | 3.893 |
| MG | 11.71% | 7.57% | 4.58% | 4.154 |
| BA | 3.86% | 6.63% | 12.17% | 3.876 |
| CE | 1.74% | 3.38% | 13.74% | 3.874 |
| MA | 0.96% | 2.35% | **17.36%** | 3.774 |

**Rio de Janeiro is the target.** It produces 13.4% of revenue and absorbs 23.0%
of the revenue sitting on late orders — a 1.7× over-representation — at a late
rate of 12.11% against São Paulo's 4.49%. It is nearly three times as likely to
fail as the largest market, and it is large enough for the difference to be worth
money rather than merely worth noting.

The northeastern states fail harder still — Maranhão at 17.36% — but each is
around 1% of revenue, so fixing them is a smaller prize. The combination of *high
volume* and *high failure rate* exists in exactly one place, and RJ's mean review
score (3.893 against SP's 4.195) confirms customers are noticing.

---

## What M4 fixes for the milestones after it

| Constraint | Applies to | Finding |
|---|---|---|
| Headline estimate uses **all reviews**; the after-delivery figure is a stated selection bound, not an alternative estimate | M5 | Review timing |
| Pre-delivery reviews are **no longer excluded** from classifier training | M6 | Review timing |
| The repeat-purchase leg of BQ-3 is **reported as unanswerable**, not estimated | M5, M7 | FR-6 |
| The business case cannot rest on retention | M7 | FR-6 |
| The intervention must target the **first week** of lateness, where the damage is | M7 | FR-5 |
| Carrier transit, not seller handover, is where the variance is | M7 | FR-5 |
| RJ is the segment to cost first | M7 | FR-8 |
| RFM labels must be reported with the F-degeneracy caveat attached | M7 | FR-7 |

---

## Limitations

1. **Everything here is descriptive.** No causal claim is made or implied. The
   2.020-point gap between late and on-time orders is a difference between two
   groups that were not randomly assigned, and it is not yet an estimate of what
   a late delivery *causes*. M5 applies controls; FR-12 states what survives them.
2. **The outcome measure is compromised by design.** The survey fires at dispatch,
   so for most late orders the review measures the experience of *waiting*, not of
   receiving a late parcel. No analysis choice fixes this, and conditioning on it
   makes the problem worse rather than better.
3. **Retention may be understated by the data rather than by the business.** A
   2.24% two-year repeat rate is unusual; `customer_unique_id` may not follow a
   person who re-registered. Untestable with the fields available.
4. **The trend window is 2017-01 to 2018-08.** 2016 (329 orders total, with
   November empty) and the truncated final two months are excluded from every
   time series (M2 F-06).
5. **Segment late rates on the seller dimension use single-seller orders only**
   (M2 F-12), so they are not directly comparable to state or category rates,
   which use all orders.

---

## Document control

| Field | Value |
|---|---|
| Milestone | M4 — Descriptive analysis |
| Satisfies | SRS FR-5, FR-6, FR-7, FR-8 |
| Evidence | `docs/descriptive_results.md`, five marts in `dbt_orderlens/models/marts/` |
| Amends | M2 finding F-09's handling decision |
| Unblocks | M5 (inferential analysis) |
| Author | Muhammad Haris Khokhar |

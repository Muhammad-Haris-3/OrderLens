# OrderLens — Inferential Analysis Results (generated)

**Do not edit by hand.** Regenerate with `python analysis/inferential.py`.

This file is the *evidence*. The interpretation, and the limitations
statement FR-12 requires, live in
[inferential_findings.md](inferential_findings.md).

| Generated | 2026-08-11 13:24 UTC |
|---|---|
| Population | 95,824 delivery-eligible orders carrying a review |
| Source | `analytics_marts.mart_order_analysis` |

---

## FR-9 — Does review score differ between on-time and late deliveries?

**H0:** the distribution of review scores is the same for on-time and
late deliveries. **H1:** they differ. Two-sided, α = 0.05.

### Groups

| group | n | mean | median | sd | % score 1 | % score 5 |
|---|---|---|---|---|---|---|
| on time | 89,443 | 4.2904 | 5.0000 | 1.1492 | 6.6187 | 62.2665 |
| late | 6,381 | 2.2705 | 1.0000 | 1.5712 | 53.7690 | 16.5335 |


### Test

| test | statistic (U) | p-value | n on time | n late |
|---|---|---|---|---|
| Mann-Whitney U (two-sided) | 467,430,237.0000 | < 1e-308 (below double precision) | 89,443 | 6,381 |


### Effect size — the part that is actually the finding

| measure | value | magnitude | reading |
|---|---|---|---|
| Rank-biserial correlation | 0.6380 | large | difference in the probability of one group outranking the other |
| Probability of superiority | 0.8190 |  | chance a random on-time order outscores a random late one |
| Difference in means | 2.0199 |  | review points, uncontrolled |
| Difference in medians | 4.0000 |  | review points |


A randomly chosen on-time order outscores a randomly chosen late order **81.9%** of the time (ties split). The rank-biserial correlation of **0.638** is a **large** effect on Cohen's conventional thresholds.

---

## FR-10 — Assumptions, stated and checked

### Why not a t-test

| group | skewness | excess kurtosis | distinct values |
|---|---|---|---|
| on time | -1.7341 | 2.0853 | 5 |
| late | 0.7289 | -1.1090 | 5 |


The outcome takes five ordered values. It is **ordinal, not interval** —
nothing in the data says the distance from 1 to 2 equals the distance from
4 to 5 — and both groups are strongly skewed. A mean on this scale is a
convenience, not a measurement.

**No normality test is reported, deliberately.** At n ≈ 96,000 a
Shapiro-Wilk or Kolmogorov-Smirnov test rejects normality for any
deviation however trivial, so its p-value carries no information about
whether normality is *approximately* satisfied. The skewness and kurtosis
above answer the question the test would have been asked to answer. On a
five-point ordinal scale the answer was never in doubt.

**Consequence:** rank-based testing (Mann-Whitney), not a t-test. This is
the SRS §11 plan, and the numbers above are why it was the right plan.

### Equality of variance

| test | statistic | p-value | verdict |
|---|---|---|---|
| Levene (median-centred) | 1,341.0706 | 1.413e-291 | violated |


Mann-Whitney does not assume equal variance, so a violation here does not
invalidate it. It is reported because it rules out Welch's t-test as a
fallback and because it is the first sign of the shape problem below.

### Distribution shape — the assumption that actually bites

| review score | % of on-time orders | % of late orders |
|---|---|---|
| 1 | 6.6187 | 53.7690 |
| 2 | 2.6486 | 8.6507 |
| 3 | 8.0744 | 10.8760 |
| 4 | 20.3918 | 10.1708 |
| 5 | 62.2665 | 16.5335 |


Mann-Whitney tests **stochastic dominance** in general. It is a test of a
*median shift* only when the two distributions have the same shape, and
these two plainly do not: on-time orders are concentrated at 5, late
orders at 1. The distributions are not shifted versions of each other,
they are differently shaped.

**Consequence — the interpretation is narrowed, not the test replaced.**
The result licenses *"late orders score stochastically lower"*. It does
**not** license *"late delivery costs exactly N review points"* on the
strength of the rank test alone. That quantity comes from the regression
in FR-11, which estimates it on stated functional-form assumptions.

### Independence

| clustering | units | observations | max per unit | % in units with >1 |
|---|---|---|---|---|
| customer (customer_unique_id) | 92,747 | 95,824 | 15 | 6.0956 |
| seller (primary_seller_id) | 2,953 | 95,824 | 1,787 | 99.4365 |


Observations are independent across customers to a good approximation —
3% of people appear more than once (M4 FR-6). They are emphatically **not**
independent within sellers: a single seller can account for thousands of
orders that share fulfilment behaviour and product mix.

**Consequence:** every regression in FR-11 uses standard errors clustered
on the seller. Ordinary standard errors would be too small, and the
confidence intervals correspondingly too confident.

---

## FR-13 — Families of tests, corrected

Two families are run. Each is a set of related tests answering one
question, so each is corrected as a set with Benjamini-Hochberg (FDR).
Bonferroni was rejected: it controls the probability of *any* false
positive, which is the wrong target when the question is which segments
to prioritise rather than whether a single effect exists, and at 27 tests
it would cost real power for no gain in decision quality.

### Is satisfaction homogeneous across segments at all?

| test | grouping | H statistic | p-value |
|---|---|---|---|
| Kruskal-Wallis | product category | 778.9905 | 1.955e-136 |
| Kruskal-Wallis | customer state | 581.4846 | 6.648e-109 |


Both reject homogeneity, which justifies looking segment by segment. On
its own this says nothing about *which* segments differ or by how much —
an omnibus test never does.

### Family 1 — does late delivery hurt in every state?

One Mann-Whitney per customer state with at least 200 orders in
each arm, corrected across the family.

| customer state | n on time | n late | raw p | rank-biserial | mean difference | BH-adjusted p | significant |
|---|---|---|---|---|---|---|---|
| ES | 1,765 | 205 | 1.92e-47 | 0.5569 | 1.7490 | 1.92e-47 | yes |
| BA | 2,844 | 384 | 6.95e-85 | 0.5675 | 1.7922 | 8.11e-85 | yes |
| SP | 38,485 | 1,786 | 0.0000 | 0.5774 | 1.7776 | 0.0000 | yes |
| MG | 10,776 | 506 | 2.42e-150 | 0.6036 | 1.9204 | 5.65e-150 | yes |
| SC | 3,236 | 284 | 3.58e-90 | 0.6413 | 1.9393 | 5.02e-90 | yes |
| RS | 5,005 | 321 | 1.95e-112 | 0.6612 | 2.1061 | 3.42e-112 | yes |
| RJ | 10,755 | 1,457 | 0.0000 | 0.7128 | 2.3298 | 0.0000 | yes |


### Family 2 — does late delivery hurt in every category?

One Mann-Whitney per product category with at least 200 orders in
each arm, corrected across the family.

| product category | n on time | n late | raw p | rank-biserial | mean difference | BH-adjusted p | significant |
|---|---|---|---|---|---|---|---|
| telephony | 3,762 | 287 | 1.84e-74 | 0.5878 | 1.7514 | 1.98e-74 | yes |
| furniture_decor | 5,704 | 439 | 4.10e-120 | 0.5967 | 1.8808 | 1.15e-119 | yes |
| bed_bath_table | 8,416 | 664 | 1.55e-175 | 0.5989 | 1.9147 | 7.22e-175 | yes |
| computers_accessories | 6,073 | 407 | 2.46e-117 | 0.6114 | 1.9342 | 5.74e-117 | yes |
| garden_tools | 3,161 | 221 | 2.19e-69 | 0.6213 | 2.0051 | 2.19e-69 | yes |
| auto | 3,501 | 273 | 7.65e-83 | 0.6223 | 1.9854 | 1.19e-82 | yes |
| health_beauty | 7,934 | 633 | 2.67e-212 | 0.6409 | 2.0406 | 3.74e-211 | yes |
| housewares | 5,346 | 300 | 7.91e-105 | 0.6538 | 2.0528 | 1.58e-104 | yes |
| perfumery | 2,859 | 200 | 6.93e-76 | 0.6581 | 2.1164 | 8.09e-76 | yes |
| watches_gifts | 5,041 | 395 | 8.91e-136 | 0.6653 | 2.0704 | 3.12e-135 | yes |
| cool_stuff | 3,297 | 204 | 5.25e-76 | 0.6725 | 2.0981 | 6.68e-76 | yes |
| sports_leisure | 6,962 | 486 | 1.40e-183 | 0.6798 | 2.2127 | 9.80e-183 | yes |
| baby | 2,519 | 218 | 1.93e-80 | 0.6871 | 2.2235 | 2.70e-80 | yes |
| toys | 3,525 | 232 | 2.10e-92 | 0.6872 | 2.2494 | 3.68e-92 | yes |


---

## FR-11 — The effect of delay on review score, with controls

Ordinary least squares on the 1-5 review score, with standard errors
**clustered on the seller** (FR-10). Controls, as required by FR-11:
log item value, freight ratio, log distance, item count, product category,
seller state, customer state, season and purchase year.

474 of 95,824 reviewed orders are dropped for a missing
control — almost all of them the orders whose customer or seller ZIP
prefix has no centroid (M2 F-07).

### Coefficients on the treatment terms

| model | term | coefficient | 95% CI | p-value | R² | n |
|---|---|---|---|---|---|---|
| A. Uncontrolled — is_late only | is_late[T.True] | -2.0217 | [-2.0690, -1.9743] | < 1e-308 (below double precision) | 0.1536 | 95,350 |
| B. Uncontrolled — delay_days only | delay_days | -0.0340 | [-0.0359, -0.0321] | 3.803e-267 | 0.0715 | 95,350 |
| C. Controlled — is_late | is_late[T.True] | -1.9800 | [-2.0288, -1.9312] | < 1e-308 (below double precision) | 0.1810 | 95,350 |
| D. Controlled — delay_days (primary) | delay_days | -0.0363 | [-0.0382, -0.0344] | < 1e-308 (below double precision) | 0.1146 | 95,350 |
| E. Controlled — asymmetric (days late / days early) | days_late | -0.0599 | [-0.0674, -0.0525] | 3.618e-56 | 0.1226 | 95,350 |
| E. Controlled — asymmetric (days late / days early) | days_early | 0.0258 | [0.0239, 0.0277] | 3.975e-153 | 0.1226 | 95,350 |
| F. Controlled — jump plus slope (recommended) | is_late[T.True] | -1.7109 | [-1.7740, -1.6477] | < 1e-308 (below double precision) | 0.1849 | 95,350 |
| F. Controlled — jump plus slope (recommended) | days_late | -0.0152 | [-0.0193, -0.0110] | 5.468e-13 | 0.1849 | 95,350 |
| F. Controlled — jump plus slope (recommended) | days_early | 0.0081 | [0.0068, 0.0095] | 1.698e-32 | 0.1849 | 95,350 |


### Reading the primary model

Controlled, **one day of delay costs 0.0363 review points** (95% CI [-0.0382, -0.0344]).

The uncontrolled estimate is 0.0340. Controls move it by 6.9% — the direction and rough size of the association survive adjustment,
which is the question BQ-2 asks.

### The asymmetry — why a single slope is misleading

| term | coefficient | std error | CI low | CI high | p-value |
|---|---|---|---|---|---|
| days_late | -0.0599 | 0.0038 | -0.0674 | -0.0525 | 3.618e-56 |
| days_early | 0.0258 | 0.0010 | 0.0239 | 0.0277 | 3.975e-153 |


A day of **lateness** costs 0.0599 review points. A day of **earliness** is worth 0.0258 — 2.3× less.

Model D's single `delay_days` slope averages those two very different
numbers and describes neither.

### Separating the cliff from the ramp — the recommended specification

M4 found the damage arrives on the *first* day of lateness rather than
accumulating. Model E cannot express that: with only a per-day slope, a
discrete drop at the boundary has to be smeared across the days that
follow it. Model F carries both — `is_late` for the jump, `days_late` for
the slope beyond it.

| term | coefficient | std error | CI low | CI high | p-value |
|---|---|---|---|---|---|
| is_late[T.True] | -1.7109 | 0.0322 | -1.7740 | -1.6477 | < 1e-308 (below double precision) |
| days_late | -0.0152 | 0.0021 | -0.0193 | -0.0110 | 5.468e-13 |
| days_early | 0.0081 | 0.0007 | 0.0068 | 0.0095 | 1.698e-32 |


**Crossing the promised date at all costs 1.7109 review points.** Each further day costs 0.0152 on top of that — 113 days of additional lateness to do as much damage again as being one day late did in the first place.

**This is the specification the M7 recommendation should be costed from.**
It says the intervention worth buying is one that prevents an order from
becoming late at all; shaving days off deliveries that are already late is
worth an order of magnitude less per day.

### Robustness — a binary outcome, which needs no interval assumption

OLS on a 1-5 ordinal scale assumes the gaps between adjacent scores are
equal, which nothing in the data supports. Logistic regression on
`is_low_score` (a review of 1 or 2) makes no such assumption: the outcome
is genuinely binary and the estimate does not depend on how the five
points are spaced.

| term | coefficient (log-odds) | odds ratio | 95% CI (OR) | p-value |
|---|---|---|---|---|
| days_late | 0.1547 | 1.1673 | [1.1591, 1.1757] | < 1e-308 (below double precision) |
| days_early | -0.0468 | 0.9543 |  | 2.247e-184 |


Each additional day late multiplies the odds of a 1-or-2 star review by **1.1673** — about **16.7% per day**, compounding. Pseudo-R² 0.1284, n = 95,350.

The two specifications agree on sign, significance and rough magnitude
while resting on different assumptions, which is what a robustness check
is for.

### Stated selection bound — reviews written after delivery only

M4 established that whether a review predates delivery is very nearly
*determined by* whether the delivery was late: 0.2% on on-time orders,
96-99% on late ones. It is a **post-treatment variable**, so restricting
to after-delivery reviews does not remove a confounder — it selects a
non-random subset of late orders.

This model is reported as a **bound, not an alternative estimate**.

| term | coefficient | std error | CI low | CI high | p-value |
|---|---|---|---|---|---|
| is_late[T.True] | -0.3652 | 0.0441 | -0.4517 | -0.2787 | 1.277e-16 |
| days_late | -0.0307 | 0.0124 | -0.0549 | -0.0064 | 0.013102 |
| days_early | 0.0078 | 0.0007 | 0.0064 | 0.0091 | 1.775e-29 |


| term | all reviews (model F) | after-delivery only | change |
|---|---|---|---|
| is_late (the jump) | -1.7109 | -0.3652 | smaller by 79% |
| days_late (the slope) | -0.0152 | -0.0307 | larger by 102% |


n = 90,734 of 95,350 (95.2%) — but only 30.0% of the *late* orders survive the restriction.

The two coefficients move in **opposite directions**, and that is the
informative part. The discrete jump shrinks — customers who waited long
enough to receive the parcel before responding are less harsh about the
fact of lateness. The per-day slope steepens — among those who did wait,
each additional day matters more.

Neither number is the truth. Restricting to after-delivery reviews
conditions on a post-treatment variable, so it trades one bias for
another rather than removing bias. The defensible statement is that the
effect on *post-delivery* sentiment lies between these specifications, and
that this dataset cannot locate it more precisely — because the instrument
measuring satisfaction is triggered by the process being measured.

---

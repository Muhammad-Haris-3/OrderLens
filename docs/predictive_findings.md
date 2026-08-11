# OrderLens — Predictive Findings

**Milestone:** M6
**Satisfies:** SRS FR-14 (pre-delivery classifier), FR-15 (cost-based
threshold), FR-16 (stated baseline, honest reporting), FR-17 (permutation
importance)
**Answers:** BQ-5 — can at-risk orders be identified before delivery?
**Date:** 2026-08-11

---

## Summary

| Question | Answer |
|---|---|
| Can at-risk orders be identified before delivery? | **Weakly.** Average precision 0.188 against a 0.097 base rate — roughly double random, and far from a targeting tool |
| Does it beat a stated baseline? | Yes — 1.4× a one-feature seller heuristic, 1.9× the base rate. Modestly, and the margin is reported as modest |
| Is it worth deploying? | **Only inside a narrow band of cost assumptions.** Outside roughly 1:5 to 1:15 (FP:FN), a blanket policy does as well |
| Why is it weak? | Partly because delivery outcomes are not predictable at purchase time. Mostly because **most bad reviews are not about delivery at all** |

**The most important number in this milestone is not a model metric.** Across the
full period, **67.5% of low reviews sit on orders that arrived on time or early**.
That bounds every delivery-based intervention M7 could recommend.

---

## 1. FR-14 — The model, and the leakage rule

### The rule, enforced twice

The classifier may use only what is known when the order is placed. Design Phase
§8 asks for an explicit allowlist rather than discipline, so there are two
independent guards:

1. **`mart_prediction_features`** never selects a post-delivery column.
2. **`analysis/predictive.py`** asserts it again against a denylist before a model
   sees anything, with three separate checks — a banned column reaching the mart,
   a banned or outcome column declared as a feature, and a declared feature that
   does not exist. Each has its own error message, because each has a different
   cause.

A third guard runs in CI without a database (`tests/test_leakage_guard.py`), so a
leak cannot reach `main` even if nobody runs the model.

Training on `is_late` would look superb — M5 measured that 53.8% of late orders
score the minimum — and be worthless, because by the time you know an order is
late there is nothing left to intervene on.

### The subtle leak: seller history

The single most useful pre-delivery feature is how often this seller has been
late before. Computed the obvious way — `avg(is_late) group by seller` — it is a
catastrophic leak: the average includes *this* order's outcome and every *future*
order's. The model reads the answer off a feature that would not exist in
production, and backtests beautifully.

So both seller features are computed **as-of the purchase timestamp**:

- Late rate counts prior orders **delivered** before this one was purchased.
- Low-score rate counts prior reviews **answered** before it — a review that
  exists but has not been written yet is not information anyone had.

The obvious correlated-subquery implementation takes **~21 minutes** over 96k
rows. Interleaving purchases and deliveries into one event stream per seller and
taking a running total is O(n log n) and runs in seconds. It was validated
against the slow version on 300 sampled orders: **300/300 exact matches**.

### Split

| Set | Orders | Low-score | Base rate | Period |
|---|---|---|---|---|
| Train | 77,304 | 10,470 | 13.54% | 2016-09-15 → 2018-05-31 |
| Test | 18,520 | 1,802 | **9.73%** | 2018-06-01 → 2018-08-29 |

**Temporal, not random.** A random split lets the model learn from June and
predict May, which no deployed model can do — and flatters it, because carrier
performance drifts month to month (M4 measured the late rate swinging between
1.16% and 18.96%).

The base rate drop from 13.5% to 9.7% is that drift showing up: the test window
happens to be a good quarter for deliveries.

---

## 2. FR-16 — Performance against stated baselines

Baselines are declared before the models, not chosen afterwards to be beatable.

| Approach | ROC AUC | Average precision |
|---|---|---|
| Never flag (majority class) | — | 0.0973 |
| Flag everything | — | 0.0973 |
| Seller prior low-score rate (one feature, no model) | 0.573 | 0.1298 |
| Logistic regression | 0.609 | 0.1697 |
| **Gradient boosting** | **0.626** | **0.1876** |

**Read average precision, not accuracy or ROC AUC.** With a 9.7% base rate, a
model predicting *no order is ever at risk* scores 90.3% accuracy — and is
useless. ROC AUC is similarly flattering on imbalanced data.

The gradient booster reaches **0.188 average precision against a 0.097 base
rate** — 1.9× random, and 1.4× the one-feature heuristic a business could run in
a spreadsheet.

**That is a real but modest result, and it is reported as modest.** The model
beats every stated baseline; it does not come close to being a reliable targeting
tool. A precision of 14% at the operating threshold means six of every seven
flagged orders would have been fine.

---

## 3. FR-15 — The threshold, chosen by cost

### Stated assumptions

Flagging an order means intervening on it — a proactive status contact, a
shipping upgrade, a goodwill credit.

| Quantity | Assumed | Meaning |
|---|---|---|
| Cost of a false positive | **R$5** | Intervening on an order that would have been fine |
| Cost of a false negative | **R$50** | A preventable low review that was not prevented |
| Ratio | 1 : 10 | |

Both are assumptions about a business this project does not run. The sensitivity
analysis matters more than the point values.

### The threshold F1 would have chosen is the wrong one

| Rule | Threshold | Flagged | Precision | Recall | Expected cost |
|---|---|---|---|---|---|
| **Cost-optimal** | **0.105** | 6,758 | 0.142 | **0.532** | **R$71,200** |
| F1-optimal | 0.165 | 1,863 | 0.234 | 0.241 | R$75,490 |
| Default 0.5 | 0.500 | 35 | 0.486 | 0.009 | R$89,340 |

The default 0.5 threshold flags **35 orders out of 18,520** and costs R$89,340 —
barely better than doing nothing at all (R$90,100). It is the threshold nobody
chose and everybody uses.

F1 does better but still optimises a quantity with no business meaning: it
weights precision and recall equally, which is a claim that a false positive
costs exactly as much as a false negative. Here they differ by 10×, and F1 leaves
R$4,290 on the table.

### Is the model worth anything?

| Policy | Expected cost |
|---|---|
| Do nothing | R$90,100 |
| Flag every order | R$83,590 |
| **Model at the cost-optimal threshold** | **R$71,200** |

The model saves **R$18,900 against doing nothing** and **R$12,390 against
flagging everything**, on 18,520 orders — **R$1.02 per order** against inaction,
and **R$0.67 per order** against the blanket policy. The second number is the one
that measures the model's own contribution, since flagging everything requires no
model at all.

### Sensitivity — and where the model stops being useful

| FP : FN ratio | Optimal threshold | Flagged | Recall | Precision |
|---|---|---|---|---|
| 1 : 2 | 0.270 | 587 | 0.119 | 0.366 |
| 1 : 5 | 0.210 | 1,049 | 0.172 | 0.295 |
| **1 : 10** | **0.105** | 6,758 | 0.532 | 0.142 |
| 1 : 20 | 0.040 | **18,464** | 0.999 | 0.098 |
| 1 : 50 | 0.030 | **18,516** | 1.000 | 0.097 |

**At a ratio of 1:20 or worse the optimal policy is to flag essentially every
order.** The model degenerates to "intervene on everything", precision collapses
to the base rate, and the classifier adds nothing a blanket policy would not.

This is the honest boundary on the deliverable: **the model is useful only if a
false negative costs somewhere between about 5× and 15× a false positive.** If
intervention is very cheap, intervene on everyone and skip the model. If it is
expensive, the model's precision is too low to justify acting on.

M7 must state which regime the business is in before recommending deployment.

### Calibration

Brier score **0.0850**, against 0.0878 for predicting the base rate every time —
a small improvement, honestly small. Predicted and observed rates track closely
across deciles (top decile: 0.257 predicted, 0.234 observed), with mild
over-prediction in the upper half.

That matters because a cost-optimal threshold is only meaningful if the
probabilities mean what they say. A threshold of 0.105 on a miscalibrated model
would not be the 10.5% risk it appears to be.

---

## 4. FR-17 — What the model actually uses

Permutation importance on the **test set**, scored by average precision, 5
repeats. Not impurity importance: impurity is computed on training data and is
biased toward high-cardinality features, which here would hand the top of the
table to `primary_category` and `distance_km` for being finely divisible rather
than for being informative.

| Feature | Drop in average precision |
|---|---|
| **`item_count`** | **0.0570** |
| `seller_prior_low_score_rate` | 0.0195 |
| `seller_count` | 0.0186 |
| `order_item_total` | 0.0034 |
| `estimated_days` | 0.0024 |
| `customer_state` | 0.0023 |
| … | |
| `seller_prior_late_rate` | 0.0003 |
| `season`, `is_same_state`, `is_single_seller` | ≈ 0 |

Three things worth saying about this table.

**Basket complexity dominates.** `item_count` is three times more important than
anything else, with `seller_count` close behind. More items and more sellers mean
more independent things that can go wrong, and the model has essentially learned
"complicated orders disappoint people". That is a plausible mechanism, not a
leak — both are known at purchase.

**Past bad reviews predict future bad reviews; past lateness does not.**
`seller_prior_low_score_rate` is the second most useful feature (0.0195), while
`seller_prior_late_rate` is worth almost nothing (0.0003). A seller's history of
disappointing customers carries signal; their history of missing dates carries
almost none. That is consistent with §5: most dissatisfaction is not about
delivery timing, so a lateness-based track record is measuring the wrong thing.

**Geography and season are worth nothing here.** M4 found strong *geographic*
variation in late rates (RJ 12.11% against SP 4.49%), and M5 found RJ has the
largest satisfaction effect of any state. Neither helps predict an individual
order's review, because the variation is between-group and the within-group noise
is far larger.

---

## 5. Why the model is weak — and the finding that matters most

A weak model invites the question of whether the features were simply poor. That
is testable, so it was tested.

### The ceiling diagnostic

A second model was fitted with `is_late` and `delay_days` added — the two columns
FR-14 forbids. **It is deliberately leaking and is never deployed.** Its only
purpose is to measure the ceiling.

| Model | Average precision |
|---|---|
| Honest (deployable) | 0.1876 |
| **Leaking (diagnostic only)** | **0.3197** |
| Base rate | 0.0973 |

Knowing the delivery outcome for certain lifts average precision by 1.7×. So some
of the signal genuinely is unavailable at purchase time — whether an order goes
late is driven by carrier-side variance that M4 measured as episodic, and none of
that is visible in the basket, the product, the route or the seller's history
when the order is placed.

### But even perfect knowledge of lateness reaches only 0.32

A model that *knows for certain* whether each order arrived late still cannot
identify most low reviews. The decomposition says why:

**Full period (2016-09 to 2018-08):**

| Group | Orders | % of orders | Low-score orders | % of all low scores | Low-score rate |
|---|---|---|---|---|---|
| Arrived late | 6,381 | 6.66% | 3,983 | **32.5%** | 62.4% |
| Arrived on time or early | 89,443 | 93.34% | 8,289 | **67.5%** | 9.3% |

**Test window (2018-06 to 2018-08), a good quarter for deliveries:**

| Group | Orders | % of orders | Low-score orders | % of all low scores | Low-score rate |
|---|---|---|---|---|---|
| Arrived late | 656 | 3.54% | 307 | **17.0%** | 46.8% |
| Arrived on time or early | 17,864 | 96.46% | 1,495 | **83.0%** | 8.4% |

**Two-thirds of low reviews across the full period — and five-sixths in the test
window — sit on orders that arrived on time or early.**

Late delivery is by far the strongest *per-order* driver of a bad review: a late
order is 6.7× more likely to score low (62.4% against 9.3%). But late orders are
rare, and 9.3% of a very large number is bigger than 62.4% of a small one.

---

## 6. What this bounds for M7

**This is the milestone's contribution to the decision, and it is a constraint,
not a capability.**

M5 established that breaching the promised date costs 1.71 review points. M6
establishes the size of the prize: **eliminating lateness entirely would address
at most 32.5% of low reviews** over the full period. Two-thirds of dissatisfaction
has causes this project has not measured — product quality, description accuracy,
seller communication, packaging — and no delivery intervention touches them.

| Constraint | Detail |
|---|---|
| Size the recommendation against **32.5% of low reviews**, not all of them | §5 |
| Proactive targeting is **not** a viable intervention on this evidence — precision 14% at the operating threshold | §2, §3 |
| If deployment is proposed, state the cost regime: the model only beats a blanket policy between roughly 1:5 and 1:15 | §3 |
| Prevention at the operational level (M5) is better supported than prediction at the order level (M6) | §5 |
| Do not cite accuracy. At a 9.7% base rate it is meaningless | §2 |

The recommendation M7 should make is therefore **operational, not algorithmic**:
fix the carrier-side variance M4 identified in the segments M4 and M5 both point
at, rather than deploying a model to guess which individual orders will suffer
from it.

---

## 7. Limitations

1. **The cost matrix is assumed, not measured.** R$5 and R$50 are plausible
   placeholders. The sensitivity analysis in §3 is the honest part; the point
   estimates are not.
2. **Intervention effectiveness is assumed to be 1.** The cost model treats a
   caught true positive as a prevented bad review. In reality an intervention
   prevents the outcome with some probability below 1, which scales the false
   negative cost down and pushes the optimal threshold up. The model is therefore
   optimistic about its own value.
3. **One temporal split, not cross-validation.** A single held-out quarter, and a
   quarter with an unusually low base rate. Rolling-origin validation across
   several windows would give a more stable estimate; it was not run.
4. **The target inherits M5's measurement problem.** `is_low_score` comes from a
   survey that fires at dispatch, so for late orders it partly measures waiting
   rather than receiving (M5 §6.3).
5. **Only orders with a review are modelled** — 95,824 of 96,470 delivery-eligible
   orders. Non-response is not modelled and may not be random.
6. **`seller_prior_*` is null for 5,230 orders** where the seller had no prior
   history. Imputed at the median for modelling; a first-time seller is a
   genuinely different case and is not treated as one.

---

## Document control

| Field | Value |
|---|---|
| Milestone | M6 — Predictive model |
| Satisfies | SRS FR-14, FR-15, FR-16, FR-17 |
| Evidence | `docs/predictive_results.md`, `analysis/predictive.py` |
| Reads | `analytics_marts.mart_prediction_features` |
| Unblocks | M7 (communication) |
| Author | Muhammad Haris Khokhar |

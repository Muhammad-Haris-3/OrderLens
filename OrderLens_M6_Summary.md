# OrderLens — M6 (Predictive Model) Milestone Summary

**Date:** 2026-08-11
**Status:** Complete
**Maps to:** SRS FR-14 (pre-delivery classifier), FR-15 (cost-based threshold),
FR-16 (stated baseline, honest reporting), FR-17 (permutation importance)
**Answers:** BQ-5 — can at-risk orders be identified before delivery?

---

## 1. Scope

Build a classifier that flags orders likely to receive a low review, using only
what is known when the order is placed, and choose its operating threshold by
what the business would actually pay rather than by a metric with no business
meaning.

The model works, modestly. The more valuable output is what it revealed about the
ceiling.

---

## 2. What was built

| Artefact | Delivers |
|---|---|
| `mart_prediction_features` | 95,824 orders, every column known at purchase time, with seller track record computed **as-of** the purchase timestamp |
| `analysis/predictive.py` | FR-14 to FR-17 → `docs/predictive_results.md` |
| `tests/test_leakage_guard.py` | Six CI-safe tests that fail if the leakage rule erodes |
| `docs/predictive_findings.md` | The interpretation and the limitations |

---

## 3. The leakage rule, enforced three times

Design Phase §8 asks for an explicit allowlist rather than discipline. There are
now three independent guards:

1. **`mart_prediction_features`** never selects a post-delivery column.
2. **`analysis/predictive.py`** asserts it again before a model sees anything —
   three separate checks with three separate error messages, because a banned
   column reaching the mart, a banned column declared as a feature, and a missing
   declared feature have different causes and different fixes.
3. **`tests/test_leakage_guard.py`** runs in CI without a database, so a leak
   cannot reach `main` even if nobody runs the model.

The guard earned its place on the first run: it fired on `review_score`, which is
the outcome rather than a leaking predictor. The fix was to separate `BANNED`
(post-delivery predictors) from `OUTCOMES` (the target and its source) so the two
failures report differently — a guard that cannot distinguish them teaches people
to ignore it.

### The subtle leak, and a 21-minute problem

The most useful pre-delivery feature is a seller's track record. Computed the
obvious way — `avg(is_late) group by seller` — it is catastrophic: the average
includes *this* order's outcome and every *future* order's. It backtests
beautifully and does not exist in production.

Both seller features are therefore computed **as-of the purchase timestamp**:
late rates count prior orders **delivered** before this one was purchased,
low-score rates count prior reviews **answered** before it — because a review that
exists but has not been written yet is not information anyone had.

The obvious correlated-subquery implementation takes **~21 minutes** over 96k
rows. Interleaving purchases and deliveries into a single event stream per seller
and taking a running total is O(n log n) and runs in **13 seconds**. It was
validated against the slow version on 300 sampled orders — **300/300 exact
matches**, checked rather than assumed.

---

## 4. FR-16 — the model beats its baselines, modestly

Temporal split at 2018-06-01. Not random: a random split lets the model learn
from June to predict May, which no deployed model can do, and flatters it because
carrier performance drifts (M4).

| Approach | ROC AUC | Average precision |
|---|---|---|
| Never flag / flag everything | — | 0.0973 |
| Seller prior low-score rate (one feature, no model) | 0.573 | 0.1298 |
| Logistic regression | 0.609 | 0.1697 |
| **Gradient boosting** | **0.626** | **0.1876** |

**0.188 average precision against a 0.097 base rate** — 1.9× random, 1.4× a
heuristic a business could run in a spreadsheet. Real, and reported as modest: at
the operating threshold, precision is 14%, so **six of every seven flagged orders
would have been fine**.

Accuracy is not reported anywhere, on purpose. At a 9.7% base rate, "no order is
ever at risk" scores 90.3%.

---

## 5. FR-15 — the threshold nobody chooses and everybody uses

Stated assumptions: a false positive costs **R$5** (intervening on an order that
was fine), a false negative **R$50** (a preventable low review). Both are
assumptions about a business this project does not run, which is why the
sensitivity analysis matters more than the point values.

| Rule | Threshold | Flagged | Precision | Recall | Expected cost |
|---|---|---|---|---|---|
| **Cost-optimal** | **0.105** | 6,758 | 0.142 | 0.532 | **R$71,200** |
| F1-optimal | 0.165 | 1,863 | 0.234 | 0.241 | R$75,490 |
| Default 0.5 | 0.500 | **35** | 0.486 | 0.009 | R$89,340 |

**The default threshold flags 35 orders out of 18,520 and costs R$89,340 —
barely better than doing nothing at all (R$90,100).** F1 does better and still
leaves R$4,290 on the table, because it weights precision and recall equally,
which is a claim that a false positive costs exactly what a false negative costs.
Here they differ tenfold.

Against a blanket "flag everything" policy (R$83,590) the model saves R$12,390 —
**R$0.67 per order**, which is the number that measures the model's own
contribution, since flagging everything needs no model.

### Where the model stops being useful

| FP : FN ratio | Optimal threshold | Flagged | Precision |
|---|---|---|---|
| 1 : 2 | 0.270 | 587 | 0.366 |
| **1 : 10** | 0.105 | 6,758 | 0.142 |
| 1 : 20 | 0.040 | **18,464 of 18,520** | 0.098 |
| 1 : 50 | 0.030 | **18,516 of 18,520** | 0.097 |

At 1:20 or worse the optimal policy is to flag **essentially every order** — the
model degenerates to "intervene on everything" and precision collapses to the
base rate.

**The honest boundary: this model is only useful if a false negative costs
between roughly 5× and 15× a false positive.** Cheaper intervention, skip the
model and act on everyone. More expensive, precision is too low to act at all.

---

## 6. FR-17 — what the model actually uses

Permutation importance on the test set, scored by average precision. Not impurity
importance, which is computed on training data and biased toward high-cardinality
features — here it would have handed the top of the table to `primary_category`
and `distance_km` for being finely divisible rather than informative.

| Feature | Drop in average precision |
|---|---|
| **`item_count`** | **0.0570** |
| `seller_prior_low_score_rate` | 0.0195 |
| `seller_count` | 0.0186 |
| `estimated_days` | 0.0024 |
| `seller_prior_late_rate` | **0.0003** |

**Basket complexity dominates** — three times more important than anything else.
More items and more sellers means more independent things that can go wrong.

**Past bad reviews predict future bad reviews; past lateness does not.**
`seller_prior_low_score_rate` matters (0.0195); `seller_prior_late_rate` is worth
almost nothing (0.0003). A seller's history of disappointing customers carries
signal; their history of missing dates carries almost none — which makes sense
given §7.

**Geography and season contribute nothing**, despite M4 finding strong geographic
variation in late rates and M5 finding RJ has the largest satisfaction effect of
any state. That variation is between-group; the within-group noise on an
individual order is far larger.

---

## 7. The finding that matters most

A weak model invites the question of whether the features were simply poor. That
is testable, so it was tested.

A second model was fitted with `is_late` and `delay_days` added — **deliberately
leaking, never deployed**, existing only to measure the ceiling.

| Model | Average precision |
|---|---|
| Honest (deployable) | 0.1876 |
| Leaking (diagnostic only) | **0.3197** |
| Base rate | 0.0973 |

Knowing the delivery outcome for certain lifts average precision 1.7×. So part of
the signal genuinely is unavailable at purchase time — M4 measured the late rate
swinging between 1.16% and 18.96% month to month, and that carrier-side variance
is invisible in the basket, the product, the route or the seller's history.

**But even perfect knowledge of lateness only reaches 0.32.** The decomposition
says why:

| Group | Orders | Low-score orders | % of all low scores | Low-score rate |
|---|---|---|---|---|
| Arrived late | 6,381 (6.7%) | 3,983 | **32.5%** | 62.4% |
| Arrived on time or early | 89,443 (93.3%) | 8,289 | **67.5%** | 9.3% |

**Two-thirds of low reviews sit on orders that arrived on time or early.**

A late order is 6.7× more likely to score low. But late orders are rare, and 9.3%
of a very large number exceeds 62.4% of a small one.

This bounds M7 directly. M5 established that breaching the promised date costs
1.71 review points; M6 establishes the size of the prize. **Eliminating lateness
entirely would address at most 32.5% of low reviews.** The remaining two-thirds
have causes this project has not measured — product quality, description
accuracy, seller communication, packaging — and no delivery intervention touches
them.

---

## 8. What M6 hands to M7

| Constraint | Source |
|---|---|
| Size the recommendation against **32.5% of low reviews**, not all dissatisfaction | §7 |
| **Do not recommend deploying the classifier as a targeting tool** — 14% precision at the operating threshold | §4, §5 |
| If deployment is proposed anyway, state the cost regime: it beats a blanket policy only between roughly 1:5 and 1:15 | §5 |
| Prevention at the **operational** level (M5) is far better supported than prediction at the **order** level (M6) | §7 |
| Never cite accuracy — meaningless at a 9.7% base rate | §4 |

The recommendation M7 should make is **operational, not algorithmic**: fix the
carrier-side variance M4 identified, in the segments M4 and M5 both point at,
rather than deploying a model to guess which individual orders will suffer from
it.

---

## 9. How it was verified

| Check | Result |
|---|---|
| `python scripts/run_dbt.py build` | **217/217** — 24 models, 193 data tests |
| `pytest -q` | **43 passed** (37 at M5) |
| `ruff check .` | clean |
| `python analysis/predictive.py` | regenerates `docs/predictive_results.md` |
| As-of seller history vs correlated-subquery ground truth | **300/300 exact** |
| Leakage guard fails without a database | ✅ 6 tests |

---

## 10. Problems hit while building this

**The leakage guard fired on the outcome.** First run aborted on `review_score` —
correct behaviour from a guard that could not tell a leaking predictor from the
target. Split into `BANNED` and `OUTCOMES` with separate messages, because a
guard that cries wolf is a guard people disable.

**The obvious as-of implementation was 21 minutes.** A correlated subquery over
96k orders ran 26.5 seconds per 2,000 rows. Rewritten as an event-stream window
— purchases and deliveries interleaved per seller, running total read at the
purchase — it takes 13 seconds. Correctness was then checked against the slow
version rather than assumed, on 300 sampled orders.

**The first cost figure was attributed to the wrong comparison.** The write-up
said the model saves "R$1.02 per order over a blanket policy"; R$1.02 is the
saving against *inaction*, and the saving against the blanket policy is R$0.67.
The second is the number that measures the model, since flagging everything
requires no model at all.

---

## 11. Definition of Done

| Criterion | Status |
|---|---|
| Artefacts committed | ✅ |
| Automated tests pass | ✅ 217 dbt + 43 pytest, lint clean |
| Every figure traceable to a committed script | ✅ |
| Assumptions and limitations recorded | ✅ six, in `predictive_findings.md` |
| Milestone summary written, including problems found | ✅ this document, §10 |
| **Negative results reported as such (NFR-8)** | ✅ §4, §5, §7 |

---

## 12. Next: M7 — Communication

FR-18 to FR-21: the dashboard, the decision memo, the A/B design, and every
recommendation quantified in currency.

The analysis is complete and the constraints are known. M7's job is to turn them
into a decision a business could act on:

- **Dashboard** (FR-18) — Tableau Public against `analytics_marts`, three views,
  colourblind-safe (NFR-6)
- **Decision memo** (FR-19) — ≤2 pages, intelligible without technical background
- **A/B design** (FR-20) — hypothesis, metric, unit of randomisation, required
  sample size
- **Currency** (FR-21) — sized against the 32.5% of low reviews delivery can
  reach, with M5's selection range stated rather than a point estimate presented
  as certain

---

## Document control

| Field | Value |
|---|---|
| Milestone | M6 — Predictive model |
| SRS version | 1.0 |
| Design Phase version | 1.1 |
| Previous | `OrderLens_M5_Summary.md` |
| Next document | `OrderLens_M7_Summary.md` |

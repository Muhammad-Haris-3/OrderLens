# OrderLens — Predictive Model Results (generated)

**Do not edit by hand.** Regenerate with `python analysis/predictive.py`.

This file is the *evidence*. The interpretation lives in
[predictive_findings.md](predictive_findings.md).

| Generated | 2026-08-11 13:46 UTC |
|---|---|
| Source | `analytics_marts.mart_prediction_features` |
| Split | temporal at 2018-06-01 |

---

## FR-14 — The leakage guard

The classifier may use only what is known at purchase time. Columns are
checked against an explicit denylist before a model sees anything; the
run aborts if any is present.

| check | result |
|---|---|
| Banned post-delivery columns in the feature frame | none |
| Declared features present in the mart | all 26 |
| Columns in the mart deliberately not used as features | order_id, purchase_date, purchase_year, purchased_at, seller_prior_late |


**18 numeric and 8 categorical features.** The two seller track-record features are
computed as-of the purchase timestamp in SQL — a naive seller average
over the whole table would include this order's own outcome.

### Split

| set | orders | low-score orders | base rate | period |
|---|---|---|---|---|
| train | 77,304 | 10,470 | 0.1354 | 2016-09-15 to 2018-05-31 |
| test | 18,520 | 1,802 | 0.0973 | 2018-06-01 to 2018-08-29 |


Temporal, not random. A random split lets the model learn from June and
predict May, which no deployed model can do — and flatters it, because
carrier performance drifts month to month (M4).

---

## FR-16 — Performance against stated baselines

Baselines are declared before the models, not chosen afterwards to be
beatable. Average precision is the metric to read: with a 9.7% base rate, ROC AUC is optimistic and accuracy is
meaningless — a model predicting *no order is ever at risk* scores 90.3% accuracy.

| approach | note | ROC AUC | average precision |
|---|---|---|---|
| Never flag (majority class) | predicts no order is at risk | _n/a_ | 0.0973 |
| Flag everything | predicts every order is at risk | _n/a_ | 0.0973 |
| Seller prior low-score rate | one feature, no model — the number a spreadsheet could produce | 0.5727 | 0.1298 |
| Logistic regression |  | 0.6092 | 0.1697 |
| Gradient boosting |  | 0.6261 | 0.1876 |


A random-guessing classifier scores an average precision equal to the base rate, **0.0973**.

---

## FR-15 — Threshold chosen by business cost, not by F1

**Stated assumptions.** Flagging an order means intervening on it — a
proactive status contact, a shipping upgrade, a goodwill credit.

| quantity | assumed value | meaning |
|---|---|---|
| Cost of a false positive | R$5.00 | intervening on an order that would have been fine |
| Cost of a false negative | R$50.00 | a preventable low review that was not prevented |
| Ratio | 1 : 10 |  |


Both are assumptions about a business this project does not run. The
sensitivity analysis below therefore matters more than the point values:
what a decision-maker needs to know is how much the answer moves when
their own numbers replace these.

Model used: **Gradient boosting** (highest average precision).

| threshold rule | threshold | flagged | TP | FP | FN | precision | recall | expected cost (R$) |
|---|---|---|---|---|---|---|---|---|
| Cost-optimal (0.105) | 0.1050 | 6,758 | 958 | 5,800 | 844 | 0.1418 | 0.5316 | 71,200.0000 |
| Default 0.5 | 0.5000 | 35 | 17 | 18 | 1,785 | 0.4857 | 0.0094 | 89,340.0000 |
| F1-optimal (0.165) | 0.1650 | 1,863 | 435 | 1,428 | 1,367 | 0.2335 | 0.2414 | 75,490.0000 |


| policy | expected cost (R$) |
|---|---|
| Do nothing (flag no order) | 90,100.0000 |
| Flag every order | 83,590.0000 |
| Model at the cost-optimal threshold | 71,200.0000 |


### Sensitivity — where the threshold goes as the cost ratio changes

| FP : FN cost ratio | optimal threshold | orders flagged | recall | precision |
|---|---|---|---|---|
| 1 : 2 | 0.2700 | 587 | 0.1193 | 0.3663 |
| 1 : 5 | 0.2100 | 1,049 | 0.1715 | 0.2946 |
| 1 : 10 | 0.1050 | 6,758 | 0.5316 | 0.1418 |
| 1 : 20 | 0.0400 | 18,464 | 0.9989 | 0.0975 |
| 1 : 50 | 0.0300 | 18,516 | 1.0000 | 0.0973 |
| 1 : 100 | 0.0300 | 18,516 | 1.0000 | 0.0973 |


---

## FR-17 — Permutation importance

Permutation importance on the **test set**, scored by average precision,
5 repeats. Not impurity importance: impurity is computed on training
data and is biased toward high-cardinality features, which here would
hand the top of the table to `primary_category` and `distance_km` for
being finely divisible rather than for being informative.

The value is the drop in average precision when that column alone is
shuffled. Near-zero means the model was not using it.

| feature | mean drop in average precision | std |
|---|---|---|
| item_count | 0.0570 | 0.0023 |
| seller_prior_low_score_rate | 0.0195 | 0.0010 |
| seller_count | 0.0186 | 0.0012 |
| order_item_total | 0.0034 | 0.0008 |
| estimated_days | 0.0024 | 0.0007 |
| customer_state | 0.0023 | 0.0009 |
| product_count | 0.0013 | 0.0002 |
| seller_state | 0.0011 | 0.0006 |
| primary_category | 0.0010 | 0.0011 |
| distance_km | 0.0009 | 0.0012 |
| order_freight_total | 0.0008 | 0.0010 |
| payment_installments | 0.0006 | 0.0002 |
| freight_ratio | 0.0005 | 0.0010 |
| seller_prior_deliveries | 0.0004 | 0.0010 |
| seller_prior_late_rate | 0.0003 | 0.0003 |
| payment_type | 0.0003 | 0.0002 |
| purchase_month | 0.0000 | 0.0003 |
| is_single_seller | 0.0000 | 0.0000 |
| season | 0.0000 | 0.0000 |
| is_same_state | -0.0000 | 0.0002 |


---

## Diagnostic — why the honest model is weak

**This model is deliberately leaking and is never deployed.** It adds
`is_late` and `delay_days` — the two columns FR-14 forbids — to answer one
question: is the honest model weak because its features are poor, or
because the signal genuinely is not present at purchase time?

| model | features | ROC AUC | average precision |
|---|---|---|---|
| Honest (deployable) | 26 pre-delivery | 0.6261 | 0.1876 |
| Leaking (diagnostic only) | 26 + is_late + delay_days | 0.7079 | 0.3197 |
| Base rate | none | 0.5000 | 0.0973 |


Knowing the delivery outcome lifts average precision from 0.1876 to **0.3197** — 1.7× the honest model, and 3.3× the base rate.

So some of the signal is genuinely unavailable at purchase time: whether
an order goes late is driven by carrier-side variance that M4 measured as
episodic — a late rate swinging between 1.16% and 18.96% month to month —
and none of that is visible in the basket, the product, the route or the
seller's history when the order is placed.

### But even perfect knowledge of lateness is not enough

The leaking model reaches only 0.32 average precision. It knows, for
certain, whether each order arrived late — and still cannot identify most
low reviews. The decomposition says why.

| group | orders | % of orders | low-score orders | % of all low scores | low-score rate within group |
|---|---|---|---|---|---|
| arrived late | 656 | 3.5421 | 307 | 17.0366 | 46.7988 |
| arrived on time or early | 17,864 | 96.4579 | 1,495 | 82.9634 | 8.3688 |


**Most bad reviews are not about lateness.** Late orders are a minority of
orders and only about half of them score low, so the majority of low
scores in this dataset sit on orders that arrived **on time or early**.

That is the single most important caveat this milestone produces, and it
bounds M7 directly: delivery is the largest *controllable* driver of
dissatisfaction that this project can measure, but eliminating lateness
entirely would still leave the majority of low reviews in place. The
recommendation must be sized against the share it can actually reach, not
against all dissatisfaction.

---

## Calibration

Brier score **0.0850** (lower is better; predicting the base rate
for every order scores 0.0878).

A cost-optimal threshold is only meaningful if the probabilities mean
what they say — a threshold of 0.2 on a miscalibrated model is not the
20% risk it appears to be.

| decile | mean predicted | observed rate | n |
|---|---|---|---|
| (0.0266, 0.0629] | 0.0556 | 0.0632 | 1,852 |
| (0.0629, 0.0695] | 0.0664 | 0.0664 | 1,852 |
| (0.0695, 0.0753] | 0.0724 | 0.0599 | 1,852 |
| (0.0753, 0.083] | 0.0789 | 0.0751 | 1,852 |
| (0.083, 0.0918] | 0.0872 | 0.0810 | 1,852 |
| (0.0918, 0.101] | 0.0965 | 0.0821 | 1,852 |
| (0.101, 0.113] | 0.1070 | 0.0929 | 1,852 |
| (0.113, 0.131] | 0.1216 | 0.1042 | 1,852 |
| (0.131, 0.165] | 0.1447 | 0.1139 | 1,852 |
| (0.165, 0.589] | 0.2566 | 0.2343 | 1,852 |


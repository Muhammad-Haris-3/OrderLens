# OrderLens — Decision Analysis Results (generated)

**Do not edit by hand.** Regenerate with `python analysis/decision.py`.

This file is the *evidence* behind the decision memo. The memo itself is
[decision_memo.md](decision_memo.md).

| Generated | 2026-08-11 16:24 UTC |
|---|---|
| Source | `analytics_marts.mart_order_analysis` |
| Policy fitted on | orders before 2018-01-01 |
| Policy scored on | orders from 2018-01-01 |

---
## 1. Mechanism — is it the broken promise, or the wait?

M5 estimated that breaching the promised date costs 1.71 review points,
controlling for price, freight, distance, category, both geographies,
season and year. It did **not** control for how long the customer
actually waited — and until that is settled, two very different
recommendations are indistinguishable:

- If the harm comes from the **wait**, only faster delivery helps, and
  changing the promise is cosmetic.
- If the harm comes from the **broken promise**, then a promise the
  business can keep is a real intervention, and a cheap one.

### The adjustment

| specification | is_late coefficient | 95% CI | delivery_days coefficient | R² |
|---|---|---|---|---|
| M5 specification (no control for the wait) | -1.7109 | [-1.7740, -1.6477] | _n/a_ | 0.1849 |
| Adding the actual wait | -1.5559 | [-1.6191, -1.4926] | -0.0274 | 0.1934 |
| Adding the wait and the promise length | -1.5560 | [-1.6192, -1.4927] | -0.0303 | 0.1934 |


Adding the actual wait moves the breach effect from -1.7109 to **-1.5559** — an attenuation of only 9%. The wait matters (-0.0274 points per day) and it is not what is doing the damage.

### Same wait, different promise

The comparison without a functional form: orders that took a similar
time to arrive, split by whether that time broke the promise.

| actual wait | n on time | n late | mean score (on time) | mean score (late) | gap |
|---|---|---|---|---|---|
| 6–9 days | 20,906 | 110 | 4.3745 | 3.6000 | 0.7745 |
| 10–13 days | 15,111 | 131 | 4.2960 | 3.3053 | 0.9907 |
| 14–18 days | 11,571 | 266 | 4.2019 | 2.9737 | 1.2282 |
| 19–25 days | 7,151 | 977 | 4.0536 | 2.8802 | 1.1733 |
| 26–40 days | 2,249 | 2,853 | 3.8266 | 2.1016 | 1.7249 |


**A customer who waits ten days and was promised eight is markedly less
satisfied than a customer who waits ten days and was promised fifteen.**
The wait is identical. The promise is not.

### Converting breaches into bad reviews

Average marginal effect of a breach on the probability of a 1-or-2 star
review, controlling for the wait: **0.4024** — so preventing one
breach prevents about **0.402** of a bad review. Fitted with the
control set without category fixed effects (singular with them). This is the
conversion factor used throughout §3, and it is much smaller than the raw
62.4%-vs-9.3% difference because that gap includes everything else that
differs between late and on-time orders.

---

## 2. Policy — what actually reduces breaches

Rules are fitted on orders before 2018-01-01 and scored on
the 52,777 orders after it. An in-sample promise policy is one
that has already seen the answers.

### The obvious policy is worse than doing nothing

| policy | mean promise (days) | breach rate % | breaches |
|---|---|---|---|
| Current promise | 23.4381 | 8.7557 | 4,621 |
| Replace with route p90 (rejected) | 20.5015 | 11.2985 | 5,963 |


**Setting the promise from route history makes things worse.** A p90
promise targets a 10% breach rate by construction, and the platform's
current promise already achieves 8.76% — it is *more* conservative than
route history would suggest. Replacing it shortens the average promise
and buys more breaches, which is the wrong side of a lopsided trade.

This is worth stating plainly because it is the recommendation an
analyst would reach for first, and it is wrong.

### Extend only where the route demonstrably breaches

Promise becomes `max(current, route p95)`, and
only on routes whose measured breach rate exceeds a threshold. Never
shortened anywhere.

| breach threshold | % orders touched | mean promise (all) | promise before (touched) | promise after (touched) | breach rate after % | breaches prevented |
|---|---|---|---|---|---|---|
| > 8% | 19.4043 | 25.0751 | 28.6814 | 37.1173 | 7.0163 | 918 |
| > 10% | 12.4069 | 24.6168 | 29.1707 | 38.6707 | 7.4881 | 669 |
| > 12% | 9.3222 | 24.3687 | 28.9244 | 38.9065 | 7.7989 | 505 |


At the recommended **>8%** threshold the average
promise across all orders moves by under two days, because the change is
concentrated: it touches a fifth of orders and leaves four fifths
untouched.

### Where it lands

| customer state | orders | promise now | promise after | breach now % | breach after % |
|---|---|---|---|---|---|
| MA | 346 | 28.5462 | 39.8699 | 21.6763 | 7.2254 |
| CE | 633 | 30.5118 | 31.6351 | 20.3791 | 19.9052 |
| PA | 453 | 37.5210 | 37.8830 | 17.4393 | 17.2185 |
| MS | 411 | 25.8856 | 25.8856 | 15.8151 | 15.8151 |
| BA | 1,725 | 29.0562 | 36.1675 | 15.4783 | 5.8551 |
| ES | 1,047 | 25.2512 | 29.4938 | 15.3773 | 7.9274 |
| RJ | 6,342 | 28.4601 | 34.9693 | 14.6326 | 8.1678 |
| PE | 854 | 29.7084 | 37.4649 | 10.6557 | 5.9719 |
| SC | 1,885 | 26.1676 | 30.1390 | 10.0265 | 6.0477 |
| GO | 1,032 | 26.1783 | 26.1783 | 8.8178 | 8.8178 |


---

## 3. What it is worth (FR-21)

| quantity | value | note |
|---|---|---|
| Orders scored | 52,777 | the out-of-sample window |
| Months covered | 7.9000 |  |
| Breaches prevented (window) | 918 |  |
| Breaches prevented (annualised) | 1,397 |  |
| Bad reviews prevented (annualised) | 562 | at 0.4024 per breach, controlled |
| Revenue on touched routes (annualised) | 2,609,290.5200 | R$ |
| Revenue, all orders (annualised) | 12,861,713.7800 | R$ |


### The intervention is free to run. The risk is conversion.

Changing a delivery estimate costs nothing operationally — it is a
change to a number shown at checkout. What it risks is the sale: a
longer quoted date may lose customers who would have bought under the
shorter one.

**This dataset cannot measure that.** It contains completed orders only.
There is no browse, no cart, no abandonment — so the conversion effect of
a longer promise is not merely unmeasured here, it is unmeasurable here.
Any number claiming otherwise would be invented.

So the decision is expressed as the trade it actually is:

| conversion lost on touched routes | revenue forgone per year (R$) | implied cost per bad review prevented (R$) |
|---|---|---|
| 0.10% | 2,609.2900 | 4.6400 |
| 0.25% | 6,523.2300 | 11.6000 |
| 0.50% | 13,046.4500 | 23.2100 |
| 1.00% | 26,092.9100 | 46.4100 |
| 2.00% | 52,185.8100 | 92.8200 |


Preventing roughly **562 bad reviews a year** is
worth doing if a prevented 1-or-2 star review is worth more than the
figure in the right-hand column at whatever conversion loss the business
believes it would suffer.

**At a 0.5% conversion loss the implied cost is around R$23 per prevented bad review.**
The business does not have to accept that number — it has to decide
whether a 1-star review costs more or less than it, which is a judgement
it is far better placed to make than this analysis is.

That is why the recommendation is to **test**, not to roll out: the
benefit is estimated from observational data and the risk is unmeasured,
and an experiment settles both at once.

---

## 4. The experiment that would settle it (FR-20)

### Design

| element | specification |
|---|---|
| Hypothesis | Extending the delivery promise on high-breach routes reduces the share of orders receiving a 1-or-2 star review |
| H₀ | The low-score rate is the same under both promises |
| Primary metric | Share of delivered orders scoring 1 or 2 |
| Unit of randomisation | The order, assigned at checkout |
| Assignment | 50/50, on the high-breach routes only |
| Secondary metrics | Breach rate (the mechanism); mean review score |
| Guardrail metric | Checkout conversion — the risk this test exists to measure |
| Alpha / power | 0.05 two-sided / 0.80 |


**Why the order and not the customer.** The promise is set per order at
checkout, so the order is the level at which the treatment is actually
applied. Customer-level assignment would be the safer choice if repeat
purchase were common enough for one customer's orders to interfere with
each other — but only 2.24% of customers ever return (M4 FR-6), so the
contamination that would justify the loss of power does not exist here.

**Why conversion is a guardrail and not the primary metric.** The
benefit is what this analysis can estimate; the risk is what it cannot.
Powering on the benefit and monitoring the risk is the honest split, and
the test should stop early if conversion moves materially against the
treatment arm regardless of what the primary metric is doing.

### Sample size

Baseline low-score rate on the affected routes: **18.06%**.
The policy prevents a breach on **8.96%** of those
orders, and a breach carries **0.4024** of a bad review, so the
expected absolute reduction is **3.61%**
(18.06% → 14.45%).

| detectable effect | control % | treatment % | absolute change (pp) | orders per arm | orders total |
|---|---|---|---|---|---|
| expected effect | 18.0568 | 14.4499 | 3.6069 | 1,638 | 3,276 |
| 75% of expected | 18.0568 | 15.3516 | 2.7052 | 2,981 | 5,962 |
| half the expected effect | 18.0568 | 16.2533 | 1.8034 | 6,856 | 13,712 |


| detectable effect | orders total | months at current volume |
|---|---|---|
| expected effect | 3,276 | 2.5000 |
| 75% of expected | 5,962 | 4.6000 |
| half the expected effect | 13,712 | 10.6000 |


At the observed volume on those routes — roughly
**1,299 orders a month** — the expected effect is
detectable in a run of a few months. The half-effect row is the one to
plan against: it is the size the test should be able to rule out, not
the size hoped for.

**Attrition.** The metric is only observed on delivered, reviewed orders
— about 99% of eligible orders carry a
review — and delivery itself takes weeks on these routes. The enrolment
window must run ahead of the measurement window by at least the p95
delivery time, or the last cohort will be measured before it has arrived.

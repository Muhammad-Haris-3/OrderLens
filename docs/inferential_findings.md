# OrderLens — Inferential Findings

**Milestone:** M5
**Satisfies:** SRS FR-9 (test with effect size), FR-10 (assumptions), FR-11
(controlled regression), **FR-12 (limitations statement)**, FR-13 (multiple
comparisons)
**Answers:** BQ-2 (does late delivery *cause* lower review scores, or is it
confounded?) and BQ-3 (what is one day of delay worth?)
**Date:** 2026-08-11

---

## How to read this document

Every number here is produced by `analysis/inferential.py` and appears in
[`inferential_results.md`](inferential_results.md) with its test statistic,
confidence interval and p-value. This document interprets them.

**Section 6 is the limitations statement (FR-12).** It is not an appendix. If
you read only two sections, read the answer to BQ-3 and then read that.

---

## Summary

| Question | Answer |
|---|---|
| Do late orders score lower? | Yes, and the effect is **large** — rank-biserial 0.638, p below double precision. A random on-time order outscores a random late one **81.9%** of the time |
| Does it survive controls? | Yes. Controlling for price, freight, distance, category, seller state, customer state, season and year moves the estimate by **6.9%** |
| Is it universal or segmented? | **Universal.** All 7 states and all 14 categories with enough data show a significant effect after Benjamini-Hochberg correction |
| **What is one day of delay worth?** | **Wrong question.** Crossing the promised date costs **1.71 review points**; each additional day costs **0.015**. The damage is in the threshold, not the increment |
| Is this causal? | **No — and that is stated, not hedged.** See §6 |

---

## 1. FR-9 — The primary test

**H0:** review scores are distributed identically for on-time and late
deliveries. Two-sided Mann-Whitney U, α = 0.05.

| Group | n | Mean | Median | % scoring 1 | % scoring 5 |
|---|---|---|---|---|---|
| On time | 89,443 | 4.290 | 5 | 6.6% | 62.3% |
| Late | 6,381 | 2.271 | 1 | **53.8%** | 16.5% |

U = 467,430,237, **p below double-precision floor** (< 1e-308).

A p-value that small is not the finding. With 95,824 observations, a trivial
difference would also produce an unreportably small p. **The finding is the
magnitude:**

| Effect size | Value | Magnitude |
|---|---|---|
| **Rank-biserial correlation** | **0.638** | **large** |
| Probability of superiority | 0.819 | — |
| Difference in means | 2.020 review points | uncontrolled |
| Difference in medians | 4 review points | uncontrolled |

A randomly chosen on-time order outscores a randomly chosen late order **81.9%
of the time**. More than half of late orders receive the minimum possible score.

---

## 2. FR-10 — Assumptions, and what they cost

Three assumptions were checked. One was violated in a way that changes the
*test*; one in a way that changes the *interpretation*; one in a way that changes
the *standard errors*.

### Normality — deliberately not tested

| Group | Skewness | Excess kurtosis | Distinct values |
|---|---|---|---|
| On time | −1.734 | 2.085 | 5 |
| Late | 0.729 | −1.109 | 5 |

**No Shapiro-Wilk or Kolmogorov-Smirnov p-value is reported, and that is a
decision rather than an omission.** At n ≈ 96,000 those tests reject normality
for any deviation however trivial, so their p-value carries no information about
whether normality is *approximately* satisfied — the only question that matters.
The moments above answer it directly, and on a five-point ordinal scale the
answer was never in doubt.

**Consequence:** rank-based testing, per the SRS §11 plan.

### Equal variance — violated

Levene (median-centred): W = 1,341.07, p = 1.4e-291. Mann-Whitney does not
assume equal variance so this does not invalidate it, but it rules out Welch's
t-test as a fallback and is the first sign of the problem below.

### Equal distribution shape — violated, and this one narrows the claim

| Review score | % of on-time orders | % of late orders |
|---|---|---|
| 1 | 6.6% | **53.8%** |
| 2 | 2.6% | 8.7% |
| 3 | 8.1% | 10.9% |
| 4 | 20.4% | 10.2% |
| 5 | **62.3%** | 16.5% |

Mann-Whitney tests **stochastic dominance** in general, and tests a *median
shift* only when the two distributions have the same shape. These are not
shifted versions of each other — on-time orders pile up at 5, late orders at 1.

**Consequence — the interpretation is narrowed rather than the test replaced.**
The rank test licenses *"late orders score stochastically lower"*. It does **not**
license *"late delivery costs N review points"*. That number has to come from a
model that states its functional form, which is §3.

This distinction is routinely skipped. It matters here because the 2.020-point
difference in means is the number everyone wants to quote, and the rank test is
not what justifies it.

### Independence — violated across sellers

| Clustering | Units | Max orders in one unit | % of orders in units with >1 |
|---|---|---|---|
| Customer | 92,747 | 15 | 6.1% |
| **Seller** | **2,953** | **1,787** | **99.4%** |

Customers are near-independent — only ~3% of people appear more than once (M4
FR-6). Sellers are emphatically not: one seller accounts for 1,787 orders, and
99.4% of all orders sit in a seller cluster holding more than one.

**Consequence:** every regression uses **standard errors clustered on the
seller**. Ordinary standard errors would be too small and the confidence
intervals correspondingly overconfident.

---

## 3. FR-11 — The controlled estimate

OLS on the 1–5 review score with seller-clustered standard errors. Controls:
log item value, freight ratio, log distance, item count, product category,
seller state, customer state, season, purchase year. 474 of 95,824 orders drop
for a missing control — nearly all of them the ZIP prefixes with no centroid
(M2 F-07).

### Does the association survive adjustment?

| Model | Term | Coefficient | 95% CI | R² |
|---|---|---|---|---|
| Uncontrolled | `delay_days` | −0.0340 | [−0.0359, −0.0321] | 0.072 |
| **Controlled** | `delay_days` | **−0.0363** | [−0.0382, −0.0344] | 0.115 |
| Uncontrolled | `is_late` | −2.0217 | [−2.0690, −1.9743] | 0.154 |
| **Controlled** | `is_late` | **−1.9800** | [−2.0288, −1.9312] | 0.181 |

**The controls move the estimate by 6.9%, and the delay coefficient gets slightly
*larger*, not smaller.** That is the answer to BQ-2 as far as this design can
give one: the association is not an artefact of expensive orders, distant
customers, particular categories, particular states, or the season. Something
that survives that control set is not obviously confounded — which is a different
and weaker claim than "it is causal" (§6).

### BQ-3: what is one day of delay worth?

The question presumes a per-day price. **The data says there isn't one.**

| Term | Coefficient | 95% CI | Reading |
|---|---|---|---|
| **`is_late` (the jump)** | **−1.7109** | [−1.7740, −1.6477] | Crossing the promised date at all |
| `days_late` (the slope) | −0.0152 | [−0.0193, −0.0110] | Each additional day beyond it |
| `days_early` | +0.0081 | [+0.0068, +0.0095] | Each day of buffer |

**Crossing the promised date costs 1.71 review points. Each further day costs
0.015.** It takes **113 more days of lateness** to do as much damage again as
being one day late did in the first place.

Specifications carrying only a slope (`delay_days` alone: −0.0363/day) have to
smear that discrete drop across the days that follow it, producing a per-day
price that describes neither the jump nor the ramp. M4 found this shape
descriptively; this is the same finding with controls attached.

The asymmetry with earliness is the other half. Within the same model, a day of
**buffer** is worth **+0.0081** review points against the **−1.7109** cost of a
breach: **211 days of extra padding to equal one breach prevented.**

**Implication for M7 — three purchases, three very different prices:**

| Buying... | Worth per day | Days to equal one prevented breach |
|---|---|---|
| Prevention of a breach | −1.7109 (one-off) | 1 |
| Shaving a day off an already-late order | 0.0152 | 113 |
| An extra day of schedule padding | 0.0081 | 211 |

The intervention worth paying for is the one that stops an order becoming late at
all. Recovering already-late orders and padding the promise are both worth two
orders of magnitude less.

### Robustness — a binary outcome that needs no interval assumption

OLS on a 1–5 ordinal scale assumes equal spacing between adjacent scores, which
nothing supports. Logistic regression on `is_low_score` (a 1 or 2) does not:

| Term | Odds ratio | 95% CI |
|---|---|---|
| `days_late` | **1.167** | [1.159, 1.176] |
| `days_early` | 0.954 | — |

Each day late multiplies the odds of a 1-or-2 star review by 1.167 — **+16.7%
per day, compounding**. Pseudo-R² 0.128.

Two specifications resting on different assumptions agree on sign, significance
and rough magnitude. That is what a robustness check is for.

---

## 4. FR-13 — Is the effect universal or concentrated?

Two families of tests, each corrected with Benjamini-Hochberg. Bonferroni was
rejected: it controls the probability of *any* false positive, which is the wrong
target when the question is which segments to prioritise, and at 27 tests it
costs real power for no gain in decision quality.

Kruskal-Wallis rejects homogeneity across both categories (H = 779.0) and states
(H = 581.5), which justifies looking segment by segment — but an omnibus test
never says *which* segments or *by how much*.

**Every state and every category with enough data shows a significant effect
after correction.** Not one survives as an exception.

| Customer state | Rank-biserial | Mean difference | BH-adjusted p |
|---|---|---|---|
| **RJ** | **0.713** | **2.330** | < 1e-308 |
| RS | 0.661 | 2.106 | 3.4e-112 |
| SC | 0.641 | 1.939 | 5.0e-90 |
| MG | 0.604 | 1.920 | 5.7e-150 |
| SP | 0.577 | 1.778 | < 1e-308 |
| BA | 0.568 | 1.792 | 8.1e-85 |
| ES | 0.557 | 1.749 | 1.9e-47 |

**Rio de Janeiro has the largest effect of any state** (0.713 against São Paulo's
0.577) — and M4 measured it as having the highest late rate among large states,
12.11% against SP's 4.49%. RJ is both more likely to fail *and* more punished
when it does. That combination is why it is the BQ-4 target, and M5 confirms the
second half of it independently.

Category effects span 0.588 (telephony) to 0.687 (toys) with no category exempt.
Combined with M4's finding that category late *rates* sit in a narrow 5–8% band,
the conclusion is that **lateness is a geographic and logistical problem, not a
product one.**

---

## 5. What the numbers do and do not support

**Supported:**

- Late orders receive substantially lower review scores; the effect is large by
  any conventional standard and is present in every segment examined.
- The association survives a control set covering price, freight, distance,
  category, both geographies, season and year.
- The relationship is a threshold, not a gradient. Breaching the promise is what
  costs; the amount of breach is nearly irrelevant.
- Earliness buys very little. The schedule padding measured in M4 is not
  purchasing satisfaction.

**Not supported:**

- That late delivery *causes* the drop. See §6.
- That the effect size transfers to another marketplace, another country, or
  today's version of this one.
- That preventing lateness would raise scores by 1.71 points. That is the
  observed difference under adjustment, not the expected result of an
  intervention.
- Anything about repeat purchase. M4 established there is essentially none to
  measure (2.24% of customers ever return), so BQ-3's repeat-purchase leg
  remains unanswerable.

---

## 6. FR-12 — Limitations

**This section is a deliverable, not a disclaimer.** The estimates above are the
project's central output, and the honest description of what they are worth is
part of that output rather than a caveat attached to it.

### 6.1 The design is observational. No delivery was randomly assigned to be late.

Every number in §3 is an adjusted association. Controls remove confounding by the
variables they contain and by nothing else. The correct reading of the primary
result is:

> Among orders alike in item value, freight ratio, distance, product category,
> seller state, customer state, season and year, those that breached the promised
> delivery date scored 1.71 review points lower.

That is a comparison, not an effect. Converting it into "fixing lateness would
raise scores by 1.71" requires an assumption the data cannot support — that
nothing else differs between the two groups.

### 6.2 Unmeasured confounding is likely, and its direction is knowable

The plausible unmeasured confounders mostly push the same way:

| Unmeasured factor | Why it confounds | Likely direction |
|---|---|---|
| Seller operational quality | A seller who ships late may also pack badly, describe products loosely, answer messages slowly | **Overstates** the delay effect |
| Product availability | Orders that go late are disproportionately ones the seller struggled to source | **Overstates** |
| Customer expectation | Customers who choose slow cheap shipping may be more tolerant | Understates |
| Item defect | A defective item can delay dispatch *and* independently earn a 1-star | **Overstates** |

Seller fixed effects would absorb some of this. They were not fitted, because
with 2,970 sellers and a highly skewed order distribution they would rest the
estimate on within-seller variation in a dataset where most sellers have few
orders. That is a defensible choice in either direction, and the estimate here
should be read as **an upper bound on the causal effect** rather than an unbiased
one.

### 6.3 The outcome measure is compromised by design — and it cannot be fixed

This is the most serious limitation and it is specific to this dataset.

The satisfaction survey **fires at dispatch, not at delivery** (M2 F-09). M4
measured the consequence: the share of reviews written before the parcel arrived
is 0.2% for on-time orders and **96–99% for late ones**. Whether a review predates
delivery is very nearly *determined by* whether the delivery was late.

So for most late orders, the review measures **the experience of waiting for a
parcel that has not arrived**, not the experience of receiving a late one. Those
are different things and this instrument cannot separate them.

Conditioning on review timing does not fix it — it makes matters worse, because
review timing is a **post-treatment variable**. Restricting to after-delivery
reviews keeps 99.8% of on-time orders but only **30.0% of late ones**, and moves
the two coefficients in *opposite* directions:

| Term | All reviews | After-delivery only | Change |
|---|---|---|---|
| `is_late` (jump) | −1.711 | −0.365 | **79% smaller** |
| `days_late` (slope) | −0.015 | −0.031 | **102% larger** |

The jump shrinks — people who waited long enough to receive the parcel are less
harsh about the fact of lateness. The slope steepens — among those who did wait,
each extra day matters more. Neither is the truth; each conditions on a different
selected population.

**The defensible statement:** the effect on post-delivery sentiment lies between
these specifications, and this dataset cannot locate it more precisely, because
the instrument that measures satisfaction is triggered by the process being
measured. M7's recommendation must be costed with that range stated, not with a
point estimate presented as certain.

### 6.4 Generalisability

- **One marketplace, one country, 2017–2018.** Brazilian logistics geography,
  domestic carrier structure and a specific customer base.
- **A 2.24% repeat rate.** Findings about satisfaction driving behaviour do not
  transfer to a business with genuine retention.
- **The promise is padded ~2×** (M4). The 6.77% late rate is a rate against a
  soft target; the same operation against a tighter promise would fail far more
  often, and the effect size measured here would apply to a much larger base.
- **The window excludes 2016 and the truncated tail** (M2 F-06).

### 6.5 Statistical limitations

- **Multiplicity beyond the corrected families.** BH was applied within each
  family (§4). Model specifications in §3 were not corrected across — they are
  nested variants reported together, not independent tests, but the reader should
  not treat six models as six confirmations.
- **The regression uses OLS on an ordinal outcome.** The logistic robustness
  check exists precisely because that assumption is unsupported. The coefficients
  in review points are interpretable only under equal spacing.
- **Cluster-robust standard errors assume many clusters.** 2,970 sellers is
  comfortable, but the largest holds 1,725 orders, so the effective number is
  smaller than the count suggests.
- **`delay_days` is measured in calendar days** (M2 F-01). Under the timestamp
  arithmetic originally specified, every estimate here would be ~14% smaller.

---

## 7. What M5 hands to M6 and M7

| Constraint | Applies to | Source |
|---|---|---|
| Target the **threshold**, not the increment — preventing a breach is worth ~113 days of shaving | M7 | §3 |
| Cost the recommendation with a **range**, not a point estimate: the jump lies between −0.365 and −1.711 depending on the selection assumption | M7 | §6.3 |
| Treat 1.71 as an **upper bound** on the causal effect; unmeasured confounders mostly push the same way | M7 | §6.2 |
| **RJ first** — largest effect (0.713) and highest late rate among large states | M7 | §4 |
| Lateness is geographic and logistical, **not** a product problem | M7 | §4 |
| Padding the promise is worth ~1/211 of preventing a breach, per day | M7 | §3 |
| Pre-delivery reviews stay in the training set | M6 | §6.3 |
| Model F is the specification to cost from | M7 | §3 |

---

## Document control

| Field | Value |
|---|---|
| Milestone | M5 — Inferential analysis |
| Satisfies | SRS FR-9, FR-10, FR-11, **FR-12**, FR-13 |
| Evidence | `docs/inferential_results.md`, `analysis/inferential.py` |
| Reads | `analytics_marts.mart_order_analysis` |
| Unblocks | M6 (predictive model), M7 (communication) |
| Author | Muhammad Haris Khokhar |

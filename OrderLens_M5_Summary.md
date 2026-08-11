# OrderLens — M5 (Inferential Analysis) Milestone Summary

**Date:** 2026-08-11
**Status:** Complete
**Maps to:** SRS FR-9 (test with effect size), FR-10 (assumptions), FR-11
(controlled regression), **FR-12 (limitations)**, FR-13 (multiple comparisons)
**Answers:** BQ-2 and BQ-3

---

## 1. Scope

M4 established that late orders score 2.020 review points lower. M5 asks the two
questions that decide whether that number is worth anything: does it survive
controls, and what does it actually mean?

The answer to the second turned out to be more interesting than the answer to the
first.

---

## 2. What was built

| Artefact | Delivers |
|---|---|
| `mart_order_analysis` | The modelling table — one row per delivery-eligible order with every FR-11 control, including a computed great-circle distance |
| `analysis/inferential.py` | FR-9, FR-10, FR-11, FR-13 → `docs/inferential_results.md` |
| `docs/inferential_findings.md` | The interpretation **and the FR-12 limitations statement** |

`mart_order_analysis` exists rather than a pandas join because FR-11's control
set — price, freight, category, seller state, customer state, season — spans four
dimension tables. Design Phase §8 is explicit: a missing control is a new mart
column, not an ad-hoc join in a script. A regression whose controls are assembled
in Python is a regression nobody else can reproduce.

---

## 3. BQ-2 — does the effect survive controls?

**Yes, and it barely moves.**

| Model | `delay_days` coefficient | 95% CI | R² |
|---|---|---|---|
| Uncontrolled | −0.0340 | [−0.0359, −0.0321] | 0.072 |
| **Controlled** | **−0.0363** | [−0.0382, −0.0344] | 0.115 |

Controlling for log item value, freight ratio, log distance, item count, product
category, seller state, customer state, season and purchase year moves the
estimate by **6.9%** — and moves it slightly *away* from zero, not toward it. The
association is not an artefact of expensive orders, distant customers, particular
categories or particular seasons.

Standard errors are **clustered on the seller**, because they had to be: 99.4% of
orders sit in a seller cluster holding more than one, and the largest seller
carries 1,787 orders. Ordinary standard errors would have been too small.

The rank test agrees. Mann-Whitney U on review score by late/on-time gives a
**rank-biserial correlation of 0.638 — a large effect** — with p below the
double-precision floor. A randomly chosen on-time order outscores a randomly
chosen late one **81.9% of the time**, and **53.8% of late orders receive the
minimum possible score**.

And it is universal. Every one of 7 states and 14 categories with sufficient data
shows a significant effect after Benjamini-Hochberg correction. Not one segment
is an exception.

---

## 4. BQ-3 — what is one day of delay worth?

**The question has a false premise, and that is the milestone's main finding.**

There is no per-day price. Fitting one produces a number that describes nothing:

| Term | Coefficient | 95% CI |
|---|---|---|
| **`is_late` — crossing the promised date** | **−1.7109** | [−1.7740, −1.6477] |
| `days_late` — each day beyond it | −0.0152 | [−0.0193, −0.0110] |
| `days_early` — each day of buffer | +0.0081 | [+0.0068, +0.0095] |

**Breaching the promise costs 1.71 review points. Each further day costs 0.015.**
It takes **113 additional days of lateness** to do as much damage again as being
one day late did in the first place.

M4 found this shape descriptively — the low-score rate quadruples on crossing
into lateness and then flattens. M5 confirms it with the full control set
attached, and the practical consequence is sharp:

| Buying... | Worth per day | Days to equal one prevented breach |
|---|---|---|
| Prevention of a breach | −1.7109 (one-off) | 1 |
| Shaving a day off an already-late order | 0.0152 | 113 |
| An extra day of schedule padding | 0.0081 | 211 |

**M7's recommendation should buy prevention.** Recovering late orders and padding
the promise are both worth roughly two orders of magnitude less. That is a
different recommendation from the one a single averaged slope would have
supported, and the single slope is what a conventional specification would have
produced.

**Robustness:** logistic regression on `is_low_score` — which needs no
equal-spacing assumption, unlike OLS on an ordinal scale — gives an odds ratio of
**1.167 per day late**, about **+16.7% per day, compounding**. Two specifications
resting on different assumptions agree on sign, significance and rough magnitude.

---

## 5. FR-10 — the assumption that changed the claim

Three assumptions were checked and all three were violated, each with a different
consequence.

**Normality — deliberately not tested.** At n ≈ 96,000, Shapiro-Wilk and
Kolmogorov-Smirnov reject for any deviation however trivial, so their p-value
carries no information about whether normality is *approximately* satisfied.
Skewness (−1.73 on time, +0.73 late) and a five-value ordinal scale answer the
question directly. Reporting a p-value there would have looked more rigorous and
been less so.

**Equal variance — violated** (Levene W = 1,341, p = 1.4e-291). Does not
invalidate Mann-Whitney, but rules out Welch's t-test as a fallback.

**Equal distribution shape — violated, and this one narrowed the claim.** On-time
orders pile up at 5 (62.3%); late orders pile up at 1 (53.8%). They are not
shifted versions of each other.

Mann-Whitney tests *stochastic dominance* in general, and tests a *median shift*
only under equal shapes. So the rank test licenses **"late orders score
stochastically lower"** and does **not** license **"late delivery costs N review
points"**. That number has to come from a model that states its functional form.

This distinction is routinely skipped, and it matters here precisely because the
2.020-point difference in means is the number everyone wants to quote — and the
rank test is not what justifies it.

---

## 6. FR-12 — the limitations statement

Written as a deliverable, not a disclaimer. The full statement is §6 of
[`docs/inferential_findings.md`](docs/inferential_findings.md); the load-bearing
parts:

**The design is observational.** The correct reading of the primary result is
*"among orders alike in value, freight, distance, category, both geographies,
season and year, those that breached the promise scored 1.71 points lower"*. That
is a comparison, not an effect.

**Unmeasured confounders mostly push one way.** Seller operational quality,
product availability and item defects would each inflate the apparent delay
effect. Seller fixed effects would absorb some of it and were not fitted — with
2,953 sellers and a highly skewed order distribution they would rest the estimate
on within-seller variation where most sellers have few orders. **The 1.71 should
be read as an upper bound on the causal effect.**

**The outcome measure is compromised by design, and cannot be fixed.** The survey
fires at dispatch, so 96–99% of late orders were reviewed before the parcel
arrived against 0.2% of on-time ones (M2 F-09, quantified in M4). For most late
orders the review measures *waiting for a parcel that has not arrived*, not
*receiving a late one*.

Conditioning on review timing makes it worse, not better — it is a post-treatment
variable. Restricting to after-delivery reviews keeps 99.8% of on-time orders but
only **30.0% of late ones**, and moves the two coefficients in **opposite
directions**:

| Term | All reviews | After-delivery only | Change |
|---|---|---|---|
| `is_late` (jump) | −1.711 | −0.365 | 79% smaller |
| `days_late` (slope) | −0.015 | −0.031 | 102% larger |

The jump shrinks; the slope steepens. Neither is the truth — each conditions on a
differently selected population. **The defensible statement is that the effect on
post-delivery sentiment lies between these specifications, and this dataset
cannot locate it more precisely.** M7 must cost the recommendation with that
range stated rather than a point estimate presented as certain.

---

## 7. How it was verified

| Check | Result |
|---|---|
| `python scripts/run_dbt.py build` | **209/209** — 23 models, 186 data tests |
| `pytest -q` | **37 passed** |
| `ruff check .` | clean |
| `python analysis/inferential.py` | regenerates `docs/inferential_results.md` |
| Analysis reads marts only | ✅ enforced by test |
| Every figure carries a test statistic, CI and p-value | ✅ |

---

## 8. Problems hit while building this

**`requirements.txt` was describing a project that did not exist.** Installing the
statistics stack revealed that the M0 pins had never been installed by anything —
pandas 2.2.3 against 3.0.5, statsmodels 0.14.4 against 0.14.6, and, worst of all,
ruff 0.8.4 against 0.16.2. CI was resolving one set of versions while the work
was being done against another, and a stale lint pin means CI and local can
disagree about whether the code passes. All pins realigned to the versions the
project is actually built and tested against (NFR-1).

**A specification that could not express the finding.** The first regression
carried `days_late` and `days_early` but no `is_late` indicator, so a discrete
drop at the boundary had to be smeared across the days following it — reporting
−0.060 per day and hiding the −1.71 jump entirely. M4's descriptive work is what
made the omission visible; without it the smeared slope would have looked like a
perfectly reasonable answer to BQ-3.

**A wrong direction word, caught on review.** The first draft of the selection
bound said the `days_late` coefficient "falls" under the after-delivery
restriction. It rises — by 102% — while the jump falls by 79%. The two moving in
opposite directions is the informative part, and describing it as a single
shrinkage would have inverted the argument.

**Boolean endog.** patsy reads a boolean response as a two-level categorical and
builds a two-column endog, which `logit` rejects with a message that does not
mention booleans. Cast to int at load.

---

## 9. Definition of Done

| Criterion | Status |
|---|---|
| Artefacts committed | ✅ |
| Automated tests pass | ✅ 209 dbt + 37 pytest, lint clean |
| Every figure traceable to a committed script | ✅ |
| Assumptions and limitations recorded | ✅ FR-10 §5, FR-12 §6 |
| Milestone summary written, including problems found | ✅ this document, §8 |

---

## 10. Next: M6 — Predictive model

FR-14 to FR-17. `mart_order_analysis` is already the feature table, with the
post-delivery columns marked in its schema documentation.

- Classifier for low review score using **only pre-delivery features** — the
  leakage allowlist is enforced by code, not discipline (Design Phase §8)
- Threshold chosen by **expected business cost**, not F1, with the assumed cost
  of a false positive and false negative stated
- Performance against a stated naive baseline; a model that fails to beat it gets
  reported as such (FR-16, NFR-8)
- Permutation importance, not impurity importance (FR-17)
- **Pre-delivery reviews stay in the training set** — M4 and M5 both establish
  that excluding them removes 70% of late orders and most of the low scores the
  classifier exists to predict

---

## Document control

| Field | Value |
|---|---|
| Milestone | M5 — Inferential analysis |
| SRS version | 1.0 |
| Design Phase version | 1.1 |
| Previous | `OrderLens_M4_Summary.md` |
| Next document | `OrderLens_M6_Summary.md` |

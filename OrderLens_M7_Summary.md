# OrderLens — M7 (Communication) Milestone Summary

**Date:** 2026-08-11
**Status:** Complete, with one item open — see §8
**Maps to:** SRS FR-18 (dashboard), FR-19 (decision memo), FR-20 (A/B design),
FR-21 (quantified in currency)

---

## 1. Scope

Turn six milestones of analysis into a decision someone could act on: what to do,
to which segment, at what cost, with what expected return, and with what
confidence.

M7 was expected to be assembly. It was not — the first thing it did was find that
the recommendation the earlier milestones implied was **not the one the evidence
supported**.

---

## 2. The question M5 left open, and why it changed the answer

M5 estimated that breaching the promised delivery date costs 1.71 review points,
controlling for price, freight, distance, category, both geographies, season and
year. It did **not** control for how long the customer actually waited.

Until that is settled, two very different recommendations are indistinguishable:

- If the harm comes from the **wait**, only faster delivery helps — expensive,
  operational, slow.
- If the harm comes from the **broken promise**, then a promise the business can
  keep is itself the intervention — and it is nearly free.

### The answer

Adding the actual wait to the regression moves the breach effect from **−1.711 to
−1.556** — an attenuation of only **9%**. The wait matters (−0.027 points per
day) and it is not what does the damage.

The comparison that needs no functional form is more striking still. Orders that
took the *same* time to arrive, split by whether that time broke the promise:

| Actual wait | Mean score, on time | Mean score, late | Gap |
|---|---|---|---|
| 6–9 days | 4.374 | 3.600 | **0.775** |
| 10–13 days | 4.296 | 3.305 | **0.991** |
| 14–18 days | 4.202 | 2.974 | **1.228** |
| 19–25 days | 4.054 | 2.880 | **1.173** |
| 26–40 days | 3.827 | 2.102 | **1.725** |

**A customer who waits ten days and was promised eight is markedly less satisfied
than one who waits ten days and was promised fifteen.** The wait is identical.

That finding is what makes the recommendation cheap, and it is the reason M7
produced a decision rather than a summary.

---

## 3. The obvious policy is worse than doing nothing

The natural next step — recalculate every delivery quote from route history —
was simulated out-of-sample (rules fitted on 2017, scored on 52,777 orders from
2018).

| Policy | Mean promise | Breach rate | Breaches |
|---|---|---|---|
| Current promise | 23.4 days | **8.76%** | 4,621 |
| Replace with route p90 | 20.5 days | **11.32%** | 5,976 |

**It makes things worse.** A p90 promise targets a 10% breach rate by
construction, and the platform's existing quote already achieves 8.76% — it is
*more* conservative than route history would suggest. Replacing it shortens
quotes on the best routes and buys more breaches than it prevents.

Reported prominently because it is the recommendation an analyst reaches for
first, and it is wrong. The value is entirely in the targeting, not in the
recalculation.

---

## 4. What is recommended

**Extend the quote only where the route demonstrably breaches — `max(current,
route p95)` on routes measured above an 8% breach rate. Never shorten anywhere.**

| | Now | After |
|---|---|---|
| Orders touched | — | 19.4% |
| Breach rate, all orders | 8.76% | **7.02%** |
| Rio de Janeiro | 14.63% | **8.17%** |
| Maranhão | 21.68% | **7.23%** |
| Bahia | 15.48% | **5.86%** |
| Mean quote, all orders | 23.4 days | 25.1 days |
| Mean quote, touched routes | 28.7 days | 37.1 days |

Four in five orders see no change. Annualised: **~1,400 fewer broken promises and
~560 fewer 1-and-2 star reviews.**

---

## 5. FR-21 — quantified, without inventing a number

Changing a delivery estimate costs nothing to run. The risk is that a longer
quote loses the sale — and **this dataset cannot measure that**. It contains
completed orders only: no browse, no cart, no abandonment. The conversion effect
is not merely unmeasured here, it is unmeasurable here.

So the recommendation is quantified as the trade it actually is:

| Conversion lost on touched routes | Revenue forgone per year | Implied cost per prevented bad review |
|---|---|---|
| 0.10% | R$2,609 | R$5 |
| **0.50%** | **R$13,046** | **R$23** |
| 1.00% | R$26,093 | R$46 |
| 2.00% | R$52,186 | R$93 |

The affected routes carry **R$2.6m of revenue a year**. The decision reduces to a
single question the business is better placed to answer than the analysis:
*is a prevented 1-star review worth more than R$23?*

Inventing a value for a review and presenting an ROI would have been easy and
would have been fiction. The break-even is the honest form of the same number.

The conversion factor matters and is stated: a prevented breach prevents
**0.402** of a bad review — the controlled marginal effect, far smaller than the
raw 62.4%-vs-9.3% gap, because that gap contains everything else that differs
between late and on-time orders.

---

## 6. FR-20 — the experiment

| Element | Specification |
|---|---|
| Hypothesis | A longer, achievable quote reduces 1-and-2 star reviews |
| Primary metric | Share of delivered orders scoring 1 or 2 — **18.06%** today on affected routes |
| Unit of randomisation | The order, assigned at checkout |
| Guardrail | Checkout conversion — the risk the analysis cannot measure |
| Alpha / power | 0.05 two-sided / 0.80 |

Sample size computed from the observed baseline and the policy's measured breach
reduction, not a rule of thumb:

| To detect | Orders total | Months at current volume |
|---|---|---|
| The expected effect (18.06% → 14.45%) | 3,276 | 2.5 |
| 75% of it | 5,962 | 4.6 |
| **Half of it** | **13,712** | **10.6** |

**Plan against the half-effect row.** The purpose of the test is not to confirm
the hoped-for effect but to rule out one too small to justify the conversion
risk.

Randomisation is at the order rather than the customer because the promise is set
per order at checkout, and the contamination that would justify losing that power
does not exist here — only 2.24% of customers ever return.

The write-up also flags a practical trap: these routes take weeks to deliver, so
enrolment must finish several weeks before the read-out or the last cohort is
measured before its parcels arrive.

---

## 7. What M7 recommends *against*

Both come straight from earlier milestones, and both would be tempting to a
reader who saw only the headline:

- **Do not deploy the M6 classifier.** 14% precision at the operating threshold —
  six of every seven flagged orders would have been fine.
- **Do not expect retention gains.** 2.24% of customers ever return, so the case
  cannot rest on customer lifetime value.

And the caveat that bounds the whole recommendation: **67.5% of low reviews are
on orders that arrived on time or early** (M6). This addresses roughly a third of
the problem and is sized that way throughout.

---

## 8. FR-18 — specified and data-ready, not published

The dashboard is fully specified in
[`docs/dashboard_spec.md`](docs/dashboard_spec.md): three views, every chart's
mart and fields, the colourblind-safe palette, the second encoding channel for
every colour-coded state (NFR-6), the read-only role, and three guardrails on
what the dashboard must not imply.

The data is ready. `delay_bucket` was added to `mart_order_analysis` so the
drill-down shares one definition with `mart_delay_buckets` — extracted into a
`delay_bucket()` macro rather than copied, and **verified: all eight bands match
exactly across the two grains.**

**Publishing requires a Tableau Public account and its desktop client, so the
final step cannot be automated from here.** Until that URL exists, FR-18 is
specified but not delivered, and SRS acceptance criterion §14.4 remains open.

Recorded as open rather than quietly marked complete. NFR-8 applies to the
project's own status as much as to its findings.

---

## 9. How it was verified

| Check | Result |
|---|---|
| `python scripts/run_dbt.py build` | **217/217** — 24 models, 193 data tests |
| `pytest -q` | **57 passed** |
| `ruff check .` | clean |
| `python analysis/decision.py` | regenerates `docs/decision_results.md` |
| Policy simulated out-of-sample | fitted on 2017, scored on 52,777 orders from 2018 |
| `delay_bucket` agrees across both grains | 8/8 bands exact |
| Every memo figure traceable | ✅ all from `decision_results.md` |

---

## 10. Problems hit while building this

**The recommendation nearly went out backwards.** The first plausible reading of
M5 was "pad the promise" — and the first policy tested, recalculating quotes from
route history, *increases* breaches from 8.76% to 11.32%. Simulating it
out-of-sample before writing the memo is the only reason that is a paragraph in
§3 rather than the recommendation itself.

**A singular Hessian in the marginal-effect model.** The logistic regression used
to convert breaches into bad reviews would not fit with 74 category dummies
against a binary outcome — cells with no variation. Rather than silently dropping
controls, the script falls back to a stated slimmer specification and prints
which one it used, because reporting a different model than the one documented is
worse than the singularity.

**A YAML block scalar, again.** `--vars '{min_repeat_customers: 50}'` in CI, and
the same class of mistake would have hit the memo tables. Caught by the workflow
test added in the previous commit, which is the first time a test written in this
project caught a regression rather than documenting one.

---

## 11. Definition of Done

| Criterion | Status |
|---|---|
| Artefacts committed | ✅ |
| Automated tests pass | ✅ 217 dbt + 57 pytest, lint clean |
| Every figure traceable to a committed query or script | ✅ |
| Assumptions and limitations recorded | ✅ §5, §7, and the memo's confidence section |
| Milestone summary written, including problems found | ✅ this document, §10 |

---

## 12. Acceptance criteria (SRS §14)

| # | Criterion | Status |
|---|---|---|
| 1 | A clean clone rebuilds the warehouse via documented commands | ✅ |
| 2 | All dbt and Python tests pass in CI | ✅ since the NFR-3 work |
| 3 | Every *Must* FR delivered and traceable | ⬜ **20 of 21** — FR-18 pending publication |
| 4 | The dashboard is publicly reachable by URL | ⬜ **open** — needs a Tableau Public account |
| 5 | The memo states a recommendation, its cost, its return and its confidence, and is intelligible to a non-technical reader | ✅ |
| 6 | The limitations statement is present and honest | ✅ |

**Four of six closed, one closed except for a manual publish step, and one open
on it.** The analysis is complete; what remains is an account login.

---

## Document control

| Field | Value |
|---|---|
| Milestone | M7 — Communication |
| SRS version | 1.0 |
| Design Phase version | 1.1 |
| Previous | `OrderLens_M6_Summary.md` |
| Deliverables | `docs/decision_memo.md`, `docs/dashboard_spec.md`, `docs/decision_results.md` |

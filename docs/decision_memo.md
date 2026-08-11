# Decision memo — the delivery promise is costing us more than the delivery

**To:** Marketplace Operations
**From:** Muhammad Haris Khokhar
**Date:** 2026-08-11
**Decision requested:** approve a three-month experiment on delivery promises for
high-risk routes

---

## The finding

Customers do not punish us for slow delivery. They punish us for **broken
promises**.

Take orders that all took the same time to arrive — say ten to thirteen days.
Those that arrived within the date we quoted average **4.30 out of 5**. Those
that missed the quoted date average **3.31**. Same wait. Nearly a full point of
difference.

That pattern holds across every delivery speed we looked at, and it survives
adjusting for price, distance, product category, seller, region and season.
Missing the promised date costs about **1.56 review points**. How *badly* we miss
it barely matters — being a day late does nearly all the damage, and the next
hundred days add about as much again.

We are not slow. Across the platform we beat our own estimate by about twelve
days on the typical order. The problem is that on some routes our estimate is
wrong often enough to matter: in Rio de Janeiro we miss the date on **14.6%** of
orders, against **6.1%** in São Paulo. Not because Rio is slower on average, but
because Rio is *less predictable* — half of Rio orders arrive within 12 days, but
one in a hundred takes 57.

---

## What we recommend

**Extend the quoted delivery date on the routes that demonstrably miss it, and
nowhere else.**

Concretely: where a route has missed its date on more than 8% of orders, quote
the date we actually hit 95% of the time instead. Never shorten a quote anywhere.

This touches **19% of orders**. Four in five customers see no change at all. On
the routes that do change, the quote moves from about 29 days to 37.

| | Now | After |
|---|---|---|
| Orders missing their promised date | 8.8% | **7.0%** |
| Rio de Janeiro | 14.6% | **8.2%** |
| Maranhão | 21.7% | **7.2%** |
| Bahia | 15.5% | **5.9%** |
| Average quote, all orders | 23.4 days | 25.1 days |

Tested properly: the rule was built on 2017 data and scored on 52,777 orders from
2018 that it had never seen.

**Expected impact: about 1,400 fewer broken promises and roughly 560 fewer 1-and-2
star reviews per year.**

We also checked the obvious version of this idea — recalculating every quote from
route history — and it is **worse than what we do today**. It shortens quotes on
our best routes and buys more broken promises than it prevents. The value is
entirely in the targeting.

---

## What it costs, and what could go wrong

Changing a delivery estimate costs nothing to run. It is a number on a checkout
page.

The risk is that a longer quoted date loses the sale. **We cannot measure that
from our order data** — we only see orders customers actually placed, not the ones
they abandoned. Nobody should pretend otherwise, so here is the trade in plain
terms:

| If we lose this much conversion on the affected routes | We forgo this much revenue a year | Which means each prevented bad review cost us |
|---|---|---|
| 0.10% | R$2,600 | R$5 |
| 0.50% | R$13,000 | **R$23** |
| 1.00% | R$26,100 | R$46 |
| 2.00% | R$52,200 | R$93 |

The affected routes carry about **R$2.6m of revenue a year**. So the question for
the business is simply: *is a prevented 1-star review worth more than R$23?* If
yes, this is worth doing at any plausible conversion cost. If a 1-star review is
worth less than about R$5 to us, it is not worth doing at all.

That is a judgement about our brand and our acquisition costs, and Operations and
Marketing are far better placed to make it than this analysis is.

---

## How confident we are

**Moderately, and the direction is safer than the size.**

- The relationship is large, highly significant, and present in **every** state
  and **every** product category we tested.
- But this is historical data, not an experiment. Nobody randomly assigned
  deliveries to be late. Sellers who miss dates may also pack badly and describe
  products loosely, and we cannot separate those. **Treat 1.56 points as a
  ceiling, not a forecast.**
- Our satisfaction survey is sent when an order ships, not when it arrives, so
  for most late orders the customer was reviewing the wait, not the delivery.
  This is a real limitation of our measurement and no analysis choice fixes it.

**Most importantly: fixing delivery does not fix satisfaction.** Only **a third**
of our 1-and-2 star reviews are on orders that arrived late at all. The other
two-thirds are on orders that arrived on time or early — driven by product
quality, description accuracy, seller communication, or things we do not currently
measure. This recommendation addresses a third of the problem. It should be sized
that way.

---

## Two things we recommend *against*

**Do not build a system to predict which orders will go wrong.** We tried. Using
only what is known when an order is placed, the best model flags orders where six
of every seven are false alarms. Even a model that is *told* whether the order
arrived late cannot identify most bad reviews. The signal is not there at
purchase time.

**Do not expect this to improve retention.** Only 2.2% of our customers ever come
back for a second shopping trip. Whatever a bad delivery costs us, it is not
repeat business, because there is almost no repeat business to lose. Any case for
this work has to rest on brand and acquisition, not on customer lifetime value.

---

## The decision

**Run a three-month A/B test on the affected routes before rolling out.**

| | |
|---|---|
| **Hypothesis** | A longer, achievable quote reduces 1-and-2 star reviews |
| **Randomise** | By order, at checkout, 50/50, affected routes only |
| **Primary metric** | Share of orders scoring 1 or 2 (today: 18.1% on these routes) |
| **Guardrail** | Checkout conversion — the risk we cannot otherwise measure |
| **Size** | 3,300 orders to detect the expected effect; **13,700 to rule out half of it** |
| **Duration** | About 2.5 months for the first, 11 for the second, at current volume |

Plan for the larger number. The point of the test is not to confirm the effect we
hope for — it is to be able to rule out an effect too small to be worth the
conversion risk.

One practical note: these routes take weeks to deliver, so enrolment must finish
several weeks before we read the results, or the last customers will be counted
before their parcels arrive.

---

*Every figure traceable to a committed query. Method and limitations:
[decision_results.md](decision_results.md), [inferential_findings.md](inferential_findings.md),
[predictive_findings.md](predictive_findings.md).*

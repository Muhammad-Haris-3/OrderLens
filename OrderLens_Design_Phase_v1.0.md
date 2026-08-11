# OrderLens — Design Phase Document v1.0

**Companion to:** `OrderLens_SRS_v1.0.md`
**Date:** 2026-08-11
**Status:** Approved for M3
**Purpose:** Translate the SRS requirements into an implementable warehouse
design — every model, its grain, its tests, and why it is shaped that way.

This document is written to be executable: M3 should be typing, not deciding.

---

## 1. Layer architecture

Three layers, each with exactly one job.

| Layer | Schema | Materialisation | Job |
|---|---|---|---|
| **Raw** | `raw` | Tables (loaded by Python) | Source fidelity. Untyped text, no constraints. |
| **Staging** | `analytics_staging` | Views | Type, rename, deduplicate. 1:1 with sources. |
| **Marts** | `analytics_marts` | Tables | Dimensional model the analysis and dashboard query. |

### 1.1 Why staging is views and marts are tables

Staging is a thin pass over raw — casting and renaming. Materialising it would
double storage for no query-time gain, because nothing queries staging directly
except marts.

Marts are queried repeatedly: by Tableau on every dashboard interaction, and by
the M5/M6 analysis scripts on every run. Recomputing the joins each time on
free-tier Postgres is the difference between responsive and unusable (NFR-4).

### 1.2 The one rule for staging

**Staging models never join.** One staging model reads exactly one source. Joins
belong in marts.

This is what keeps lineage readable — when a mart is wrong, the fault is in the
mart or in one identifiable staging model, never in an invisible chain of
upstream joins.

The single exception is `stg_geolocation`, which aggregates (not joins) to solve
risk R-2 at the earliest possible point. See §3.9.

---

## 2. Naming conventions

| Pattern | Meaning |
|---|---|
| `stg_<source>` | Staging model, 1:1 with a raw table |
| `dim_<entity>` | Dimension — a thing (customer, product, seller, date) |
| `fct_<process>` | Fact — an event (order, order item, payment) |
| `<entity>_id` | Natural key carried from source |
| `is_<condition>` | Boolean |
| `<measure>_days` / `_value` / `_total` | Unit is explicit in the name |

Natural keys are used throughout rather than generated surrogate keys. The source
keys are already opaque 32-character hashes, globally unique and stable — adding
surrogates would be ceremony that makes debugging harder, not easier.

---

## 3. Staging models

All nine are views in `analytics_staging`. Casting happens here, where a failure
is visible and attributable (see M0 §3.1).

### 3.1 `stg_orders`
**Grain:** one order.

| Column | Transformation |
|---|---|
| `order_id`, `customer_id` | passthrough |
| `order_status` | passthrough, lowercased |
| `purchased_at` | `order_purchase_timestamp::timestamp` |
| `approved_at` | `order_approved_at::timestamp` |
| `handed_to_carrier_at` | `order_delivered_carrier_date::timestamp` |
| `delivered_at` | `order_delivered_customer_date::timestamp` |
| `estimated_delivery_at` | `order_estimated_delivery_date::timestamp` |

Renamed from source: the `_date` suffix on columns that are actually timestamps
is misleading and has caused real bugs elsewhere. `_at` marks a timestamp.

**Tests:** `order_id` unique + not_null; `order_status` accepted_values.

### 3.2 `stg_order_items`
**Grain:** (`order_id`, `order_item_id`).

Casts `price` and `freight_value` to `numeric(12,2)`, `order_item_id` to int.

**Tests:** compound uniqueness on the grain; `price` not_null; relationship to
`stg_orders`.

### 3.3 `stg_order_payments`
**Grain:** (`order_id`, `payment_sequential`).

Casts `payment_value` to `numeric(12,2)`, installments/sequential to int.

**Tests:** compound uniqueness; `payment_type` accepted_values.

### 3.4 `stg_order_reviews`
**Grain:** one **`order_id`** — settled by M2 finding F-02 (decision D-1).

Casts `review_score` to int, timestamps to `timestamp`.

M2 measured both candidate keys failing: 814 excess rows on `review_id`, 551 on
`order_id`. The two failures are different things. A `review_id` appearing
against several orders is one survey covering a basket — 789 such cases, all
spanning genuinely different orders and all agreeing on the score. An `order_id`
appearing twice is the real grain violation: 547 orders, **202 of them carrying
reviews that disagree**.

```sql
select distinct on (order_id) ...
order by order_id, review_answer_timestamp desc, review_id
```

Latest, not earliest: a second response to the same order is the settled
opinion. The `review_id` tie-break exists so two builds of the same data cannot
disagree.

**Tests:** `review_score` accepted_values 1–5; `order_id` unique + not_null
*after* dedup. **`review_id` is deliberately not tested for uniqueness** — it is
genuinely not unique and never will be, and a permanently failing test is one
everybody learns to ignore.

`review_count` is carried through to `fct_orders` so the 547 collapsed orders
stay visible.

### 3.5 `stg_customers`
**Grain:** one `customer_id` (per-order key).

Carries `customer_unique_id` through unchanged. **This model does not
deduplicate to the person** — that is `dim_customers`' job (§4.1).

**Tests:** `customer_id` unique + not_null; `customer_unique_id` not_null.

### 3.6 `stg_sellers` / 3.7 `stg_products`

`stg_products` corrects the source misspellings at the boundary:
`product_name_lenght` → `product_name_length`, `product_description_lenght` →
`product_description_length`. Raw preserves the typo; nothing downstream repeats it.

Also derives `product_volume_cm3 = length × height × width`.

**Tests:** `product_id` / `seller_id` unique + not_null.

### 3.8 `stg_product_categories`
**Grain:** one Portuguese category name.

Straight passthrough of the 71-row translation table. The incomplete-translation
problem found in M1 §5 is handled in `dim_products`, not here — staging reflects
the source as it is.

### 3.9 `stg_geolocation` — solves risk R-2
**Grain:** one ZIP prefix. **This is the model that prevents fan-out.**

```sql
select
    geolocation_zip_code_prefix::text            as zip_prefix,
    avg(geolocation_lat::numeric)                as latitude,
    avg(geolocation_lng::numeric)                as longitude,
    mode() within group (order by geolocation_city)  as city,
    mode() within group (order by geolocation_state) as state,
    count(*)                                     as source_point_count
from {{ source('raw', 'geolocation') }}
group by 1
```

Raw geolocation is 1,000,163 rows across 19,015 prefixes — a **52.6× fan-out**
measured in M1. Joining it un-aggregated to any fact table would multiply rows
by ~50 and inflate every revenue figure.

Centroid by mean lat/lng; city and state by modal value, because a prefix can
carry inconsistent spellings across its rows. M2 measured how often: **8,556 of
19,015 prefixes (45%) carry more than one spelling of their own city name**, and
8 span more than one state (A-20). Modal, not `min()` or an arbitrary pick.
`source_point_count` is retained so a thinly-evidenced centroid can be spotted
rather than trusted blindly.

**Added by M2 (finding F-13):** the aggregation filters out-of-bounds
coordinates **before** averaging — 42 points fall outside Brazil's bounding box
(lat −34 to +6, lng −74 to −33), affecting 21 prefixes. This is the only place
in the pipeline where a row is discarded rather than flagged: an impossible
coordinate contributes nothing recoverable to a centroid, but one point in the
wrong hemisphere drags a whole prefix off the map. The discarded count is
asserted by a test so it cannot grow unnoticed.

**Coverage, not just fan-out (F-07):** 157 customer ZIP prefixes and 7 seller
prefixes have no geolocation row at all. Geography joins are therefore
`LEFT JOIN` — an inner join removes 278 customers and 7 sellers from the fact
table and every geographic total under-reports with no test noticing.

**Tests:** `zip_prefix` unique + not_null — the assertion that R-2 is dead.

---

## 4. Dimension models

### 4.1 `dim_customers` — solves risk R-1
**Grain:** one **`customer_unique_id`** — one row per *person*, not per order.

| Column | Definition |
|---|---|
| `customer_unique_id` | PK |
| `zip_prefix`, `city`, `state` | From most recent order |
| `first_order_at` / `last_order_at` | min / max `purchased_at` |
| `cohort_month` | `date_trunc('month', first_order_at)` |
| `total_orders` | count distinct `order_id` |
| `is_repeat_customer` | `total_orders > 1` |

M1 measured 99,441 `customer_id` values collapsing to 96,096 people. Keying this
model on `customer_id` would produce a 100% first-time customer base — a wrong
answer that looks entirely reasonable.

**Tests:** `customer_unique_id` unique + not_null; **plus a bespoke test
asserting `count(*) where is_repeat_customer` > 0.** A schema test cannot catch
the R-1 mistake, because keying on the wrong column still produces a perfectly
unique key. Only asserting that repeat customers *exist* catches it.

### 4.2 `dim_products` — handles the M1 translation gap
**Grain:** one `product_id`.

```sql
left join {{ ref('stg_product_categories') }} ...
coalesce(t.product_category_name_english,   -- 32,328 products
         p.product_category_name,           -- 13 products, Portuguese retained
         'uncategorised') as category       -- 610 products
```

**`LEFT JOIN`, never `INNER JOIN`.** M1 §5 found 623 of 32,951 products with no
English translation — 610 with a null category and 13 whose Portuguese category
is genuinely missing from the translation file (`pc_gamer`,
`portateis_cozinha_e_preparadores_de_alimentos`). M2 priced it (F-05): an inner
join would silently delete **R$185,049.76 of item revenue across 1,473 orders**,
and the resulting category report would look perfectly clean because every
remaining row would be correct.

The three-step `coalesce` degrades gracefully: English if known, Portuguese if
untranslated, `'uncategorised'` if absent.

**Amended by M2 (D-3):** the label for the absent case is `'uncategorised'`
rather than `'unknown'` — it describes the product's state rather than the
analyst's. And the `category_is_translated` boolean becomes a
**`category_source`** enum: `translated` / `portuguese_fallback` / `missing`. A
boolean collapses two different situations into one. `pc_gamer` has an accurate,
usable Portuguese name and a gap in the lookup table; a product with no category
at all is missing data. The analysis needs to distinguish them to state honestly
what share of category revenue is attributable.

**Tests:** `product_id` unique + not_null; `category` not_null (guaranteed by the
coalesce — the test proves the coalesce works).

### 4.3 `dim_sellers`
**Grain:** one `seller_id`. Joined to `stg_geolocation` for a centroid.

### 4.4 `dim_dates`
**Grain:** one calendar date, generated across the dataset's observed range.

Carries year, quarter, month, week, day-of-week, `is_weekend`, and month/day
names. Needed so the dashboard can show gapless time series — a date spine built
from observed order dates alone would silently skip days with no orders, which is
itself a signal worth seeing.

M2 found the concrete case (F-06): **November 2016 contains no orders at all**.
A spine built from observed dates would join October 2016 directly to December
2016 and draw a trend line through a month that never existed, with no reader
able to tell. The generated spine makes the gap a visible zero.

### 4.5 `dim_geography`
**Grain:** one ZIP prefix. Thin pass over `stg_geolocation` plus a
region grouping for the five Brazilian macro-regions.

---

## 5. Fact models

### 5.1 `fct_orders` — the central model
**Grain:** one order. This is the table the headline analysis runs against.

**Delivery measures** (null unless the order is delivery-eligible — see below):

| Measure | Definition |
|---|---|
| `delivery_days` | `delivered_at − purchased_at` |
| `estimated_days` | `estimated_delivery_at − purchased_at` |
| **`delay_days`** | **`delivered_at::date − estimated_delivery_at::date`** — **signed whole days**; the project's central independent variable |
| `is_late` | `delay_days > 0` |
| `seller_handover_days` | `handed_to_carrier_at − purchased_at`, **null if negative** |
| `carrier_transit_days` | `delivered_at − handed_to_carrier_at`, **null if negative** |

Splitting the wait into **seller handover** and **carrier transit** is what makes
the eventual recommendation actionable. "Deliveries are late" is not something a
business can act on; "sellers in state X take four days to hand over" is.

#### Amended by M2 — `delay_days` is measured in calendar days (F-01)

`estimated_delivery_at` is a **date stored at midnight** — all 96,470 delivered
orders. `delivered_at` is a real timestamp, and **no delivery in the dataset
lands at exactly midnight**. Subtracting the two as timestamps therefore calls
an order late if it arrived at any hour of the day it was promised.

That is not a rounding quibble. It misfiles **1,292 orders** — orders whose mean
review score is 4.03, i.e. that behave like on-time deliveries — into the late
group, dragging the late-group mean from 2.27 to 2.57 and **understating the
delay-to-satisfaction gap by 14.4%**, the single estimate this project exists to
produce.

The promise was a *day*. `delivery_days` and the two split measures keep full
timestamp precision: they compare a measurement to another measurement, so no
unit mismatch arises.

#### Delivery eligibility (F-03, decision D-2)

```sql
is_delivery_eligible = order_status = 'delivered' and delivered_at is not null
```

Both conditions, materialised as a column so every consumer applies the same
rule instead of re-deriving it and drifting. Status alone admits 8 orders with
no delivery timestamp; the timestamp alone admits 6 orders delivered and then
cancelled.

**`fct_orders` keeps all 99,441 orders.** Delivery measures are null outside the
eligible 96,470. A fact table that has already dropped the ineligible rows
cannot answer "how many orders never arrived", which is BQ-1.

**Value measures**, rolled up from `stg_order_items`:

| Measure | Definition |
|---|---|
| `item_count` | count of items |
| `order_item_total` | `sum(price)` |
| `order_freight_total` | `sum(freight_value)` |
| `order_value` | `order_item_total + order_freight_total` |
| `freight_ratio` | `order_freight_total / nullif(order_item_total, 0)` |

**Value comes from items, not payments** (data dictionary Part 2). Payments
include installment interest and split across instruments — summing them inflates
revenue and double-counts splits. M2 evidenced this rather than assuming it
(F-10): payments exceed item totals on 264 orders and fall short on 39, a 6.8:1
asymmetry that is the signature of interest. `nullif` guards a division by zero
that would otherwise abort the whole model build.

**The items roll-up is a `LEFT JOIN` (F-04, decision D-4).** M2 found **775
orders with no items** — 603 `unavailable`, 164 `canceled`. They are a real
business state, not corruption: every one has a payment record and 756 have a
customer review. An inner join would delete them, and with them the entire
population of orders the platform failed to fulfil — which is one of the
operational failures the project exists to quantify.

`order_value` is **NULL for these orders, not 0**. Zero claims the order was
worth nothing; null says it was never itemised. A zero would silently drag every
average-order-value figure down.

**Satisfaction:** `review_score`, `is_low_score` (`review_score <= 2`).

**Foreign keys:** `customer_unique_id` (**not** `customer_id`), `dim_dates`.

**Tests:** `order_id` unique + not_null; relationships to `dim_customers` and
`dim_dates`; `delay_days` null whenever status ≠ delivered; **row count equals
`stg_orders` row count** — the fan-out assertion.

### 5.2 `fct_order_items`
**Grain:** (`order_id`, `order_item_id`). Item-level detail for
product/seller analysis. Relationships to `dim_products`, `dim_sellers`,
`fct_orders`.

### 5.3 `fct_payments`
**Grain:** (`order_id`, `payment_sequential`). Kept separate precisely
*because* summing it into `fct_orders` would double-count. Payment-method
analysis reads this; revenue analysis does not.

---

## 6. Lineage

```
raw.orders            → stg_orders           ─┐
raw.order_items       → stg_order_items      ─┼→ fct_orders → analysis / dashboard
raw.order_reviews     → stg_order_reviews    ─┘
raw.customers         → stg_customers        → dim_customers ↗
raw.products          → stg_products         ─┐
raw.product_category… → stg_product_categories┴→ dim_products → fct_order_items
raw.sellers           → stg_sellers          ─┐
raw.geolocation       → stg_geolocation      ─┴→ dim_sellers / dim_geography
                        (aggregated — R-2)
```

---

## 7. Test strategy

Four kinds, in increasing order of what they actually protect:

| Kind | Example | Catches |
|---|---|---|
| **Schema** | `unique`, `not_null` | Structural breakage |
| **Referential** | `relationships` | Orphans and broken joins |
| **Domain** | `accepted_values` | Unexpected category values |
| **Bespoke** | repeat customers exist; row counts preserved across joins | **Logic that is structurally valid but semantically wrong** |

The fourth kind is the one that matters. Both risks in this project — R-1 and
R-2 — produce output that passes every schema test. Keying on `customer_id`
yields a perfectly unique key; a fanned-out geolocation join yields perfectly
valid rows. Only an assertion about *meaning* catches them:

- `dim_customers`: assert repeat customers exist (R-1)
- `fct_orders`: assert row count equals `stg_orders` (R-2 and any other fan-out)
- `stg_geolocation`: assert `zip_prefix` is unique (R-2 at source)

**A test suite that only checks structure gives false confidence.** These three
are the ones worth writing.

### 7.1 Bespoke tests added by M2

The audit found three more failures of the same kind — structurally valid,
semantically wrong — and each earns an assertion about meaning:

| Test | Asserts | Catches |
|---|---|---|
| `fct_orders`: `delay_days` is a whole number of days | The calendar-day rule was applied | Silent reversion to timestamp arithmetic, which shifts the headline late rate from 6.77% to 8.11% (F-01) |
| `fct_orders`: `seller_handover_days` and `carrier_transit_days` are null-or-non-negative | Backwards timestamps became null, not negative | A negative duration averaging into a segment mean (F-08) |
| `stg_geolocation`: every centroid falls inside Brazil's bounding box | The coordinate filter ran | One out-of-hemisphere point dragging a ZIP prefix off the map (F-13) |

The first is the important one. Nothing about the timestamp form of
`delay_days` fails — it produces a perfectly valid signed number for every
delivered order. Only an assertion that the value is a whole day catches a
reversion, and without it the regression in M5 would simply come back 14%
smaller with nothing to say why.

---

## 8. Analysis layer (M4–M6)

Python reads **marts only** — never `raw`, never `staging`. If an analysis needs
a column that doesn't exist in a mart, the fix is a new mart column, not a
bespoke query in a script. This is what keeps NFR-2 (traceability) true: one
definition of `delay_days`, in one place.

| Milestone | Reads | Produces |
|---|---|---|
| M4 Descriptive | `fct_orders`, `dim_customers` | Delivery profile, cohorts, RFM, revenue concentration |
| M5 Inferential | `fct_orders` + dims | Effect sizes, controlled regression |
| M6 Predictive | `fct_orders` + dims | Cost-optimised classifier |

**M6 leakage rule:** the classifier may use only features known **before**
delivery completes — purchase timestamp, estimated delivery date, price, freight,
category, seller, distance. It may **not** use `delivered_at`, `delay_days`,
`is_late`, or anything derived from them. Training on `is_late` to predict a low
review score would produce a spectacular, useless model. This constraint is
enforced by an explicit feature allowlist, not by discipline.

### 8.1 Constraints added by M2

| Constraint | Applies to | Finding |
|---|---|---|
| ~~Reviews answered before the parcel arrived are excluded from M6 training~~ — **superseded by M4.** They are a post-treatment variable (0.2% of on-time orders, 96–99% of late ones), so excluding them selects a subset rather than removing bias. Headline uses all reviews; the after-delivery figure is a **stated selection bound** | M5, M6 | F-09, M4 |
| Seller-level ranking is built from `fct_order_items`, **single-seller orders only**; the 1,278 multi-seller orders are reported as an explicit exclusion rather than attributed to every seller involved | M4 (BQ-4) | F-12 |
| Hypothesis tests on review score are **rank-based**; scores are bimodal (57.8% five-star, 11.5% one-star), not central | M5 | F-11 |
| Trend and cohort charts cover **2017-01 to 2018-08**; the window is stated on the chart, not footnoted | M4 | F-06 |
| Distance features are **null** for the 157 uncovered customer ZIP prefixes; the model must handle null rather than silently drop | M6 | F-07 |

F-09 is the one that constrains interpretation rather than code. The
satisfaction survey is triggered at dispatch, so 4,795 reviews were written
before the customer had the parcel — they cannot be a response to the delivery
experience. That is a limitation of the measurement instrument, not something
cleaning fixes, and FR-12's limitations statement must say so.

---

## 9. Dashboard design (M7)

Tableau Public connects **directly to `analytics_marts`** — no extracts, no
hand-maintained CSVs, so the dashboard cannot drift from the warehouse.

Three views:

1. **Operations** — on-time rate over time, delay distribution, handover vs transit split
2. **Impact** — review score by delay bucket, revenue at risk by segment
3. **Drill-down** — category, state, seller, filterable

Per NFR-6: colourblind-safe palette, and no meaning encoded by colour alone —
every colour-coded state also carries a label or shape.

---

## 10. Decisions deferred to M2 — all resolved

Honest sequencing — these needed the audit's findings, and guessing would have
been inventing requirements. M2 answered all five; full reasoning and evidence in
[`docs/data_quality_audit.md`](docs/data_quality_audit.md).

| # | Question | Resolution |
|---|---|---|
| D-1 | How duplicated is `review_id`, and what is the dedup rule? | ✅ Grain is `order_id`, not `review_id`. Keep latest by `review_answer_timestamp`, tie-break `review_id`. `review_id` never tested for uniqueness. §3.4 |
| D-2 | Which order statuses are eligible for delivery analysis? | ✅ `order_status = 'delivered' AND delivered_at IS NOT NULL` — 96,470 orders, materialised as `is_delivery_eligible`. All 99,441 retained. §5.1 |
| D-3 | How are the 623 unmapped-category products labelled in reporting? | ✅ `'uncategorised'` for the absent case, Portuguese retained for the untranslated case, `category_source` enum records which. §4.2 |
| D-4 | Are there orders with no items, or reviews with no order? | ✅ 775 item-less orders (business state — `LEFT JOIN`, null order value). Zero orphans in any child-to-parent direction, so reverse relationship tests are `error` severity. §5.1 |
| D-5 | What is the analysis anchor date? | ✅ **2018-08-31**; trend and cohort window 2017-01 to 2018-08. Data dictionary, *Analysis date* |

### 10.1 What M2 changed that was not on this list

The audit was expected to answer open questions. It also **overturned two
settled ones**, which is the stronger argument for having sequenced it before
M3 rather than after:

| Change | Section | Finding |
|---|---|---|
| `delay_days` and `is_late` computed on calendar days, not timestamps — the timestamp form understated the project's central estimate by 14.4% | §5.1 | F-01 |
| `stg_geolocation` filters coordinates outside Brazil before averaging | §3.9 | F-13 |
| `seller_handover_days` / `carrier_transit_days` are null rather than negative | §5.1 | F-08 |
| Geography joins are `LEFT JOIN` — 157 customer ZIP prefixes have no coordinates | §3.9 | F-07 |
| Reviews answered before delivery are flagged, excluded from M6 training, and reported as an M5 sensitivity | §8 | F-09 |
| Seller-level ranking uses single-seller orders only | §8 | F-12 |

---

## 11. Document control

| Field | Value |
|---|---|
| Version | 1.1 — amended by the M2 data-quality audit |
| Status | Approved for M3 — no open decisions |
| Depends on | `OrderLens_SRS_v1.0.md`, `docs/data_dictionary.md`, `docs/data_quality_audit.md` |
| Blocked by | Nothing. D-1 to D-5 resolved; see §10 |

### Change log

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-08-11 | Initial design, five decisions deferred to M2 |
| 1.1 | 2026-08-11 | M2 audit applied: D-1 to D-5 resolved (§10); `delay_days`/`is_late` moved to calendar days (§5.1, F-01); `stg_order_reviews` grain settled (§3.4); `dim_products` labelling settled (§4.2); geolocation coordinate filter and LEFT JOIN coverage rule added (§3.9); `dim_dates` gap noted (§4.4); three bespoke tests added (§7.1); M4–M6 constraints added (§8.1) |

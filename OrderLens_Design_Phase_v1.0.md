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
**Grain:** one review. **Deduplication rule pending M2** — `review_id` is known
not to be reliably unique, and M2 quantifies it before a rule is chosen.

Casts `review_score` to int, timestamps to `timestamp`.

**Tests:** `review_score` accepted_values 1–5; grain test added once M2 settles
the dedup rule.

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
carry inconsistent spellings across its rows. `source_point_count` is retained so
a thinly-evidenced centroid can be spotted rather than trusted blindly.

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
coalesce(t.product_category_name_english,
         p.product_category_name,
         'unknown') as category
```

**`LEFT JOIN`, never `INNER JOIN`.** M1 §5 found 623 of 32,951 products with no
English translation — 610 with a null category and 13 whose Portuguese category
is genuinely missing from the translation file (`pc_gamer`,
`portateis_cozinha_e_preparadores_de_alimentos`). An inner join would silently
drop those products *and every order containing them*, biasing category revenue
in a way that looks perfectly clean.

The three-step `coalesce` degrades gracefully: English if known, Portuguese if
untranslated, `'unknown'` if absent. A `category_is_translated` boolean is
carried so the analysis can quantify the gap rather than ignore it.

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

### 4.5 `dim_geography`
**Grain:** one ZIP prefix. Thin pass over `stg_geolocation` plus a
region grouping for the five Brazilian macro-regions.

---

## 5. Fact models

### 5.1 `fct_orders` — the central model
**Grain:** one order. This is the table the headline analysis runs against.

**Delivery measures** (null unless `order_status = 'delivered'`):

| Measure | Definition |
|---|---|
| `delivery_days` | `delivered_at − purchased_at` |
| `estimated_days` | `estimated_delivery_at − purchased_at` |
| **`delay_days`** | `delivered_at − estimated_delivery_at` — **signed**; the project's central independent variable |
| `is_late` | `delay_days > 0` |
| `seller_handover_days` | `handed_to_carrier_at − purchased_at` |
| `carrier_transit_days` | `delivered_at − handed_to_carrier_at` |

Splitting the wait into **seller handover** and **carrier transit** is what makes
the eventual recommendation actionable. "Deliveries are late" is not something a
business can act on; "sellers in state X take four days to hand over" is.

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
revenue and double-counts splits. `nullif` guards a division by zero that would
otherwise abort the whole model build.

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

## 10. Decisions deferred to M2

Honest sequencing — these need the audit's findings, and guessing now would be
inventing requirements:

| # | Question | Blocks |
|---|---|---|
| D-1 | How duplicated is `review_id`, and what is the dedup rule? | `stg_order_reviews` grain test |
| D-2 | Which order statuses are eligible for delivery analysis? | `fct_orders` delivery filter |
| D-3 | How are the 623 unmapped-category products labelled in reporting? | `dim_products` (fallback built; label wording open) |
| D-4 | Are there orders with no items, or reviews with no order? | Relationship test severity |
| D-5 | What is the analysis anchor date? | RFM recency |

---

## 11. Document control

| Field | Value |
|---|---|
| Version | 1.0 |
| Status | Approved for M3 |
| Depends on | `OrderLens_SRS_v1.0.md`, `docs/data_dictionary.md` |
| Blocked by | M2 for decisions D-1 to D-5 |

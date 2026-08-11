# OrderLens — Data Dictionary

Two parts: the **source fields** as they arrive, and the **derived measures**
this project computes from them. The second part matters more — a derived metric
without a written formula is where analyses quietly disagree with each other.

---

## Part 1 — Source fields

### orders (99,441)

| Field | Type (after staging cast) | Notes |
|---|---|---|
| `order_id` | text PK | |
| `customer_id` | text FK → customers | **Per-order key, not a person.** See R-1. |
| `order_status` | text | delivered / shipped / canceled / unavailable / invoiced / processing / created / approved |
| `order_purchase_timestamp` | timestamp | When the customer ordered |
| `order_approved_at` | timestamp | Payment approved; null if never approved |
| `order_delivered_carrier_date` | timestamp | Handed to logistics partner |
| `order_delivered_customer_date` | timestamp | **Arrived with customer.** Null unless delivered |
| `order_estimated_delivery_date` | timestamp | Promise shown to customer at purchase |

### order_items (112,650)

| Field | Type | Notes |
|---|---|---|
| `order_id` | text FK | |
| `order_item_id` | int | Sequence within order; grain is (order_id, order_item_id) |
| `product_id` | text FK | |
| `seller_id` | text FK | |
| `shipping_limit_date` | timestamp | Seller's handover deadline |
| `price` | numeric | Item price, excludes freight |
| `freight_value` | numeric | Shipping charged for this item |

### order_payments (103,886)

| Field | Type | Notes |
|---|---|---|
| `order_id` | text FK | Multiple rows per order when payment is split |
| `payment_sequential` | int | |
| `payment_type` | text | credit_card / boleto / voucher / debit_card |
| `payment_installments` | int | |
| `payment_value` | numeric | |

### order_reviews (99,224)

| Field | Type | Notes |
|---|---|---|
| `review_id` | text | **Not reliably unique** — quantified in M2 |
| `order_id` | text FK | |
| `review_score` | int 1–5 | Ordinal, heavily skewed to 5 |
| `review_comment_title` | text | Mostly null |
| `review_comment_message` | text | Mostly null; contains embedded newlines |
| `review_creation_date` | timestamp | |
| `review_answer_timestamp` | timestamp | |

### customers (99,441) / sellers (3,095)

| Field | Type | Notes |
|---|---|---|
| `customer_id` | text PK | Per-order |
| `customer_unique_id` | text | **The person.** Retention/RFM key |
| `customer_zip_code_prefix` | text | 5-digit prefix, not full postcode |
| `customer_state` | text | 2-letter Brazilian state |
| `seller_id` | text PK | |
| `seller_zip_code_prefix` / `seller_state` | text | |

### products (32,951) / product_category_translation (71)

| Field | Type | Notes |
|---|---|---|
| `product_id` | text PK | |
| `product_category_name` | text | Portuguese; nullable |
| `product_name_lenght` | int | *[sic]* — misspelled in source, preserved in raw |
| `product_description_lenght` | int | *[sic]* |
| `product_weight_g`, `product_length_cm`, `product_height_cm`, `product_width_cm` | numeric | Used to derive volume/density |

### geolocation (1,000,163)

| Field | Type | Notes |
|---|---|---|
| `geolocation_zip_code_prefix` | text | **Many rows per prefix.** Aggregate before joining — see R-2 |
| `geolocation_lat` / `geolocation_lng` | numeric | |

---

## Part 2 — Derived measures

These are the definitions the whole analysis rests on. Any figure in any
deliverable traces back to one of these formulas (NFR-2).

### Delivery

| Measure | Formula | Notes |
|---|---|---|
| `delivery_days` | `delivered_customer_date − purchase_timestamp` | Total customer-perceived wait. Full timestamp precision |
| `estimated_days` | `estimated_delivery_date − purchase_timestamp` | The promise |
| **`delay_days`** | **`delivered_customer_date::date − estimated_delivery_date::date`** | **Signed whole days.** Positive = late, negative = early. The project's central independent variable |
| `is_late` | `delay_days > 0` | |
| `seller_handover_days` | `delivered_carrier_date − purchase_timestamp` | Isolates seller-controlled time. **NULL if negative** |
| `carrier_transit_days` | `delivered_customer_date − delivered_carrier_date` | Isolates logistics-controlled time. **NULL if negative** |

Splitting the wait into **seller handover** vs **carrier transit** is what makes
the eventual recommendation actionable — "deliveries are late" is not something
anyone can fix; "sellers in state X take 4 days to hand over" is.

Delivery measures are computed **only** where
`order_status = 'delivered' AND delivered_customer_date IS NOT NULL` — both
conditions. Status alone admits 8 orders with no delivery timestamp; the
timestamp alone admits 6 orders that were delivered and then cancelled (M2
finding F-03).

### Why `delay_days` casts to `::date` (M2 finding F-01)

`order_estimated_delivery_date` is a **date**, stored at midnight — all 96,470
delivered orders, without exception. `delivered_customer_date` is a real
timestamp, and **no delivery in the dataset was recorded at exactly midnight**.

Subtracting the two as timestamps therefore calls an order late if it arrived at
any time on the day it was promised. That misclassifies **1,292 orders** whose
mean review score is 4.03 — they behave like on-time deliveries — into the late
group, dragging its mean from 2.27 up to 2.57 and **understating the measured
effect of late delivery by 14.4%**.

The promise was a *day*. The comparison is made at the granularity the promise
was made at. `delivery_days`, `seller_handover_days` and `carrier_transit_days`
keep full timestamp precision — they compare a measurement against another
measurement, so no unit mismatch arises.

`seller_handover_days` and `carrier_transit_days` are **null rather than
negative**: 165 orders record carrier handover before purchase and 23 record
delivery before handover (F-08). A clamped zero would assert an instantaneous
handover; null asserts the timestamps cannot support the measure.

### Delay decomposition (M5)

`delay_days` is a single signed number, and M5 found that fitting a single slope
to it describes nothing. The relationship is a **threshold plus a ramp**, so the
regression carries three terms rather than one.

| Measure | Formula | Notes |
|---|---|---|
| `is_late` | `delay_days > 0` | The threshold. Costs **1.71 review points** on crossing |
| `days_late` | `GREATEST(delay_days, 0)` | The ramp beyond it. Costs 0.015 per day |
| `days_early` | `GREATEST(−delay_days, 0)` | Buffer. Worth +0.008 per day |

Fitting `delay_days` alone reports −0.036 per day and hides the jump entirely,
because a discrete drop at the boundary has to be smeared across the days that
follow it. It takes **113 days** of additional lateness to do as much damage
again as the breach itself, and **211 days** of extra padding to be worth one
breach prevented. See `docs/inferential_findings.md` §3.

### Delay buckets (M4)

Used by `mart_delay_buckets` and by the dashboard. Buckets rather than a mean
because the relationship is sharply non-linear.

| Bucket | Range in `delay_days` |
|---|---|
| 15+ days early | `≤ −15` |
| 8–14 days early | `−14 … −8` |
| 1–7 days early | `−7 … −1` |
| On the promised day | `= 0` |
| 1–7 days late | `1 … 7` |
| 8–14 days late | `8 … 14` |
| 15–30 days late | `15 … 30` |
| More than 30 days late | `> 30` |

### Order value

| Measure | Formula | Notes |
|---|---|---|
| `order_item_total` | `SUM(price)` per order | Excludes freight |
| `order_freight_total` | `SUM(freight_value)` per order | |
| `order_value` | `order_item_total + order_freight_total` | What the customer paid |
| `freight_ratio` | `order_freight_total / order_item_total` | Shipping burden |

`order_value` is derived from `order_items`, **not** `order_payments` — payments
can exceed order value through installment interest, and can split across
instruments. Summing payments would double-count. This choice is the difference
between a correct revenue figure and a plausible-looking wrong one.

### Customer

| Measure | Formula | Notes |
|---|---|---|
| `recency_days` | `analysis_date − last purchase` | R in RFM. Anchored to **2018-08-31** |
| `frequency_orders` | Distinct orders per `customer_unique_id` | F |
| `shopping_days` | Distinct `purchase_date` per `customer_unique_id` | The honest repeat measure — see below |
| `monetary_value` | `COALESCE(SUM(order_value), 0)` per `customer_unique_id` | M. Zero, not null, for the 775 never-itemised orders |
| `cohort_month` | `DATE_TRUNC('month', first purchase)` | Retention cohort |
| `is_repeat_customer` | `frequency_orders > 1` | 3.12% of people |
| `returned_on_a_later_day` | `shopping_days > 1` | **2.24%** of people |

All customer measures key on **`customer_unique_id`**. Using `customer_id`
produces a 100% single-purchase population — a wrong answer that looks entirely
reasonable, which is why R-1 carries a dedicated test.

**`is_repeat_customer` and `returned_on_a_later_day` are not the same thing, and
the difference is a finding.** 897 of the 2,997 customers with two or more orders
placed the second on the *same day* as the first — a split basket, one shopping
occasion, not a return visit (M4 FR-6). Retention is measured in **shopping
days**; counting orders would book those customers as retained when they never
came back.

### RFM scoring (M4, `mart_customer_rfm`)

| Score | Formula | Notes |
|---|---|---|
| `r_score` | `6 − NTILE(5) OVER (ORDER BY recency_days)` | Reversed: lower recency is better |
| `f_score` | `3+ orders → 5`, `2 → 3`, `1 → 1` | **Not quintiles.** See below |
| `m_score` | `NTILE(5) OVER (ORDER BY monetary_value)` | |

**`f_score` is not quintiled, and that is deliberate.** 96.88% of people placed
exactly one order, so `NTILE(5)` would cut five arbitrary slices through a column
that is the value 1 for nineteen people in twenty and return five segments
differing in nothing — while looking exactly like a normal RFM output.

Segments are assigned from `r_score` and `m_score` only, since those vary.
`f_score` is carried into the output so the degeneracy is visible rather than
hidden inside a label. **"Champions" therefore does not mean loyal repeat
buyers** — 94% of them bought exactly once. It means recent, high-value,
single-purchase customers.

| Segment | Rule |
|---|---|
| Champions | `r ≥ 4 AND m ≥ 4` |
| Recent, promising | `r ≥ 4 AND m ≥ 2` |
| Recent, low value | `r ≥ 4` |
| Needs attention | `r = 3 AND m ≥ 4` |
| At risk, high value | `r ≤ 2 AND m ≥ 4` |
| Lost, low value | `r ≤ 2 AND m ≤ 2` |
| Hibernating | otherwise |

### Geography and route (M5, `mart_order_analysis`)

| Measure | Formula | Notes |
|---|---|---|
| `distance_km` | Great-circle between customer and seller ZIP centroids | `2 · 6371 · asin(√(sin²(Δφ/2) + cos φ₁ cos φ₂ sin²(Δλ/2)))` |
| `is_same_state` | `customer_state = seller_state` | 36% of orders |
| `region` | IBGE macro-region from the two-letter state code | `brazil_region()` macro — one definition, three models |

`distance_km` is **null** on 475 orders whose customer or seller ZIP prefix has
no centroid (M2 F-07). Null, not zero: an unknown distance is not a short one.
The M5 regression drops those rows and reports how many.

### Seller track record, as-of purchase (M6, `mart_prediction_features`)

These are the only features in the project computed **relative to a point in
time**, and the reason is leakage.

| Measure | Formula | Availability rule |
|---|---|---|
| `seller_prior_deliveries` | Count of that seller's orders **delivered** before this order was purchased | |
| `seller_prior_late_rate` | `seller_prior_late / seller_prior_deliveries` | Null if no prior delivery |
| `seller_prior_reviews` | Count of that seller's reviews **answered** before this order was purchased | |
| `seller_prior_low_score_rate` | `seller_prior_low_scores / seller_prior_reviews` | Null if no prior review |

Computed the obvious way — `AVG(is_late) GROUP BY seller` — these would include
*this* order's own outcome and every *future* order's. The model would read the
answer off a feature that does not exist in production, and would backtest
beautifully.

Late rates key on **delivery** time and low-score rates on **review answer**
time, because those are the moments the information became available. A review
that exists but has not been written yet is not information anyone had.

Null, not zero, where a seller has no history: an unknown track record is not a
clean one.

### Satisfaction

| Measure | Formula | Notes |
|---|---|---|
| `review_score` | 1–5 ordinal | Outcome variable |
| `is_low_score` | `review_score <= 2` | Binary target for the M6 classifier |
| `review_count` | Reviews on the order before deduplication | 547 orders carried more than one |
| `reviewed_before_delivery` | `review_answered_at < delivered_at` | **Read the warning below** |

Ordinal, not interval — the gap between 1 and 2 is not assumed equal to 4→5.
This is why M5 uses rank-based tests rather than a t-test on the mean.

**`reviewed_before_delivery` must never be used as a filter or a control.** The
satisfaction survey fires at *dispatch*, not delivery, so this flag is true for
0.2% of on-time orders and 96–99% of late ones — it is very nearly *determined
by* the delay. It is a **post-treatment variable**: conditioning on it keeps
99.8% of on-time orders but only 30% of late ones, which selects a subset rather
than removing a bias.

It exists to be *reported*, not to be conditioned on. See
`docs/inferential_findings.md` §6.3.

---

## Analysis date

Recency is relative to a fixed **analysis date = 2018-08-31**, not `now()` and
not the maximum timestamp in the data.

`now()` is wrong for the obvious reason: the data ends in 2018, so anchoring to
the current date makes every customer maximally stale and renders RFM
meaningless.

The maximum `order_purchase_timestamp` — 2018-10-17 — is wrong for a subtler
one. September and October 2018 carry **16 and 4 orders** against ~6,500 a month
through the rest of 2018, and **none of those 20 orders was ever delivered**:
they were still in flight when the extract was taken (M2 finding F-06). That
tail is a truncation artefact, not a collapse in trading. Anchoring to it adds
47 days of artificial staleness to every customer and leaves the most recent RFM
segment populated by eight orders.

2018-08-31 is the last day of the last month with full trading coverage. The 20
orders after it are excluded from RFM and reported as excluded.

**Trend and cohort window: 2017-01 to 2018-08.** 2016 carries 329 orders in
total — a pilot period whose inclusion in a trend chart shows explosive growth
that is an artefact of the platform's launch. It is retained in the warehouse
and excluded from trend analysis, with the exclusion stated on the chart rather
than in a footnote. **November 2016 has no orders at all**, so `dim_dates` is
generated as a gapless spine and the gap appears as a visible zero.

Both dates and the trend window are declared once, as `vars` in
`dbt_orderlens/dbt_project.yml`, so the models and the tests that check them
cannot drift apart.

---

## Part 3 — Where each measure lives

Every figure in any deliverable resolves to one of these models (NFR-2). If an
analysis needs something that is not here, the fix is a new mart column, not a
bespoke query in a script (Design Phase §8).

| Model | Grain | Holds |
|---|---|---|
| `fct_orders` | one order (all 99,441) | Delivery measures, order value, satisfaction, `is_delivery_eligible` |
| `fct_order_items` | (order_id, order_item_id) | Item value, plus delivery outcome denormalised for seller analysis |
| `fct_payments` | (order_id, payment_sequential) | Payment instruments — never revenue |
| `dim_customers` | one **person** | Cohort, recency, order counts, region |
| `dim_products` | one product | `category`, `category_source`, physical attributes |
| `dim_sellers` / `dim_geography` | one seller / one ZIP prefix | Centroids, region, `has_coordinates` |
| `dim_dates` | one calendar day | Gapless spine, `in_trend_window` |
| `mart_delivery_monthly` | one purchase month | On-time rate, handover vs transit split |
| `mart_delay_buckets` | one delay bucket | Distribution and the satisfaction cost of each band |
| `mart_cohort_retention` | (cohort, months since) | Retention on shopping days |
| `mart_customer_rfm` | one person | R/F/M scores and segment |
| `mart_revenue_concentration` | (dimension, key) | Revenue rank, cumulative share, late rate |
| `mart_order_analysis` | one delivery-eligible order | The M5 modelling table — every FR-11 control |
| `mart_prediction_features` | one reviewed order | The M6 feature table — pre-delivery columns only |

**Currency.** All monetary values are Brazilian reais (R$), as they arrive in the
source. No conversion is applied anywhere.

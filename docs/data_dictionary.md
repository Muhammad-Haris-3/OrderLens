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
| `recency_days` | `analysis_date − last purchase` | R in RFM |
| `frequency` | Distinct orders per `customer_unique_id` | F |
| `monetary` | `SUM(order_value)` per `customer_unique_id` | M |
| `cohort_month` | `DATE_TRUNC('month', first purchase)` | Retention cohort |
| `is_repeat_customer` | `frequency > 1` | |

All customer measures key on **`customer_unique_id`**. Using `customer_id`
produces a 100% single-purchase population — a wrong answer that looks entirely
reasonable, which is why R-1 carries a dedicated test.

### Satisfaction

| Measure | Formula | Notes |
|---|---|---|
| `review_score` | 1–5 ordinal | Outcome variable |
| `is_low_score` | `review_score <= 2` | Binary target for the M6 classifier |

Ordinal, not interval — the gap between 1 and 2 is not assumed equal to 4→5.
This is why M5 uses rank-based tests rather than a t-test on the mean.

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

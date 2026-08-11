# OrderLens — Data-Quality Audit Results (generated)

**Do not edit by hand.** Regenerate with `python scripts/run_audit.py`.

This file is the *evidence*. The adjudication — what each anomaly means and
what was decided about it — lives in [data_quality_audit.md](data_quality_audit.md).

| Generated | 2026-08-11 11:18 UTC |
|---|---|
| Checks run | 30 |
| Warehouse | PostgreSQL 18.4 (be2730e) |

---

## A-01 — Load reconciliation — does the warehouse still match the source files?

**Question:** Did every row in every CSV land, and is the warehouse still in that state?

Source: [`sql/audit/a01_load_reconciliation.sql`](../sql/audit/a01_load_reconciliation.sql)

| table_name | rows_in_file | rows_loaded | rows_now | status | loaded_at |
|---|---|---|---|---|---|
| raw.geolocation | 1000163 | 1000163 | 1000163 | OK | 2026-08-10 22:30:33.242498+00:00 |
| raw.order_items | 112650 | 112650 | 112650 | OK | 2026-08-10 22:30:33.242498+00:00 |
| raw.order_payments | 103886 | 103886 | 103886 | OK | 2026-08-10 22:30:33.242498+00:00 |
| raw.customers | 99441 | 99441 | 99441 | OK | 2026-08-10 22:30:33.242498+00:00 |
| raw.orders | 99441 | 99441 | 99441 | OK | 2026-08-10 22:30:33.242498+00:00 |
| raw.order_reviews | 99224 | 99224 | 99224 | OK | 2026-08-10 22:30:33.242498+00:00 |
| raw.products | 32951 | 32951 | 32951 | OK | 2026-08-10 22:30:33.242498+00:00 |
| raw.sellers | 3095 | 3095 | 3095 | OK | 2026-08-10 22:30:33.242498+00:00 |
| raw.product_category_translation | 71 | 71 | 71 | OK | 2026-08-10 22:30:33.242498+00:00 |


## A-02 — Declared grain — is every table's stated key actually unique?

**Question:** Where does the documented grain fail to hold in the source?

Source: [`sql/audit/a02_key_uniqueness.sql`](../sql/audit/a02_key_uniqueness.sql)

| declared_grain | rows | distinct_keys | excess_rows |
|---|---|---|---|
| raw.geolocation (zip prefix) — expected NOT unique | 1000163 | 19015 | 981148 |
| raw.order_reviews (review_id) | 99224 | 98410 | 814 |
| raw.order_reviews (order_id) | 99224 | 98673 | 551 |
| raw.products (product_id) | 32951 | 32951 | 0 |
| raw.customers (customer_id) | 99441 | 99441 | 0 |
| raw.orders (order_id) | 99441 | 99441 | 0 |
| raw.product_category_translation (product_category_name) | 71 | 71 | 0 |
| raw.order_payments (order_id, payment_sequential) | 103886 | 103886 | 0 |
| raw.sellers (seller_id) | 3095 | 3095 | 0 |
| raw.order_reviews (whole row) | 99224 | 99224 | 0 |
| raw.order_items (order_id, order_item_id) | 112650 | 112650 | 0 |


## A-03 — Review grain — how many rows per review_id and per order_id?

**Question:** Is "one review per order" true? (Design Phase decision D-1)

Source: [`sql/audit/a03_review_grain.sql`](../sql/audit/a03_review_grain.sql)

| key | n_rows | keys | rows_involved |
|---|---|---|---|
| rows per order_id | 1 | 98126 | 98126 |
| rows per order_id | 2 | 543 | 1086 |
| rows per order_id | 3 | 4 | 12 |
| rows per review_id | 1 | 97621 | 97621 |
| rows per review_id | 2 | 764 | 1528 |
| rows per review_id | 3 | 25 | 75 |


## A-04 — Review duplication — what shape is it, and do duplicates disagree?

**Question:** Are duplicated review_ids the same review repeated, or one review spanning several orders? Do orders with several reviews agree on the score? (D-1)

Source: [`sql/audit/a04_review_duplicate_shape.sql`](../sql/audit/a04_review_duplicate_shape.sql)

| finding | groups | spanning_several_orders | with_disagreeing_scores |
|---|---|---|---|
| duplicated review_id groups | 789 | 789 | 0 |
| orders with several reviews | 547 | _null_ | 202 |


## A-05 — Review dedup — does the choice of rule change the headline numbers?

**Question:** How much does keeping the latest review per order differ from keeping the earliest, or from leaving the duplicates in? (D-1)

Source: [`sql/audit/a05_review_dedup_impact.sql`](../sql/audit/a05_review_dedup_impact.sql)

| rows_before_dedup | rows_after_dedup | mean_score_all_rows | mean_score_keep_latest | mean_score_keep_earliest | pct_low_score_all_rows | pct_low_score_keep_latest | pct_low_score_keep_earliest |
|---|---|---|---|---|---|---|---|
| 99224 | 98673 | 4.0864 | 4.0864 | 4.0872 | 14.689 | 14.689 | 14.671 |


## A-06 — Order status distribution and delivery-timestamp completeness

**Question:** Which statuses exist, how common are they, and which carry the timestamps delivery analysis needs? (D-2)

Source: [`sql/audit/a06_order_status_profile.sql`](../sql/audit/a06_order_status_profile.sql)

| order_status | orders | pct_of_orders | has_approved_at | has_carrier_at | has_delivered_at | has_estimated_at |
|---|---|---|---|---|---|---|
| delivered | 96478 | 97.02 | 96464 | 96476 | 96470 | 96478 |
| shipped | 1107 | 1.11 | 1107 | 1107 | 0 | 1107 |
| canceled | 625 | 0.63 | 484 | 75 | 6 | 625 |
| unavailable | 609 | 0.61 | 609 | 0 | 0 | 609 |
| invoiced | 314 | 0.32 | 314 | 0 | 0 | 314 |
| processing | 301 | 0.30 | 301 | 0 | 0 | 301 |
| created | 5 | 0.01 | 0 | 0 | 0 | 5 |
| approved | 2 | 0.00 | 2 | 0 | 0 | 2 |


## A-07 — Status contradicts the timestamps

**Question:** Are there orders whose status and delivery timestamp disagree? (D-2)

Source: [`sql/audit/a07_status_timestamp_contradictions.sql`](../sql/audit/a07_status_timestamp_contradictions.sql)

| contradiction | order_status | orders |
|---|---|---|
| status <> delivered but a delivery timestamp exists | canceled | 6 |
| status = delivered but no delivery timestamp | delivered | 8 |


## A-08 — Null profile of the orders table

**Question:** Which order columns are incomplete, and by how much?

Source: [`sql/audit/a08_orders_null_profile.sql`](../sql/audit/a08_orders_null_profile.sql)

| column_name | rows | sql_nulls | empty_strings | pct_missing |
|---|---|---|---|---|
| order_delivered_customer_date | 99441 | 2965 | 0 | 2.982 |
| order_delivered_carrier_date | 99441 | 1783 | 0 | 1.793 |
| order_approved_at | 99441 | 160 | 0 | 0.161 |
| customer_id | 99441 | 0 | 0 | 0.000 |
| order_status | 99441 | 0 | 0 | 0.000 |
| order_id | 99441 | 0 | 0 | 0.000 |
| order_estimated_delivery_date | 99441 | 0 | 0 | 0.000 |
| order_purchase_timestamp | 99441 | 0 | 0 | 0.000 |


## A-09 — Timestamp ordering violations

**Question:** Do the order lifecycle timestamps ever run backwards?

Source: [`sql/audit/a09_timestamp_ordering.sql`](../sql/audit/a09_timestamp_ordering.sql)

| delivered_orders | approved_before_purchase | carrier_before_purchase | approved_after_carrier | delivered_before_carrier | delivered_before_purchase |
|---|---|---|---|---|---|
| 96478 | 0 | 165 | 1350 | 23 | 0 |


## A-10 — The is_late boundary — timestamp arithmetic vs calendar-day comparison

**Question:** How many orders delivered ON the promised day are classified late because the promise is stored as midnight?

Source: [`sql/audit/a10_is_late_boundary.sql`](../sql/audit/a10_is_late_boundary.sql)

| delivered_orders | promise_stored_at_midnight | delivery_recorded_at_midnight | late_by_timestamp | late_by_calendar_day | on_promised_day_but_called_late | pct_late_by_timestamp | pct_late_by_calendar_day |
|---|---|---|---|---|---|---|---|
| 96470 | 96470 | 0 | 7826 | 6534 | 1292 | 8.11 | 6.77 |


## A-11 — Does the is_late definition change the answer to the project's question?

**Question:** What is the mean review score of late vs on-time orders under each definition, and how do the boundary orders actually behave?

Source: [`sql/audit/a11_is_late_definition_effect.sql`](../sql/audit/a11_is_late_definition_effect.sql)

| sort_order | group_name | orders | mean_review_score |
|---|---|---|---|
| 1 | late (timestamp rule) | 7661 | 2.565 |
| 2 | on time (timestamp rule) | 88163 | 4.294 |
| 3 | late (calendar-day rule) | 6381 | 2.270 |
| 4 | on time (calendar-day rule) | 89443 | 4.290 |
| 5 | boundary: delivered on the promised day, called late by timestamp | 1280 | 4.034 |


## A-12 — What time of day do deliveries land?

**Question:** How much of the day sits after midnight — i.e. how much of the delivery volume the timestamp rule in A-10 would misclassify?

Source: [`sql/audit/a12_delivery_hour_profile.sql`](../sql/audit/a12_delivery_hour_profile.sql)

| hour_of_day | deliveries | pct_of_deliveries |
|---|---|---|
| 0 | 2885 | 2.99 |
| 1 | 1515 | 1.57 |
| 2 | 649 | 0.67 |
| 3 | 260 | 0.27 |
| 4 | 187 | 0.19 |
| 5 | 198 | 0.21 |
| 6 | 269 | 0.28 |
| 7 | 396 | 0.41 |
| 8 | 779 | 0.81 |
| 9 | 1196 | 1.24 |
| 10 | 1798 | 1.86 |
| 11 | 2579 | 2.67 |
| 12 | 3651 | 3.78 |
| 13 | 4561 | 4.73 |
| 14 | 5644 | 5.85 |
| 15 | 6740 | 6.99 |
| 16 | 7901 | 8.19 |
| 17 | 8775 | 9.10 |
| 18 | 9639 | 9.99 |
| 19 | 9484 | 9.83 |
| 20 | 9157 | 9.49 |
| 21 | 7627 | 7.91 |
| 22 | 6142 | 6.37 |
| 23 | 4438 | 4.60 |


## A-13 — Delay distribution and outliers

**Question:** How is delay_days distributed, and how extreme are the tails?

Source: [`sql/audit/a13_delay_distribution.sql`](../sql/audit/a13_delay_distribution.sql)

| delivered_orders | min_delay_days | p01 | p25 | median | p75 | p99 | max_delay_days | mean_delay_days | late_orders | late_over_30_days | late_over_90_days | early_over_60_days |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 96470 | -147 | -36.0 | -17.0 | -12.0 | -7.0 | 18.0 | 188 | -11.88 | 6534 | 345 | 47 | 34 |


## A-14 — Referential integrity — orphans in both directions

**Question:** Are there child rows with no parent, and parents with no children? (D-4)

Source: [`sql/audit/a14_referential_integrity.sql`](../sql/audit/a14_referential_integrity.sql)

| check_name | rows | severity |
|---|---|---|
| orders with no items | 775 | business state |
| orders with no review | 768 | business state |
| orders with no payment | 1 | business state |
| products never ordered | 0 | business state |
| sellers with nothing sold | 0 | business state |
| customers never used by an order | 0 | business state |
| orders with no customer record | 0 | corruption |
| payments with no parent order | 0 | corruption |
| items referencing an unknown seller | 0 | corruption |
| items referencing an unknown product | 0 | corruption |
| items with no parent order | 0 | corruption |
| reviews with no parent order | 0 | corruption |


## A-15 — Orders with no items — what are they?

**Question:** Is an item-less order corruption or an unfulfilled order? (D-4)

Source: [`sql/audit/a15_orders_without_items.sql`](../sql/audit/a15_orders_without_items.sql)

| order_status | orders | with_a_payment | with_a_review | earliest_purchase | latest_purchase |
|---|---|---|---|---|---|
| unavailable | 603 | 603 | 589 | 2016-10-05 18:06:48 | 2018-08-21 12:21:00 |
| canceled | 164 | 164 | 161 | 2016-09-13 15:24:19 | 2018-10-17 17:30:18 |
| created | 5 | 5 | 3 | 2017-11-06 13:12:34 | 2018-02-09 17:21:04 |
| invoiced | 2 | 2 | 2 | 2016-10-05 13:22:20 | 2016-10-05 21:03:33 |
| shipped | 1 | 1 | 1 | 2016-10-05 01:47:40 | 2016-10-05 01:47:40 |


## A-16 — Product category translation coverage

**Question:** How many products fail to reach an English category name, and why? (D-3)

Source: [`sql/audit/a16_category_translation_coverage.sql`](../sql/audit/a16_category_translation_coverage.sql)

| products | translated | no_category_at_all | category_missing_from_lookup | lookup_rows | distinct_categories_in_use |
|---|---|---|---|---|---|
| 32951 | 32328 | 610 | 13 | 71 | 73 |


## A-17 — What is at stake in the untranslated categories?

**Question:** How much order volume and revenue would an INNER JOIN on the category lookup silently delete? (D-3)

Source: [`sql/audit/a17_untranslated_category_weight.sql`](../sql/audit/a17_untranslated_category_weight.sql)

| category_pt | cause | products | order_items | orders | item_revenue |
|---|---|---|---|---|---|
| (no category) | no category at all | 610 | 1603 | 1451 | 179535.28 |
| portateis_cozinha_e_preparadores_de_alimentos | missing from lookup | 10 | 15 | 14 | 3968.53 |
| pc_gamer | missing from lookup | 3 | 9 | 8 | 1545.95 |


## A-18 — Monthly order volume — where does the data actually start and stop?

**Question:** Is the observed date range the usable analysis window? (D-5)

Source: [`sql/audit/a18_date_coverage.sql`](../sql/audit/a18_date_coverage.sql)

| purchase_month | orders | delivered | with_delivery_timestamp | pct_delivered |
|---|---|---|---|---|
| 2016-09 | 4 | 1 | 1 | 25.0 |
| 2016-10 | 324 | 265 | 270 | 81.8 |
| 2016-12 | 1 | 1 | 1 | 100.0 |
| 2017-01 | 800 | 750 | 750 | 93.8 |
| 2017-02 | 1780 | 1653 | 1653 | 92.9 |
| 2017-03 | 2682 | 2546 | 2546 | 94.9 |
| 2017-04 | 2404 | 2303 | 2303 | 95.8 |
| 2017-05 | 3700 | 3546 | 3545 | 95.8 |
| 2017-06 | 3245 | 3135 | 3135 | 96.6 |
| 2017-07 | 4026 | 3872 | 3872 | 96.2 |
| 2017-08 | 4331 | 4193 | 4193 | 96.8 |
| 2017-09 | 4285 | 4150 | 4150 | 96.8 |
| 2017-10 | 4631 | 4478 | 4478 | 96.7 |
| 2017-11 | 7544 | 7289 | 7288 | 96.6 |
| 2017-12 | 5673 | 5513 | 5513 | 97.2 |
| 2018-01 | 7269 | 7069 | 7069 | 97.2 |
| 2018-02 | 6728 | 6555 | 6556 | 97.4 |
| 2018-03 | 7211 | 7003 | 7003 | 97.1 |
| 2018-04 | 6939 | 6798 | 6798 | 98.0 |
| 2018-05 | 6873 | 6749 | 6749 | 98.2 |
| 2018-06 | 6167 | 6099 | 6096 | 98.9 |
| 2018-07 | 6292 | 6159 | 6156 | 97.9 |
| 2018-08 | 6512 | 6351 | 6351 | 97.5 |
| 2018-09 | 16 | 0 | 0 | 0.0 |
| 2018-10 | 4 | 0 | 0 | 0.0 |


## A-19 — customer_id vs customer_unique_id — how many people are hidden? (risk R-1)

**Question:** How many repeat customers exist, and how many orders would keying retention on customer_id make invisible?

Source: [`sql/audit/a19_customer_key_collapse.sql`](../sql/audit/a19_customer_key_collapse.sql)

| orders_placed | people | orders_represented | pct_of_people |
|---|---|---|---|
| 1 | 93099 | 93099 | 96.881 |
| 2 | 2745 | 5490 | 2.857 |
| 3 | 203 | 609 | 0.211 |
| 4 | 30 | 120 | 0.031 |
| 5 | 8 | 40 | 0.008 |
| 6 | 6 | 36 | 0.006 |
| 7 | 3 | 21 | 0.003 |
| 9 | 1 | 9 | 0.001 |
| 17 | 1 | 17 | 0.001 |


## A-20 — Geolocation fan-out and internal consistency (risk R-2)

**Question:** How badly would an un-aggregated geolocation join multiply fact rows, and is a prefix internally consistent about where it is?

Source: [`sql/audit/a20_geolocation_fanout.sql`](../sql/audit/a20_geolocation_fanout.sql)

| geolocation_rows | distinct_prefixes | mean_rows_per_prefix | max_rows_for_one_prefix | prefixes_with_several_city_names | prefixes_with_several_states |
|---|---|---|---|---|---|
| 1000163 | 19015 | 52.6 | 1146 | 8556 | 8 |


## A-21 — Geolocation coverage — which ZIP prefixes have no coordinates?

**Question:** How many customers and sellers cannot be placed on a map?

Source: [`sql/audit/a21_geolocation_coverage.sql`](../sql/audit/a21_geolocation_coverage.sql)

| side | rows | rows_without_coordinates | pct_without | distinct_prefixes | distinct_prefixes_without |
|---|---|---|---|---|---|
| customers | 99441 | 278 | 0.280 | 14994 | 157 |
| sellers | 3095 | 7 | 0.226 | 2246 | 7 |


## A-22 — Are the coordinates actually in Brazil?

**Question:** How many geolocation points fall outside Brazil's bounding box?

Source: [`sql/audit/a22_geolocation_coordinates.sql`](../sql/audit/a22_geolocation_coordinates.sql)

| geolocation_rows | latitude_outside_brazil | longitude_outside_brazil | points_outside_brazil | prefixes_affected | distinct_states |
|---|---|---|---|---|---|
| 1000163 | 31 | 37 | 42 | 21 | 27 |


## A-23 — Price and freight plausibility

**Question:** Are there zero, negative or absurd item values?

Source: [`sql/audit/a23_price_freight_sanity.sql`](../sql/audit/a23_price_freight_sanity.sql)

| items | price_zero_or_negative | freight_negative | freight_exactly_zero | orders_with_free_freight | min_price | mean_price | median_price | max_price | min_freight | max_freight |
|---|---|---|---|---|---|---|---|---|---|---|
| 112650 | 0 | 0 | 383 | 339 | 0.85 | 120.65 | 74.99 | 6735.00 | 0.00 | 409.68 |


## A-24 — Payments vs item totals

**Question:** Do payments reconcile to order value, and if not, in which direction?

Source: [`sql/audit/a24_payment_reconciliation.sql`](../sql/audit/a24_payment_reconciliation.sql)

| orders_with_both | payments_exceed_items | payments_below_items | reconciled | largest_overpayment | largest_underpayment | total_paid | total_owed | difference |
|---|---|---|---|---|---|---|---|---|
| 98665 | 264 | 39 | 98362 | 182.81 | -51.62 | 15846280.17 | 15843409.78 | 2870.39 |


## A-25 — Payment instrument profile

**Question:** Which payment types exist, and are any rows degenerate?

Source: [`sql/audit/a25_payment_types.sql`](../sql/audit/a25_payment_types.sql)

| payment_type | rows | pct_of_rows | value_zero | value_negative | installments_zero | max_installments | total_value |
|---|---|---|---|---|---|---|---|
| credit_card | 76795 | 73.922 | 0 | 0 | 2 | 24 | 12542084.19 |
| boleto | 19784 | 19.044 | 0 | 0 | 0 | 1 | 2869361.27 |
| voucher | 5775 | 5.559 | 6 | 0 | 0 | 1 | 379436.87 |
| debit_card | 1529 | 1.472 | 0 | 0 | 0 | 1 | 217989.79 |
| not_defined | 3 | 0.003 | 3 | 0 | 0 | 1 | 0.00 |


## A-26 — Product attribute completeness

**Question:** Are weight and dimensions usable as model features?

Source: [`sql/audit/a26_product_attributes.sql`](../sql/audit/a26_product_attributes.sql)

| products | missing_category | missing_weight | missing_length | missing_photo_count | weight_zero | any_dimension_zero | max_weight_g |
|---|---|---|---|---|---|---|---|
| 32951 | 610 | 2 | 2 | 610 | 4 | 0 | 40425 |


## A-27 — When is a review written, relative to delivery?

**Question:** Do reviews exist that were created or answered before the order arrived — and on orders that never arrived at all?

Source: [`sql/audit/a27_review_timing.sql`](../sql/audit/a27_review_timing.sql)

| reviews_joined_to_an_order | on_delivered_orders | on_orders_never_delivered | survey_created_before_delivery | answered_before_delivery | pct_answered_before_delivery |
|---|---|---|---|---|---|
| 99224 | 96359 | 2865 | 8320 | 4795 | 4.98 |


## A-28 — Review score distribution and comment completeness

**Question:** How skewed are the scores, and how much free text is actually there?

Source: [`sql/audit/a28_review_score_and_text.sql`](../sql/audit/a28_review_score_and_text.sql)

| review_score | reviews | pct_of_reviews | with_title | with_message | pct_with_message |
|---|---|---|---|---|---|
| 1 | 11424 | 11.51 | 1873 | 8745 | 76.5 |
| 2 | 3151 | 3.18 | 478 | 2145 | 68.1 |
| 3 | 8179 | 8.24 | 824 | 3557 | 43.5 |
| 4 | 19142 | 19.29 | 1735 | 5976 | 31.2 |
| 5 | 57328 | 57.78 | 6658 | 20554 | 35.9 |


## A-29 — How many orders involve more than one seller?

**Question:** Can a delivery outcome be attributed to a single seller?

Source: [`sql/audit/a29_multi_seller_orders.sql`](../sql/audit/a29_multi_seller_orders.sql)

| sellers_in_order | orders | pct_of_orders |
|---|---|---|
| 1 | 97388 | 98.705 |
| 2 | 1219 | 1.235 |
| 3 | 54 | 0.055 |
| 4 | 3 | 0.003 |
| 5 | 2 | 0.002 |


## A-30 — Candidate analysis anchor dates

**Question:** What date should RFM recency be measured from? (D-5)

Source: [`sql/audit/a30_analysis_anchor_date.sql`](../sql/audit/a30_analysis_anchor_date.sql)

| candidate | anchor_date | orders_in_prior_30_days | orders_after_this_date |
|---|---|---|---|
| max order_purchase_timestamp | 2018-10-17 | 8 | 0 |
| max order_delivered_customer_date | 2018-10-17 | 8 | 0 |
| last day of the last month with >= 1000 orders | 2018-08-31 | 6201 | 20 |


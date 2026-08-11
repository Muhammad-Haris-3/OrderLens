# OrderLens — Descriptive Analysis Results (generated)

**Do not edit by hand.** Regenerate with `python analysis/descriptive.py`.

This file is the *evidence*. The interpretation — what these numbers mean
and what follows from them — lives in
[descriptive_findings.md](descriptive_findings.md).

| Generated | 2026-08-11 12:58 UTC |
|---|---|
| Source | `analytics_marts` (marts only — never raw, never staging) |

---

## FR-5 — Delivery performance

### Monthly delivery performance, 2017-01 to 2018-08

From `mart_delivery_monthly`.

| year_month | delivered_orders | late_orders | pct_late | mean_delay_days | mean_delivery_days | mean_seller_handover_days | mean_carrier_transit_days | mean_review_score |
|---|---|---|---|---|---|---|---|---|
| 2017-01 | 750 | 22 | 2.93 | -27.41 | 12.65 | 3.45 | 9.22 | 4.198 |
| 2017-02 | 1,653 | 49 | 2.96 | -19.20 | 13.17 | 3.63 | 9.56 | 4.203 |
| 2017-03 | 2,546 | 116 | 4.56 | -12.33 | 12.95 | 3.12 | 9.84 | 4.187 |
| 2017-04 | 2,303 | 151 | 6.56 | -12.97 | 14.92 | 3.68 | 11.24 | 4.135 |
| 2017-05 | 3,545 | 106 | 2.99 | -13.50 | 11.32 | 2.98 | 8.34 | 4.236 |
| 2017-06 | 3,135 | 95 | 3.03 | -12.64 | 12.01 | 3.13 | 8.88 | 4.223 |
| 2017-07 | 3,872 | 108 | 2.79 | -12.47 | 11.59 | 3.11 | 8.51 | 4.260 |
| 2017-08 | 4,193 | 122 | 2.91 | -13.10 | 11.15 | 3.08 | 8.07 | 4.313 |
| 2017-09 | 4,150 | 182 | 4.39 | -11.35 | 11.85 | 3.19 | 8.65 | 4.268 |
| 2017-10 | 4,478 | 187 | 4.18 | -11.92 | 11.86 | 3.45 | 8.41 | 4.205 |
| 2017-11 | 7,288 | 904 | 12.40 | -8.12 | 15.16 | 4.07 | 11.09 | 3.989 |
| 2017-12 | 5,513 | 411 | 7.46 | -13.01 | 15.39 | 3.72 | 11.67 | 4.088 |
| 2018-01 | 7,069 | 403 | 5.70 | -12.93 | 14.08 | 3.60 | 10.48 | 4.109 |
| 2018-02 | 6,555 | 926 | 14.13 | -8.29 | 16.95 | 3.56 | 13.38 | 3.881 |
| 2018-03 | 7,003 | 1,328 | 18.96 | -6.43 | 16.30 | 3.33 | 12.97 | 3.813 |
| 2018-04 | 6,798 | 306 | 4.50 | -12.90 | 11.50 | 2.83 | 8.67 | 4.206 |
| 2018-05 | 6,749 | 443 | 6.56 | -12.19 | 11.42 | 2.70 | 8.73 | 4.236 |
| 2018-06 | 6,096 | 71 | 1.16 | -19.24 | 9.24 | 2.57 | 6.68 | 4.307 |
| 2018-07 | 6,156 | 208 | 3.38 | -11.44 | 8.96 | 2.87 | 6.14 | 4.317 |
| 2018-08 | 6,351 | 393 | 6.19 | -8.16 | 7.73 | 2.54 | 5.21 | 4.310 |


### Where the wait goes — seller handover vs carrier transit

From `mart_delivery_monthly`.

| mean_total_wait_days | mean_seller_handover_days | mean_carrier_transit_days | pct_of_wait_seller | pct_of_wait_carrier |
|---|---|---|---|---|
| 12.51 | 3.23 | 9.29 | 25.8 | 74.2 |


### Delay distribution and what each band costs

From `mart_delay_buckets`.

| delay_bucket | orders | pct_of_delivered | mean_review_score | pct_low_score | revenue |
|---|---|---|---|---|---|
| 1. 15+ days early | 34,939 | 36.22 | 4.323 | 9.04 | 5916682.41 |
| 2. 8-14 days early | 36,364 | 37.69 | 4.311 | 8.91 | 5568427.94 |
| 3. 1-7 days early | 17,341 | 17.98 | 4.201 | 10.24 | 2581659.52 |
| 4. on the promised day | 1,292 | 1.34 | 4.034 | 12.42 | 200732.83 |
| 5. 1-7 days late | 3,672 | 3.81 | 2.714 | 49.39 | 627569.59 |
| 6. 8-14 days late | 1,478 | 1.53 | 1.671 | 80.15 | 268801.99 |
| 7. 15-30 days late | 1,039 | 1.08 | 1.614 | 81.81 | 189409.17 |
| 8. more than 30 days late | 345 | 0.36 | 2.058 | 67.78 | 65111.38 |


### Review timing by delay band — the selection problem

From `mart_delay_buckets`.

| delay_bucket | orders | pct_reviewed_before_delivery | mean_all_reviews | mean_review_reviewed_after | mean_review_reviewed_before |
|---|---|---|---|---|---|
| 1. 15+ days early | 34,939 | 0.2 | 4.323 | 4.324 | 4.131 |
| 2. 8-14 days early | 36,364 | 0.2 | 4.311 | 4.311 | 3.986 |
| 3. 1-7 days early | 17,341 | 0.2 | 4.201 | 4.202 | 3.780 |
| 4. on the promised day | 1,292 | 0.6 | 4.034 | 4.039 | 3.250 |
| 5. 1-7 days late | 3,672 | 49.1 | 2.714 | 3.734 | 1.657 |
| 6. 8-14 days late | 1,478 | 96.1 | 1.671 | 3.526 | 1.595 |
| 7. 15-30 days late | 1,039 | 98.8 | 1.614 | 3.167 | 1.596 |
| 8. more than 30 days late | 345 | 97.9 | 2.058 | 2.429 | 2.050 |


### Sensitivity — what excluding pre-delivery reviews would do

Computed from `fct_orders`. This is the calculation that shows why the
M2 F-09 handling decision could not stand.

| population | on-time orders | late orders | mean (on time) | mean (late) | gap |
|---|---|---|---|---|---|
| all reviews | 89,443 | 6,381 | 4.290 | 2.271 | 2.020 |
| reviews written after delivery only | 89,263 | 1,908 | 4.291 | 3.720 | 0.572 |

Excluding pre-delivery reviews retains 99.8% of on-time orders but only 29.9% of late ones.

---

## FR-6 — Cohort retention

### Retention by cohort, months 1-6

From `mart_cohort_retention`.

| cohort_month | cohort_customers | month_1 | month_2 | month_3 | month_6 |
|---|---|---|---|---|---|
| 2017-01-01 | 764 | 0.393 | 0.262 | 0.131 | 0.524 |
| 2017-02-01 | 1,752 | 0.228 | 0.285 | 0.114 | 0.228 |
| 2017-03-01 | 2,636 | 0.493 | 0.379 | 0.379 | 0.152 |
| 2017-04-01 | 2,352 | 0.595 | 0.213 | 0.170 | 0.340 |
| 2017-05-01 | 3,596 | 0.501 | 0.501 | 0.389 | 0.417 |
| 2017-06-01 | 3,139 | 0.478 | 0.350 | 0.414 | 0.382 |
| 2017-07-01 | 3,894 | 0.514 | 0.360 | 0.257 | 0.308 |
| 2017-08-01 | 4,184 | 0.693 | 0.335 | 0.263 | 0.287 |
| 2017-09-01 | 4,130 | 0.678 | 0.533 | 0.291 | 0.218 |
| 2017-10-01 | 4,470 | 0.694 | 0.246 | 0.089 | 0.224 |
| 2017-11-01 | 7,304 | 0.548 | 0.383 | 0.178 | 0.110 |
| 2017-12-01 | 5,487 | 0.255 | 0.273 | 0.346 | 0.164 |
| 2018-01-01 | 7,025 | 0.342 | 0.384 | 0.285 | 0.171 |
| 2018-02-01 | 6,451 | 0.388 | 0.388 | 0.295 | 0.202 |
| 2018-03-01 | 6,965 | 0.459 | 0.316 | 0.287 | _null_ |
| 2018-04-01 | 6,711 | 0.581 | 0.313 | 0.238 | _null_ |
| 2018-05-01 | 6,622 | 0.529 | 0.272 | 0.211 | _null_ |
| 2018-06-01 | 5,940 | 0.421 | 0.286 | _null_ | _null_ |
| 2018-07-01 | 6,071 | 0.725 | 0.033 | _null_ | _null_ |
| 2018-08-01 | 6,271 | 0.112 | 0.032 | _null_ | _null_ |


### Retention pooled across cohorts of 500+ customers

From `mart_cohort_retention (grid generated to keep zero-retention cohorts in the denominator)`.

| months_since_first_order | cohorts_observable | customers | active | retention_pct |
|---|---|---|---|---|
| 0 | 20 | 95764 | 95764 | 100.000 |
| 1 | 20 | 95764 | 460 | 0.480 |
| 2 | 20 | 95764 | 289 | 0.302 |
| 3 | 19 | 89493 | 202 | 0.226 |
| 4 | 18 | 83422 | 186 | 0.223 |
| 5 | 17 | 77482 | 143 | 0.185 |
| 6 | 16 | 70860 | 132 | 0.186 |


### Repeat purchase, measured two ways

From `mart_customer_rfm`.

| people | placed_2plus_orders | pct_2plus_orders | shopped_on_2plus_days | pct_2plus_days |
|---|---|---|---|---|
| 96,096 | 2,997 | 3.12 | 2,149 | 2.24 |


---

## FR-7 — RFM segmentation

### Segment profile

From `mart_customer_rfm`.

| rfm_segment | people | pct_of_people | revenue | pct_of_revenue | mean_spend | mean_recency_days | returned_later |
|---|---|---|---|---|---|---|---|
| Champions | 15,970 | 16.62 | 4904355.50 | 30.95 | 307.10 | 94 | 942 |
| At risk, high value | 14,877 | 15.48 | 4636491.73 | 29.26 | 311.66 | 397 | 469 |
| Needs attention | 7,591 | 7.90 | 2158100.49 | 13.62 | 284.30 | 224 | 326 |
| Hibernating | 19,200 | 19.98 | 1647607.27 | 10.40 | 85.81 | 292 | 155 |
| Recent, promising | 15,046 | 15.66 | 1345861.15 | 8.49 | 89.45 | 92 | 192 |
| Lost, low value | 15,989 | 16.64 | 863166.29 | 5.45 | 53.99 | 400 | 47 |
| Recent, low value | 7,423 | 7.72 | 287970.81 | 1.82 | 38.79 | 91 | 18 |


### The frequency dimension, as it actually is

From `mart_customer_rfm`.

| f_score | frequency_orders | people | pct_of_people |
|---|---|---|---|
| 1 | 1 | 93,099 | 96.881 |
| 3 | 2 | 2,745 | 2.857 |
| 5 | 3 | 203 | 0.211 |
| 5 | 4 | 30 | 0.031 |
| 5 | 5 | 8 | 0.008 |
| 5 | 6 | 6 | 0.006 |
| 5 | 7 | 3 | 0.003 |
| 5 | 9 | 1 | 0.001 |
| 5 | 17 | 1 | 0.001 |


---

## FR-8 — Revenue concentration

### Category concentration

From `mart_revenue_concentration` where `dimension = 'category'`. Gini and top-N shares computed in `analysis/descriptive.py`.

| members | reaching 80% of revenue | as % of members | Gini |
|---|---|---|---|
| 74 | 18 | 24.300 | 0.713 |


| tier | members | share of revenue % |
|---|---|---|
| top 1% | 1 | 9.100 |
| top 5% | 4 | 32.470 |
| top 10% | 7 | 49.770 |
| top 20% | 15 | 76.410 |


### Seller concentration

From `mart_revenue_concentration` where `dimension = 'seller'`. Gini and top-N shares computed in `analysis/descriptive.py`.

| members | reaching 80% of revenue | as % of members | Gini |
|---|---|---|---|
| 3,095 | 562 | 18.200 | 0.785 |


| tier | members | share of revenue % |
|---|---|---|
| top 1% | 31 | 25.620 |
| top 5% | 155 | 52.510 |
| top 10% | 310 | 66.760 |
| top 20% | 619 | 82.060 |


### Customer state concentration

From `mart_revenue_concentration` where `dimension = 'customer_state'`. Gini and top-N shares computed in `analysis/descriptive.py`.

| members | reaching 80% of revenue | as % of members | Gini |
|---|---|---|---|
| 27 | 7 | 25.900 | 0.703 |


| tier | members | share of revenue % |
|---|---|---|
| top 1% | 1 | 37.390 |
| top 5% | 1 | 37.390 |
| top 10% | 3 | 62.550 |
| top 20% | 5 | 73.190 |


### Top 15 categories

From `mart_revenue_concentration`.

| revenue_rank | category | revenue | pct_of_revenue | cumulative_pct_of_revenue | orders | pct_late | mean_review_score |
|---|---|---|---|---|---|---|---|
| 1 | health_beauty | 1441248.07 | 9.0967 | 9.0967 | 8,836 | 7.56 | 4.141 |
| 2 | watches_gifts | 1305541.61 | 8.2402 | 17.3370 | 5,624 | 7.21 | 4.019 |
| 3 | bed_bath_table | 1241681.72 | 7.8371 | 25.1741 | 9,417 | 7.03 | 3.898 |
| 4 | sports_leisure | 1156656.48 | 7.3005 | 32.4746 | 7,720 | 6.31 | 4.107 |
| 5 | computers_accessories | 1059272.40 | 6.6858 | 39.1604 | 6,689 | 6.49 | 3.933 |
| 6 | furniture_decor | 902511.79 | 5.6964 | 44.8568 | 6,449 | 7.03 | 3.907 |
| 7 | housewares | 778397.77 | 4.9130 | 49.7698 | 5,884 | 5.00 | 4.053 |
| 8 | cool_stuff | 719329.95 | 4.5402 | 54.3100 | 3,632 | 5.84 | 4.147 |
| 9 | auto | 685384.32 | 4.3260 | 58.6360 | 3,897 | 7.03 | 4.064 |
| 10 | garden_tools | 584219.21 | 3.6874 | 62.3234 | 3,518 | 6.56 | 4.045 |
| 11 | toys | 561372.55 | 3.5432 | 65.8666 | 3,886 | 6.35 | 4.159 |
| 12 | baby | 480118.00 | 3.0304 | 68.8970 | 2,885 | 7.68 | 4.011 |
| 13 | perfumery | 453338.71 | 2.8613 | 71.7584 | 3,162 | 6.50 | 4.166 |
| 14 | telephony | 394883.32 | 2.4924 | 74.2507 | 4,199 | 6.95 | 3.946 |
| 15 | office_furniture | 342532.65 | 2.1620 | 76.4127 | 1,273 | 7.97 | 3.492 |


### Revenue and failure rate by customer state (top 12)

From `mart_revenue_concentration`.

| revenue_rank | state | revenue | pct_of_revenue | cumulative_pct_of_revenue | orders | pct_late | mean_review_score |
|---|---|---|---|---|---|---|---|
| 1 | SP | 5924087.82 | 37.3912 | 37.3912 | 41,381 | 4.49 | 4.195 |
| 2 | RJ | 2129526.31 | 13.4410 | 50.8321 | 12,763 | 12.11 | 3.893 |
| 3 | MG | 1855816.53 | 11.7134 | 62.5455 | 11,541 | 4.58 | 4.154 |
| 4 | RS | 885910.82 | 5.5916 | 68.1371 | 5,432 | 6.08 | 4.147 |
| 5 | PR | 799884.27 | 5.0486 | 73.1858 | 4,996 | 4.04 | 4.201 |
| 6 | BA | 611230.06 | 3.8579 | 77.0437 | 3,356 | 12.17 | 3.876 |
| 7 | SC | 609728.50 | 3.8484 | 80.8921 | 3,612 | 8.20 | 4.093 |
| 8 | DF | 352333.47 | 2.2238 | 83.1159 | 2,122 | 5.58 | 4.082 |
| 9 | GO | 347898.78 | 2.1958 | 85.3118 | 2,006 | 6.49 | 4.059 |
| 10 | ES | 324946.11 | 2.0510 | 87.3627 | 2,026 | 10.72 | 4.050 |
| 11 | PE | 321902.11 | 2.0318 | 89.3945 | 1,647 | 9.67 | 4.013 |
| 12 | CE | 275870.84 | 1.7412 | 91.1357 | 1,329 | 13.74 | 3.874 |


### Where the damage concentrates — states ranked by late orders

From `mart_revenue_concentration`.

| state | orders | pct_late | late_orders | revenue_on_late_orders | pct_of_all_late_revenue | pct_of_all_revenue | mean_review_score |
|---|---|---|---|---|---|---|---|
| SP | 41,381 | 4.49 | 1858 | 265991.54 | 23.70 | 37.39 | 4.195 |
| RJ | 12,763 | 12.11 | 1546 | 257885.64 | 22.98 | 13.44 | 3.893 |
| MG | 11,541 | 4.58 | 529 | 84996.40 | 7.57 | 11.71 | 4.154 |
| BA | 3,356 | 12.17 | 408 | 74386.70 | 6.63 | 3.86 | 3.876 |
| RS | 5,432 | 6.08 | 330 | 53863.38 | 4.80 | 5.59 | 4.147 |
| SC | 3,612 | 8.20 | 296 | 49997.74 | 4.45 | 3.85 | 4.093 |
| CE | 1,329 | 13.74 | 183 | 37904.65 | 3.38 | 1.74 | 3.874 |
| ES | 2,026 | 10.72 | 217 | 34834.22 | 3.10 | 2.05 | 4.050 |
| PR | 4,996 | 4.04 | 202 | 32315.32 | 2.88 | 5.05 | 4.201 |
| PE | 1,647 | 9.67 | 159 | 31127.93 | 2.77 | 2.03 | 4.013 |
| MA | 743 | 17.36 | 129 | 26323.59 | 2.35 | 0.96 | 3.774 |
| PA | 970 | 11.21 | 109 | 24398.24 | 2.17 | 1.37 | 3.859 |


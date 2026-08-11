-- FR-5 — the delay distribution and what it costs. Grain: one delay bucket.
--
-- Buckets rather than a mean, because the relationship is not linear and a mean
-- would describe none of it. Being one to seven days late does not cost a
-- fraction of what being fourteen days late costs — it costs most of it.
--
-- pct_reviewed_before_delivery is carried here deliberately, and it is the most
-- important column in the model. The satisfaction survey fires at dispatch
-- (M2 F-09), so the later a parcel is, the more likely the review was written
-- while the customer was still waiting for it. The share climbs from 0.2% on
-- on-time orders to over 96% on every late bucket.
--
-- That is not a nuisance to be filtered out. It means review timing is a
-- CONSEQUENCE of the delay, not an independent nuisance — a post-treatment
-- variable. Conditioning on it drops 96%+ of late orders and ~0% of on-time
-- ones, which is why this model reports the split rather than picking a side.
-- See M4 §Review timing.

with bucketed as (

    select
        {{ delay_bucket('delay_days') }}                        as delay_bucket,
        delay_days > 0                                          as is_late,
        review_score,
        is_low_score,
        reviewed_before_delivery,
        order_value
    from {{ ref('fct_orders') }}
    where is_delivery_eligible

)

select
    delay_bucket,
    is_late,

    count(*)                                                        as orders,
    round(100.0 * count(*) / sum(count(*)) over (), 2)              as pct_of_delivered,

    count(review_score)                                             as reviewed_orders,
    round(avg(review_score), 3)                                     as mean_review_score,
    round(100.0 * count(*) filter (where is_low_score)
          / nullif(count(review_score), 0), 2)                      as pct_low_score,

    -- The confound, quantified per bucket.
    round(100.0 * count(*) filter (where reviewed_before_delivery)
          / nullif(count(reviewed_before_delivery::int), 0), 1)     as pct_reviewed_before_delivery,
    round(avg(review_score) filter (where not reviewed_before_delivery), 3)
                                                                    as mean_review_reviewed_after,
    round(avg(review_score) filter (where reviewed_before_delivery), 3)
                                                                    as mean_review_reviewed_before,

    round(sum(order_value), 2)                                      as revenue

from bucketed
group by delay_bucket, is_late

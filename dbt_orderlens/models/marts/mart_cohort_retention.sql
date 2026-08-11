-- FR-6 — cohort retention. Grain: (cohort_month, months_since_first_order).
--
-- Keyed on customer_unique_id, which is the whole point (risk R-1). Built on
-- customer_id it would show 0% retention in every cell for every cohort, and the
-- output would look like a perfectly ordinary — if catastrophic — retention
-- curve. dim_customers already carries the correct key and cohort_month.
--
-- SHOPPING DAYS, NOT ORDERS. 897 of the 2,997 repeat customers placed their
-- second order on the SAME DAY as their first — a split basket, not a repeat
-- purchase. Counting orders would inflate month-0 retention with people who
-- never came back at all. Retention here means "returned on a later day", which
-- is what the word is supposed to mean.
--
-- Expect a flat curve. This marketplace has almost no repeat business (2.24% of
-- people ever shop on a second day) and the honest deliverable is that number,
-- not a curve massaged until it slopes (SRS NFR-8).

with customer_activity as (

    select distinct
        o.customer_unique_id,
        c.cohort_month,
        date_trunc('month', o.purchased_at)::date               as activity_month
    from {{ ref('fct_orders') }} o
    join {{ ref('dim_customers') }} c on c.customer_unique_id = o.customer_unique_id

),

with_offset as (

    select
        cohort_month,
        customer_unique_id,
        activity_month,
        (extract(year  from activity_month) - extract(year  from cohort_month)) * 12
      + (extract(month from activity_month) - extract(month from cohort_month))
                                                                as months_since_first_order
    from customer_activity

),

cohort_size as (

    select cohort_month, count(distinct customer_unique_id)      as cohort_customers
    from with_offset
    where months_since_first_order = 0
    group by cohort_month

)

select
    o.cohort_month,
    o.months_since_first_order::int                             as months_since_first_order,
    s.cohort_customers,
    count(distinct o.customer_unique_id)                        as active_customers,
    round(100.0 * count(distinct o.customer_unique_id) / s.cohort_customers, 3)
                                                                as retention_pct
from with_offset o
join cohort_size s on s.cohort_month = o.cohort_month
group by o.cohort_month, o.months_since_first_order, s.cohort_customers

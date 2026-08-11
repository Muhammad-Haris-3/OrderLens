-- Grain: one customer_unique_id — one row per PERSON. ~96,096 rows.
--
-- THIS MODEL EXISTS TO SOLVE RISK R-1, the highest-risk trap in the dataset.
-- The source's customer_id is a per-ORDER key: 99,441 of them map to 96,096
-- people (A-19). Keying this dimension on customer_id instead would produce a
-- perfectly unique key, a perfectly clean build, and a 100% first-time customer
-- base — destroying all retention and RFM analysis while failing nothing.
--
-- That is why this model carries a bespoke test asserting repeat customers
-- EXIST. No schema test can catch R-1, because the wrong key is still unique.
-- Only an assertion about meaning catches it. 2,997 people placed more than one
-- order; one placed 17.
--
-- Location comes from the most recent order, not the first: where a person moved
-- between orders, the current address is the useful one for logistics analysis.

with customer_orders as (

    select
        c.customer_unique_id,
        c.customer_id,
        c.zip_prefix,
        c.city,
        c.state,
        o.order_id,
        o.purchased_at,
        row_number() over (
            partition by c.customer_unique_id
            order by o.purchased_at desc, o.order_id
        )                                                       as recency_rank
    from {{ ref('stg_customers') }} c
    join {{ ref('stg_orders') }} o on o.customer_id = c.customer_id

),

aggregated as (

    select
        customer_unique_id,
        count(distinct order_id)                                as total_orders,
        min(purchased_at)                                       as first_order_at,
        max(purchased_at)                                       as last_order_at
    from customer_orders
    group by customer_unique_id

),

most_recent as (

    -- The tie-break on order_id matters: without it, a person with two orders at
    -- the same instant gets a location that can change between builds.
    select customer_unique_id, zip_prefix, city, state
    from customer_orders
    where recency_rank = 1

)

select
    a.customer_unique_id,

    r.zip_prefix,
    r.city,
    r.state,
    {{ brazil_region('r.state') }}                              as region,

    a.first_order_at,
    a.last_order_at,
    date_trunc('month', a.first_order_at)::date                 as cohort_month,

    a.total_orders,
    a.total_orders > 1                                          as is_repeat_customer,

    -- Recency against the M2 anchor (decision D-5), not now() and not the
    -- dataset maximum. See dbt_project.yml vars for why 2018-08-31.
    ('{{ var("analysis_anchor_date") }}'::date - a.last_order_at::date)
                                                                as recency_days

from aggregated a
join most_recent r using (customer_unique_id)

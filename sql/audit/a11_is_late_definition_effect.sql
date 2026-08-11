-- id: A-11
-- title: Does the is_late definition change the answer to the project's question?
-- question: What is the mean review score of late vs on-time orders under each
--   definition, and how do the boundary orders actually behave?
--
-- A-10 counts the misclassification. This one prices it. If the boundary group
-- behaves like on-time orders but is filed under "late", it dilutes the late
-- group and shrinks the measured effect of delay on satisfaction — the central
-- estimate of the whole project (BQ-2, BQ-3).
--
-- One review per order, latest kept, per the rule adopted in D-1 — otherwise
-- the 547 multi-review orders would be counted twice and the comparison would
-- be measuring two things at once.

with one_review_per_order as (
    select distinct on (order_id)
        order_id,
        review_score::int as score
    from raw.order_reviews
    order by order_id, review_answer_timestamp::timestamp desc, review_id
),
d as (
    select
        nullif(o.order_delivered_customer_date, '')::timestamp as delivered_at,
        o.order_estimated_delivery_date::timestamp             as estimated_at,
        r.score
    from raw.orders o
    join one_review_per_order r on r.order_id = o.order_id
    where o.order_status = 'delivered'
      and nullif(o.order_delivered_customer_date, '') is not null
)
select 1 as sort_order, 'late (timestamp rule)' as group_name,
       count(*) filter (where delivered_at > estimated_at)             as orders,
       round(avg(score) filter (where delivered_at > estimated_at), 3) as mean_review_score
from d
union all
select 2, 'on time (timestamp rule)',
       count(*) filter (where delivered_at <= estimated_at),
       round(avg(score) filter (where delivered_at <= estimated_at), 3)
from d
union all
select 3, 'late (calendar-day rule)',
       count(*) filter (where delivered_at::date > estimated_at::date),
       round(avg(score) filter (where delivered_at::date > estimated_at::date), 3)
from d
union all
select 4, 'on time (calendar-day rule)',
       count(*) filter (where delivered_at::date <= estimated_at::date),
       round(avg(score) filter (where delivered_at::date <= estimated_at::date), 3)
from d
union all
select 5, 'boundary: delivered on the promised day, called late by timestamp',
       count(*) filter (where delivered_at > estimated_at
                          and delivered_at::date = estimated_at::date),
       round(avg(score) filter (where delivered_at > estimated_at
                                  and delivered_at::date = estimated_at::date), 3)
from d
order by sort_order;

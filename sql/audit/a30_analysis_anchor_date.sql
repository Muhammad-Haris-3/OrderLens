-- id: A-30
-- title: Candidate analysis anchor dates
-- question: What date should RFM recency be measured from? (D-5)
--
-- The data dictionary anchors recency to "the maximum order_purchase_timestamp"
-- rather than now(). A-18 shows why that needs a second look: the final weeks
-- carry a handful of orders each, so the maximum is set by a near-empty tail
-- rather than by the end of trading. The candidates are laid side by side here
-- so the choice is made against numbers rather than against a default.

with monthly as (
    select
        date_trunc('month', order_purchase_timestamp::timestamp) as month_start,
        count(*)                                                 as orders
    from raw.orders
    group by 1
),
last_full_month as (
    select max(month_start) as month_start
    from monthly
    where orders >= 1000
),
candidates (rank_order, candidate, anchor_date) as (
    select 1, 'max order_purchase_timestamp',
           (select max(order_purchase_timestamp::timestamp)::date from raw.orders)
    union all
    select 2, 'max order_delivered_customer_date',
           (select max(nullif(order_delivered_customer_date, '')::timestamp)::date from raw.orders)
    union all
    select 3, 'last day of the last month with >= 1000 orders',
           (select (month_start + interval '1 month' - interval '1 day')::date from last_full_month)
)
select
    c.candidate,
    c.anchor_date,
    (select count(*) from raw.orders o
      where o.order_purchase_timestamp::timestamp::date > c.anchor_date - 30
        and o.order_purchase_timestamp::timestamp::date <= c.anchor_date) as orders_in_prior_30_days,
    (select count(*) from raw.orders o
      where o.order_purchase_timestamp::timestamp::date > c.anchor_date)  as orders_after_this_date
from candidates c
order by c.rank_order;

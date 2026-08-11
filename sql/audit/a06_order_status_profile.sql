-- id: A-06
-- title: Order status distribution and delivery-timestamp completeness
-- question: Which statuses exist, how common are they, and which carry the
--   timestamps delivery analysis needs? (D-2)
--
-- This is the query that decides the population of fct_orders. Delivery
-- measures are only meaningful where a delivery actually happened, and the
-- eligible set is defined by what this returns, not by assumption.

select
    order_status,
    count(*)                                                          as orders,
    round(100.0 * count(*) / sum(count(*)) over (), 2)                as pct_of_orders,
    count(nullif(order_approved_at, ''))                              as has_approved_at,
    count(nullif(order_delivered_carrier_date, ''))                   as has_carrier_at,
    count(nullif(order_delivered_customer_date, ''))                  as has_delivered_at,
    count(nullif(order_estimated_delivery_date, ''))                  as has_estimated_at
from raw.orders
group by 1
order by 2 desc;

-- id: A-15
-- title: Orders with no items — what are they?
-- question: Is an item-less order corruption or an unfulfilled order? (D-4)
--
-- The answer decides whether fct_orders may join items with an INNER JOIN. If
-- these orders are a real business state they must survive the join with a null
-- order value, because "orders that could not be fulfilled" is itself one of the
-- operational failures this project exists to quantify (BQ-1).

select
    o.order_status,
    count(*)                                                            as orders,
    count(*) filter (where exists (select 1 from raw.order_payments p
                                   where p.order_id = o.order_id))      as with_a_payment,
    count(*) filter (where exists (select 1 from raw.order_reviews r
                                   where r.order_id = o.order_id))      as with_a_review,
    min(o.order_purchase_timestamp)                                     as earliest_purchase,
    max(o.order_purchase_timestamp)                                     as latest_purchase
from raw.orders o
where not exists (select 1 from raw.order_items i where i.order_id = o.order_id)
group by 1
order by 2 desc;

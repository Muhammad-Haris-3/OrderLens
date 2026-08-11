-- id: A-29
-- title: How many orders involve more than one seller?
-- question: Can a delivery outcome be attributed to a single seller?
--
-- fct_orders holds one row per order and one delivery outcome, but an order can
-- contain items from several sellers. For those orders "which seller caused the
-- delay" has no single answer, and any seller-level ranking built from
-- order-level outcomes double-attributes them. Small here, but the size has to
-- be known before BQ-4 ranks sellers by damage caused.

select
    sellers_in_order,
    count(*)                                                       as orders,
    round(100.0 * count(*) / sum(count(*)) over (), 3)             as pct_of_orders
from (
    select order_id, count(distinct seller_id) as sellers_in_order
    from raw.order_items
    group by 1
) t
group by 1
order by 1;

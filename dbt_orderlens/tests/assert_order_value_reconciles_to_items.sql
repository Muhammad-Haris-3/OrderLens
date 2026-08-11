-- BESPOKE TEST — the two fact grains must agree about money.
--
-- fct_orders holds one pre-aggregated order_value per order; fct_order_items
-- holds the items it was aggregated from. Every revenue figure in M4 and the
-- dashboard comes from one or the other, and a dashboard whose order-level total
-- disagrees with its item-level drill-down is the single most damaging thing this
-- project could publish — it invalidates every number on the page, including the
-- correct ones.
--
-- Tolerance is 0.01 for numeric(12,2) rounding, not for genuine drift.
--
-- Orders with no items are excluded on purpose: their order_value is NULL by
-- design (M2 F-04), and null is not a disagreement.

with per_order as (
    select
        order_id,
        sum(item_value) as items_total
    from {{ ref('fct_order_items') }}
    group by order_id
)

select
    o.order_id,
    o.order_value,
    i.items_total,
    o.order_value - i.items_total as difference
from {{ ref('fct_orders') }} o
join per_order i on i.order_id = o.order_id
where abs(o.order_value - i.items_total) > 0.01

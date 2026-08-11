-- Grain: (order_id, order_item_id). 112,650 rows.
--
-- Item-level detail for product and seller analysis. This is the model BQ-4's
-- seller ranking reads, not fct_orders: a delivery outcome is recorded per order,
-- but 1,278 orders contain items from several sellers (M2 finding F-12), so
-- attributing an order-level outcome to every seller in it would double-count
-- the damage. The delivery columns are carried down here so the ranking can be
-- built at item grain and filtered to single-seller orders in one place.
--
-- Carrying delay_days down rather than recomputing it: NFR-2 wants one definition
-- of the measure, in one place. A second copy of the calendar-day rule is a
-- second place for it to revert to timestamps.

select
    i.order_id,
    i.order_item_id,
    i.product_id,
    i.seller_id,

    o.customer_unique_id,
    o.purchase_date,
    o.order_status,

    i.shipping_limit_at,
    i.price,
    i.freight_value,
    i.price + i.freight_value                   as item_value,

    -- Denormalised from fct_orders, not recalculated.
    o.is_delivery_eligible,
    o.delay_days,
    o.is_late,
    o.is_single_seller,
    o.review_score,
    o.is_low_score

from {{ ref('stg_order_items') }} i
join {{ ref('fct_orders') }} o on o.order_id = i.order_id

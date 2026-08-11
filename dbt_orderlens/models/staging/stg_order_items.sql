-- Grain: (order_id, order_item_id). 112,650 rows, zero excess (A-02).
--
-- order_item_id is a sequence number within the order, not a global key. Treating
-- it as one is a classic way to lose 12,000 rows to a bad join.

select
    order_id,
    order_item_id::int                          as order_item_id,
    product_id,
    seller_id,
    shipping_limit_date::timestamp              as shipping_limit_at,
    price::numeric(12, 2)                       as price,
    freight_value::numeric(12, 2)               as freight_value

from {{ source('raw', 'order_items') }}

-- Grain: one order. 99,441 rows.
--
-- Renamed from source: the source suffixes several columns `_date` when they are
-- actually timestamps to the second. `_at` marks a timestamp here, because a
-- column called `_date` that carries a time is how the M2 audit's headline bug
-- (F-01) got written in the first place.
--
-- estimated_delivery_at is the exception and keeps DATE type deliberately — the
-- source stores it at midnight for every single order (A-10), so it is a date
-- wearing a timestamp's clothes. Typing it as what it is makes the calendar-day
-- comparison in fct_orders obvious rather than clever.

select
    order_id,
    customer_id,
    lower(order_status)                                    as order_status,

    order_purchase_timestamp::timestamp                    as purchased_at,
    nullif(order_approved_at, '')::timestamp                as approved_at,
    nullif(order_delivered_carrier_date, '')::timestamp     as handed_to_carrier_at,
    nullif(order_delivered_customer_date, '')::timestamp    as delivered_at,
    order_estimated_delivery_date::timestamp::date          as estimated_delivery_date

from {{ source('raw', 'orders') }}

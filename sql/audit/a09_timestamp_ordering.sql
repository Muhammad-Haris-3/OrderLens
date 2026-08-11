-- id: A-09
-- title: Timestamp ordering violations
-- question: Do the order lifecycle timestamps ever run backwards?
--
-- purchase -> approved -> handed to carrier -> delivered is the only sequence
-- that can physically happen. Where it is violated, the derived measures
-- seller_handover_days and carrier_transit_days go negative — and a negative
-- duration averaged into a segment mean silently pulls it down.

with t as (
    select
        order_purchase_timestamp::timestamp                       as purchased_at,
        nullif(order_approved_at, '')::timestamp                   as approved_at,
        nullif(order_delivered_carrier_date, '')::timestamp        as carrier_at,
        nullif(order_delivered_customer_date, '')::timestamp       as delivered_at
    from raw.orders
    where order_status = 'delivered'
)
select
    count(*)                                                       as delivered_orders,
    count(*) filter (where approved_at  < purchased_at)            as approved_before_purchase,
    count(*) filter (where carrier_at   < purchased_at)            as carrier_before_purchase,
    count(*) filter (where approved_at  > carrier_at)              as approved_after_carrier,
    count(*) filter (where delivered_at < carrier_at)              as delivered_before_carrier,
    count(*) filter (where delivered_at < purchased_at)            as delivered_before_purchase
from t;

-- id: A-10
-- title: The is_late boundary — timestamp arithmetic vs calendar-day comparison
-- question: How many orders delivered ON the promised day are classified late
--   because the promise is stored as midnight?
--
-- order_estimated_delivery_date is a DATE stored at 00:00:00. delivered_at is a
-- real timestamp. `delivered_at > estimated_at` therefore calls an order late if
-- it arrives at any time after midnight on the promised day — which is every
-- delivery on that day except one arriving at exactly midnight.
--
-- The promise made to the customer is a day, not an instant. The comparison has
-- to be made at the granularity the promise was made at.

with d as (
    select
        nullif(order_delivered_customer_date, '')::timestamp as delivered_at,
        order_estimated_delivery_date::timestamp             as estimated_at
    from raw.orders
    where order_status = 'delivered'
      and nullif(order_delivered_customer_date, '') is not null
)
select
    count(*)                                                                as delivered_orders,
    count(*) filter (where estimated_at = date_trunc('day', estimated_at))  as promise_stored_at_midnight,
    count(*) filter (where delivered_at = date_trunc('day', delivered_at))  as delivery_recorded_at_midnight,
    count(*) filter (where delivered_at > estimated_at)                     as late_by_timestamp,
    count(*) filter (where delivered_at::date > estimated_at::date)         as late_by_calendar_day,
    count(*) filter (where delivered_at > estimated_at
                       and delivered_at::date = estimated_at::date)         as on_promised_day_but_called_late,
    round(100.0 * count(*) filter (where delivered_at > estimated_at) / count(*), 2)
                                                                            as pct_late_by_timestamp,
    round(100.0 * count(*) filter (where delivered_at::date > estimated_at::date) / count(*), 2)
                                                                            as pct_late_by_calendar_day
from d;

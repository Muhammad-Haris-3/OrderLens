-- BESPOKE TEST — M2 finding F-03 / decision D-2.
--
-- Delivery measures must be null for every ineligible order and populated for
-- every eligible one. Both directions matter and both have a live failure case in
-- this dataset:
--
--   * 8 orders have status 'delivered' with no delivery timestamp. Filtering on
--     status alone admits them, and they land in the on-time-rate denominator
--     with a null delay.
--   * 6 orders were delivered and then CANCELLED. Filtering on the timestamp
--     alone admits them, and a returned parcel counts as a satisfied sale.
--
-- Either mistake produces a fact table that passes every schema test. This
-- asserts the rule that was actually decided.

select
    order_id,
    order_status,
    delivered_at,
    is_delivery_eligible,
    delay_days,
    'delivery measure set on an ineligible order' as problem
from {{ ref('fct_orders') }}
where not is_delivery_eligible
  and (delay_days is not null or delivery_days is not null or is_late is not null)

union all

select
    order_id,
    order_status,
    delivered_at,
    is_delivery_eligible,
    delay_days,
    'delivery measure missing on an eligible order'
from {{ ref('fct_orders') }}
where is_delivery_eligible
  and (delay_days is null or delivery_days is null or is_late is null)

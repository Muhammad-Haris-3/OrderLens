-- BESPOKE TEST — M2 finding F-08.
--
-- 165 orders record handover to the carrier BEFORE the customer placed the order
-- — the worst by nearly six months — and 23 record delivery before handover.
-- These are data-entry errors, not physics.
--
-- fct_orders sets the affected durations to NULL rather than clamping them to
-- zero, because a clamped zero asserts an instantaneous handover while null
-- asserts that the timestamps cannot support the measure. This test asserts the
-- null-not-negative rule holds: a negative duration averaged into a segment mean
-- pulls it down silently, and "sellers in state X hand over in 2.1 days" would be
-- wrong in a way no reader could detect.

select
    order_id,
    seller_handover_days,
    carrier_transit_days,
    delivery_days
from {{ ref('fct_orders') }}
where seller_handover_days < 0
   or carrier_transit_days < 0
   or delivery_days < 0

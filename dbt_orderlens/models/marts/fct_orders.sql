-- Grain: one order. ALL 99,441 of them. This is the table the headline analysis
-- runs against, and every M2 decision that touches a number lands here.
--
-- ============================================================================
-- delay_days IS MEASURED IN CALENDAR DAYS (M2 finding F-01)
-- ============================================================================
-- estimated_delivery_date is a DATE — the source stores it at midnight for all
-- 96,470 delivered orders, without exception. delivered_at is a real timestamp,
-- and no delivery in the dataset lands at exactly midnight.
--
-- Subtracting the two as timestamps therefore calls an order late if it arrived
-- at ANY hour of the day it was promised. That misfiles 1,292 orders whose mean
-- review score is 4.03 — orders that behave like on-time deliveries, because
-- they were on-time deliveries — into the late group. It drags the late-group
-- mean from 2.270 to 2.565 and UNDERSTATES the delay-to-satisfaction gap by
-- 14.4%: the single estimate this project exists to produce (BQ-2, BQ-3).
--
-- Nothing about the timestamp form fails. It returns a valid signed number for
-- every delivered order. The answer is simply 14% too small, with nothing to
-- compare it against. The promise was a DAY; the comparison is made at the
-- granularity the promise was made at, and a test asserts delay_days stays a
-- whole number so a reversion cannot happen quietly.
--
-- delivery_days, seller_handover_days and carrier_transit_days keep full
-- timestamp precision — they compare a measurement to another measurement, so no
-- unit mismatch arises.
-- ============================================================================

with items as (

    -- Value comes from ITEMS, never payments (M2 finding F-10): payments carry
    -- installment interest and split across instruments, exceeding item totals on
    -- 264 orders against falling short on 39.
    select
        order_id,
        count(*)                                        as item_count,
        count(distinct seller_id)                       as seller_count,
        count(distinct product_id)                      as product_count,
        sum(price)                                      as order_item_total,
        sum(freight_value)                              as order_freight_total
    from {{ ref('stg_order_items') }}
    group by order_id

),

customers as (

    select customer_id, customer_unique_id
    from {{ ref('stg_customers') }}

),

joined as (

    select
        o.order_id,
        o.customer_id,
        c.customer_unique_id,
        o.order_status,

        o.purchased_at,
        o.approved_at,
        o.handed_to_carrier_at,
        o.delivered_at,
        o.estimated_delivery_date,
        o.purchased_at::date                            as purchase_date,

        -- Eligibility needs BOTH conditions (M2 finding F-03, decision D-2).
        -- Status alone admits 8 orders with no delivery timestamp; the timestamp
        -- alone admits 6 orders delivered and then CANCELLED — a returned parcel
        -- is a delivery outcome but not a satisfied sale. Materialised rather
        -- than left to each consumer to re-derive and drift on.
        (o.order_status = 'delivered' and o.delivered_at is not null)
                                                        as is_delivery_eligible,

        i.item_count,
        i.seller_count,
        i.product_count,
        i.order_item_total,
        i.order_freight_total,

        r.review_score,
        r.is_low_score,
        r.review_count,
        r.answered_at                                   as review_answered_at

    from {{ ref('stg_orders') }} o
    join customers c on c.customer_id = o.customer_id

    -- LEFT JOIN (M2 finding F-04, decision D-4). 775 orders have no items at all
    -- — 603 unavailable, 164 canceled. They are a real business state, not
    -- corruption: every one has a payment and 756 have a review. An inner join
    -- would delete them, and with them the entire population of orders the
    -- platform failed to fulfil, which is BQ-1.
    left join items i on i.order_id = o.order_id

    -- LEFT JOIN: 768 orders were never reviewed.
    left join {{ ref('stg_order_reviews') }} r on r.order_id = o.order_id

)

select
    order_id,
    customer_id,
    customer_unique_id,
    order_status,

    purchased_at,
    approved_at,
    handed_to_carrier_at,
    delivered_at,
    estimated_delivery_date,
    purchase_date,
    is_delivery_eligible,

    -- ---- Delivery measures: null unless the order is delivery-eligible -------

    case when is_delivery_eligible
         then round(extract(epoch from (delivered_at - purchased_at)) / 86400.0, 3)
    end                                                 as delivery_days,

    -- Whole days: the promise is a date, so days-until-promise is a whole number
    -- for the same reason delay_days is.
    case when is_delivery_eligible
         then estimated_delivery_date - purchased_at::date
    end                                                 as estimated_days,

    -- THE central independent variable. Signed whole days: positive = late.
    case when is_delivery_eligible
         then delivered_at::date - estimated_delivery_date
    end                                                 as delay_days,

    case when is_delivery_eligible
         then delivered_at::date > estimated_delivery_date
    end                                                 as is_late,

    -- NULL rather than negative (M2 finding F-08). 165 orders record carrier
    -- handover BEFORE the customer ordered — the worst by nearly six months —
    -- and 23 record delivery before handover. A clamped zero would assert an
    -- instantaneous handover; null asserts the timestamps cannot support the
    -- measure, which is the truth. A negative duration averaged into a segment
    -- mean silently pulls it down and nothing fails.
    case when is_delivery_eligible and handed_to_carrier_at >= purchased_at
         then round(extract(epoch from (handed_to_carrier_at - purchased_at)) / 86400.0, 3)
    end                                                 as seller_handover_days,

    case when is_delivery_eligible and delivered_at >= handed_to_carrier_at
         then round(extract(epoch from (delivered_at - handed_to_carrier_at)) / 86400.0, 3)
    end                                                 as carrier_transit_days,

    -- ---- Value measures ------------------------------------------------------

    item_count,
    seller_count,
    product_count,

    -- Single-seller attribution (M2 finding F-12). 1,278 orders contain items
    -- from several sellers but carry one delivery outcome, so "which seller
    -- caused the delay" has no answer for them. BQ-4's seller ranking filters on
    -- this rather than attributing the damage to everyone involved, which would
    -- double-count it.
    seller_count = 1                                    as is_single_seller,

    order_item_total,
    order_freight_total,
    order_item_total + order_freight_total              as order_value,

    -- nullif guards a division by zero that would otherwise abort the build.
    round(order_freight_total / nullif(order_item_total, 0), 4)
                                                        as freight_ratio,

    -- ---- Satisfaction --------------------------------------------------------

    review_score,
    is_low_score,
    coalesce(review_count, 0)                           as review_count,
    review_answered_at,

    -- M2 finding F-09: the satisfaction survey fires at DISPATCH, not delivery,
    -- so 4,795 reviews (4.98%) were answered before the customer had the parcel.
    -- Those reviews cannot be a response to the delivery experience. M5 runs the
    -- headline test with and without them; M6 excludes them from training.
    case when is_delivery_eligible and review_answered_at is not null
         then review_answered_at < delivered_at
    end                                                 as reviewed_before_delivery

from joined

-- id: A-27
-- title: When is a review written, relative to delivery?
-- question: Do reviews exist that were created or answered before the order
--   arrived — and on orders that never arrived at all?
--
-- This is a validity finding rather than a cleanliness one. The satisfaction
-- survey is triggered at dispatch, not at delivery, so a share of reviews were
-- written before the customer had the parcel. Those reviews cannot be a
-- response to the delivery experience, which bears directly on how the M5
-- estimate is interpreted (FR-12) and on the M6 leakage rule.

select
    count(*)                                                                as reviews_joined_to_an_order,
    count(*) filter (where delivered_at is not null)                        as on_delivered_orders,
    count(*) filter (where delivered_at is null)                            as on_orders_never_delivered,
    count(*) filter (where delivered_at is not null and created_at  < delivered_at)
                                                                            as survey_created_before_delivery,
    count(*) filter (where delivered_at is not null and answered_at < delivered_at)
                                                                            as answered_before_delivery,
    round(100.0 * count(*) filter (where delivered_at is not null and answered_at < delivered_at)
          / nullif(count(*) filter (where delivered_at is not null), 0), 2) as pct_answered_before_delivery
from (
    select
        r.review_creation_date::timestamp                    as created_at,
        r.review_answer_timestamp::timestamp                 as answered_at,
        nullif(o.order_delivered_customer_date, '')::timestamp as delivered_at
    from raw.order_reviews r
    join raw.orders o on o.order_id = r.order_id
) t;

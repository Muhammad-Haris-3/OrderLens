-- The M6 feature table. Grain: one delivery-eligible order carrying a review.
--
-- ============================================================================
-- EVERY COLUMN HERE IS KNOWN AT PURCHASE TIME. That is the model's whole claim.
-- ============================================================================
-- Design Phase §8: the classifier may use only features available BEFORE
-- delivery completes. Training on `is_late` to predict a low review score would
-- produce a spectacular and useless model — spectacular because lateness is
-- nearly deterministic of a bad review (M5: 53.8% of late orders score 1), and
-- useless because by the time you know an order is late there is nothing left to
-- intervene on.
--
-- The allowlist is enforced again in `analysis/predictive.py`, because a model
-- reading straight from `mart_order_analysis` would have the banned columns in
-- reach. Two independent guards, neither relying on discipline.
--
-- ============================================================================
-- THE SUBTLE LEAK: SELLER HISTORY
-- ============================================================================
-- The single most useful pre-delivery feature is how often this seller has been
-- late before. Computed naively — `avg(is_late) group by seller` over the whole
-- table — it is a catastrophic leak: the average includes THIS order's outcome
-- and every future order's outcome, so the model reads the answer off a feature
-- that would be unavailable in production and would look excellent doing it.
--
-- These features are therefore computed AS-OF the purchase timestamp, counting
-- only what had already happened when the order was placed:
--
--   * late rate counts prior orders DELIVERED before this order was purchased
--   * low-score rate counts prior reviews ANSWERED before this order was
--     purchased — a review that exists but has not been written yet is not
--     information anyone had
--
-- Implemented as an event-stream window rather than a correlated subquery: the
-- obvious `(select ... where delivered_at < o.purchased_at)` form takes ~21
-- minutes over 96k rows. Interleaving deliveries and purchases into one stream
-- and taking a running total is O(n log n) and runs in seconds.
--
-- Ties: `is_event` ascending puts the purchase before a delivery recorded at the
-- same instant, so "before" stays strict.

with orders as (

    select
        a.order_id,
        a.primary_seller_id,
        a.purchased_at,
        o.delivered_at,
        o.review_answered_at,
        o.is_late,
        o.is_low_score
    from {{ ref('mart_order_analysis') }} a
    join {{ ref('fct_orders') }} o on o.order_id = a.order_id

),

-- One stream per seller: purchases (which ask the question) interleaved with
-- deliveries and review answers (which supply it).
delivery_events as (

    select primary_seller_id, delivered_at as event_at, 1 as is_event,
           is_late::int as late_flag, null::text as asking_order_id
    from orders
    where delivered_at is not null

    union all

    select primary_seller_id, purchased_at, 0, 0, order_id
    from orders

),

review_events as (

    select primary_seller_id, review_answered_at as event_at, 1 as is_event,
           is_low_score::int as low_flag, null::text as asking_order_id
    from orders
    where review_answered_at is not null

    union all

    select primary_seller_id, purchased_at, 0, 0, order_id
    from orders

),

seller_delivery_history as (

    select
        asking_order_id                                     as order_id,
        sum(is_event) over w                                as seller_prior_deliveries,
        sum(late_flag) over w                               as seller_prior_late
    from delivery_events
    window w as (
        partition by primary_seller_id
        order by event_at, is_event
        rows between unbounded preceding and current row
    )

),

seller_review_history as (

    select
        asking_order_id                                     as order_id,
        sum(is_event) over w                                as seller_prior_reviews,
        sum(low_flag) over w                                as seller_prior_low_scores
    from review_events
    window w as (
        partition by primary_seller_id
        order by event_at, is_event
        rows between unbounded preceding and current row
    )

)

select
    a.order_id,
    a.purchase_date,
    a.purchased_at,

    -- ---- Target -------------------------------------------------------------
    a.is_low_score,
    a.review_score,

    -- ---- The promise, and what it implies ------------------------------------
    a.estimated_days,

    -- ---- Basket --------------------------------------------------------------
    a.order_item_total,
    a.order_freight_total,
    a.freight_ratio,
    a.primary_item_price,
    a.item_count,
    a.product_count,
    a.seller_count,
    a.is_single_seller,

    -- ---- Product -------------------------------------------------------------
    a.primary_category,
    a.primary_product_weight_g,
    a.primary_product_volume_cm3,

    -- ---- Geography -----------------------------------------------------------
    a.seller_state,
    a.customer_state,
    a.is_same_state,
    a.distance_km,

    -- ---- Payment -------------------------------------------------------------
    a.payment_type,
    a.payment_installments,

    -- ---- Timing --------------------------------------------------------------
    a.purchase_year,
    a.purchase_month,
    a.purchase_day_of_week,
    a.purchased_on_weekend,
    a.season,

    -- ---- Seller track record, as-of the purchase timestamp -------------------
    coalesce(dh.seller_prior_deliveries, 0)                 as seller_prior_deliveries,
    coalesce(dh.seller_prior_late, 0)                       as seller_prior_late,
    case
        when coalesce(dh.seller_prior_deliveries, 0) = 0 then null
        else round(dh.seller_prior_late::numeric / dh.seller_prior_deliveries, 4)
    end                                                     as seller_prior_late_rate,

    coalesce(rh.seller_prior_reviews, 0)                    as seller_prior_reviews,
    case
        when coalesce(rh.seller_prior_reviews, 0) = 0 then null
        else round(rh.seller_prior_low_scores::numeric / rh.seller_prior_reviews, 4)
    end                                                     as seller_prior_low_score_rate

from {{ ref('mart_order_analysis') }} a
left join seller_delivery_history dh on dh.order_id = a.order_id
left join seller_review_history rh   on rh.order_id = a.order_id
where a.review_score is not null

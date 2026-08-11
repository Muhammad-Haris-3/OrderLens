-- Grain: (order_id, payment_sequential). 103,886 rows.
--
-- KEPT SEPARATE PRECISELY BECAUSE SUMMING IT INTO fct_orders WOULD DOUBLE-COUNT.
-- An order can split across several instruments, and installments carry interest:
-- M2 (A-24) measured payments exceeding item totals on 264 orders against falling
-- short on 39, a 6.8:1 asymmetry that is the signature of interest rather than of
-- noise. Payment-method analysis reads this model. Revenue analysis does not, and
-- fct_orders.order_value is built from items instead.
--
-- payment_type admits 'not_defined' — three real zero-value rows in the source
-- (A-25). Excluding it would fail the build on a known, harmless property of the
-- data, and a test that fails on something harmless is a test people learn to
-- ignore.

select
    p.order_id,
    p.payment_sequential,
    p.payment_type,
    p.payment_installments,
    p.payment_value,

    o.customer_unique_id,
    o.purchase_date,
    o.order_status,

    -- An order paid on several instruments has several rows here; this makes the
    -- split visible without needing a window function at query time.
    count(*) over (partition by p.order_id)     as instruments_used

from {{ ref('stg_order_payments') }} p
join {{ ref('fct_orders') }} o on o.order_id = p.order_id

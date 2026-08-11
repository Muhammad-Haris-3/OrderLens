-- Grain: (order_id, payment_sequential). 103,886 rows, zero excess (A-02).
--
-- This is NOT the source of order value. M2 (A-24) measured payments exceeding
-- item totals on 264 orders and falling short on 39 — a 6.8:1 asymmetry that is
-- the signature of installment interest. Revenue comes from order_items;
-- payment-method analysis reads this and nothing else does.

select
    order_id,
    payment_sequential::int                     as payment_sequential,
    payment_type,
    payment_installments::int                   as payment_installments,
    payment_value::numeric(12, 2)               as payment_value

from {{ source('raw', 'order_payments') }}

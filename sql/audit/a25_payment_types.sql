-- id: A-25
-- title: Payment instrument profile
-- question: Which payment types exist, and are any rows degenerate?
--
-- Feeds the accepted_values test on stg_order_payments. The point of interest
-- is not the credit-card share, it is whether the source contains placeholder
-- values that an accepted_values list must either admit or reject on purpose.

select
    payment_type,
    count(*)                                                      as rows,
    round(100.0 * count(*) / sum(count(*)) over (), 3)            as pct_of_rows,
    count(*) filter (where payment_value::numeric = 0)            as value_zero,
    count(*) filter (where payment_value::numeric < 0)            as value_negative,
    count(*) filter (where payment_installments::numeric = 0)     as installments_zero,
    max(payment_installments::numeric)                            as max_installments,
    round(sum(payment_value::numeric), 2)                         as total_value
from raw.order_payments
group by 1
order by 2 desc;

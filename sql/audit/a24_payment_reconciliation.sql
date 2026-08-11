-- id: A-24
-- title: Payments vs item totals
-- question: Do payments reconcile to order value, and if not, in which direction?
--
-- The data dictionary asserts that order_value must come from items rather than
-- payments, because payments carry installment interest and split across
-- instruments. This is that assertion tested rather than repeated: if payments
-- exceed items far more often than they fall short, the asymmetry is interest,
-- and summing payments would systematically overstate revenue.

with pay as (
    select order_id, sum(payment_value::numeric) as paid
    from raw.order_payments group by 1
),
itm as (
    select order_id, sum(price::numeric + freight_value::numeric) as owed
    from raw.order_items group by 1
)
select
    count(*)                                                        as orders_with_both,
    count(*) filter (where paid > owed + 0.01)                      as payments_exceed_items,
    count(*) filter (where paid < owed - 0.01)                      as payments_below_items,
    count(*) filter (where abs(paid - owed) <= 0.01)                as reconciled,
    round(max(paid - owed), 2)                                      as largest_overpayment,
    round(min(paid - owed), 2)                                      as largest_underpayment,
    round(sum(paid), 2)                                             as total_paid,
    round(sum(owed), 2)                                             as total_owed,
    round(sum(paid) - sum(owed), 2)                                 as difference
from pay join itm using (order_id);

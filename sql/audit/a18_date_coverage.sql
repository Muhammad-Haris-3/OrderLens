-- id: A-18
-- title: Monthly order volume — where does the data actually start and stop?
-- question: Is the observed date range the usable analysis window? (D-5)
--
-- min() and max() of the purchase timestamp describe the range but not the
-- coverage. A month with four orders is not a month of trading, and a trend
-- line drawn through it reports a collapse that never happened. The delivered
-- column matters just as much: orders placed at the very end were still in
-- flight when the extract was taken, so their delivery outcome is unknown
-- rather than good.

select
    to_char(date_trunc('month', order_purchase_timestamp::timestamp), 'YYYY-MM') as purchase_month,
    count(*)                                                                     as orders,
    count(*) filter (where order_status = 'delivered')                           as delivered,
    count(*) filter (where nullif(order_delivered_customer_date, '') is not null) as with_delivery_timestamp,
    round(100.0 * count(*) filter (where order_status = 'delivered') / count(*), 1) as pct_delivered
from raw.orders
group by 1
order by 1;

-- id: A-13
-- title: Delay distribution and outliers
-- question: How is delay_days distributed, and how extreme are the tails?
--
-- delay_days is the project's central independent variable. Reported here in
-- whole days from the calendar-day rule adopted in A-10, with percentiles
-- rather than a mean alone — the distribution is strongly asymmetric and a mean
-- would describe none of it.

with d as (
    select
        (nullif(order_delivered_customer_date, '')::timestamp::date
         - order_estimated_delivery_date::timestamp::date) as delay_days
    from raw.orders
    where order_status = 'delivered'
      and nullif(order_delivered_customer_date, '') is not null
)
select
    count(*)                                                                     as delivered_orders,
    min(delay_days)                                                              as min_delay_days,
    percentile_cont(0.01) within group (order by delay_days)                     as p01,
    percentile_cont(0.25) within group (order by delay_days)                     as p25,
    percentile_cont(0.50) within group (order by delay_days)                     as median,
    percentile_cont(0.75) within group (order by delay_days)                     as p75,
    percentile_cont(0.99) within group (order by delay_days)                     as p99,
    max(delay_days)                                                              as max_delay_days,
    round(avg(delay_days), 2)                                                    as mean_delay_days,
    count(*) filter (where delay_days > 0)                                       as late_orders,
    count(*) filter (where delay_days > 30)                                      as late_over_30_days,
    count(*) filter (where delay_days > 90)                                      as late_over_90_days,
    count(*) filter (where delay_days < -60)                                     as early_over_60_days
from d;

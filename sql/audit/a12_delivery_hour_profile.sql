-- id: A-12
-- title: What time of day do deliveries land?
-- question: How much of the day sits after midnight — i.e. how much of the
--   delivery volume the timestamp rule in A-10 would misclassify?
--
-- Supporting evidence for A-10. If deliveries clustered just after midnight the
-- boundary problem would be marginal. They do not: they cluster in the evening,
-- so essentially every on-the-promised-day delivery is hours past the midnight
-- the promise is stored at.

select
    extract(hour from nullif(order_delivered_customer_date, '')::timestamp)::int as hour_of_day,
    count(*)                                                                    as deliveries,
    round(100.0 * count(*) / sum(count(*)) over (), 2)                          as pct_of_deliveries
from raw.orders
where order_status = 'delivered'
  and nullif(order_delivered_customer_date, '') is not null
group by 1
order by 1;

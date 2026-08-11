-- id: A-07
-- title: Status contradicts the timestamps
-- question: Are there orders whose status and delivery timestamp disagree? (D-2)
--
-- Two contradictions are possible and both are present. Filtering delivery
-- analysis on status alone would admit orders with no delivery timestamp;
-- filtering on the timestamp alone would admit orders that were cancelled.
-- The eligibility rule has to satisfy both conditions, which is only obvious
-- once the contradiction is measured.

select
    'status = delivered but no delivery timestamp' as contradiction,
    order_status,
    count(*)                                        as orders
from raw.orders
where order_status = 'delivered'
  and nullif(order_delivered_customer_date, '') is null
group by 1, 2
union all
select
    'status <> delivered but a delivery timestamp exists',
    order_status,
    count(*)
from raw.orders
where order_status <> 'delivered'
  and nullif(order_delivered_customer_date, '') is not null
group by 1, 2
order by 1, 3 desc;

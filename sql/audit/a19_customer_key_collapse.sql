-- id: A-19
-- title: customer_id vs customer_unique_id — how many people are hidden? (risk R-1)
-- question: How many repeat customers exist, and how many orders would keying
--   retention on customer_id make invisible?
--
-- Measured in M1 §4 and re-run here as part of the audit proper, with the
-- frequency distribution added. R-1 is the highest-risk trap in the dataset
-- because the wrong key produces a perfectly unique, perfectly wrong dimension.

select
    orders_placed,
    count(*)                                                     as people,
    count(*) * orders_placed                                     as orders_represented,
    round(100.0 * count(*) / sum(count(*)) over (), 3)           as pct_of_people
from (
    select c.customer_unique_id, count(distinct o.order_id) as orders_placed
    from raw.customers c
    join raw.orders o on o.customer_id = c.customer_id
    group by 1
) t
group by 1
order by 1;

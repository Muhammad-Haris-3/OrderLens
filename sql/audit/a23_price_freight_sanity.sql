-- id: A-23
-- title: Price and freight plausibility
-- question: Are there zero, negative or absurd item values?
--
-- order_value is built from these two columns (data dictionary Part 2), so a
-- bad value here propagates into every revenue figure and into the freight_ratio
-- control used in the M5 regression.

select
    count(*)                                                          as items,
    count(*) filter (where price::numeric <= 0)                       as price_zero_or_negative,
    count(*) filter (where freight_value::numeric < 0)                as freight_negative,
    count(*) filter (where freight_value::numeric = 0)                as freight_exactly_zero,
    count(distinct order_id) filter (where freight_value::numeric = 0) as orders_with_free_freight,
    min(price::numeric)                                               as min_price,
    round(avg(price::numeric), 2)                                     as mean_price,
    percentile_cont(0.50) within group (order by price::numeric)      as median_price,
    max(price::numeric)                                               as max_price,
    min(freight_value::numeric)                                       as min_freight,
    max(freight_value::numeric)                                       as max_freight
from raw.order_items;

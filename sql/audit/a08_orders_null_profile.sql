-- id: A-08
-- title: Null profile of the orders table
-- question: Which order columns are incomplete, and by how much?
--
-- Raw is all text, so "missing" is either SQL NULL or the empty string that
-- COPY writes for an empty CSV field. Both are counted here — a null check that
-- misses the empty-string case reports a clean table that is not clean.

select
    'order_id'                       as column_name,
    count(*)                         as rows,
    count(*) filter (where order_id is null)      as sql_nulls,
    count(*) filter (where order_id = '')         as empty_strings,
    round(100.0 * count(*) filter (where nullif(order_id, '') is null) / count(*), 3) as pct_missing
from raw.orders
union all
select 'customer_id', count(*),
       count(*) filter (where customer_id is null),
       count(*) filter (where customer_id = ''),
       round(100.0 * count(*) filter (where nullif(customer_id, '') is null) / count(*), 3)
from raw.orders
union all
select 'order_status', count(*),
       count(*) filter (where order_status is null),
       count(*) filter (where order_status = ''),
       round(100.0 * count(*) filter (where nullif(order_status, '') is null) / count(*), 3)
from raw.orders
union all
select 'order_purchase_timestamp', count(*),
       count(*) filter (where order_purchase_timestamp is null),
       count(*) filter (where order_purchase_timestamp = ''),
       round(100.0 * count(*) filter (where nullif(order_purchase_timestamp, '') is null) / count(*), 3)
from raw.orders
union all
select 'order_approved_at', count(*),
       count(*) filter (where order_approved_at is null),
       count(*) filter (where order_approved_at = ''),
       round(100.0 * count(*) filter (where nullif(order_approved_at, '') is null) / count(*), 3)
from raw.orders
union all
select 'order_delivered_carrier_date', count(*),
       count(*) filter (where order_delivered_carrier_date is null),
       count(*) filter (where order_delivered_carrier_date = ''),
       round(100.0 * count(*) filter (where nullif(order_delivered_carrier_date, '') is null) / count(*), 3)
from raw.orders
union all
select 'order_delivered_customer_date', count(*),
       count(*) filter (where order_delivered_customer_date is null),
       count(*) filter (where order_delivered_customer_date = ''),
       round(100.0 * count(*) filter (where nullif(order_delivered_customer_date, '') is null) / count(*), 3)
from raw.orders
union all
select 'order_estimated_delivery_date', count(*),
       count(*) filter (where order_estimated_delivery_date is null),
       count(*) filter (where order_estimated_delivery_date = ''),
       round(100.0 * count(*) filter (where nullif(order_estimated_delivery_date, '') is null) / count(*), 3)
from raw.orders
order by pct_missing desc;

-- Grain: one customer_id — the PER-ORDER key. 99,441 rows.
--
-- This model does NOT deduplicate to the person. That is dim_customers' job,
-- keyed on customer_unique_id (risk R-1). Staging is 1:1 with its source and
-- collapsing here would hide the collapse.
--
-- The numbers, from A-19: 99,441 customer_id values map to 96,096 people, of whom
-- 2,997 placed more than one order. Key retention on customer_id and every one of
-- those people becomes a first-time buyer — a wrong answer with a perfectly
-- unique key, which is why no schema test can catch it.

select
    customer_id,
    customer_unique_id,
    customer_zip_code_prefix                    as zip_prefix,
    customer_city                               as city,
    upper(customer_state)                       as state

from {{ source('raw', 'customers') }}

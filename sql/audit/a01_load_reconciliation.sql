-- id: A-01
-- title: Load reconciliation — does the warehouse still match the source files?
-- question: Did every row in every CSV land, and is the warehouse still in that state?
--
-- The audit begins by re-establishing that the thing being audited is what M1
-- loaded. raw.load_log records what the loader believed at load time; this
-- compares that against what the tables actually hold now.

with actual (table_name, rows_now) as (
    select 'raw.orders',                        count(*) from raw.orders
    union all select 'raw.order_items',         count(*) from raw.order_items
    union all select 'raw.order_payments',      count(*) from raw.order_payments
    union all select 'raw.order_reviews',       count(*) from raw.order_reviews
    union all select 'raw.customers',           count(*) from raw.customers
    union all select 'raw.sellers',             count(*) from raw.sellers
    union all select 'raw.products',            count(*) from raw.products
    union all select 'raw.product_category_translation', count(*) from raw.product_category_translation
    union all select 'raw.geolocation',         count(*) from raw.geolocation
),
latest_load as (
    select distinct on (table_name) table_name, rows_in_file, rows_loaded, loaded_at
    from raw.load_log
    order by table_name, id desc
)
select
    a.table_name,
    l.rows_in_file,
    l.rows_loaded,
    a.rows_now,
    case
        when l.rows_in_file is null                       then 'NOT LOGGED'
        when l.rows_in_file = l.rows_loaded
         and l.rows_loaded  = a.rows_now                  then 'OK'
        else 'MISMATCH'
    end as status,
    l.loaded_at
from actual a
left join latest_load l using (table_name)
order by a.rows_now desc;

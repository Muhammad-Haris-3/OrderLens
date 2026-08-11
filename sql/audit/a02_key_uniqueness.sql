-- id: A-02
-- title: Declared grain — is every table's stated key actually unique?
-- question: Where does the documented grain fail to hold in the source?
--
-- The Design Phase declares a grain for every model. This tests those claims
-- against the raw data before any model is built on them. A grain that is wrong
-- does not fail loudly — it silently double-counts.

select 'raw.orders (order_id)'                            as declared_grain,
       count(*)                                           as rows,
       count(distinct order_id)                           as distinct_keys,
       count(*) - count(distinct order_id)                as excess_rows
from raw.orders
union all
select 'raw.order_items (order_id, order_item_id)',
       count(*), count(distinct (order_id, order_item_id)),
       count(*) - count(distinct (order_id, order_item_id))
from raw.order_items
union all
select 'raw.order_payments (order_id, payment_sequential)',
       count(*), count(distinct (order_id, payment_sequential)),
       count(*) - count(distinct (order_id, payment_sequential))
from raw.order_payments
union all
select 'raw.order_reviews (review_id)',
       count(*), count(distinct review_id), count(*) - count(distinct review_id)
from raw.order_reviews
union all
select 'raw.order_reviews (order_id)',
       count(*), count(distinct order_id), count(*) - count(distinct order_id)
from raw.order_reviews
union all
-- Whole-row check: distinguishes a genuinely repeated row, which can simply be
-- deleted, from a shared key across different rows, which cannot.
select 'raw.order_reviews (whole row)',
       count(*),
       count(distinct (review_id, order_id, review_score, review_creation_date)),
       count(*) - count(distinct (review_id, order_id, review_score, review_creation_date))
from raw.order_reviews
union all
select 'raw.customers (customer_id)',
       count(*), count(distinct customer_id), count(*) - count(distinct customer_id)
from raw.customers
union all
select 'raw.sellers (seller_id)',
       count(*), count(distinct seller_id), count(*) - count(distinct seller_id)
from raw.sellers
union all
select 'raw.products (product_id)',
       count(*), count(distinct product_id), count(*) - count(distinct product_id)
from raw.products
union all
select 'raw.product_category_translation (product_category_name)',
       count(*), count(distinct product_category_name),
       count(*) - count(distinct product_category_name)
from raw.product_category_translation
union all
select 'raw.geolocation (zip prefix) — expected NOT unique',
       count(*), count(distinct geolocation_zip_code_prefix),
       count(*) - count(distinct geolocation_zip_code_prefix)
from raw.geolocation
order by excess_rows desc;

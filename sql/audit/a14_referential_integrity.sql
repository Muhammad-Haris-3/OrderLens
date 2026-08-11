-- id: A-14
-- title: Referential integrity — orphans in both directions
-- question: Are there child rows with no parent, and parents with no children? (D-4)
--
-- Both directions matter and they mean different things. A child with no parent
-- is corruption and the relationship test must fail on it. A parent with no
-- child is usually a real business state — an order that was never fulfilled
-- still exists — and failing a test on it would be wrong.

select 'items with no parent order'      as check_name, count(*) as rows, 'corruption' as severity
from raw.order_items i
where not exists (select 1 from raw.orders o where o.order_id = i.order_id)
union all
select 'payments with no parent order', count(*), 'corruption'
from raw.order_payments p
where not exists (select 1 from raw.orders o where o.order_id = p.order_id)
union all
select 'reviews with no parent order', count(*), 'corruption'
from raw.order_reviews r
where not exists (select 1 from raw.orders o where o.order_id = r.order_id)
union all
select 'orders with no customer record', count(*), 'corruption'
from raw.orders o
where not exists (select 1 from raw.customers c where c.customer_id = o.customer_id)
union all
select 'items referencing an unknown product', count(*), 'corruption'
from raw.order_items i
where not exists (select 1 from raw.products p where p.product_id = i.product_id)
union all
select 'items referencing an unknown seller', count(*), 'corruption'
from raw.order_items i
where not exists (select 1 from raw.sellers s where s.seller_id = i.seller_id)
union all
select 'orders with no items', count(*), 'business state'
from raw.orders o
where not exists (select 1 from raw.order_items i where i.order_id = o.order_id)
union all
select 'orders with no payment', count(*), 'business state'
from raw.orders o
where not exists (select 1 from raw.order_payments p where p.order_id = o.order_id)
union all
select 'orders with no review', count(*), 'business state'
from raw.orders o
where not exists (select 1 from raw.order_reviews r where r.order_id = o.order_id)
union all
select 'customers never used by an order', count(*), 'business state'
from raw.customers c
where not exists (select 1 from raw.orders o where o.customer_id = c.customer_id)
union all
select 'sellers with nothing sold', count(*), 'business state'
from raw.sellers s
where not exists (select 1 from raw.order_items i where i.seller_id = s.seller_id)
union all
select 'products never ordered', count(*), 'business state'
from raw.products p
where not exists (select 1 from raw.order_items i where i.product_id = p.product_id)
order by severity, rows desc;

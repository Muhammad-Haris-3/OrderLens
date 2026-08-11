-- id: A-03
-- title: Review grain — how many rows per review_id and per order_id?
-- question: Is "one review per order" true? (Design Phase decision D-1)
--
-- The data dictionary records review_id as "not reliably unique" without a
-- number attached. This attaches the number — and checks the other key too,
-- because order_id is the one the fact table will actually join on.

select 'rows per review_id' as key, n_rows, count(*) as keys, count(*) * n_rows as rows_involved
from (select review_id, count(*) as n_rows from raw.order_reviews group by 1) t
group by 1, 2
union all
select 'rows per order_id', n_rows, count(*), count(*) * n_rows
from (select order_id, count(*) as n_rows from raw.order_reviews group by 1) t
group by 1, 2
order by key, n_rows;

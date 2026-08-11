-- id: A-21
-- title: Geolocation coverage — which ZIP prefixes have no coordinates?
-- question: How many customers and sellers cannot be placed on a map?
--
-- Aggregating geolocation solves the fan-out (A-20) but not the coverage.
-- Prefixes absent from the lookup make the geography join a LEFT JOIN with a
-- null centroid, not an INNER JOIN — otherwise these rows leave the fact table
-- entirely and every geographic total quietly under-reports.

select
    'customers'                                                       as side,
    count(*)                                                          as rows,
    count(*) filter (where g.zip_prefix is null)                      as rows_without_coordinates,
    round(100.0 * count(*) filter (where g.zip_prefix is null) / count(*), 3) as pct_without,
    count(distinct c.customer_zip_code_prefix)                        as distinct_prefixes,
    count(distinct c.customer_zip_code_prefix) filter (where g.zip_prefix is null)
                                                                      as distinct_prefixes_without
from raw.customers c
left join (select distinct geolocation_zip_code_prefix as zip_prefix from raw.geolocation) g
       on g.zip_prefix = c.customer_zip_code_prefix
union all
select
    'sellers',
    count(*),
    count(*) filter (where g.zip_prefix is null),
    round(100.0 * count(*) filter (where g.zip_prefix is null) / count(*), 3),
    count(distinct s.seller_zip_code_prefix),
    count(distinct s.seller_zip_code_prefix) filter (where g.zip_prefix is null)
from raw.sellers s
left join (select distinct geolocation_zip_code_prefix as zip_prefix from raw.geolocation) g
       on g.zip_prefix = s.seller_zip_code_prefix;

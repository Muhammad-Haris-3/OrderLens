-- BESPOKE TEST — risk R-2 and any other fan-out.
--
-- fct_orders joins customers, items and reviews. If any of those joins acquires a
-- duplicate on the right-hand side, the fact table gains rows and every revenue
-- figure inflates. The classic case is joining raw geolocation directly, which
-- multiplies rows by 52.6 (M2 A-20) while producing perfectly valid output that
-- passes uniqueness, not-null and referential tests alike.
--
-- The `unique` test on order_id catches duplication. It does NOT catch loss — an
-- accidental INNER JOIN to items would silently delete the 775 item-less orders
-- (M2 F-04) and still leave order_id unique. This asserts equality in both
-- directions.

select
    (select count(*) from {{ ref('fct_orders') }})  as fct_rows,
    (select count(*) from {{ ref('stg_orders') }})  as stg_rows
where
    (select count(*) from {{ ref('fct_orders') }})
    <> (select count(*) from {{ ref('stg_orders') }})

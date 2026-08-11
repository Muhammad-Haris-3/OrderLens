-- Grain: one seller_id. 3,095 rows.
--
-- LEFT JOIN to the geolocation centroid (M2 finding F-07). Seven sellers have a
-- ZIP prefix with no row in the geolocation table at all. An inner join would
-- drop them from the dimension and, through the relationship test, take their
-- order items with them — quietly under-reporting seller revenue with nothing
-- failing.
--
-- Their latitude and longitude are null. Distance features in M6 must handle
-- null rather than assume coverage.

select
    s.seller_id,
    s.zip_prefix,
    s.city,
    s.state,
    {{ brazil_region('s.state') }}              as region,

    g.latitude,
    g.longitude,
    g.source_point_count                        as centroid_point_count,
    g.zip_prefix is not null                    as has_coordinates

from {{ ref('stg_sellers') }} s
left join {{ ref('stg_geolocation') }} g on g.zip_prefix = s.zip_prefix

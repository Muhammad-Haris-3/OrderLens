-- Grain: one ZIP prefix. ~19,010 rows.
--
-- A thin pass over stg_geolocation plus the macro-region grouping BQ-4 segments
-- on. The fan-out was already killed upstream (stg_geolocation, risk R-2); this
-- model inherits one row per prefix and must not reintroduce a join that breaks
-- it, which is what the uniqueness test here is for.
--
-- centroid_point_count is carried forward deliberately. A centroid averaged from
-- two points and one averaged from eleven hundred are not equally trustworthy,
-- and a map that renders them identically invites a confident conclusion drawn
-- from almost nothing.

select
    zip_prefix,
    city,
    state,
    {{ brazil_region('state') }}                as region,
    latitude,
    longitude,
    source_point_count                          as centroid_point_count

from {{ ref('stg_geolocation') }}

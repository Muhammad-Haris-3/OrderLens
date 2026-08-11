-- BESPOKE TEST — M2 finding F-13.
--
-- 42 source coordinates fall outside Brazil across 21 ZIP prefixes (A-22).
-- stg_geolocation discards them BEFORE averaging, which is the only place in this
-- pipeline where a row is thrown away rather than flagged.
--
-- Averaging is what makes the discard necessary and this test necessary in turn:
-- a single point in the wrong hemisphere does not produce an obviously wrong
-- centroid, it produces a plausible one that is a few hundred kilometres off,
-- along with every distance derived from it. The bounds come from the same
-- project variables the filter uses, so the two cannot drift apart.

select
    zip_prefix,
    latitude,
    longitude,
    centroid_point_count
from {{ ref('dim_geography') }}
where latitude  not between {{ var('brazil_min_lat') }} and {{ var('brazil_max_lat') }}
   or longitude not between {{ var('brazil_min_lng') }} and {{ var('brazil_max_lng') }}

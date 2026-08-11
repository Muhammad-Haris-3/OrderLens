-- Grain: one ZIP prefix. ~19,015 rows from 1,000,163 source rows.
--
-- THIS IS THE MODEL THAT KILLS RISK R-2. The source carries 52.6 rows per prefix
-- on average and up to 1,146 for a single prefix (A-20). Joined un-aggregated to
-- any fact table it multiplies rows by roughly fifty and inflates every revenue
-- figure by the same factor — while producing perfectly valid-looking rows that
-- no schema test would reject. The uniqueness test on zip_prefix below is the
-- assertion that this is dead.
--
-- MEAN coordinates for the centroid, but MODAL city and state. A prefix
-- frequently disagrees with itself: 8,556 of 19,015 (45%) carry more than one
-- spelling of their own city name, and 8 span more than one state (A-20). An
-- arbitrary pick would silently choose a typo as canonical for 45% of Brazil.
--
-- OUT-OF-BOUNDS POINTS ARE DISCARDED BEFORE AVERAGING (M2 finding F-13). 42 rows
-- fall outside Brazil's bounding box across 21 prefixes (A-22). This is the only
-- place in the whole pipeline where a row is thrown away rather than flagged, and
-- the justification is narrow: an impossible coordinate contributes nothing
-- recoverable to a mean, but one point in the wrong hemisphere drags an entire
-- ZIP prefix — and every distance derived from it — off the map. 42 rows in a
-- million cannot meaningfully thin any prefix.
--
-- source_point_count is retained so a centroid resting on two points can be
-- spotted rather than trusted like one resting on a thousand.

with bounded as (

    select
        geolocation_zip_code_prefix             as zip_prefix,
        geolocation_lat::numeric                as latitude,
        geolocation_lng::numeric                as longitude,
        geolocation_city                        as city,
        upper(geolocation_state)                as state
    from {{ source('raw', 'geolocation') }}
    where geolocation_lat::numeric between {{ var('brazil_min_lat') }} and {{ var('brazil_max_lat') }}
      and geolocation_lng::numeric between {{ var('brazil_min_lng') }} and {{ var('brazil_max_lng') }}

)

select
    zip_prefix,
    avg(latitude)                                       as latitude,
    avg(longitude)                                      as longitude,
    mode() within group (order by city)                 as city,
    mode() within group (order by state)                as state,
    count(*)                                            as source_point_count
from bounded
group by zip_prefix

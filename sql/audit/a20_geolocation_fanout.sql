-- id: A-20
-- title: Geolocation fan-out and internal consistency (risk R-2)
-- question: How badly would an un-aggregated geolocation join multiply fact rows,
--   and is a prefix internally consistent about where it is?
--
-- The fan-out ratio is R-2 restated as a number. The consistency columns justify
-- the aggregation rule chosen in the Design Phase §3.9: mean coordinates but
-- MODAL city and state, because a prefix frequently disagrees with itself about
-- its own city name.

with per_prefix as (
    select
        geolocation_zip_code_prefix                as zip_prefix,
        count(*)                                   as rows_in_prefix,
        count(distinct geolocation_city)           as distinct_cities,
        count(distinct geolocation_state)          as distinct_states
    from raw.geolocation
    group by 1
)
select
    sum(rows_in_prefix)                                              as geolocation_rows,
    count(*)                                                         as distinct_prefixes,
    round(sum(rows_in_prefix)::numeric / count(*), 1)                as mean_rows_per_prefix,
    max(rows_in_prefix)                                              as max_rows_for_one_prefix,
    count(*) filter (where distinct_cities > 1)                      as prefixes_with_several_city_names,
    count(*) filter (where distinct_states > 1)                      as prefixes_with_several_states
from per_prefix;

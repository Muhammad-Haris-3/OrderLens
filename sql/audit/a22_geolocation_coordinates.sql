-- id: A-22
-- title: Are the coordinates actually in Brazil?
-- question: How many geolocation points fall outside Brazil's bounding box?
--
-- Bounding box: latitude -34 to +6, longitude -74 to -33. A point outside it is
-- not a rounding error, it is a wrong number. These rows are averaged into a
-- prefix centroid in stg_geolocation, so one point in the wrong hemisphere
-- drags a whole ZIP prefix off the map and any distance derived from it.

select
    count(*)                                                            as geolocation_rows,
    count(*) filter (where geolocation_lat::numeric not between -34 and 6)   as latitude_outside_brazil,
    count(*) filter (where geolocation_lng::numeric not between -74 and -33) as longitude_outside_brazil,
    count(*) filter (where geolocation_lat::numeric not between -34 and 6
                        or geolocation_lng::numeric not between -74 and -33) as points_outside_brazil,
    count(distinct geolocation_zip_code_prefix) filter (
        where geolocation_lat::numeric not between -34 and 6
           or geolocation_lng::numeric not between -74 and -33)              as prefixes_affected,
    count(distinct geolocation_state)                                        as distinct_states
from raw.geolocation;

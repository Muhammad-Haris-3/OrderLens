-- Grain: one product_id. 32,951 rows.
--
-- Corrects the source misspellings at the boundary: product_name_lenght ->
-- product_name_length. Raw preserves the typo for fidelity; nothing downstream
-- repeats it.
--
-- ZERO WEIGHT IS SET TO NULL (M2 finding F-15). Four products record a weight of
-- 0 g. A product does not weigh nothing — zero here is an unrecorded value
-- wearing a number's clothes, and left alone it would corrupt any density
-- feature derived from it in M6. Null says "unknown", which is what it is.
--
-- Dimensions are guarded the same way even though A-26 found no zero dimension:
-- the guard costs nothing and the volume calculation must not silently produce 0.

with typed as (

    select
        product_id,
        nullif(product_category_name, '')                       as category_pt,
        nullif(product_name_lenght, '')::int                    as product_name_length,
        nullif(product_description_lenght, '')::int             as product_description_length,
        nullif(product_photos_qty, '')::int                     as product_photos_qty,
        nullif(nullif(product_weight_g, '')::numeric, 0)        as product_weight_g,
        nullif(nullif(product_length_cm, '')::numeric, 0)       as product_length_cm,
        nullif(nullif(product_height_cm, '')::numeric, 0)       as product_height_cm,
        nullif(nullif(product_width_cm, '')::numeric, 0)        as product_width_cm
    from {{ source('raw', 'products') }}

)

select
    *,
    product_length_cm * product_height_cm * product_width_cm    as product_volume_cm3
from typed

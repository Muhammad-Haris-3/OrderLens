-- id: A-26
-- title: Product attribute completeness
-- question: Are weight and dimensions usable as model features?
--
-- The M6 classifier may use product physical attributes — they are known before
-- delivery, so they are inside the leakage allowlist. Whether they are usable
-- depends on whether they are populated and non-degenerate. A zero-weight
-- product is not light, it is unrecorded, and imputing a mean over it would
-- invent data.

select
    count(*)                                                              as products,
    count(*) filter (where nullif(product_category_name, '') is null)     as missing_category,
    count(*) filter (where nullif(product_weight_g, '') is null)          as missing_weight,
    count(*) filter (where nullif(product_length_cm, '') is null)         as missing_length,
    count(*) filter (where nullif(product_photos_qty, '') is null)        as missing_photo_count,
    count(*) filter (where nullif(product_weight_g, '')::numeric = 0)     as weight_zero,
    count(*) filter (where nullif(product_length_cm, '')::numeric = 0
                        or nullif(product_height_cm, '')::numeric = 0
                        or nullif(product_width_cm,  '')::numeric = 0)    as any_dimension_zero,
    max(nullif(product_weight_g, '')::numeric)                            as max_weight_g
from raw.products;

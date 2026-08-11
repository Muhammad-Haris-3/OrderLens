-- Grain: one Portuguese category name. 71 rows.
--
-- Straight passthrough — staging reflects the source as it is. The lookup is
-- incomplete (71 rows against 73 categories actually in use, A-16) and that is
-- handled in dim_products, not here. Patching the gap at this layer would mean
-- staging no longer matches its source, and the next person to diff the two
-- would find a discrepancy with no explanation attached to it.

select
    product_category_name                       as category_pt,
    product_category_name_english               as category_en

from {{ source('raw', 'product_category_translation') }}

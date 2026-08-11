-- Grain: one product_id. 32,951 rows.
--
-- LEFT JOIN, NEVER INNER (M2 finding F-05, decision D-3). 623 products never
-- reach an English category name: 610 have no category at all, and 13 carry a
-- category genuinely absent from the 71-row lookup — pc_gamer and
-- portateis_cozinha_e_preparadores_de_alimentos.
--
-- An inner join would silently delete R$185,049.76 of item revenue across 1,473
-- orders (A-17), and the category report that came out the other side would look
-- perfectly clean, because every row remaining in it would be correct.
--
-- category_source records WHICH step of the coalesce fired, because the two
-- causes are different things. pc_gamer has an accurate, usable Portuguese name
-- and a gap in the lookup table; a product with no category at all is missing
-- data. Collapsing both into one boolean would stop M4 from stating honestly
-- what share of category revenue is actually attributable.

select
    p.product_id,

    coalesce(t.category_en, p.category_pt, 'uncategorised')     as category,
    p.category_pt,
    case
        when t.category_en is not null then 'translated'
        when p.category_pt is not null then 'portuguese_fallback'
        else 'missing'
    end                                                         as category_source,

    p.product_name_length,
    p.product_description_length,
    p.product_photos_qty,
    p.product_weight_g,
    p.product_length_cm,
    p.product_height_cm,
    p.product_width_cm,
    p.product_volume_cm3

from {{ ref('stg_products') }} p
left join {{ ref('stg_product_categories') }} t on t.category_pt = p.category_pt

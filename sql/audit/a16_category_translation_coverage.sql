-- id: A-16
-- title: Product category translation coverage
-- question: How many products fail to reach an English category name, and why? (D-3)
--
-- Found in M1 §5 while verifying the BOM fix. Split by cause because the two
-- causes need different handling: a product with no category at all is missing
-- data, while a category absent from the translation file is a gap in the
-- lookup table and the Portuguese name is still perfectly usable.

select
    (select count(*) from raw.products)                                as products,
    (select count(*) from raw.products p
      join raw.product_category_translation t
        on t.product_category_name = p.product_category_name)          as translated,
    (select count(*) from raw.products
      where nullif(product_category_name, '') is null)                 as no_category_at_all,
    (select count(*) from raw.products p
      where nullif(p.product_category_name, '') is not null
        and not exists (select 1 from raw.product_category_translation t
                        where t.product_category_name = p.product_category_name))
                                                                       as category_missing_from_lookup,
    (select count(*) from raw.product_category_translation)            as lookup_rows,
    (select count(distinct product_category_name) from raw.products
      where nullif(product_category_name, '') is not null)             as distinct_categories_in_use;

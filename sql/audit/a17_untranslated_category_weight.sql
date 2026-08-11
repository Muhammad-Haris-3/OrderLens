-- id: A-17
-- title: What is at stake in the untranslated categories?
-- question: How much order volume and revenue would an INNER JOIN on the
--   category lookup silently delete? (D-3)
--
-- A coverage percentage is not a decision input; revenue is. This converts the
-- gap from "623 products" into the money that would disappear from category
-- analysis if the join were written the obvious wrong way.

select
    coalesce(p.product_category_name, '(no category)')       as category_pt,
    case
        when nullif(p.product_category_name, '') is null then 'no category at all'
        else 'missing from lookup'
    end                                                       as cause,
    count(distinct p.product_id)                              as products,
    count(i.order_id)                                         as order_items,
    count(distinct i.order_id)                                as orders,
    round(coalesce(sum(i.price::numeric), 0), 2)              as item_revenue
from raw.products p
left join raw.order_items i on i.product_id = p.product_id
where nullif(p.product_category_name, '') is null
   or not exists (select 1 from raw.product_category_translation t
                  where t.product_category_name = p.product_category_name)
group by 1, 2
order by item_revenue desc;

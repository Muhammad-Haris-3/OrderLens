-- id: A-04
-- title: Review duplication — what shape is it, and do duplicates disagree?
-- question: Are duplicated review_ids the same review repeated, or one review
--   spanning several orders? Do orders with several reviews agree on the score? (D-1)
--
-- The shape decides the fix. A repeated identical row is deleted. A review_id
-- shared across genuinely different orders is a survey covering a basket, and
-- deleting it would throw away real satisfaction data. Two reviews on one order
-- that disagree on the score need a tie-break rule, not a delete.

select 'duplicated review_id groups' as finding,
       count(*)                                        as groups,
       count(*) filter (where n_orders > 1)            as spanning_several_orders,
       count(*) filter (where n_scores > 1)            as with_disagreeing_scores
from (
    select r.review_id,
           count(distinct r.order_id)    as n_orders,
           count(distinct r.review_score) as n_scores
    from raw.order_reviews r
    where r.review_id in (select review_id from raw.order_reviews group by 1 having count(*) > 1)
    group by 1
) t
union all
select 'orders with several reviews',
       count(*),
       null,
       count(*) filter (where n_scores > 1)
from (
    select r.order_id, count(distinct r.review_score) as n_scores
    from raw.order_reviews r
    where r.order_id in (select order_id from raw.order_reviews group by 1 having count(*) > 1)
    group by 1
) t
order by 1;

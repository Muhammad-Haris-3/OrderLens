-- id: A-28
-- title: Review score distribution and comment completeness
-- question: How skewed are the scores, and how much free text is actually there?
--
-- The SRS asserts the scores are skewed toward 5 and that mean-based summaries
-- will mislead (§6.3). This measures the skew so M5 can justify rank-based tests
-- rather than assert them. Comment coverage is recorded because an analysis that
-- reaches for review text later needs to know how much of it exists first.

select
    review_score,
    count(*)                                                                  as reviews,
    round(100.0 * count(*) / sum(count(*)) over (), 2)                        as pct_of_reviews,
    count(*) filter (where nullif(review_comment_title, '') is not null)      as with_title,
    count(*) filter (where nullif(review_comment_message, '') is not null)    as with_message,
    round(100.0 * count(*) filter (where nullif(review_comment_message, '') is not null)
          / count(*), 1)                                                      as pct_with_message
from raw.order_reviews
group by 1
order by 1;

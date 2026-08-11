-- id: A-05
-- title: Review dedup — does the choice of rule change the headline numbers?
-- question: How much does keeping the latest review per order differ from keeping
--   the earliest, or from leaving the duplicates in? (D-1)
--
-- A dedup rule is only worth arguing about if it moves a number. This measures
-- the movement before the rule is chosen, so the choice can be made on evidence
-- rather than on taste — and so the audit can say honestly how much it matters.

with ranked as (
    select
        order_id,
        review_score::int as score,
        row_number() over (partition by order_id
            order by review_answer_timestamp::timestamp desc, review_id) as rn_latest,
        row_number() over (partition by order_id
            order by review_answer_timestamp::timestamp asc,  review_id) as rn_earliest
    from raw.order_reviews
)
select
    count(*)                                       as rows_before_dedup,
    count(*) filter (where rn_latest = 1)          as rows_after_dedup,
    round(avg(score), 4)                           as mean_score_all_rows,
    round(avg(score) filter (where rn_latest = 1), 4)   as mean_score_keep_latest,
    round(avg(score) filter (where rn_earliest = 1), 4) as mean_score_keep_earliest,
    round(100.0 * count(*) filter (where score <= 2) / count(*), 3)
                                                   as pct_low_score_all_rows,
    round(100.0 * count(*) filter (where rn_latest = 1 and score <= 2)
          / nullif(count(*) filter (where rn_latest = 1), 0), 3)
                                                   as pct_low_score_keep_latest,
    round(100.0 * count(*) filter (where rn_earliest = 1 and score <= 2)
          / nullif(count(*) filter (where rn_earliest = 1), 0), 3)
                                                   as pct_low_score_keep_earliest
from ranked;

-- Grain: one order_id. 98,673 rows from 99,224 source rows.
--
-- M2 decision D-1 (finding F-02). "One review per order" is false in the source:
-- 547 orders carry several reviews and 202 of those disagree on the score. The
-- fact table joins on order_id, so without a rule those 551 excess rows weight
-- 547 orders twice in every downstream join.
--
-- KEEP LATEST by review_answer_timestamp. Where a customer responded twice, the
-- second response is the settled opinion. The review_id tie-break is not
-- decoration — without it two builds of identical data can pick different rows,
-- and a warehouse that disagrees with itself between runs is unusable.
--
-- review_id is NOT the grain and is never tested for uniqueness. 789 review_ids
-- appear against several DIFFERENT orders, always agreeing on the score: that is
-- one survey covering a basket, not a duplicated row, and deleting those rows
-- would discard real satisfaction data.
--
-- review_count is carried so the 547 collapsed orders stay visible downstream
-- rather than silently becoming ordinary single-review orders.

with typed as (

    select
        review_id,
        order_id,
        review_score::int                                   as review_score,
        nullif(review_comment_title, '')                    as review_comment_title,
        nullif(review_comment_message, '')                  as review_comment_message,
        review_creation_date::timestamp                     as survey_created_at,
        review_answer_timestamp::timestamp                  as answered_at
    from {{ source('raw', 'order_reviews') }}

),

counted as (

    select
        *,
        count(*) over (partition by order_id)               as review_count
    from typed

)

select distinct on (order_id)
    order_id,
    review_id,
    review_score,
    review_score <= 2                                       as is_low_score,
    review_comment_title,
    review_comment_message,
    review_comment_message is not null                      as has_comment,
    survey_created_at,
    answered_at,
    review_count
from counted
order by order_id, answered_at desc, review_id

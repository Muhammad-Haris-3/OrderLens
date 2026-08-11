-- BESPOKE TEST — risk R-1, the highest-risk trap in this dataset.
--
-- Every schema test on dim_customers passes if the model is keyed on customer_id
-- instead of customer_unique_id. The key is still unique, the row count is still
-- plausible, nothing is null. The only symptom is that 2,997 repeat customers
-- become first-time buyers and every retention and RFM figure in M4 is wrong.
--
-- A test can only catch that by asserting something about MEANING. This one
-- asserts repeat customers exist at all. Keyed on the per-order id, the count is
-- exactly zero and this test is the only thing in the project that notices.
--
-- The threshold is 1,000, not 1: a partial regression that leaves a handful of
-- repeats should fail too. M2 (A-19) measured 2,997.

select
    count(*) as repeat_customers
from {{ ref('dim_customers') }}
where is_repeat_customer
having count(*) < 1000

-- BESPOKE TEST — FR-8. The Pareto arithmetic must actually add up.
--
-- cumulative_pct_of_revenue is a window function over a partition. If the
-- partitioning or the ordering is wrong the column still populates, still rises,
-- and still looks like a concentration curve — it just describes the wrong
-- denominator. Every "the top N sellers make X% of revenue" claim in M4 reads
-- straight off it.
--
-- The last row of each dimension must reach 100%. Tolerance is 0.01 for the
-- rounding applied in the model, not for drift.

select
    dimension,
    max(cumulative_pct_of_revenue)  as final_cumulative_pct,
    sum(pct_of_revenue)             as summed_pct
from {{ ref('mart_revenue_concentration') }}
group by dimension
having abs(max(cumulative_pct_of_revenue) - 100) > 0.01
    or abs(sum(pct_of_revenue) - 100) > 0.01

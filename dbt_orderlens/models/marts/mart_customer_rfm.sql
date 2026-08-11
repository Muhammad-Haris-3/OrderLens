-- FR-7 — RFM segmentation. Grain: one customer_unique_id. ~96,096 rows.
--
-- ============================================================================
-- THE FREQUENCY DIMENSION IS DEGENERATE, AND THE MODEL SAYS SO
-- ============================================================================
-- 96.88% of people placed exactly one order. Textbook RFM scores each dimension
-- into quintiles; applied to this frequency distribution, NTILE(5) would cut
-- five arbitrary slices through a column that is the value 1 for nineteen people
-- in twenty, and produce five "segments" that differ in nothing.
--
-- So F is scored on its actual distribution — 1 order, 2 orders, 3+ — and the
-- segmentation rule below leans on R and M, which do vary. f_score is carried so
-- the degeneracy is visible in the output rather than hidden inside a label.
--
-- This is a finding, not a workaround. A marketplace where 97% of customers
-- never return is a marketplace whose problem is acquisition-to-retention, and
-- an RFM deck that quietly implied otherwise would be describing a different
-- business (SRS NFR-8).
-- ============================================================================
--
-- Recency is measured from 2018-08-31, the anchor settled in M2 D-5 — not
-- now(), and not the 2018-10-17 maximum that sits in a truncated tail.

with monetary as (

    select
        customer_unique_id,
        -- coalesce to 0: a person whose only order was one of the 775 that were
        -- never itemised has null order_value, and null monetary would drop them
        -- from the segmentation entirely. Zero is right here — they spent nothing.
        coalesce(sum(order_value), 0)                       as monetary_value,
        count(distinct purchase_date)                       as shopping_days
    from {{ ref('fct_orders') }}
    group by customer_unique_id

),

base as (

    select
        c.customer_unique_id,
        c.state,
        c.region,
        c.cohort_month,
        c.first_order_at,
        c.last_order_at,
        c.recency_days,
        c.total_orders                                      as frequency_orders,
        c.is_repeat_customer,
        m.shopping_days,
        m.shopping_days > 1                                 as returned_on_a_later_day,
        m.monetary_value
    from {{ ref('dim_customers') }} c
    join monetary m on m.customer_unique_id = c.customer_unique_id

),

scored as (

    select
        *,
        -- Recency: lower is better, so the quintile is reversed.
        6 - ntile(5) over (order by recency_days)           as r_score,

        case
            when frequency_orders >= 3 then 5
            when frequency_orders  = 2 then 3
            else 1
        end                                                 as f_score,

        ntile(5) over (order by monetary_value)             as m_score
    from base

)

select
    *,
    case
        when r_score >= 4 and m_score >= 4 then 'Champions'
        when r_score >= 4 and m_score >= 2 then 'Recent, promising'
        when r_score >= 4                  then 'Recent, low value'
        when r_score  = 3 and m_score >= 4 then 'Needs attention'
        when r_score <= 2 and m_score >= 4 then 'At risk, high value'
        when r_score <= 2 and m_score <= 2 then 'Lost, low value'
        else                                    'Hibernating'
    end                                                     as rfm_segment
from scored

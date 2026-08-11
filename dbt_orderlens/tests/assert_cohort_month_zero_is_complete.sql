-- BESPOKE TEST — FR-6. Month 0 of every cohort must be 100% retained.
--
-- A cohort is defined by the month of its members' first order, so by
-- construction every member is active in month 0. If that cell is not exactly
-- 100%, the cohort_month on dim_customers and the activity months computed here
-- disagree — a timezone cast, a date_trunc on the wrong column, an off-by-one in
-- the month arithmetic.
--
-- The failure this catches is not a crash. It is a retention curve that starts
-- at 97% instead of 100% and looks entirely plausible, silently rescaling every
-- later period against the wrong base.

select
    cohort_month,
    cohort_customers,
    active_customers,
    retention_pct
from {{ ref('mart_cohort_retention') }}
where months_since_first_order = 0
  and retention_pct <> 100

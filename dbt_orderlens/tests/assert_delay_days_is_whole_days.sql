-- BESPOKE TEST — M2 finding F-01. The most valuable test in the project.
--
-- delay_days must be the difference of two DATES, not of a timestamp and a
-- midnight. The timestamp form produces a perfectly valid signed number for every
-- delivered order: no null appears, no row count changes, no schema test fails.
-- The only symptom is that the delay-to-satisfaction gap comes back 14.4% smaller
-- — 1.729 review points instead of 2.020 — because 1,292 orders delivered ON the
-- promised day get filed as late (M2 A-10, A-11).
--
-- That is the number the M5 regression estimates and the M7 recommendation is
-- costed from. A reversion would arrive looking entirely reasonable and there
-- would be nothing to compare it against.
--
-- Whole days is the observable signature of the correct rule, so that is what
-- this asserts. A fractional value means someone subtracted timestamps again.

select
    order_id,
    delay_days
from {{ ref('fct_orders') }}
where delay_days is not null
  and delay_days <> trunc(delay_days)

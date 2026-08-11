-- Grain: one calendar date, generated across the dataset's observed range.
--
-- GENERATED, NOT OBSERVED (M2 finding F-06). A date spine built from the dates
-- orders actually carry would omit November 2016 entirely — the source has zero
-- orders that month — and a time series drawn from it would join October 2016
-- straight to December 2016 and draw a line through a month that never existed.
-- No reader could tell. The generated spine makes the gap a visible zero.
--
-- The range spans purchase through estimated delivery, so every date column in
-- fct_orders resolves: the last estimated delivery date (2018-11-12) falls after
-- the last purchase (2018-10-17), and a spine stopping at the latter would leave
-- promised-delivery joins unmatched.
--
-- in_trend_window marks the full-coverage period settled in M2. 2016 carries 329
-- orders in total and the final two months carry 20, none of them delivered.
-- Carrying the flag here means M4 and the dashboard filter on one definition
-- instead of each re-deriving it from memory.

with bounds as (

    select
        min(purchased_at)::date                             as first_date,
        greatest(
            max(purchased_at)::date,
            max(delivered_at)::date,
            max(estimated_delivery_date)
        )                                                   as last_date
    from {{ ref('stg_orders') }}

),

spine as (

    select generate_series(first_date, last_date, interval '1 day')::date as date_day
    from bounds

)

select
    date_day,

    extract(year    from date_day)::int                     as year,
    extract(quarter from date_day)::int                     as quarter,
    extract(month   from date_day)::int                     as month,
    extract(week    from date_day)::int                     as iso_week,
    extract(day     from date_day)::int                     as day_of_month,
    extract(isodow  from date_day)::int                     as day_of_week,

    to_char(date_day, 'YYYY-MM')                            as year_month,
    to_char(date_day, 'Month')                              as month_name,
    to_char(date_day, 'Day')                                as day_name,

    date_trunc('month',   date_day)::date                   as month_start,
    date_trunc('quarter', date_day)::date                   as quarter_start,

    extract(isodow from date_day)::int in (6, 7)            as is_weekend,

    date_day between '{{ var("trend_window_start") }}'::date
                 and '{{ var("trend_window_end") }}'::date  as in_trend_window

from spine

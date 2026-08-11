-- FR-5 — delivery performance over time. Grain: one purchase month.
--
-- Restricted to in_trend_window (2017-01 to 2018-08), the full-coverage period
-- settled in M2 F-06. Outside it the series is not a trend: 2016 carries 329
-- orders in total, November 2016 has none at all, and the final two months carry
-- 20 orders of which none was ever delivered. A line drawn through those points
-- reports a collapse that never happened.
--
-- The handover/transit split is the column that makes the eventual
-- recommendation actionable. "Deliveries are late" is not something a business
-- can act on. "The carrier owns three quarters of the wait, and the spikes are
-- entirely carrier-side" is.

select
    d.year_month,
    d.month_start,

    count(*)                                                        as delivered_orders,
    count(*) filter (where o.is_late)                               as late_orders,
    round(100.0 * count(*) filter (where o.is_late) / count(*), 2)  as pct_late,

    round(avg(o.delay_days), 2)                                     as mean_delay_days,
    percentile_cont(0.5) within group (order by o.delay_days)       as median_delay_days,

    round(avg(o.delivery_days), 2)                                  as mean_delivery_days,
    round(avg(o.estimated_days), 2)                                 as mean_promised_days,

    -- Null-safe by construction: these are null on the 188 orders with backwards
    -- timestamps (M2 F-08), and avg() skips nulls rather than counting them as 0.
    round(avg(o.seller_handover_days), 2)                           as mean_seller_handover_days,
    round(avg(o.carrier_transit_days), 2)                           as mean_carrier_transit_days,

    round(avg(o.review_score), 3)                                   as mean_review_score,
    round(100.0 * count(*) filter (where o.is_low_score)
          / nullif(count(o.review_score), 0), 2)                    as pct_low_score,

    round(sum(o.order_value), 2)                                    as revenue

from {{ ref('fct_orders') }} o
join {{ ref('dim_dates') }} d on d.date_day = o.purchase_date
where o.is_delivery_eligible
  and d.in_trend_window
group by d.year_month, d.month_start

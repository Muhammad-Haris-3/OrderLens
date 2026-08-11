{#
    Bucket a signed delay_days value into the bands used everywhere.

    A macro rather than a repeated CASE because the bands appear in
    mart_delay_buckets (the aggregate), mart_order_analysis (the order grain the
    dashboard drills into) and the data dictionary. Three copies of eight
    boundaries is three chances for "1-7 days late" to mean something slightly
    different on one chart than on the next, and a dashboard whose summary
    disagrees with its own drill-down is worse than no dashboard.

    The bands are not evenly spaced on purpose. M4 measured the relationship as a
    cliff: crossing from "on the promised day" into "1-7 days late" quadruples
    the low-score rate, and the following three weeks add less than that first
    week did. Even bands would smooth the one feature that matters.

    The leading digit exists so the buckets sort correctly as strings — Tableau
    and most BI tools sort a discrete dimension alphabetically, and without it
    "15-30 days late" lands between "1-7" and "8-14".
#}

{% macro delay_bucket(delay_column) %}
    case
        when {{ delay_column }} is null then null
        when {{ delay_column }} <= -15 then '1. 15+ days early'
        when {{ delay_column }} <=  -8 then '2. 8-14 days early'
        when {{ delay_column }} <=  -1 then '3. 1-7 days early'
        when {{ delay_column }} =    0 then '4. on the promised day'
        when {{ delay_column }} <=   7 then '5. 1-7 days late'
        when {{ delay_column }} <=  14 then '6. 8-14 days late'
        when {{ delay_column }} <=  30 then '7. 15-30 days late'
        else                                '8. more than 30 days late'
    end
{% endmacro %}

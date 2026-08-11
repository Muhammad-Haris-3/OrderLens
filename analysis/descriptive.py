"""M4 — descriptive analysis (SRS FR-5 to FR-8).

Reads the analysis marts, computes the statistics that are genuinely statistics,
and writes `docs/descriptive_results.md`.

WHAT THIS SCRIPT DOES NOT DO IS AGGREGATE. Every count, sum, rate and ranking
below is selected from a dbt model — `mart_delivery_monthly`,
`mart_delay_buckets`, `mart_cohort_retention`, `mart_customer_rfm`,
`mart_revenue_concentration`. That is the deliberate constraint in SRS §9.2:
transformation and aggregation happen in SQL, and Python is reserved for
statistics and modelling. A figure computed here that could have been a GROUP BY
is a figure the dashboard cannot reproduce.

What is left for Python is the Gini coefficient, the top-N share curve, and the
review-timing sensitivity — none of which is a GROUP BY.

Reads marts only, never `raw` and never `analytics_staging` (Design Phase §8).

Usage:
    python analysis/descriptive.py
    python analysis/descriptive.py --stdout
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "docs" / "descriptive_results.md"

MARTS = "analytics_marts"


# --------------------------------------------------------------------------
# Statistics — the part that is not a GROUP BY
# --------------------------------------------------------------------------

def gini(values: list[float]) -> float:
    """Gini coefficient of a revenue distribution.

    0 = every member earns the same; 1 = one member earns everything. Reported
    alongside the Pareto share because the two answer different questions: the
    share says "how much do the top N hold", the Gini says "how unequal is the
    whole distribution", and a market can look Pareto-normal at the top while
    being far more or less equal in its tail.

    Standard formula on the sorted series:
        G = (2 * sum(i * x_i) / (n * sum(x))) - (n + 1) / n
    """
    ordered = sorted(v for v in values if v is not None)
    n = len(ordered)
    total = sum(ordered)
    if n == 0 or total == 0:
        return float("nan")

    weighted = sum((i + 1) * value for i, value in enumerate(ordered))
    return (2 * weighted) / (n * total) - (n + 1) / n


def top_share(revenues: list[float], fraction: float) -> tuple[int, float]:
    """Revenue share held by the top `fraction` of members, by count."""
    ordered = sorted((v for v in revenues if v is not None), reverse=True)
    total = sum(ordered)
    if not ordered or total == 0:
        return 0, float("nan")

    cutoff = max(1, round(len(ordered) * fraction))
    return cutoff, 100.0 * sum(ordered[:cutoff]) / total


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def fmt(value: object) -> str:
    if value is None:
        return "_null_"
    if isinstance(value, float):
        return f"{value:,.3f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def table(columns: list[str], rows: list[tuple]) -> str:
    if not rows:
        return "_No rows._\n"
    lines = [
        "| " + " | ".join(columns) + " |",
        "|" + "|".join("---" for _ in columns) + "|",
    ]
    lines += ["| " + " | ".join(fmt(v) for v in row) + " |" for row in rows]
    return "\n".join(lines) + "\n"


def query(cur, sql: str) -> tuple[list[str], list[tuple]]:
    cur.execute(sql)
    return [d[0] for d in cur.description], cur.fetchall()


def section(cur, title: str, source: str, sql: str) -> str:
    columns, rows = query(cur, sql)
    return f"### {title}\n\nFrom `{source}`.\n\n{table(columns, rows)}\n"


# --------------------------------------------------------------------------
# The report
# --------------------------------------------------------------------------

def build_report(cur) -> str:
    parts: list[str] = [
        "# OrderLens — Descriptive Analysis Results (generated)",
        "",
        "**Do not edit by hand.** Regenerate with `python analysis/descriptive.py`.",
        "",
        "This file is the *evidence*. The interpretation — what these numbers mean",
        "and what follows from them — lives in",
        "[descriptive_findings.md](descriptive_findings.md).",
        "",
        f"| Generated | {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')} |",
        "|---|---|",
        "| Source | `analytics_marts` (marts only — never raw, never staging) |",
        "",
        "---",
        "",
        "## FR-5 — Delivery performance",
        "",
    ]

    parts.append(section(
        cur,
        "Monthly delivery performance, 2017-01 to 2018-08",
        "mart_delivery_monthly",
        f"""
        select year_month, delivered_orders, late_orders, pct_late,
               mean_delay_days, mean_delivery_days,
               mean_seller_handover_days, mean_carrier_transit_days,
               mean_review_score
        from {MARTS}.mart_delivery_monthly
        order by year_month
        """,
    ))

    parts.append(section(
        cur,
        "Where the wait goes — seller handover vs carrier transit",
        "mart_delivery_monthly",
        f"""
        select
            round(avg(mean_delivery_days), 2)                as mean_total_wait_days,
            round(avg(mean_seller_handover_days), 2)         as mean_seller_handover_days,
            round(avg(mean_carrier_transit_days), 2)         as mean_carrier_transit_days,
            round(100.0 * avg(mean_seller_handover_days)
                  / avg(mean_delivery_days), 1)              as pct_of_wait_seller,
            round(100.0 * avg(mean_carrier_transit_days)
                  / avg(mean_delivery_days), 1)              as pct_of_wait_carrier
        from {MARTS}.mart_delivery_monthly
        """,
    ))

    parts.append(section(
        cur,
        "Delay distribution and what each band costs",
        "mart_delay_buckets",
        f"""
        select delay_bucket, orders, pct_of_delivered,
               mean_review_score, pct_low_score, revenue
        from {MARTS}.mart_delay_buckets
        order by delay_bucket
        """,
    ))

    parts.append(section(
        cur,
        "Review timing by delay band — the selection problem",
        "mart_delay_buckets",
        f"""
        select delay_bucket, orders,
               pct_reviewed_before_delivery,
               mean_review_score            as mean_all_reviews,
               mean_review_reviewed_after,
               mean_review_reviewed_before
        from {MARTS}.mart_delay_buckets
        order by delay_bucket
        """,
    ))

    # ---- Review-timing sensitivity: a statistic, not an aggregation ---------
    _, rows = query(cur, f"""
        select
            round(avg(review_score) filter (where not is_late), 4),
            round(avg(review_score) filter (where is_late), 4),
            round(avg(review_score) filter (where not is_late
                                              and not reviewed_before_delivery), 4),
            round(avg(review_score) filter (where is_late
                                              and not reviewed_before_delivery), 4),
            count(*) filter (where is_late),
            count(*) filter (where is_late and not reviewed_before_delivery),
            count(*) filter (where not is_late),
            count(*) filter (where not is_late and not reviewed_before_delivery)
        from {MARTS}.fct_orders
        where is_delivery_eligible and review_score is not null
    """)
    (on_all, late_all, on_after, late_after,
     late_n, late_after_n, on_n, on_after_n) = rows[0]

    parts += [
        "### Sensitivity — what excluding pre-delivery reviews would do",
        "",
        "Computed from `fct_orders`. This is the calculation that shows why the",
        "M2 F-09 handling decision could not stand.",
        "",
        table(
            ["population", "on-time orders", "late orders",
             "mean (on time)", "mean (late)", "gap"],
            [
                ("all reviews", on_n, late_n, float(on_all), float(late_all),
                 float(on_all) - float(late_all)),
                ("reviews written after delivery only",
                 on_after_n, late_after_n, float(on_after), float(late_after),
                 float(on_after) - float(late_after)),
            ],
        ),
        f"Excluding pre-delivery reviews retains "
        f"{100.0 * on_after_n / on_n:.1f}% of on-time orders but only "
        f"{100.0 * late_after_n / late_n:.1f}% of late ones.",
        "",
        "---",
        "",
        "## FR-6 — Cohort retention",
        "",
    ]

    parts.append(section(
        cur,
        "Retention by cohort, months 1-6",
        "mart_cohort_retention",
        f"""
        select
            cohort_month,
            cohort_customers,
            max(retention_pct) filter (where months_since_first_order = 1) as month_1,
            max(retention_pct) filter (where months_since_first_order = 2) as month_2,
            max(retention_pct) filter (where months_since_first_order = 3) as month_3,
            max(retention_pct) filter (where months_since_first_order = 6) as month_6
        from {MARTS}.mart_cohort_retention
        where cohort_customers >= 500
        group by cohort_month, cohort_customers
        order by cohort_month
        """,
    ))

    # The grid is generated rather than read straight off the mart. The mart only
    # holds rows where a cohort had at least one active customer, so summing its
    # cohort_customers per period silently drops every cohort that retained
    # nobody — inflating retention by removing the zeros from the denominator.
    # The grid also excludes periods a cohort could not yet have reached, so
    # right-censoring does not masquerade as churn.
    parts.append(section(
        cur,
        "Retention pooled across cohorts of 500+ customers",
        "mart_cohort_retention (grid generated to keep zero-retention cohorts in the denominator)",
        f"""
        with cohorts as (
            select distinct cohort_month, cohort_customers
            from {MARTS}.mart_cohort_retention
            where months_since_first_order = 0 and cohort_customers >= 500
        ),
        last_observed as (
            select max((cohort_month + make_interval(months => months_since_first_order))::date)
                       as last_activity_month
            from {MARTS}.mart_cohort_retention
        ),
        grid as (
            select c.cohort_month, c.cohort_customers, m as months_since
            from cohorts c
            cross join generate_series(0, 6) as m
            where (c.cohort_month + make_interval(months => m))::date
                  <= (select last_activity_month from last_observed)
        )
        select
            g.months_since                                              as months_since_first_order,
            count(*)                                                    as cohorts_observable,
            sum(g.cohort_customers)                                     as customers,
            coalesce(sum(r.active_customers), 0)                        as active,
            round(100.0 * coalesce(sum(r.active_customers), 0)
                  / sum(g.cohort_customers), 3)                         as retention_pct
        from grid g
        left join {MARTS}.mart_cohort_retention r
               on r.cohort_month = g.cohort_month
              and r.months_since_first_order = g.months_since
        group by g.months_since
        order by g.months_since
        """,
    ))

    parts.append(section(
        cur,
        "Repeat purchase, measured two ways",
        "mart_customer_rfm",
        f"""
        select
            count(*)                                                    as people,
            count(*) filter (where is_repeat_customer)                  as placed_2plus_orders,
            round(100.0 * count(*) filter (where is_repeat_customer)
                  / count(*), 2)                                        as pct_2plus_orders,
            count(*) filter (where returned_on_a_later_day)             as shopped_on_2plus_days,
            round(100.0 * count(*) filter (where returned_on_a_later_day)
                  / count(*), 2)                                        as pct_2plus_days
        from {MARTS}.mart_customer_rfm
        """,
    ))

    parts += ["---", "", "## FR-7 — RFM segmentation", ""]

    parts.append(section(
        cur,
        "Segment profile",
        "mart_customer_rfm",
        f"""
        select
            rfm_segment,
            count(*)                                                    as people,
            round(100.0 * count(*) / sum(count(*)) over (), 2)          as pct_of_people,
            round(sum(monetary_value), 2)                               as revenue,
            round(100.0 * sum(monetary_value)
                  / sum(sum(monetary_value)) over (), 2)                as pct_of_revenue,
            round(avg(monetary_value), 2)                               as mean_spend,
            round(avg(recency_days), 0)                                 as mean_recency_days,
            count(*) filter (where returned_on_a_later_day)             as returned_later
        from {MARTS}.mart_customer_rfm
        group by rfm_segment
        order by 5 desc
        """,
    ))

    parts.append(section(
        cur,
        "The frequency dimension, as it actually is",
        "mart_customer_rfm",
        f"""
        select
            f_score,
            frequency_orders,
            count(*)                                                    as people,
            round(100.0 * count(*) / sum(count(*)) over (), 3)          as pct_of_people
        from {MARTS}.mart_customer_rfm
        group by f_score, frequency_orders
        order by frequency_orders
        """,
    ))

    parts += ["---", "", "## FR-8 — Revenue concentration", ""]

    for dimension, label in [
        ("category", "Category"),
        ("seller", "Seller"),
        ("customer_state", "Customer state"),
    ]:
        _, revenue_rows = query(cur, f"""
            select revenue from {MARTS}.mart_revenue_concentration
            where dimension = '{dimension}'
        """)
        revenues = [float(r[0]) for r in revenue_rows]

        _, threshold = query(cur, f"""
            select members_in_dimension,
                   min(revenue_rank) filter (where cumulative_pct_of_revenue >= 80)
            from {MARTS}.mart_revenue_concentration
            where dimension = '{dimension}'
            group by members_in_dimension
        """)
        members, to_eighty = threshold[0]

        share_rows = [
            (f"top {int(f * 100)}%", *top_share(revenues, f))
            for f in (0.01, 0.05, 0.10, 0.20)
        ]

        parts += [
            f"### {label} concentration",
            "",
            f"From `mart_revenue_concentration` where `dimension = '{dimension}'`. "
            f"Gini and top-N shares computed in `analysis/descriptive.py`.",
            "",
            table(
                ["members", "reaching 80% of revenue", "as % of members", "Gini"],
                [(members, to_eighty,
                  round(100.0 * to_eighty / members, 1),
                  round(gini(revenues), 4))],
            ),
            "",
            table(["tier", "members", "share of revenue %"],
                  [(t, n, round(s, 2)) for t, n, s in share_rows]),
            "",
        ]

    parts.append(section(
        cur,
        "Top 15 categories",
        "mart_revenue_concentration",
        f"""
        select revenue_rank, dimension_key as category, revenue,
               pct_of_revenue, cumulative_pct_of_revenue, orders,
               pct_late, mean_review_score
        from {MARTS}.mart_revenue_concentration
        where dimension = 'category' and revenue_rank <= 15
        order by revenue_rank
        """,
    ))

    parts.append(section(
        cur,
        "Revenue and failure rate by customer state (top 12)",
        "mart_revenue_concentration",
        f"""
        select revenue_rank, dimension_key as state, revenue,
               pct_of_revenue, cumulative_pct_of_revenue, orders,
               pct_late, mean_review_score
        from {MARTS}.mart_revenue_concentration
        where dimension = 'customer_state' and revenue_rank <= 12
        order by revenue_rank
        """,
    ))

    # BQ-4 asks which segments concentrate the DAMAGE, which is not the same
    # question as which concentrate the revenue. A state can be large and
    # reliable, or small and failing. Ranking on late orders rather than on
    # revenue or on rate alone is what separates the two.
    parts.append(section(
        cur,
        "Where the damage concentrates — states ranked by late orders",
        "mart_revenue_concentration",
        f"""
        select
            dimension_key                                               as state,
            orders,
            pct_late,
            round(orders * pct_late / 100.0)                            as late_orders,
            round(revenue * pct_late / 100.0, 2)                        as revenue_on_late_orders,
            round(100.0 * (revenue * pct_late / 100.0)
                  / sum(revenue * pct_late / 100.0) over (), 2)         as pct_of_all_late_revenue,
            round(100.0 * revenue / sum(revenue) over (), 2)            as pct_of_all_revenue,
            mean_review_score
        from {MARTS}.mart_revenue_concentration
        where dimension = 'customer_state'
        order by revenue * pct_late desc
        limit 12
        """,
    ))

    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stdout", action="store_true",
                        help="print the report instead of writing the file")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is not set. Copy .env.example to .env and fill it in.")
        return 1

    conn = psycopg2.connect(database_url)
    try:
        # Read-only: an analysis script has no business writing to the warehouse.
        conn.set_session(readonly=True, autocommit=True)
        with conn.cursor() as cur:
            report = build_report(cur)
    finally:
        conn.close()

    if args.stdout:
        print(report)
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
        print(f"Written to {args.out.relative_to(ROOT)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

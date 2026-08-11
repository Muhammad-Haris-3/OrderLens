"""Export the dashboard marts to CSV for Tableau Public (SRS FR-18).

WHY THIS EXISTS. The Design Phase (§9) assumed Tableau Public would connect
directly to `analytics_marts`, live, with no extracts. That is not possible:
Tableau *Public* — the free edition — offers only file and a few cloud
connectors. PostgreSQL is a paid Tableau Desktop feature, and everything
published to Tableau Public is uploaded as data rather than queried live.

The assumption was made at M0 and went unchallenged until someone tried to
follow the instructions at M7. It is corrected in docs/dashboard_spec.md §1.

WHAT THIS COSTS. The dashboard becomes a snapshot rather than a live view, so it
can drift from the warehouse — the exact failure the "no extracts" rule existed
to prevent. Two things keep that honest:

  * every file carries the timestamp it was exported at, and the dashboard shows
    it, so a stale dashboard says so rather than looking current
  * re-running this script and re-publishing is the documented refresh path

Reads marts only. Writes to `data/dashboard/`, which is gitignored — these are
derived artefacts that regenerate in seconds, not source.

Usage:
    python scripts/export_dashboard_data.py
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "data" / "dashboard"

# One file per dashboard view. mart_order_analysis is the drill-down detail and
# is by far the largest; the rest are small aggregates.
EXPORTS = {
    "delivery_monthly": "select * from analytics_marts.mart_delivery_monthly order by year_month",
    "delay_buckets": "select * from analytics_marts.mart_delay_buckets order by delay_bucket",
    "revenue_concentration": (
        "select * from analytics_marts.mart_revenue_concentration "
        "order by dimension, revenue_rank"
    ),
    # Trimmed to the columns the drill-down actually uses. Exporting all 40 would
    # make the Tableau extract several times larger for no benefit, and Tableau
    # Public has a 15 million row / 10 GB ceiling worth staying well under.
    "orders": """
        select order_id, purchase_date, customer_state, seller_state,
               primary_category, primary_seller_id,
               delay_days, delay_bucket, is_late, delivery_days, estimated_days,
               seller_handover_days, carrier_transit_days,
               review_score, is_low_score, reviewed_before_delivery,
               order_value, order_item_total, order_freight_total,
               item_count, seller_count, is_single_seller, distance_km, season
        from analytics_marts.mart_order_analysis
        order by purchase_date
    """,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is not set. Copy .env.example to .env and fill it in.")
        return 1

    import psycopg2

    args.out.mkdir(parents=True, exist_ok=True)
    exported_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    conn = psycopg2.connect(database_url)
    try:
        # Read-only: an export has no business writing to the warehouse.
        conn.set_session(readonly=True, autocommit=True)
        with conn.cursor() as cur:
            for name, query in EXPORTS.items():
                path = args.out / f"{name}.csv"
                with path.open("w", newline="", encoding="utf-8") as handle:
                    cur.copy_expert(
                        f"COPY ({query.strip().rstrip(';')}) TO STDOUT "
                        "WITH (FORMAT csv, HEADER true)",
                        handle,
                    )
                rows = sum(1 for _ in path.open(encoding="utf-8")) - 1
                size_mb = path.stat().st_size / 1_048_576
                print(f"  {name:24} {rows:>8,} rows  {size_mb:>6.1f} MB")
    finally:
        conn.close()

    # The dashboard shows this, so a stale extract announces itself rather than
    # looking current. A snapshot that cannot say how old it is is worse than no
    # snapshot.
    stamp = args.out / "exported_at.csv"
    stamp.write_text(f"exported_at\n{exported_at}\n", encoding="utf-8")

    print(f"\nExported at {exported_at} to {args.out.relative_to(ROOT)}")
    print("Connect Tableau Public to these files — see docs/dashboard_spec.md §1.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

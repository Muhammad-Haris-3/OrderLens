"""Load the nine source CSVs into the Postgres RAW layer (SRS FR-1).

Idempotent: each run truncates and reloads every table, so a partial or failed
run never leaves the warehouse in a half-populated state.

Reconciliation: the row count in each file is compared against the row count
actually landed in the database, and both are recorded in `raw.load_log`. A
mismatch raises rather than warns — a loader that silently drops rows is worse
than one that fails.

Usage:
    python scripts/load_raw.py             # load everything
    python scripts/load_raw.py --check     # verify only, load nothing
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

# utf-8-sig, not utf-8: product_category_name_translation.csv ships with a UTF-8
# BOM. Read as plain utf-8, its first column name becomes "﻿product_category_name",
# which silently fails every join against it. utf-8-sig strips a BOM when present
# and is a no-op when absent, so it is safe for all nine files.
ENCODING = "utf-8-sig"

# source CSV -> (raw table, expected header)
TABLES: dict[str, tuple[str, tuple[str, ...]]] = {
    "olist_orders_dataset.csv": (
        "raw.orders",
        ("order_id", "customer_id", "order_status", "order_purchase_timestamp",
         "order_approved_at", "order_delivered_carrier_date",
         "order_delivered_customer_date", "order_estimated_delivery_date"),
    ),
    "olist_order_items_dataset.csv": (
        "raw.order_items",
        ("order_id", "order_item_id", "product_id", "seller_id",
         "shipping_limit_date", "price", "freight_value"),
    ),
    "olist_order_payments_dataset.csv": (
        "raw.order_payments",
        ("order_id", "payment_sequential", "payment_type",
         "payment_installments", "payment_value"),
    ),
    "olist_order_reviews_dataset.csv": (
        "raw.order_reviews",
        ("review_id", "order_id", "review_score", "review_comment_title",
         "review_comment_message", "review_creation_date",
         "review_answer_timestamp"),
    ),
    "olist_customers_dataset.csv": (
        "raw.customers",
        ("customer_id", "customer_unique_id", "customer_zip_code_prefix",
         "customer_city", "customer_state"),
    ),
    "olist_sellers_dataset.csv": (
        "raw.sellers",
        ("seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"),
    ),
    "olist_products_dataset.csv": (
        "raw.products",
        ("product_id", "product_category_name", "product_name_lenght",
         "product_description_lenght", "product_photos_qty",
         "product_weight_g", "product_length_cm", "product_height_cm",
         "product_width_cm"),
    ),
    "product_category_name_translation.csv": (
        "raw.product_category_translation",
        ("product_category_name", "product_category_name_english"),
    ),
    "olist_geolocation_dataset.csv": (
        "raw.geolocation",
        ("geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng",
         "geolocation_city", "geolocation_state"),
    ),
}


def count_data_rows(path: Path) -> int:
    """Count rows excluding the header, using the csv module.

    A plain line count would be wrong: review comments contain embedded
    newlines inside quoted fields.
    """
    with path.open(newline="", encoding=ENCODING) as fh:
        reader = csv.reader(fh)
        next(reader, None)  # header
        return sum(1 for _ in reader)


def read_header(path: Path) -> tuple[str, ...]:
    with path.open(newline="", encoding=ENCODING) as fh:
        return tuple(next(csv.reader(fh), []))


def check_files() -> list[str]:
    """Verify every expected file exists with the expected header."""
    problems: list[str] = []
    for filename, (table, expected_header) in TABLES.items():
        path = RAW_DIR / filename
        if not path.exists():
            problems.append(f"MISSING: {filename}")
            continue
        actual = read_header(path)
        if actual != expected_header:
            problems.append(
                f"HEADER MISMATCH in {filename} -> {table}\n"
                f"  expected: {expected_header}\n"
                f"  actual:   {actual}"
            )
    return problems


def load_table(cur, path: Path, table: str) -> tuple[int, int]:
    """Truncate and COPY one file into one table. Returns (in_file, loaded)."""
    rows_in_file = count_data_rows(path)

    cur.execute(f"TRUNCATE {table}")
    with path.open("r", newline="", encoding=ENCODING) as fh:
        cur.copy_expert(
            f"COPY {table} FROM STDIN WITH (FORMAT csv, HEADER true)", fh
        )

    cur.execute(f"SELECT count(*) FROM {table}")
    rows_loaded = cur.fetchone()[0]
    return rows_in_file, rows_loaded


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="verify files only; do not touch the database")
    args = parser.parse_args()

    problems = check_files()
    if problems:
        print("Source file check FAILED:\n")
        for p in problems:
            print(f"  {p}")
        print(f"\nExpected files in: {RAW_DIR}")
        print("See data/raw/README.md for how to obtain the dataset.")
        return 1

    print(f"Source file check passed — {len(TABLES)} files present with expected headers.")
    if args.check:
        return 0

    load_dotenv()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is not set. Copy .env.example to .env and fill it in.")
        return 1

    conn = psycopg2.connect(database_url)
    try:
        with conn, conn.cursor() as cur:
            mismatches = []
            for filename, (table, _) in TABLES.items():
                path = RAW_DIR / filename
                in_file, loaded = load_table(cur, path, table)
                status = "OK" if in_file == loaded else "MISMATCH"
                if in_file != loaded:
                    mismatches.append((table, in_file, loaded))
                cur.execute(
                    "INSERT INTO raw.load_log (table_name, source_file, rows_in_file, rows_loaded)"
                    " VALUES (%s, %s, %s, %s)",
                    (table, filename, in_file, loaded),
                )
                print(f"  {status:8} {table:36} {loaded:>7,} rows")

            if mismatches:
                # Rollback via exception — a partial load must not be committed.
                detail = "; ".join(
                    f"{name}: file={in_file:,} loaded={loaded:,}"
                    for name, in_file, loaded in mismatches
                )
                raise RuntimeError(f"Row-count reconciliation failed — {detail}")
    finally:
        conn.close()

    print("\nAll tables loaded and reconciled.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

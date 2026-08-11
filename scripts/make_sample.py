"""Build a referentially-complete sample of the source CSVs (SRS NFR-3).

WHY THIS EXISTS. NFR-3 asks CI to run the dbt tests on every push. It could not:
the tests need a loaded warehouse, and the dataset is ~120 MB of CSV that is
deliberately not committed. So the 193 data tests only ever ran on one laptop,
against one warehouse, and CI checked that the project *parsed*. A test suite
that runs somewhere other than CI is a test suite that will eventually stop
running.

This produces a small fixture — committed, a few hundred kilobytes — that CI
loads into a throwaway Postgres and builds the whole project against.

REFERENTIAL COMPLETENESS IS THE WHOLE PROBLEM. Sampling rows independently from
nine files produces items whose order does not exist and orders whose customer
does not exist, and every `relationships` test fails for reasons that have
nothing to do with the code being tested. So the sample is grown outward from a
seed set of orders:

    orders  ->  their items, payments, reviews, and customer
            ->  the products and sellers those items reference
            ->  the geolocation prefixes those customers and sellers reference

The category translation is copied whole: it is 71 rows, and truncating it would
change the `dim_products` coverage numbers that M2 settled.

GEOLOCATION IS CAPPED per ZIP prefix. The real table averages 52.6 rows per
prefix (M2 A-20), which would dominate the fixture. The cap keeps the fan-out
behaviour — more than one row per prefix, so `stg_geolocation` still has
something to aggregate — without carrying tens of thousands of rows.

Deterministic: the seed is fixed, so re-running produces byte-identical output
and the fixture does not churn in git.

Usage:
    python scripts/make_sample.py                # 1,200 orders
    python scripts/make_sample.py --orders 500
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from collections import defaultdict
from pathlib import Path

from scripts.load_raw import ENCODING, RAW_DIR, TABLES

OUT_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "raw_sample"

SEED = 20260811
DEFAULT_ORDERS = 1200

# Repeat customers deliberately included, with all of their orders. See the
# comment at the seed set for why this cannot be left to chance.
REPEAT_PEOPLE = 120

# Rows kept per ZIP prefix. Above 1 so the fan-out that stg_geolocation exists to
# kill is still present in the fixture; low enough that the file stays small.
GEO_ROWS_PER_PREFIX = 4

ORDERS_CSV = "olist_orders_dataset.csv"
ITEMS_CSV = "olist_order_items_dataset.csv"
PAYMENTS_CSV = "olist_order_payments_dataset.csv"
REVIEWS_CSV = "olist_order_reviews_dataset.csv"
CUSTOMERS_CSV = "olist_customers_dataset.csv"
SELLERS_CSV = "olist_sellers_dataset.csv"
PRODUCTS_CSV = "olist_products_dataset.csv"
CATEGORIES_CSV = "product_category_name_translation.csv"
GEOLOCATION_CSV = "olist_geolocation_dataset.csv"


def read_rows(filename: str) -> tuple[list[str], list[dict[str, str]]]:
    path = RAW_DIR / filename
    if not path.exists():
        raise SystemExit(
            f"Missing {path}.\nThe full dataset is needed to build the fixture — "
            "see data/raw/README.md."
        )
    with path.open(newline="", encoding=ENCODING) as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_rows(filename: str, header: list[str], rows: list[dict[str, str]]) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / filename
    # newline="" and \n: identical bytes on Windows and Linux, so the committed
    # fixture does not change depending on who regenerated it.
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def index_by(rows: list[dict[str, str]], key: str) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row[key]].append(row)
    return grouped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--orders", type=int, default=DEFAULT_ORDERS,
                        help=f"seed orders to sample (default {DEFAULT_ORDERS})")
    args = parser.parse_args()

    rng = random.Random(SEED)

    orders_header, orders = read_rows(ORDERS_CSV)
    items_header, items = read_rows(ITEMS_CSV)
    payments_header, payments = read_rows(PAYMENTS_CSV)
    reviews_header, reviews = read_rows(REVIEWS_CSV)
    customers_header, customers = read_rows(CUSTOMERS_CSV)
    sellers_header, sellers = read_rows(SELLERS_CSV)
    products_header, products = read_rows(PRODUCTS_CSV)
    categories_header, categories = read_rows(CATEGORIES_CSV)
    geo_header, geolocation = read_rows(GEOLOCATION_CSV)

    # ---- Seed set --------------------------------------------------------
    # Stratified by status so the fixture keeps every order status, including the
    # rare ones. `created` has 5 rows in 99,441; a uniform sample of 1,200 would
    # miss it entirely and the accepted_values test would never exercise it.
    by_status = index_by(orders, "order_status")
    seed_orders: list[dict[str, str]] = []
    for status in sorted(by_status):
        group = by_status[status]
        share = max(1, round(args.orders * len(group) / len(orders)))
        seed_orders.extend(rng.sample(group, min(share, len(group))))

    # REPEAT CUSTOMERS MUST BE DELIBERATELY INCLUDED, or the fixture cannot
    # exercise the most important test in the project.
    #
    # Only 3.12% of people order twice, and a 1.2% sample of orders lands BOTH
    # orders of a repeat customer essentially never — the first attempt produced
    # a fixture with exactly zero. assert_repeat_customers_exist (risk R-1) would
    # then fail in CI at any threshold, and the tempting fix is to drop the test
    # from CI, which is precisely the failure it guards.
    #
    # So a slice of repeat customers is included on purpose, with ALL of their
    # orders, and the sample is then closed over customer_unique_id so no person
    # is represented by only some of their orders.
    person_of = {row["customer_id"]: row["customer_unique_id"] for row in customers}
    orders_of_person: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in orders:
        orders_of_person[person_of[row["customer_id"]]].append(row)

    repeat_people = sorted(
        person for person, group in orders_of_person.items() if len(group) > 1
    )
    for person in rng.sample(repeat_people, min(REPEAT_PEOPLE, len(repeat_people))):
        seed_orders.extend(orders_of_person[person])

    # Close over the person: pull in any sibling orders of customers already in.
    people = {person_of[row["customer_id"]] for row in seed_orders}
    for person in people:
        seed_orders.extend(orders_of_person[person])

    seen: set[str] = set()
    deduped = []
    for row in seed_orders:
        if row["order_id"] not in seen:
            seen.add(row["order_id"])
            deduped.append(row)

    seed_orders = sorted(deduped, key=lambda row: row["order_id"])
    order_ids = {row["order_id"] for row in seed_orders}
    customer_ids = {row["customer_id"] for row in seed_orders}

    # ---- Grow outward ----------------------------------------------------
    sample_items = [row for row in items if row["order_id"] in order_ids]
    sample_payments = [row for row in payments if row["order_id"] in order_ids]
    sample_reviews = [row for row in reviews if row["order_id"] in order_ids]
    sample_customers = [row for row in customers if row["customer_id"] in customer_ids]

    product_ids = {row["product_id"] for row in sample_items}
    seller_ids = {row["seller_id"] for row in sample_items}
    sample_products = [row for row in products if row["product_id"] in product_ids]
    sample_sellers = [row for row in sellers if row["seller_id"] in seller_ids]

    prefixes = (
        {row["customer_zip_code_prefix"] for row in sample_customers}
        | {row["seller_zip_code_prefix"] for row in sample_sellers}
    )

    kept_per_prefix: dict[str, int] = defaultdict(int)
    sample_geo = []
    for row in geolocation:
        prefix = row["geolocation_zip_code_prefix"]
        if prefix in prefixes and kept_per_prefix[prefix] < GEO_ROWS_PER_PREFIX:
            kept_per_prefix[prefix] += 1
            sample_geo.append(row)

    # ---- Write -----------------------------------------------------------
    written = {
        ORDERS_CSV: write_rows(ORDERS_CSV, orders_header, seed_orders),
        ITEMS_CSV: write_rows(ITEMS_CSV, items_header, sample_items),
        PAYMENTS_CSV: write_rows(PAYMENTS_CSV, payments_header, sample_payments),
        REVIEWS_CSV: write_rows(REVIEWS_CSV, reviews_header, sample_reviews),
        CUSTOMERS_CSV: write_rows(CUSTOMERS_CSV, customers_header, sample_customers),
        SELLERS_CSV: write_rows(SELLERS_CSV, sellers_header, sample_sellers),
        PRODUCTS_CSV: write_rows(PRODUCTS_CSV, products_header, sample_products),
        CATEGORIES_CSV: write_rows(CATEGORIES_CSV, categories_header, categories),
        GEOLOCATION_CSV: write_rows(GEOLOCATION_CSV, geo_header, sample_geo),
    }

    # ---- Report and self-check -------------------------------------------
    print(f"Sample written to {OUT_DIR.relative_to(OUT_DIR.parent.parent.parent)}\n")
    for filename, (table, _) in TABLES.items():
        print(f"  {table:36} {written[filename]:>7,} rows")

    problems = []
    if not {row["order_id"] for row in sample_items} <= order_ids:
        problems.append("items reference an order not in the sample")
    if not {row["product_id"] for row in sample_items} <= product_ids:
        problems.append("items reference a product not in the sample")
    if not {row["seller_id"] for row in sample_items} <= seller_ids:
        problems.append("items reference a seller not in the sample")
    if not customer_ids <= {row["customer_id"] for row in sample_customers}:
        problems.append("orders reference a customer not in the sample")

    statuses = {row["order_status"] for row in seed_orders}
    if len(statuses) < len(by_status):
        problems.append(
            f"statuses missing from the sample: {sorted(set(by_status) - statuses)}"
        )

    # Without repeat customers the fixture cannot exercise risk R-1, which is the
    # single most valuable assertion in the project.
    sampled_person_orders: dict[str, int] = defaultdict(int)
    for row in seed_orders:
        sampled_person_orders[person_of[row["customer_id"]]] += 1
    repeats_in_sample = sum(1 for count in sampled_person_orders.values() if count > 1)

    if repeats_in_sample < 50:
        problems.append(
            f"only {repeats_in_sample} repeat customers in the sample — "
            "assert_repeat_customers_exist would be untestable in CI"
        )

    if problems:
        print("\nFAILED referential self-check:")
        for problem in problems:
            print(f"  {problem}")
        return 1

    print(
        f"\nReferentially complete. {len(statuses)} order statuses, "
        f"{len(sampled_person_orders):,} people, "
        f"{repeats_in_sample} of them repeat customers."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

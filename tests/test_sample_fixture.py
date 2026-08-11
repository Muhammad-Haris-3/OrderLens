"""Guard the committed CI fixture (SRS NFR-3).

`tests/fixtures/raw_sample` is what CI loads to run the dbt data tests. It is
committed, so it can drift from the sampler that produced it — and regenerating
it needs the full ~120 MB dataset, which CI does not have. These tests check the
shape of what is committed instead.

The properties below are not arbitrary. Each one, if lost, would silently
disable a specific test in the dbt suite while leaving CI green:

  * a missing foreign key breaks every `relationships` test for reasons that
    have nothing to do with the code under test
  * a missing order status stops `accepted_values` ever seeing the rare ones
  * missing repeat customers make `assert_repeat_customers_exist` — the R-1
    guard, the most valuable assertion in the project — impossible to satisfy at
    any threshold, and the tempting fix is to drop it from CI
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from scripts.load_raw import ENCODING, TABLES

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "raw_sample"

# The eight statuses the audit measured (M2 A-06). All must survive sampling.
EXPECTED_STATUSES = {
    "delivered", "shipped", "canceled", "unavailable",
    "invoiced", "processing", "created", "approved",
}

MIN_REPEAT_CUSTOMERS = 50


def read(filename: str) -> list[dict[str, str]]:
    path = FIXTURE / filename
    if not path.exists():
        pytest.fail(f"fixture file missing: {path.name}. Run scripts/make_sample.py.")
    with path.open(newline="", encoding=ENCODING) as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def data() -> dict[str, list[dict[str, str]]]:
    return {filename: read(filename) for filename in TABLES}


def test_every_source_file_is_present(data):
    for filename, (_table, expected_header) in TABLES.items():
        assert data[filename], f"{filename} is empty"
        header = tuple(data[filename][0].keys())
        assert header == expected_header, (
            f"{filename} header drifted from the loader's expectation.\n"
            f"  fixture: {header}\n  loader:  {expected_header}"
        )


def test_fixture_stays_small(data):
    """A fixture that grows without limit stops being a fixture."""
    total = sum(len(rows) for rows in data.values())
    assert total < 40_000, (
        f"fixture has grown to {total:,} rows. It exists to make CI fast; "
        "if it needs to be this big, something else is wrong."
    )


def test_orders_reference_customers_that_exist(data):
    customers = {row["customer_id"] for row in data["olist_customers_dataset.csv"]}
    orders = {row["customer_id"] for row in data["olist_orders_dataset.csv"]}
    assert orders <= customers, f"{len(orders - customers)} orders have no customer"


def test_children_reference_orders_that_exist(data):
    orders = {row["order_id"] for row in data["olist_orders_dataset.csv"]}
    for filename in (
        "olist_order_items_dataset.csv",
        "olist_order_payments_dataset.csv",
        "olist_order_reviews_dataset.csv",
    ):
        referenced = {row["order_id"] for row in data[filename]}
        orphans = referenced - orders
        assert not orphans, f"{filename}: {len(orphans)} rows have no parent order"


def test_items_reference_products_and_sellers_that_exist(data):
    items = data["olist_order_items_dataset.csv"]
    products = {row["product_id"] for row in data["olist_products_dataset.csv"]}
    sellers = {row["seller_id"] for row in data["olist_sellers_dataset.csv"]}

    assert {row["product_id"] for row in items} <= products
    assert {row["seller_id"] for row in items} <= sellers


def test_every_order_status_survives_sampling(data):
    """`created` has 5 rows in 99,441 — a uniform sample would lose it."""
    statuses = {row["order_status"] for row in data["olist_orders_dataset.csv"]}
    assert statuses == EXPECTED_STATUSES, (
        f"statuses missing from the fixture: {sorted(EXPECTED_STATUSES - statuses)}. "
        "accepted_values would never exercise them in CI."
    )


def test_repeat_customers_are_present(data):
    """Risk R-1 — without these, the guard cannot run in CI at all.

    Only 3.12% of people order twice, so a 1.5% sample of orders lands both
    orders of a repeat customer essentially never. The sampler includes them
    deliberately; this asserts it kept doing so.
    """
    person_of = {
        row["customer_id"]: row["customer_unique_id"]
        for row in data["olist_customers_dataset.csv"]
    }
    counts: dict[str, int] = {}
    for row in data["olist_orders_dataset.csv"]:
        person = person_of[row["customer_id"]]
        counts[person] = counts.get(person, 0) + 1

    repeats = sum(1 for count in counts.values() if count > 1)
    assert repeats >= MIN_REPEAT_CUSTOMERS, (
        f"only {repeats} repeat customers in the fixture. "
        "assert_repeat_customers_exist becomes untestable in CI, and the "
        "tempting fix is to stop running it."
    )


def test_category_translation_is_complete(data):
    """Truncating it would change the dim_products coverage M2 settled."""
    assert len(data["product_category_name_translation.csv"]) == 71


def test_geolocation_keeps_more_than_one_row_per_prefix(data):
    """stg_geolocation must still have something to aggregate (risk R-2)."""
    prefixes: dict[str, int] = {}
    for row in data["olist_geolocation_dataset.csv"]:
        prefix = row["geolocation_zip_code_prefix"]
        prefixes[prefix] = prefixes.get(prefix, 0) + 1

    assert prefixes, "no geolocation rows in the fixture"
    assert max(prefixes.values()) > 1, (
        "every ZIP prefix has exactly one row — the fan-out stg_geolocation "
        "exists to kill is not represented, so its uniqueness test proves nothing"
    )

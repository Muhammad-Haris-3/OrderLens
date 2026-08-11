"""Guard the dbt project's structural rules (SRS FR-2, FR-3).

`dbt build` enforces the data; it needs a loaded warehouse and ~120 MB of CSV
that is not committed, so CI cannot run it. These tests enforce the rules that
can be checked from the files alone, and they run in CI on every push.

Two of them are worth more than they look:

  * `test_staging_models_never_join` encodes the Design Phase's single rule for
    the staging layer (§1.2). Break it and lineage stops being readable — when a
    mart is wrong the fault could be anywhere upstream instead of in one
    identifiable model.

  * `test_delay_days_is_computed_on_calendar_dates` guards the M2 headline
    finding at the source level. The dbt test that guards it in the data needs a
    warehouse; this one does not, so a reversion cannot reach main unnoticed.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

DBT = Path(__file__).resolve().parent.parent / "dbt_orderlens"
STAGING = DBT / "models" / "staging"
MARTS = DBT / "models" / "marts"
DATA_TESTS = DBT / "tests"

# The bespoke tests. Each one catches a failure that is structurally valid and
# semantically wrong — the kind no schema test can see. Named individually
# because deleting one is exactly the change that must not pass review.
BESPOKE_TESTS = {
    "assert_repeat_customers_exist.sql":              "risk R-1",
    "assert_fct_orders_grain_preserved.sql":          "risk R-2 and any fan-out",
    "assert_delay_days_is_whole_days.sql":            "M2 finding F-01",
    "assert_durations_are_never_negative.sql":        "M2 finding F-08",
    "assert_centroids_inside_brazil.sql":             "M2 finding F-13",
    "assert_delivery_measures_respect_eligibility.sql": "M2 finding F-03",
    "assert_order_value_reconciles_to_items.sql":     "cross-grain revenue agreement",
}

EXPECTED_STAGING = {
    "stg_orders", "stg_order_items", "stg_order_payments", "stg_order_reviews",
    "stg_customers", "stg_sellers", "stg_products", "stg_product_categories",
    "stg_geolocation",
}

EXPECTED_MARTS = {
    "dim_customers", "dim_products", "dim_sellers", "dim_geography", "dim_dates",
    "fct_orders", "fct_order_items", "fct_payments",
}


def model_sql(path: Path) -> str:
    """Model body with comments stripped — comments discuss joins constantly."""
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"\{#.*?#\}", " ", text, flags=re.DOTALL)   # jinja comments
    text = re.sub(r"--[^\n]*", " ", text)                     # sql comments
    return text


def documented_models() -> set[str]:
    names: set[str] = set()
    for schema_file in DBT.glob("models/**/_*_models.yml"):
        parsed = yaml.safe_load(schema_file.read_text(encoding="utf-8"))
        names.update(m["name"] for m in parsed.get("models", []))
    return names


def test_all_expected_models_exist():
    staging = {p.stem for p in STAGING.glob("*.sql")}
    marts = {p.stem for p in MARTS.glob("*.sql")}

    assert staging == EXPECTED_STAGING, f"staging drift: {staging ^ EXPECTED_STAGING}"
    assert marts == EXPECTED_MARTS, f"marts drift: {marts ^ EXPECTED_MARTS}"


def test_staging_models_never_join():
    """Design Phase §1.2 — one staging model reads exactly one source.

    stg_geolocation aggregates, which is not joining; it is the documented
    exception to nothing.
    """
    for path in sorted(STAGING.glob("*.sql")):
        body = model_sql(path).lower()
        assert not re.search(r"\bjoin\b", body), (
            f"{path.name} contains a join. Staging models read one source and do "
            "not join (Design Phase §1.2) — joins belong in marts."
        )


def test_staging_models_read_sources_not_refs():
    for path in sorted(STAGING.glob("*.sql")):
        body = model_sql(path)
        assert "source(" in body, f"{path.name} reads no source"
        assert "ref(" not in body, (
            f"{path.name} refs another model. Staging is 1:1 with raw."
        )


def test_marts_read_refs_not_sources():
    """Marts must not reach past staging into raw.

    A mart reading `source()` directly bypasses every cast, rename and cleaning
    rule staging applies — including the review dedup and the geolocation
    aggregation that kills risk R-2.
    """
    for path in sorted(MARTS.glob("*.sql")):
        body = model_sql(path)
        assert "source(" not in body, (
            f"{path.name} reads a raw source directly, bypassing staging."
        )


def test_every_model_is_documented():
    """NFR-5 — every model carries a description."""
    documented = documented_models()
    built = EXPECTED_STAGING | EXPECTED_MARTS

    assert built <= documented, f"undocumented models: {sorted(built - documented)}"


def test_every_bespoke_test_exists():
    present = {p.name for p in DATA_TESTS.glob("*.sql")}
    for filename, guards in BESPOKE_TESTS.items():
        assert filename in present, f"missing bespoke test for {guards}: {filename}"


def test_delay_days_is_computed_on_calendar_dates():
    """M2 finding F-01 — the project's most expensive bug, guarded at the source.

    The timestamp form of this subtraction returns a valid signed number for
    every delivered order and fails nothing. It just makes the delay-to-
    satisfaction gap come back 14.4% smaller.
    """
    body = model_sql(MARTS / "fct_orders.sql")

    match = re.search(
        r"delivered_at\s*(::date)?\s*-\s*estimated_delivery_date", body
    )
    assert match, "fct_orders no longer computes delay_days from those two columns"
    assert match.group(1) == "::date", (
        "fct_orders computes delay_days without casting delivered_at to ::date. "
        "estimated_delivery_date is a DATE stored at midnight and no delivery "
        "lands at midnight, so this counts every on-the-promised-day arrival as "
        "late — 1,292 orders, understating the headline effect by 14.4% (M2 F-01)."
    )


def test_fct_orders_left_joins_items():
    """M2 finding F-04 — 775 orders have no items and must survive the join."""
    body = model_sql(MARTS / "fct_orders.sql").lower()
    assert re.search(r"left\s+join\s+items\b", body), (
        "fct_orders must LEFT JOIN its item roll-up. An inner join deletes the "
        "775 unfulfilled orders, which are the population BQ-1 asks about."
    )


def test_dim_customers_is_keyed_on_the_person():
    """Risk R-1 — customer_unique_id, never customer_id."""
    body = model_sql(MARTS / "dim_customers.sql")
    assert "customer_unique_id" in body

    selected = body.split("select")[-1]
    assert "customer_id" not in selected.replace("customer_unique_id", ""), (
        "dim_customers appears to select customer_id in its final projection — "
        "the grain is the person (customer_unique_id), not the order."
    )

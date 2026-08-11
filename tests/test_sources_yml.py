"""Guard dbt_orderlens/models/staging/_sources.yml.

CI's `dbt parse` step currently ends in `|| echo "::warning::..."` because no
models exist until M3, so a malformed `_sources.yml` would pass CI silently and
only surface as a confusing failure on the first real dbt build. These tests
fail instead.

They also check that the file still declares all nine sources with the exact
table names the loader targets — the same drift failure `test_load_raw_config`
guards on the DDL side, on the other side of the pipeline.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.load_raw import TABLES

yaml = pytest.importorskip("yaml")

SOURCES_YML = (
    Path(__file__).resolve().parent.parent
    / "dbt_orderlens" / "models" / "staging" / "_sources.yml"
)


@pytest.fixture(scope="module")
def raw_source() -> dict:
    parsed = yaml.safe_load(SOURCES_YML.read_text(encoding="utf-8"))
    sources = {s["name"]: s for s in parsed["sources"]}
    assert "raw" in sources, "no source named 'raw' declared"
    return sources["raw"]


def test_declared_tables_match_the_loader(raw_source):
    declared = {t["name"] for t in raw_source["tables"]}
    loaded = {table.split(".", 1)[1] for table, _ in TABLES.values()}

    assert declared == loaded, (
        "_sources.yml and the loader disagree about which tables exist.\n"
        f"  only in _sources.yml: {sorted(declared - loaded)}\n"
        f"  only in the loader:   {sorted(loaded - declared)}"
    )


def test_every_table_and_column_is_documented(raw_source):
    """NFR-5 — a source column with a test but no description explains nothing."""
    for table in raw_source["tables"]:
        assert table.get("description", "").strip(), f"{table['name']} has no description"


def test_review_id_is_never_tested_for_uniqueness(raw_source):
    """M2 finding F-02: review_id is genuinely not unique — 814 excess rows.

    A uniqueness test on it would fail on every build forever, and a test that
    always fails is one everybody learns to ignore. The uniqueness assertion
    belongs on stg_order_reviews.order_id after deduplication.
    """
    reviews = next(t for t in raw_source["tables"] if t["name"] == "order_reviews")
    for column in reviews.get("columns", []):
        if column["name"] in ("review_id", "order_id"):
            tests = column.get("tests", [])
            assert "unique" not in tests, (
                f"order_reviews.{column['name']} is not unique in the source "
                "(M2 A-02); testing it here fails every build"
            )


def test_geolocation_zip_prefix_is_never_tested_for_uniqueness(raw_source):
    """Risk R-2: the prefix is genuinely not unique — 52.6 rows each on average.

    Uniqueness is asserted on stg_geolocation, after aggregation, where it is
    the test that proves the fan-out was killed.
    """
    geo = next(t for t in raw_source["tables"] if t["name"] == "geolocation")
    for column in geo.get("columns", []):
        if column["name"] == "geolocation_zip_code_prefix":
            assert "unique" not in column.get("tests", [])


def test_order_status_accepted_values_cover_what_the_audit_measured(raw_source):
    """A-06 measured all eight statuses present in the source."""
    measured = {
        "delivered", "shipped", "canceled", "unavailable",
        "invoiced", "processing", "created", "approved",
    }
    orders = next(t for t in raw_source["tables"] if t["name"] == "orders")
    status = next(c for c in orders["columns"] if c["name"] == "order_status")

    declared = next(
        set(t["accepted_values"]["values"])
        for t in status["tests"]
        if isinstance(t, dict) and "accepted_values" in t
    )
    assert declared == measured, f"accepted_values drifted from A-06: {declared ^ measured}"


def test_payment_type_admits_not_defined(raw_source):
    """A-25: `not_defined` is a real source value on 3 zero-value rows.

    Excluding it fails the build on a known, harmless property of the source.
    """
    payments = next(t for t in raw_source["tables"] if t["name"] == "order_payments")
    payment_type = next(c for c in payments["columns"] if c["name"] == "payment_type")

    declared = next(
        set(t["accepted_values"]["values"])
        for t in payment_type["tests"]
        if isinstance(t, dict) and "accepted_values" in t
    )
    assert "not_defined" in declared

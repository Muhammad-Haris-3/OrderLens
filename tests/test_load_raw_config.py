"""Guard the loader against drifting out of sync with the raw DDL.

These run without the dataset or a database, so CI can enforce them on every
push. The failure they prevent is nasty and silent: if a column is added to
sql/raw_schema.sql but not to the loader's expected header (or vice versa),
`COPY` shifts every subsequent column by one and lands a fully populated,
entirely wrong table.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.load_raw import TABLES

RAW_SCHEMA = Path(__file__).resolve().parent.parent / "sql" / "raw_schema.sql"


def parse_ddl_columns() -> dict[str, list[str]]:
    """Extract {table_name: [column, ...]} from the CREATE TABLE statements."""
    sql = RAW_SCHEMA.read_text(encoding="utf-8")
    tables: dict[str, list[str]] = {}

    for match in re.finditer(
        r"CREATE TABLE (\w+\.\w+)\s*\((.*?)\n\);", sql, re.DOTALL
    ):
        name, body = match.group(1), match.group(2)
        columns = []
        for line in body.splitlines():
            line = line.split("--")[0].strip().rstrip(",")
            if not line:
                continue
            columns.append(line.split()[0])
        tables[name] = columns

    return tables


@pytest.fixture(scope="module")
def ddl_columns() -> dict[str, list[str]]:
    return parse_ddl_columns()


def test_ddl_parsed_successfully(ddl_columns):
    # If the regex silently matches nothing, every other test would vacuously pass.
    assert len(ddl_columns) >= 10, f"only parsed {len(ddl_columns)} tables from the DDL"


def test_every_loader_table_exists_in_ddl(ddl_columns):
    for filename, (table, _) in TABLES.items():
        assert table in ddl_columns, f"{filename} targets {table}, absent from raw_schema.sql"


def test_loader_headers_match_ddl_columns(ddl_columns):
    for filename, (table, expected_header) in TABLES.items():
        assert list(expected_header) == ddl_columns[table], (
            f"{filename} -> {table}: loader header and DDL columns disagree.\n"
            f"  loader: {list(expected_header)}\n"
            f"  ddl:    {ddl_columns[table]}"
        )


def test_no_duplicate_target_tables():
    targets = [table for table, _ in TABLES.values()]
    assert len(targets) == len(set(targets)), "two source files target the same table"


def test_all_nine_source_tables_are_covered():
    # The load_log table is infrastructure, not source data.
    assert len(TABLES) == 9, f"expected 9 source files, loader declares {len(TABLES)}"


def test_customer_unique_id_is_present_in_customers_header():
    # Risk R-1: retention analysis is impossible without this column landing.
    _, header = TABLES["olist_customers_dataset.csv"]
    assert "customer_unique_id" in header

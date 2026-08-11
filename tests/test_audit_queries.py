"""Guard the M2 audit query set (SRS FR-4, NFR-2).

These run without a database, so CI enforces them on every push. What they
protect is the audit's claim to be evidence: every figure in
`docs/data_quality_audit.md` cites a check id, and that citation is only worth
anything if the id resolves to a committed query that still exists, still
parses, and still only reads.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.run_audit import AUDIT_DIR, ID_RE, load_checks, parse_check

ROOT = Path(__file__).resolve().parent.parent
AUDIT_DOC = ROOT / "docs" / "data_quality_audit.md"
RAW_INDEXES = ROOT / "sql" / "raw_indexes.sql"

# The audit reads; it never writes. A stray write in a query that runs against
# the warehouse under an analyst's credentials is the one failure mode here that
# damages the thing being measured.
FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|truncate|alter|create|grant|revoke|copy)\b",
    re.IGNORECASE,
)

# Decisions the Design Phase §10 deferred to this milestone. Each must be
# answered by at least one committed query, or M3 is unblocked by assertion.
DEFERRED_DECISIONS = ["D-1", "D-2", "D-3", "D-4", "D-5"]


@pytest.fixture(scope="module")
def checks():
    return load_checks()


def test_audit_directory_is_not_empty(checks):
    # If the glob silently matched nothing, every other test would vacuously pass.
    assert len(checks) >= 20, f"only {len(checks)} audit queries found in {AUDIT_DIR}"


def test_every_id_is_well_formed_and_unique(checks):
    ids = [c.id for c in checks]
    assert len(ids) == len(set(ids))
    for check_id in ids:
        assert ID_RE.match(check_id), f"{check_id} is not of the form A-01"


def test_ids_are_contiguous(checks):
    # A gap means a check was deleted; the audit document may still cite it.
    numbers = sorted(int(c.id.split("-")[1]) for c in checks)
    assert numbers == list(range(1, len(numbers) + 1)), f"non-contiguous ids: {numbers}"


def test_filename_matches_id(checks):
    for check in checks:
        expected_prefix = "a" + check.id.split("-")[1]
        assert check.path.name.startswith(expected_prefix + "_"), (
            f"{check.path.name} declares {check.id}; filename should start '{expected_prefix}_'"
        )


def test_every_check_has_a_title_and_a_question(checks):
    for check in checks:
        assert check.title.strip(), f"{check.id} has an empty title"
        assert len(check.question.strip()) > 20, f"{check.id} has a stub question"


def test_every_check_is_a_single_read_only_statement(checks):
    for check in checks:
        assert check.sql.rstrip().endswith(";"), f"{check.id}: SQL does not end with ';'"
        assert check.sql.count(";") == 1, (
            f"{check.id}: expected exactly one statement, found {check.sql.count(';')} semicolons"
        )
        forbidden = FORBIDDEN_SQL.search(check.sql)
        assert forbidden is None, (
            f"{check.id} contains a write/DDL keyword: {forbidden.group(0)!r}. "
            "Audit queries read only."
        )


def test_every_check_reads_the_raw_schema(checks):
    # An audit query that reads no source table is measuring nothing.
    for check in checks:
        assert "raw." in check.sql, f"{check.id} references no raw table"


def test_deferred_design_decisions_are_all_covered(checks):
    covered = " ".join(f"{c.question} {c.title}" for c in checks)
    for decision in DEFERRED_DECISIONS:
        assert decision in covered, (
            f"Design Phase §10 decision {decision} is not addressed by any audit query"
        )


def test_audit_document_only_cites_ids_that_exist(checks):
    if not AUDIT_DOC.exists():
        pytest.skip("audit document not written yet")

    known = {c.id for c in checks}
    cited = set(re.findall(r"\bA-\d{2}\b", AUDIT_DOC.read_text(encoding="utf-8")))
    assert cited <= known, f"audit document cites checks that do not exist: {sorted(cited - known)}"


def test_audit_document_cites_evidence_at_all(checks):
    if not AUDIT_DOC.exists():
        pytest.skip("audit document not written yet")

    cited = set(re.findall(r"\bA-\d{2}\b", AUDIT_DOC.read_text(encoding="utf-8")))
    assert len(cited) >= 20, (
        f"audit document cites only {len(cited)} checks — findings should trace to queries (NFR-2)"
    )


def test_raw_indexes_add_nothing_but_indexes():
    """The index file must not become a place where data quietly gets changed."""
    statements = [
        s.strip()
        for s in re.sub(r"--[^\n]*", "", RAW_INDEXES.read_text(encoding="utf-8")).split(";")
        if s.strip()
    ]
    assert statements, "sql/raw_indexes.sql contains no statements"
    for statement in statements:
        assert statement.upper().startswith("CREATE INDEX IF NOT EXISTS"), (
            f"non-index statement in sql/raw_indexes.sql: {statement[:60]!r}"
        )


def test_wrapped_header_field_is_not_truncated(tmp_path):
    """Regression: a question wrapped over two lines was silently cut at the break.

    The report then showed half a sentence, which reads as a typo rather than as
    the parsing bug it is.
    """
    sql_file = tmp_path / "a99_wrapped.sql"
    sql_file.write_text(
        "-- id: A-99\n"
        "-- title: Wrapped\n"
        "-- question: First part of the question\n"
        "--   and the second part.\n"
        "--\n"
        "-- Rationale paragraph that must not be appended to the question.\n"
        "select 1 from raw.orders;\n",
        encoding="utf-8",
    )

    check = parse_check(sql_file)
    assert check.question == "First part of the question and the second part."


def test_malformed_header_is_rejected(tmp_path):
    sql_file = tmp_path / "a98_no_id.sql"
    sql_file.write_text("-- title: No id here\nselect 1;\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing header field"):
        parse_check(sql_file)

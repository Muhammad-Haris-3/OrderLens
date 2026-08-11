"""Run the committed data-quality audit queries against the warehouse (SRS FR-4).

Every anomaly reported in `docs/data_quality_audit.md` is produced by one of the
`.sql` files in `sql/audit/`, and this script is what runs them. That is the
whole point: an audit whose numbers come from an unsaved console session is an
assertion, not evidence (SRS NFR-2).

Output is written to `docs/data_quality_audit_results.md` — a generated file
containing, for each check, the exact SQL and the exact rows it returned.
Re-running it after a reload regenerates the evidence and any drift shows up as
a diff.

The script reports; it does not judge. A check returning "8 delivered orders
have no delivery timestamp" is a fact. Whether that is acceptable, and what is
done about it, is adjudicated by a human in the audit document.

Usage:
    python scripts/run_audit.py                # run all checks, write results
    python scripts/run_audit.py --list         # list checks, no database needed
    python scripts/run_audit.py --only A-01 A-07
    python scripts/run_audit.py --stdout       # print instead of writing the file
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT_DIR = ROOT / "sql" / "audit"
DEFAULT_OUT = ROOT / "docs" / "data_quality_audit_results.md"

# Header metadata each audit file must declare, e.g. "-- id: A-01".
HEADER_RE = re.compile(r"^--\s*(id|title|question)\s*:\s*(.+?)\s*$", re.IGNORECASE)
# A field may wrap onto following lines, which are indented by three spaces after
# the comment marker. Without this a wrapped question is silently truncated at
# the line break, and the report shows half a sentence.
CONTINUATION_RE = re.compile(r"^--\s{3,}(\S.*?)\s*$")
ID_RE = re.compile(r"^A-\d{2}$")

# Cell width in the rendered markdown. Review comment text runs to paragraphs;
# an untruncated cell would make the results file unreadable.
MAX_CELL = 80


@dataclass(frozen=True)
class Check:
    id: str
    title: str
    question: str
    sql: str
    path: Path


def parse_check(path: Path) -> Check:
    """Read one audit file into a Check, or raise if its header is malformed.

    The header is the leading run of comment and blank lines; the SQL is
    everything from the first line that is neither. Rationale comments may sit
    freely in the header alongside the three required fields.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    meta: dict[str, str] = {}
    body: list[str] = []

    in_header = True
    last_field: str | None = None
    for line in lines:
        if in_header and (not line.strip() or line.lstrip().startswith("--")):
            stripped = line.strip()
            match = HEADER_RE.match(stripped)
            if match:
                last_field = match.group(1).lower()
                meta[last_field] = match.group(2)
                continue
            continuation = CONTINUATION_RE.match(stripped)
            if continuation and last_field:
                meta[last_field] += " " + continuation.group(1)
                continue
            last_field = None  # a rationale comment ends the wrapped field
            continue
        in_header = False
        body.append(line)

    missing = [k for k in ("id", "title", "question") if k not in meta]
    if missing:
        raise ValueError(f"{path.name}: missing header field(s): {', '.join(missing)}")
    if not ID_RE.match(meta["id"]):
        raise ValueError(f"{path.name}: id {meta['id']!r} is not of the form A-01")

    sql = "\n".join(body).strip()
    if not sql:
        raise ValueError(f"{path.name}: no SQL after the header")

    return Check(meta["id"], meta["title"], meta["question"], sql, path)


def load_checks() -> list[Check]:
    """Parse every audit file, ordered by id."""
    paths = sorted(AUDIT_DIR.glob("*.sql"))
    if not paths:
        raise FileNotFoundError(f"no audit queries found in {AUDIT_DIR}")

    checks = [parse_check(p) for p in paths]

    seen: dict[str, Path] = {}
    for check in checks:
        if check.id in seen:
            raise ValueError(
                f"duplicate audit id {check.id}: {seen[check.id].name} and {check.path.name}"
            )
        seen[check.id] = check.path

    return sorted(checks, key=lambda c: c.id)


def render_cell(value: object) -> str:
    if value is None:
        return "_null_"
    text = str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")
    if len(text) > MAX_CELL:
        text = text[: MAX_CELL - 1] + "…"
    return text


def render_table(columns: list[str], rows: list[tuple]) -> str:
    if not rows:
        return "_No rows returned — the condition this check looks for was not found._\n"

    lines = [
        "| " + " | ".join(columns) + " |",
        "|" + "|".join("---" for _ in columns) + "|",
    ]
    lines.extend("| " + " | ".join(render_cell(v) for v in row) + " |" for row in rows)
    return "\n".join(lines) + "\n"


def render_report(results: list[tuple[Check, list[str], list[tuple]]], db_version: str) -> str:
    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    parts = [
        "# OrderLens — Data-Quality Audit Results (generated)",
        "",
        "**Do not edit by hand.** Regenerate with `python scripts/run_audit.py`.",
        "",
        "This file is the *evidence*. The adjudication — what each anomaly means and",
        "what was decided about it — lives in [data_quality_audit.md](data_quality_audit.md).",
        "",
        f"| Generated | {generated_at} |",
        "|---|---|",
        f"| Checks run | {len(results)} |",
        f"| Warehouse | {db_version} |",
        "",
        "---",
        "",
    ]

    for check, columns, rows in results:
        parts += [
            f"## {check.id} — {check.title}",
            "",
            f"**Question:** {check.question}",
            "",
            f"Source: [`sql/audit/{check.path.name}`](../sql/audit/{check.path.name})",
            "",
            render_table(columns, rows),
            "",
        ]

    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true",
                        help="list the checks and exit; no database required")
    parser.add_argument("--only", nargs="+", metavar="ID",
                        help="run only these check ids (e.g. A-01 A-07)")
    parser.add_argument("--stdout", action="store_true",
                        help="print the report instead of writing the results file")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help=f"output path (default: {DEFAULT_OUT.relative_to(ROOT)})")
    args = parser.parse_args()

    try:
        checks = load_checks()
    except (ValueError, FileNotFoundError) as exc:
        print(f"Audit query set is invalid: {exc}")
        return 1

    if args.only:
        wanted = {i.upper() for i in args.only}
        unknown = wanted - {c.id for c in checks}
        if unknown:
            print(f"Unknown check id(s): {', '.join(sorted(unknown))}")
            return 1
        checks = [c for c in checks if c.id in wanted]

    if args.list:
        for check in checks:
            print(f"  {check.id}  {check.title}")
        print(f"\n{len(checks)} checks in {AUDIT_DIR.relative_to(ROOT)}")
        return 0

    # Imported here so --list works in an environment without the driver.
    import psycopg2
    from dotenv import load_dotenv

    load_dotenv()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is not set. Copy .env.example to .env and fill it in.")
        return 1

    results: list[tuple[Check, list[str], list[tuple]]] = []
    conn = psycopg2.connect(database_url)
    try:
        # Read-only: the audit must never be able to change what it is auditing.
        conn.set_session(readonly=True, autocommit=True)
        with conn.cursor() as cur:
            cur.execute("SELECT split_part(version(), ' on ', 1)")
            db_version = cur.fetchone()[0]

            for check in checks:
                print(f"  {check.id}  {check.title}")
                cur.execute(check.sql)
                columns = [d[0] for d in cur.description]
                results.append((check, columns, cur.fetchall()))
    finally:
        conn.close()

    report = render_report(results, db_version)

    if args.stdout:
        print()
        print(report)
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
        print(f"\n{len(results)} checks run — results written to {args.out.relative_to(ROOT)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Run dbt with the warehouse credentials from .env already loaded.

dbt's postgres adapter reads discrete DBT_* environment variables, but the
credentials live in .env alongside DATABASE_URL. Without this wrapper the
documented command sequence differs per shell — `export` on bash, `$env:` on
PowerShell, `set` on cmd — and NFR-1 asks for *one* sequence that rebuilds the
warehouse from a clean clone.

Usage:
    python scripts/run_dbt.py build          # everything: models then tests
    python scripts/run_dbt.py run
    python scripts/run_dbt.py test
    python scripts/run_dbt.py build --select fct_orders+

Any arguments are passed straight through to dbt; --project-dir and
--profiles-dir are supplied automatically.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
PROJECT_DIR = ROOT / "dbt_orderlens"

REQUIRED = ("DBT_HOST", "DBT_USER", "DBT_PASSWORD", "DBT_DBNAME", "DBT_SCHEMA", "DBT_PORT")


def main() -> int:
    if not sys.argv[1:]:
        print(__doc__)
        return 1

    load_dotenv(ROOT / ".env")

    missing = [key for key in REQUIRED if not os.environ.get(key)]
    if missing:
        print(f"Missing in .env: {', '.join(missing)}")
        print("Copy .env.example to .env and fill it in.")
        return 1

    # `python -m dbt.cli.main` rather than the `dbt` console script: the script
    # is only on PATH when the virtualenv is activated, and half the point of
    # this wrapper is that it works whether or not it is.
    command = [
        sys.executable, "-m", "dbt.cli.main",
        *sys.argv[1:],
        "--project-dir", str(PROJECT_DIR),
        "--profiles-dir", str(PROJECT_DIR),
    ]
    # shell=False, list form: no interpolation of anything the user typed.
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())

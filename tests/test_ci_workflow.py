"""Guard the CI workflow itself (SRS NFR-3).

A syntax error here does not fail a build — it stops the workflow existing, and
GitHub reports it somewhere nobody looks. Everything else in this suite is
enforced *by* CI, so CI is the one thing that has to be checked another way.

Written after breaking it: `--vars '{min_repeat_customers: 50}'` as a plain YAML
scalar contains ": ", which YAML reads as a mapping indicator and rejects.
"""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "ci.yml"


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def steps(workflow) -> list[dict]:
    return workflow["jobs"]["quality"]["steps"]


def test_workflow_parses(workflow):
    assert workflow["jobs"]["quality"]["steps"]


def test_ci_has_a_warehouse_to_test_against(workflow):
    """NFR-3 — without this, the dbt data tests cannot run in CI at all."""
    services = workflow["jobs"]["quality"].get("services", {})
    assert "postgres" in services, (
        "CI has no Postgres service, so `dbt build` cannot run and the 193 data "
        "tests would only ever execute on someone's laptop"
    )


def test_ci_runs_the_full_dbt_build(steps):
    """`dbt parse` compiles the project; only `dbt build` runs the tests."""
    commands = " ".join(step.get("run", "") for step in steps)

    assert "dbt build" in commands, (
        "CI no longer runs `dbt build`. Parsing the project is not testing it — "
        "NFR-3 asks for the dbt tests, not a syntax check."
    )
    assert "scripts/load_raw.py --data-dir tests/fixtures/raw_sample" in commands, (
        "CI no longer loads the sample fixture, so `dbt build` has no data"
    )


def test_ci_runs_lint_and_python_tests(steps):
    commands = " ".join(step.get("run", "") for step in steps)
    assert "ruff check ." in commands
    assert "pytest" in commands


def test_ci_does_not_point_at_a_real_warehouse(workflow):
    """The throwaway Postgres must be local, or CI would write to production."""
    env = workflow["jobs"]["quality"]["env"]

    assert "localhost" in env["DATABASE_URL"], (
        f"CI DATABASE_URL is not local: {env['DATABASE_URL']!r}. CI truncates "
        "and reloads every raw table — pointing it at a real warehouse would "
        "replace the dataset with the 1,550-order fixture."
    )
    assert env["DBT_HOST"] == "localhost"

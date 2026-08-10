# OrderLens — M0 (Foundation) Milestone Summary

**Date:** 2026-08-11
**Status:** Complete
**Maps to:** SRS §12 (M0), NFR-1 (reproducibility), NFR-3 (testability)

---

## 1. Scope

Establish a reproducible skeleton before any analysis: repository structure,
warehouse DDL, an idempotent loader, CI, and the documented definitions the whole
analysis will rest on. No data is analysed in M0 — the point is that everything
after it is repeatable.

---

## 2. What was built

| Artefact | Purpose |
|---|---|
| `OrderLens_SRS_v1.0.md` | 21 functional + 8 non-functional requirements, feasibility study, architecture decisions with rejected alternatives, analysis plan, 7 risks |
| `sql/raw_schema.sql` | RAW layer DDL — 9 source tables plus `raw.load_log` |
| `scripts/load_raw.py` | Idempotent COPY-based loader with row-count reconciliation and a `--check` dry-run |
| `dbt_orderlens/` | dbt project scaffold, materialisation strategy, `_sources.yml` documenting all 9 sources with tests |
| `docs/data_dictionary.md` | Source fields, and every derived measure's exact formula |
| `tests/test_load_raw_config.py` | 6 tests guarding loader/DDL drift |
| `.github/workflows/ci.yml` | ruff + pytest on every push |
| `README.md` | Leads with the business question, not the stack |

---

## 3. Three decisions worth recording

### 3.1 The RAW layer is entirely untyped text

Every raw column is `text`, with no constraints, no foreign keys, no `NOT NULL`.

This looks lazy and is the opposite. Typing at load time makes Postgres reject
malformed rows — which means the anomalies M2 exists to *find and quantify* would
instead vanish at the door, and the audit would report a suspiciously clean
dataset. Casting happens in dbt staging, where a failed cast is a visible,
testable event attached to a named model.

### 3.2 Order value comes from `order_items`, not `order_payments`

Both look like they measure what the customer paid. They don't:
payments include installment interest and split across multiple instruments, so
summing them inflates revenue and double-counts split payments.

Committing this to the data dictionary in M0 — before anyone writes a revenue
query — is what stops two analyses quietly disagreeing later.

### 3.3 Two source traps are documented as risks *before* being hit

- **R-1 — `customer_id` vs `customer_unique_id`.** `customer_id` is regenerated
  per order. Keying retention on it yields a 100% single-purchase customer base:
  a wrong answer that looks completely plausible and would invalidate FR-6 and
  FR-7 silently. `_sources.yml` documents this on the column itself.
- **R-2 — geolocation fan-out.** `geolocation` holds ~1M rows across ~19k ZIP
  prefixes. Joining it directly to a fact table multiplies rows and inflates
  revenue. It must be aggregated to one row per prefix first, with a row-count
  assertion after the join.

Writing these down in M0 costs minutes. Discovering them in M5, after building
analysis on top, costs the analysis.

---

## 4. How it was verified

Not "should work" — actually run:

| Check | Result |
|---|---|
| `pytest -q` | **6 passed** |
| `ruff check .` | clean (after fixing one E741 flagged on first run) |
| `python scripts/load_raw.py --check` with no data present | Correctly failed, listed all 9 missing files, exited 1, pointed to `data/raw/README.md` |
| DDL/loader cross-check | The test suite parses `raw_schema.sql` and asserts every loader header matches the DDL column list exactly — it passes, so the two are provably in sync today |

The DDL-parsing test carries its own guard (`test_ddl_parsed_successfully`)
asserting at least 10 tables were extracted. Without it, a regex that silently
matched nothing would make every other test in the file vacuously pass — a
green suite proving nothing.

---

## 5. Definition of Done

| Criterion | Status |
|---|---|
| Artefacts committed | ✅ |
| Automated tests pass | ✅ 6/6, lint clean |
| Every figure traceable | ✅ n/a — no figures produced in M0 |
| Assumptions recorded | ✅ §3, plus SRS §6.3 and §13 |
| Milestone summary written | ✅ this document |

---

## 6. Open items carried into M1

Two steps need credentials and therefore a human:

1. **Provision a Neon database** — a *new* one, not the InsightForge database.
   Fill `DATABASE_URL` and the `DBT_*` variables in `.env`.
2. **Download the dataset** from Kaggle into `data/raw/` — see
   [data/raw/README.md](data/raw/README.md). Kaggle requires an account, so this
   is a manual step by design.

Once both are done, M1 is: run `sql/raw_schema.sql`, run the loader, and confirm
`raw.load_log` reconciles for all nine tables.

---

## 7. Next: M1 — Ingestion

Load the raw layer and reconcile row counts (FR-1). Expected to be short — the
loader is already written and tested. The real work begins at M2, where the
data-quality audit determines what the analysis plan can honestly support.

---

## Document Control

| Field | Value |
|---|---|
| Milestone | M0 — Foundation |
| SRS version | 1.0 |
| Next document | `OrderLens_M1_Summary.md` |

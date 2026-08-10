# OrderLens — M1 (Ingestion) Milestone Summary

**Date:** 2026-08-11
**Status:** Complete
**Maps to:** SRS FR-1 (load all 9 source tables into the raw layer, reconciled)

---

## 1. Scope

Provision the warehouse, run the raw DDL, load all nine source CSVs, and prove
by reconciliation that nothing was silently dropped or shifted.

---

## 2. What was done

| Step | Result |
|---|---|
| Neon Postgres database provisioned | PostgreSQL 18.4, direct (non-pooled) endpoint |
| `sql/raw_schema.sql` applied | 10 tables created — 9 source + `raw.load_log` |
| Nine CSVs loaded via `scripts/load_raw.py` | 1,550,922 rows total, all reconciled |

### Loaded row counts

| Table | Rows |
|---|---|
| `raw.geolocation` | 1,000,163 |
| `raw.order_items` | 112,650 |
| `raw.order_payments` | 103,886 |
| `raw.orders` | 99,441 |
| `raw.customers` | 99,441 |
| `raw.order_reviews` | 99,224 |
| `raw.products` | 32,951 |
| `raw.sellers` | 3,095 |
| `raw.product_category_translation` | 71 |

`raw.load_log` reports `rows_in_file = rows_loaded` for all nine — FR-1 satisfied
with an audit trail rather than an assertion.

---

## 3. Real issue found and fixed: a UTF-8 BOM in the translation file

The pre-load `--check` failed on the first run:

```
HEADER MISMATCH in product_category_name_translation.csv
  expected: ('product_category_name', 'product_category_name_english')
  actual:   ('﻿product_category_name', 'product_category_name_english')
```

`product_category_name_translation.csv` ships with a **UTF-8 byte-order mark** —
three invisible bytes (`EF BB BF`) before the first character.

**Why it mattered.** Nothing would have crashed. `COPY` would have loaded the
file happily, and the column would have been named `﻿product_category_name` —
visually identical to `product_category_name` in every console and IDE. Every
subsequent join to translate Portuguese category names to English would have
matched **zero rows**, and the failure would have surfaced much later as
"category is mysteriously always null" rather than as an encoding problem.

**Fix.** Read all files with `utf-8-sig`, which strips a BOM when present and is
a no-op when absent — so it is safe for all nine files, not just this one.

**Guarded.** Two regression tests were added (`test_read_header_strips_utf8_bom`,
`test_read_header_unaffected_when_no_bom`) so the fix cannot be silently
reverted. Suite is now 8 tests.

This is precisely the failure the `--check` step was written to catch in M0, and
it caught it on the very first real run.

---

## 4. Both documented risks confirmed empirically

M0 recorded two risks as predictions. Both are now measured facts.

### R-1 — `customer_id` is not a person ✅ confirmed

| Key | Distinct values |
|---|---|
| `customer_id` | 99,441 |
| `customer_unique_id` | **96,096** |

**3,345 repeat orders would be invisible** if retention were keyed on
`customer_id`. The analysis would have reported a 100% first-time customer base
— internally consistent, entirely wrong, and impossible to spot without knowing
to look. FR-6 and FR-7 must key on `customer_unique_id`.

### R-2 — geolocation fan-out ✅ confirmed

1,000,163 rows across **19,015 distinct ZIP prefixes** — an average **52.6×
fan-out**. Joining `raw.geolocation` directly to any fact table would multiply
rows by roughly fifty and inflate every revenue figure accordingly. It must be
aggregated to one row per prefix before use, with a row-count assertion after
the join.

---

## 5. New finding for M2: the category translation table is incomplete

Verifying the BOM fix surfaced something the SRS did not anticipate. Of 32,951
products, only 32,328 match a translation. The 623-row gap decomposes as:

| Cause | Products |
|---|---|
| `product_category_name` is NULL or empty | 610 |
| Category exists but is **missing from the translation table** | 13 |

The two untranslated categories are `portateis_cozinha_e_preparadores_de_alimentos`
and `pc_gamer` — genuinely absent from the 71-row translation file.

**Consequence for M3:** the category join must be a `LEFT JOIN` with an explicit
fallback, never an `INNER JOIN`. An inner join would silently drop 623 products
and every order containing them, quietly biasing category-level revenue analysis.

Carried into M2 for a formal decision on how unmapped categories are labelled.

---

## 6. How it was verified

| Check | Result |
|---|---|
| `pytest -q` | 8 passed |
| `ruff check .` | clean |
| `scripts/load_raw.py --check` | 9 files, headers matched |
| Loader reconciliation | 9/9 `rows_in_file = rows_loaded` |
| `raw.load_log` queried post-load | All nine rows reconcile |
| Category join after BOM fix | 32,328 matches — proves the join works, and quantifies the gap |

Every figure above comes from a query run against the loaded warehouse, not from
the loader's own output — the loader reporting its own success is not evidence.

---

## 7. Definition of Done

| Criterion | Status |
|---|---|
| Artefacts committed | ✅ |
| Automated tests pass | ✅ 8/8, lint clean |
| Every figure traceable to a query | ✅ |
| Assumptions and limitations recorded | ✅ §3, §4, §5 |
| Milestone summary written, including problems found | ✅ this document |

---

## 8. Next: M2 — Data-quality audit

The raw layer is loaded and trustworthy. M2 interrogates it (FR-4):

- Quantify `review_id` duplication (deliberately untested in `_sources.yml`)
- Null profile across every column, especially delivery timestamps by order status
- Order-status distribution, and which statuses are eligible for delivery analysis
- Decide and document handling for the 623 unmapped-category products (§5)
- Check for orders with no items, reviews with no order, and other orphan records
- Confirm the date range and identify the analysis anchor date

Every anomaly gets a documented handling decision with justification — the audit
determines what the analysis plan can honestly support.

---

## Document Control

| Field | Value |
|---|---|
| Milestone | M1 — Ingestion |
| SRS version | 1.0 |
| Previous | `OrderLens_M0_Summary.md` |
| Next document | `OrderLens_M2_Summary.md` |

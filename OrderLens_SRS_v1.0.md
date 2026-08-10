# OrderLens — Software Requirements Specification v1.0

**Project:** OrderLens — Marketplace Operations Analytics
**Author:** Muhammad Haris Khokhar
**Date:** 2026-08-11
**Status:** Approved for M0

---

## 1. Introduction

### 1.1 Purpose

This document specifies the requirements for **OrderLens**, an end-to-end
analytics engagement that quantifies how operational failures in an online
marketplace destroy customer satisfaction and revenue, and recommends a costed
intervention.

Unlike a software product, the deliverable here is **a decision** — supported by
a reproducible data pipeline, a dashboard, and a written recommendation. The
software exists to make the analysis trustworthy and repeatable, not to be used
by end users.

### 1.2 Scope

OrderLens ingests a real marketplace transactional dataset (~100k orders across
9 relational tables), models it into a dimensional warehouse, and answers a
ranked set of business questions using descriptive, inferential, and predictive
methods. It publishes a public dashboard and a decision memo.

**In scope:** data ingestion, dimensional modeling, data-quality testing,
descriptive analysis, hypothesis testing with effect sizes, regression with
controls, a cost-optimised predictive model, a published dashboard, a decision
memo.

**Out of scope:** real-time/streaming ingestion, a user-facing web application,
authentication, deep learning, causal inference requiring instrumental variables
or randomised data.

### 1.3 Definitions

| Term | Meaning |
|---|---|
| **Grain** | The precise meaning of one row in a fact table |
| **Star schema** | Central fact table joined to denormalised dimension tables |
| **dbt** | SQL transformation framework providing modularity, lineage, and tests |
| **Effect size** | Magnitude of a difference, independent of sample size |
| **Late delivery** | `order_delivered_customer_date` > `order_estimated_delivery_date` |
| **Delay days** | Actual delivery date minus estimated delivery date (signed) |
| **CSAT proxy** | `review_score` (1–5) used as the satisfaction outcome |

### 1.4 Intended audience

Primarily hiring managers and technical interviewers assessing analytical
capability. Written so a non-technical reader can follow Sections 2, 11 and the
decision memo, while a technical reader can reproduce every number.

---

## 2. Business context and problem statement

### 2.1 Context

An online marketplace connects independent sellers to customers. The platform
does not control fulfilment directly but is held responsible for it by customers
— a late delivery damages the platform's rating, not just the seller's.

### 2.2 Problem statement

> The platform knows its average review score is falling and that some deliveries
> arrive late. It does **not** know how much a late delivery actually costs, which
> of its many operational problems is most expensive, or where to spend a limited
> remediation budget first.

### 2.3 Primary business question

**Which operational failures cost the most revenue, and what should be fixed
first?**

Decomposed into answerable sub-questions:

| # | Question | Method |
|---|---|---|
| BQ-1 | How large and how frequent are delivery delays? | Descriptive |
| BQ-2 | Does late delivery *cause* lower review scores, or is it confounded? | Inferential + regression controls |
| BQ-3 | What is one day of delay worth in review score and repeat-purchase terms? | Regression |
| BQ-4 | Which segments (category, seller, route, season) concentrate the damage? | Segmentation |
| BQ-5 | Can at-risk orders be identified before delivery? | Classification |
| BQ-6 | What intervention maximises return on a fixed budget? | Cost-benefit |

### 2.4 Success criteria

The project succeeds if it produces a recommendation that names **what to do**,
**to which segment**, **at what cost**, and **with what expected return** — with
every figure traceable to a query in the repository.

---

## 3. Feasibility study

| Dimension | Assessment |
|---|---|
| **Technical** | Feasible. Dataset is ~120 MB across 9 CSVs; Postgres, dbt and Python handle this comfortably on free tiers. No distributed computing required. |
| **Data** | Feasible. Real, public, relational, with delivery timestamps *and* satisfaction scores — the two variables the central question needs. Known quality issues (missing review text, some null delivery dates) are themselves analysable. |
| **Economic** | Zero cost. Neon Postgres free tier, dbt-core (open source), Python, Tableau Public, GitHub — all free. |
| **Schedule** | Feasible for a solo analyst across 8 milestones at part-time pace. |
| **Operational** | Feasible. Read-only analysis of a static historical dataset; no production dependency, no live users, no on-call burden. |
| **Ethical/legal** | Public dataset released for research under an open licence. Contains no direct personal identifiers; customer keys are anonymised hashes. Geolocation is aggregated to ZIP prefix. |

**Verdict: feasible on all dimensions.**

### 3.1 Principal risk to validity

The dataset is **observational, not experimental**. Deliveries were not randomly
assigned to be late. Any causal claim is therefore conditional on the controls
applied, and this limitation must be stated explicitly in every deliverable
rather than buried. Requirement **FR-12** makes this a hard deliverable.

---

## 4. SDLC methodology

**Iterative and incremental**, solo-adapted — the same methodology used
successfully on the InsightForge project.

Each milestone is independently demonstrable and produces a committed artefact.
Analysis milestones additionally require that **every published number is
reproducible from a committed query or script** — no figures derived in an
unsaved notebook cell.

Rationale for iterative over waterfall: the analysis plan depends on what the
data-quality audit (M2) reveals. Committing to a full analysis design before
seeing the data would be dishonest sequencing.

### 4.1 Definition of Done (applies to every milestone)

1. Artefacts committed to the repository.
2. All automated tests pass (dbt tests, Python tests, linting).
3. Every figure in prose traceable to a committed query or script.
4. Assumptions and limitations recorded, not just results.
5. A milestone summary document written, including problems found.

---

## 5. Stakeholders and user characteristics

| Stakeholder | Interest | Implication |
|---|---|---|
| Marketplace operations lead (simulated) | Wants to know where to spend a fixed budget | Deliverables must be costed and ranked |
| Non-technical reviewer | Wants the finding in plain language | Decision memo must stand alone |
| Technical interviewer | Wants to verify rigour | Methods, assumptions and code must be inspectable |

---

## 6. Data source specification

### 6.1 Source

Brazilian e-commerce public dataset (Olist), ~100k orders placed 2016–2018.
Nine relational tables joined on documented keys.

### 6.2 Tables

| Table | Grain | Key fields |
|---|---|---|
| `orders` | One order | order_id, customer_id, status, purchase/approved/carrier/delivered/estimated timestamps |
| `order_items` | One item within an order | order_id, order_item_id, product_id, seller_id, price, freight_value |
| `order_payments` | One payment instrument per order | order_id, payment_type, installments, payment_value |
| `order_reviews` | One review per order | order_id, review_score, timestamps |
| `customers` | One customer per order | customer_id, customer_unique_id, ZIP prefix, city, state |
| `sellers` | One seller | seller_id, ZIP prefix, city, state |
| `products` | One product | product_id, category, weight, dimensions |
| `product_category_translation` | Category name | Portuguese → English |
| `geolocation` | ZIP prefix | latitude, longitude, city, state |

### 6.3 Known data characteristics requiring handling

These are anticipated in advance and confirmed or refuted in M2:

- `customer_id` is **per-order**; `customer_unique_id` identifies the person.
  Using the wrong one silently makes every customer look like a first-time buyer
  and destroys all retention analysis. **This is the single highest-risk
  modelling trap in the dataset.**
- Orders not yet delivered have null `order_delivered_customer_date`.
- `geolocation` has multiple rows per ZIP prefix and requires aggregation before
  joining, or it will fan out the fact table.
- Order status includes cancelled and unavailable orders which must be excluded
  from delivery analysis but retained for cancellation analysis.
- Review scores are heavily skewed toward 5, so mean-based summaries alone will
  mislead.

---

## 7. Functional requirements

Requirements are analytical deliverables. Each is verifiable.

### 7.1 Data foundation

| ID | Requirement | Priority |
|---|---|---|
| **FR-1** | Load all 9 source tables into a Postgres warehouse raw layer without transformation, preserving source fidelity | Must |
| **FR-2** | Transform raw tables into a documented dimensional model (star schema) with declared grain per fact table | Must |
| **FR-3** | Enforce data-quality tests on every model: uniqueness and non-nullity of keys, referential integrity, accepted values, and row-count reconciliation against source | Must |
| **FR-4** | Produce a data-quality audit documenting every anomaly found and the handling decision taken, with justification | Must |

### 7.2 Descriptive analysis

| ID | Requirement | Priority |
|---|---|---|
| **FR-5** | Quantify delivery performance: on-time rate, delay distribution, and trend over time | Must |
| **FR-6** | Produce cohort retention analysis by first-purchase month, keyed on `customer_unique_id` | Must |
| **FR-7** | Segment customers by RFM (recency, frequency, monetary) and profile each segment | Must |
| **FR-8** | Rank revenue concentration by category, seller, and geography | Must |

### 7.3 Inferential analysis

| ID | Requirement | Priority |
|---|---|---|
| **FR-9** | Test whether review scores differ between on-time and late deliveries, reporting the test statistic, p-value, **and effect size with a magnitude interpretation** | Must |
| **FR-10** | State and check the assumptions of every test used; where violated, use an appropriate alternative and record why | Must |
| **FR-11** | Estimate the effect of delay on review score using regression **controlling for** price, freight, category, seller state, customer state and season | Must |
| **FR-12** | Publish an explicit limitations statement covering observational design, unmeasured confounding, and generalisability | Must |
| **FR-13** | Apply multiple-comparison correction where a family of tests is run | Should |

### 7.4 Predictive analysis

| ID | Requirement | Priority |
|---|---|---|
| **FR-14** | Build a classifier predicting whether an order will receive a low review score, using only features available **before** delivery completes | Must |
| **FR-15** | Select the decision threshold by **business cost**, not by F1 — stating the assumed cost of a false positive and false negative | Must |
| **FR-16** | Report performance against a stated naive baseline; a model that fails to beat it must be reported as such | Must |
| **FR-17** | Explain drivers using permutation importance, not impurity importance | Should |

### 7.5 Communication

| ID | Requirement | Priority |
|---|---|---|
| **FR-18** | Publish a public, interactive dashboard covering delivery performance, satisfaction, and segment drill-down | Must |
| **FR-19** | Write a decision memo (≤2 pages) stating finding, recommendation, projected impact, and confidence — readable without technical background | Must |
| **FR-20** | Design an A/B test to validate the recommendation, specifying hypothesis, metric, unit of randomisation, and required sample size | Must |
| **FR-21** | Quantify every recommendation in currency | Must |

---

## 8. Non-functional requirements

| ID | Category | Requirement |
|---|---|---|
| **NFR-1** | Reproducibility | A clean clone must rebuild the entire warehouse from raw data with one documented command sequence |
| **NFR-2** | Traceability | Every figure in any deliverable maps to a committed query or script |
| **NFR-3** | Testability | CI runs dbt tests and Python tests on every push to `main` |
| **NFR-4** | Performance | Full warehouse rebuild completes in under 10 minutes on free-tier Postgres |
| **NFR-5** | Documentation | Every dbt model carries a description and column-level documentation |
| **NFR-6** | Accessibility | Dashboard is colourblind-safe and does not encode meaning by colour alone |
| **NFR-7** | Cost | Zero monetary cost — free tiers only |
| **NFR-8** | Honesty | Negative and null results are reported, not discarded |

**NFR-8 is a requirement, not a platitude.** If delay proves not to drive
satisfaction once controls are applied, that finding is the deliverable.

---

## 9. Architecture

### 9.1 Layered design

```
Source CSVs (9 files)
        │  Python loader (idempotent, chunked)
        ▼
┌──────────────────────────────┐
│ RAW layer      (Postgres)    │  Source fidelity, no transformation
├──────────────────────────────┤
│ STAGING layer  (dbt)         │  Typed, renamed, deduplicated
├──────────────────────────────┤
│ MARTS layer    (dbt)         │  Star schema: facts + dimensions
└──────────────────────────────┘
        │                    │
        ▼                    ▼
  Python analysis      Tableau Public
  (stats, ML)          (dashboard)
        │                    │
        └────────┬───────────┘
                 ▼
          Decision memo
```

### 9.2 Technology decisions and rejected alternatives

| Decision | Chosen | Rejected | Rationale |
|---|---|---|---|
| Warehouse | Postgres (Neon) | DuckDB, BigQuery | Free, persistent, remotely accessible by Tableau; DuckDB is file-local so a dashboard cannot connect to it |
| Transformation | dbt-core | Raw SQL scripts, pandas | Provides lineage, testing and documentation as first-class features; pandas would hide the SQL this project exists to demonstrate |
| Analysis | Python (statsmodels, scipy, scikit-learn) | R | Consistency with existing toolchain; statsmodels gives regression summaries with inference, which scikit-learn does not |
| Dashboard | Tableau Public | Power BI, custom React | Free public publishing without a work account; a custom React dashboard would signal *developer*, and this project must signal *analyst* |
| Orchestration | None (documented sequence) | Airflow, Prefect | Dataset is static and historical; scheduling would be ceremony without purpose |

**Deliberate constraint:** transformation and aggregation happen in **SQL**, not
pandas. Python is reserved for statistics and modelling. This is a portfolio
decision as much as a technical one — SQL depth is the capability this project
exists to evidence.

---

## 10. Conceptual data model

**Facts**

| Model | Grain | Key measures |
|---|---|---|
| `fct_orders` | One delivered order | delay_days, is_late, delivery_days, order_value, freight_total, review_score |
| `fct_order_items` | One item within an order | price, freight_value |
| `fct_payments` | One payment instrument per order | payment_value, installments |

**Dimensions**

`dim_customers` (keyed on `customer_unique_id`), `dim_sellers`, `dim_products`
(with English category), `dim_dates`, `dim_geography` (ZIP prefix, aggregated).

Grain is declared and tested for every fact model — an untested grain is the
most common source of silently double-counted revenue.

---

## 11. Analysis plan and statistical methods

| Stage | Method | Guards against |
|---|---|---|
| Delivery performance | Distribution + time series | Mean hiding a skewed tail |
| On-time vs late satisfaction | Mann-Whitney U (review scores are ordinal and skewed) with rank-biserial effect size | Assuming normality of a 1–5 ordinal scale |
| Category/state differences | Kruskal-Wallis, then pairwise with Benjamini-Hochberg correction | Multiple-comparison false positives |
| Delay → score, controlled | Ordinal or OLS regression with controls; report coefficient, CI, R² | Confounding by price, category, distance, season |
| Retention | Cohort curves on `customer_unique_id` | Per-order customer key destroying repeat detection |
| At-risk prediction | Logistic regression baseline, then gradient boosting; permutation importance | Impurity-importance bias toward high-cardinality features |
| Threshold choice | Expected-cost minimisation over a stated cost matrix | Optimising a metric with no business meaning |

Every test reports **effect size alongside p-value** (FR-9). Statistical
significance without magnitude is not a finding.

---

## 12. Milestone plan

| # | Milestone | Delivers | Maps to |
|---|---|---|---|
| **M0** | Foundation — repo, environment, warehouse connection, CI, data dictionary | Reproducible skeleton | NFR-1, NFR-3 |
| **M1** | Ingestion — raw layer loaded, row counts reconciled | FR-1 |
| **M2** | Data-quality audit — anomalies found, decisions documented | FR-4 |
| **M3** | Dimensional model — staging + marts, all tests green | FR-2, FR-3 |
| **M4** | Descriptive analysis — delivery, cohorts, RFM, revenue concentration | FR-5 – FR-8 |
| **M5** | Inferential analysis — hypothesis tests, effect sizes, controlled regression | FR-9 – FR-13 |
| **M6** | Predictive model — cost-optimised classifier | FR-14 – FR-17 |
| **M7** | Communication — dashboard, decision memo, A/B design | FR-18 – FR-21 |

Each milestone produces `OrderLens_MX_Summary.md` recording what was built, what
broke, and what was decided.

---

## 13. Risks and mitigations

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| R-1 | Using `customer_id` instead of `customer_unique_id` invalidates all retention analysis | High | Explicit dbt test asserting repeat customers exist in `dim_customers`; called out in §6.3 |
| R-2 | Geolocation join fans out fact rows, inflating revenue | High | Aggregate geolocation to one row per ZIP prefix before joining; row-count test after join |
| R-3 | Confounding produces a causal claim the data cannot support | High | FR-11 controls, FR-12 mandatory limitations statement |
| R-4 | Free-tier Postgres too slow for full rebuild | Medium | Index join keys; materialise marts as tables, not views |
| R-5 | Analysis finds no significant effect | Medium | NFR-8 — a null result is a valid deliverable and reported as such |
| R-6 | Scope creep into building a web product | Medium | Out-of-scope list in §1.2 is binding; the deliverable is a decision |
| R-7 | Tableau Public makes data public | Low | Dataset is already public and anonymised |

---

## 14. Acceptance criteria

The project is complete when:

1. A clean clone rebuilds the warehouse via documented commands (NFR-1).
2. All dbt and Python tests pass in CI (NFR-3).
3. Every FR marked *Must* is delivered and traceable.
4. The dashboard is publicly reachable by URL.
5. The decision memo states a recommendation, its cost, its projected return, and
   its confidence — and is intelligible to a non-technical reader.
6. The limitations statement is present and honest.

---

## 15. Document control

| Field | Value |
|---|---|
| Version | 1.0 |
| Status | Approved for M0 |
| Author | Muhammad Haris Khokhar |
| Companion project | InsightForge — analytics *product*; OrderLens is the analytics *engagement* |
| Next document | `OrderLens_Design_Phase_v1.0.md` |

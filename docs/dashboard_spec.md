# Dashboard build specification (FR-18)

**Status:** ✅ **Published** —
[public.tableau.com/app/profile/muhammad.haris2276/viz/OrderLens/Dashboard1](https://public.tableau.com/app/profile/muhammad.haris2276/viz/OrderLens/Dashboard1)

**Satisfies:** FR-18 (public interactive dashboard covering delivery performance,
satisfaction and segment drill-down) and NFR-6 (colourblind-safe, no meaning
encoded by colour alone).

---

## 1. Connection — corrected

> ### ⚠️ The Design Phase assumption was wrong
>
> Design Phase §9 says *"Tableau Public connects directly to `analytics_marts` —
> no extracts, no hand-maintained CSVs, so the dashboard cannot drift from the
> warehouse."* **That is not possible.**
>
> Tableau **Public** — the free edition — offers only file-based and a few cloud
> connectors. PostgreSQL is a paid Tableau Desktop feature, and everything
> published to Tableau Public is uploaded as data rather than queried live.
>
> The assumption was made at M0, chosen the warehouse (§9.2 rejected DuckDB
> partly *because* "a dashboard cannot connect to it"), and went unchallenged
> until someone tried to follow the instructions at M7. Recorded rather than
> quietly edited, because a design decision justified by a false premise is worth
> knowing about.

**The route is a file extract.**

```bash
python scripts/export_dashboard_data.py
```

Writes four CSVs plus a timestamp to `data/dashboard/` (gitignored — derived
artefacts, regenerated in seconds):

| File | Rows | Feeds |
|---|---|---|
| `delivery_monthly.csv` | 20 | View 1 |
| `delay_buckets.csv` | 8 | View 2 |
| `revenue_concentration.csv` | 3,196 | View 3 |
| `orders.csv` | 96,470 | View 3 drill-down |
| `exported_at.csv` | 1 | The freshness stamp |

**What this costs.** The dashboard becomes a snapshot and can drift from the
warehouse — the exact failure the "no extracts" rule existed to prevent. Two
things keep it honest:

1. `exported_at.csv` is placed on the dashboard as a caption. A stale dashboard
   says how stale it is rather than looking current.
2. Refreshing is `export_dashboard_data.py` + re-publish, and it is documented
   here rather than living in someone's memory.

**If a live connection is ever needed**, it requires paid Tableau Desktop plus
Tableau Server/Cloud, or a different tool. That is a cost decision, not a
technical blocker, and it is out of scope under NFR-7 (zero monetary cost).

---

## 2. Sources — one per view, no joins in Tableau

Every aggregate the dashboard shows already exists as a mart, and the export
preserves that. Joining in Tableau would recompute definitions dbt already owns
and let the dashboard disagree with the analysis.

| View | File | Mart behind it | Grain |
|---|---|---|---|
| Operations | `delivery_monthly.csv` | `mart_delivery_monthly` | one purchase month |
| Impact | `delay_buckets.csv` | `mart_delay_buckets` | one delay band |
| Drill-down | `revenue_concentration.csv` | `mart_revenue_concentration` | (dimension, key) |
| Drill-down detail | `orders.csv` | `mart_order_analysis` | one delivery-eligible order |

Add each as a **separate data source** in Tableau, not as a join.

`mart_order_analysis.delay_bucket` uses the same macro as `mart_delay_buckets`,
so the summary and the drill-down cannot disagree — verified: all eight bands
match exactly across the two grains.

---

## 3. The three views

### View 1 — Operations: are we keeping our promise?

| Element | Spec |
|---|---|
| **Headline** | On-time rate, latest month, with month-over-month change |
| **Chart 1** | Line: `pct_late` by `year_month`. Reference line at the 20-month average |
| **Chart 2** | Stacked area: `mean_seller_handover_days` and `mean_carrier_transit_days` by month |
| **Chart 3** | Line: `mean_review_score` by month, dual axis with `pct_late` |
| **Filter** | Date range, defaulting to the full trend window |

**The point of Chart 2 is the split.** "Deliveries are late" is not actionable.
"The carrier owns 74% of the wait and all of the variance, while seller handover
barely moves" is. Annotate the two failure episodes (November 2017, February–March
2018) directly on Chart 1 — both are carrier-side.

**Axis note:** the trend window is 2017-01 to 2018-08. It must be stated *on the
axis*, not in a footnote (M2 F-06): 2016 is a 329-order pilot and the final two
months are a truncated tail with no deliveries.

### View 2 — Impact: what does a broken promise cost?

| Element | Spec |
|---|---|
| **Chart 1** | Bar: `mean_review_score` by `delay_bucket`, ordered by the bucket's leading digit |
| **Chart 2** | Bar: `pct_low_score` by `delay_bucket` |
| **Chart 3** | Bar: `revenue` by `delay_bucket` — the money sitting in each band |
| **Annotation** | A marker between "on the promised day" and "1–7 days late" reading *"the cliff: 12% → 49% low scores"* |

**The cliff is the whole message.** Do not smooth these into a line chart: the
relationship is a step, and a line implies a gradient that does not exist.

Chart 1 needs a **caveat caption**, not a footnote: *"Reviews are sent at
dispatch, so most late orders were reviewed before arrival — these bars partly
measure waiting, not receiving."*

### View 3 — Drill-down: where is it concentrated?

| Element | Spec |
|---|---|
| **Control** | Parameter switching `dimension` between category / seller / customer_state |
| **Chart 1** | Pareto: `revenue` bars descending with `cumulative_pct_of_revenue` as a line, 80% reference line |
| **Chart 2** | Scatter: `pct_late` (x) against `revenue` (y), one mark per member, labelled |
| **Chart 3** | Map: `customer_state` shaded by `pct_late`, sized by revenue |
| **Filter** | Minimum order count, to suppress noisy small segments |

**Chart 2 is the BQ-4 answer** and should be the dashboard's most prominent
panel. It separates *large* from *failing*: São Paulo sits bottom-right (huge
revenue, low failure rate), Rio de Janeiro sits upper-middle (large revenue,
triple the failure rate), Maranhão sits upper-left (small, failing badly). Draw
quadrant lines at the revenue median and the platform late rate, and label the
upper-right quadrant **"fix first"**.

---

## 4. NFR-6 — accessibility

**Colourblind-safe palette.** Tableau's built-in *Color Blind 10*, or:

| Meaning | Hex | |
|---|---|---|
| On time / good | `#0173B2` | blue |
| Late / bad | `#DE8F05` | orange |
| Neutral | `#949494` | grey |
| Emphasis | `#029E73` | green |

Blue–orange rather than red–green: red–green is the pairing 8% of men cannot
distinguish, and it is the pairing every operations dashboard reaches for first.

**No meaning encoded by colour alone.** Every colour-coded state also carries a
second channel:

| Where | Colour | Plus |
|---|---|---|
| Delay buckets | blue → orange ramp | The bucket label on every bar |
| On-time vs late series | blue / orange | Solid vs dashed line, and a direct end-of-line label |
| Scatter quadrants | fill | Quadrant border lines and a text label per quadrant |
| Map | sequential shade | The rate printed in each state's tooltip and on the top five |

**Also:**
- Every axis labelled with its unit (`days`, `%`, `R$`).
- No dual-axis chart without both axes labelled and coloured to match their series.
- Tooltips give the underlying counts, not just the percentage — a 17% late rate
  on 346 orders is not the same claim as 17% on 40,000.
- Minimum 11pt type; no text baked into images.

---

## 5. What the dashboard must not imply

Three guardrails, because a dashboard is read faster than it is explained:

1. **Do not put the classifier on it.** M6 measured 14% precision at the
   operating threshold — six of every seven flagged orders would have been fine.
   A "risk score" column would be acted on far beyond what it can support.
2. **Do not headline the review score as a satisfaction KPI without the
   two-thirds caveat.** 67.5% of low reviews are on orders that arrived on time
   (M6). A delivery dashboard that owns the review score implies delivery drives
   it, and it mostly does not.
3. **Do not show retention.** 2.24% of customers ever return (M4). A cohort
   retention chart at that level is a flat line at zero, and putting it on a
   dashboard invites someone to read a trend into noise.

---

## 6. Publishing — the manual step

Tableau Public requires its desktop client and a personal account, so this step
cannot be automated from here.

1. **Export the data:** `python scripts/export_dashboard_data.py`
2. **Create a free account** at [public.tableau.com](https://public.tableau.com)
   → Sign Up.
3. **Install Tableau Public Desktop** (free) from the same site, and sign in.
4. **Connect:** Connect → To a File → Text file → `data/dashboard/delivery_monthly.csv`.
   Add the other three the same way, each as its own data source.
5. **Build** the three views from §3 as separate sheets, then one dashboard with
   tabs.
6. Put `exported_at` on the dashboard as a caption — a snapshot must say how old
   it is.
7. **File → Save to Tableau Public As…**, sign in, name it `OrderLens`.
8. Copy the resulting URL into the README and SRS §14.4.

**Row limits.** Tableau Public caps a workbook at 15 million rows. The largest
file here is 96,470 rows and 17 MB, so there is no issue — but do not add
`fct_order_items` (112,650 rows) without a reason, and do not export the raw
layer at all.

**Done** —
[public.tableau.com/app/profile/muhammad.haris2276/viz/OrderLens/Dashboard1](https://public.tableau.com/app/profile/muhammad.haris2276/viz/OrderLens/Dashboard1),
closing acceptance criterion §14.4.

**Refreshing it** is `python scripts/export_dashboard_data.py`, then re-open the
workbook and **File → Save to Tableau Public**. The published dashboard is a
snapshot, so the `exported_at` caption is what tells a viewer how old it is.

**One caution before publishing.** Tableau Public makes both the workbook and its
data public (SRS risk R-7). That is acceptable here — the dataset is already
public and anonymised, geolocation is aggregated to ZIP prefix, and customer keys
are opaque hashes. It would not be acceptable against a real marketplace's
warehouse, and the read-only role should be scoped to `analytics_marts` only so
that never becomes a question.

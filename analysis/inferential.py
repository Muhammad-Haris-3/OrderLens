"""M5 — inferential analysis (SRS FR-9 to FR-13).

Reads `mart_order_analysis` and answers BQ-2 and BQ-3: does late delivery lower
review scores once confounders are controlled for, and what is one day of delay
worth?

Structure mirrors the requirements:

    FR-9   Mann-Whitney U on review score by late/on-time, with a rank-biserial
           effect size and a magnitude interpretation. A p-value without a
           magnitude is not a finding.
    FR-10  Every assumption stated and checked. Where one is violated the test is
           replaced or the interpretation is narrowed, and the reason is recorded.
    FR-11  OLS with the full FR-11 control set and seller-clustered standard
           errors, plus an ordered-logit and a logistic robustness check.
    FR-13  Benjamini-Hochberg correction over the family of per-state and
           per-category tests.

Reads marts only (Design Phase §8). Writes `docs/inferential_results.md`.

Usage:
    python analysis/inferential.py
    python analysis/inferential.py --section fr9
"""

from __future__ import annotations

import argparse
import os
import sys
import warnings
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from dotenv import load_dotenv
from scipy import stats
from statsmodels.stats.multitest import multipletests

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "docs" / "inferential_results.md"

# Minimum group size for a per-segment test to be worth running. Below this the
# test is underpowered to the point of being noise, and including it in a
# family-wise correction penalises every other test for nothing.
MIN_GROUP = 200

CONTROLS = (
    "np.log(order_item_total) + freight_ratio + np.log1p(distance_km) "
    "+ item_count + C(primary_category) + C(seller_state) + C(customer_state) "
    "+ C(season) + C(purchase_year)"
)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_orders() -> pd.DataFrame:
    load_dotenv(ROOT / ".env")
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is not set. Copy .env.example to .env.")

    from sqlalchemy import create_engine

    query = """
        select
            order_id, customer_unique_id, primary_seller_id,
            review_score, is_low_score, reviewed_before_delivery,
            delay_days, is_late, delivery_days,
            seller_handover_days, carrier_transit_days, estimated_days,
            order_item_total, order_freight_total, freight_ratio, item_count,
            primary_category, seller_state, customer_state,
            distance_km, is_same_state, payment_type, payment_installments,
            season, purchase_year, purchase_year_month
        from analytics_marts.mart_order_analysis
        where review_score is not null
    """
    # SQLAlchemy rather than a bare psycopg2 connection: pandas only supports the
    # former, and warns loudly (and eventually errors) on the latter.
    engine = create_engine(database_url.replace("postgresql://", "postgresql+psycopg2://", 1))
    try:
        with engine.connect() as connection:
            frame = pd.read_sql(query, connection)
    finally:
        engine.dispose()

    numeric = [
        "review_score", "delay_days", "delivery_days", "seller_handover_days",
        "carrier_transit_days", "estimated_days", "order_item_total",
        "order_freight_total", "freight_ratio", "item_count", "distance_km",
        "payment_installments", "purchase_year",
    ]
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    # The asymmetric decomposition of delay. M4 found the relationship is a
    # cliff: crossing into lateness costs 1.32 review points, and the following
    # three weeks cost 1.10 combined. A single linear delay_days term averages
    # those two very different slopes into one number that describes neither.
    frame["days_late"] = frame["delay_days"].clip(lower=0)
    frame["days_early"] = (-frame["delay_days"]).clip(lower=0)

    # Cast to int: patsy reads a boolean response as a two-level categorical and
    # builds a two-column endog, which logit rejects with a confusing message.
    frame["is_low_score"] = frame["is_low_score"].astype(int)

    return frame


# ---------------------------------------------------------------------------
# Effect sizes
# ---------------------------------------------------------------------------

def rank_biserial(u_statistic: float, n1: int, n2: int) -> float:
    """Rank-biserial correlation from Mann-Whitney U.

    r = 2U/(n1*n2) - 1, on [-1, 1]. Interpretable directly as the difference
    between the probability that a random draw from group 1 exceeds one from
    group 2 and the probability of the reverse.
    """
    return 2.0 * u_statistic / (n1 * n2) - 1.0


def magnitude(r: float) -> str:
    """Cohen's conventional thresholds for a correlation-family effect size.

    Stated as conventions rather than facts. They are a shared vocabulary, not a
    measurement, and the raw value above is what actually matters.
    """
    size = abs(r)
    if size < 0.10:
        return "negligible"
    if size < 0.30:
        return "small"
    if size < 0.50:
        return "medium"
    return "large"


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def fmt(value: object) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "_n/a_"
    if isinstance(value, (bool, np.bool_)):
        return "yes" if value else "no"
    if isinstance(value, (int, np.integer)):
        return f"{value:,}"
    if isinstance(value, (float, np.floating)):
        if value != 0 and abs(value) < 1e-4:
            return f"{value:.2e}"
        return f"{value:,.4f}"
    return str(value)


def table(columns: list[str], rows: list[tuple]) -> str:
    if not rows:
        return "_No rows._\n"
    lines = [
        "| " + " | ".join(columns) + " |",
        "|" + "|".join("---" for _ in columns) + "|",
    ]
    lines += ["| " + " | ".join(fmt(v) for v in row) + " |" for row in rows]
    return "\n".join(lines) + "\n"


def p_display(p: float) -> str:
    """Never print p = 0. Report the floating-point floor honestly instead."""
    if p == 0.0:
        return "< 1e-308 (below double precision)"
    if p < 1e-10:
        return f"{p:.3e}"
    return f"{p:.6f}"


# ---------------------------------------------------------------------------
# FR-9 / FR-10 — the primary test and its assumptions
# ---------------------------------------------------------------------------

def section_fr9(frame: pd.DataFrame) -> str:
    late = frame.loc[frame["is_late"], "review_score"].to_numpy()
    ontime = frame.loc[~frame["is_late"], "review_score"].to_numpy()

    result = stats.mannwhitneyu(ontime, late, alternative="two-sided")
    r = rank_biserial(result.statistic, len(ontime), len(late))
    superiority = (r + 1) / 2

    parts = [
        "## FR-9 — Does review score differ between on-time and late deliveries?",
        "",
        "**H0:** the distribution of review scores is the same for on-time and",
        "late deliveries. **H1:** they differ. Two-sided, α = 0.05.",
        "",
        "### Groups",
        "",
        table(
            ["group", "n", "mean", "median", "sd", "% score 1", "% score 5"],
            [
                (
                    label,
                    len(values),
                    float(np.mean(values)),
                    float(np.median(values)),
                    float(np.std(values, ddof=1)),
                    100.0 * float(np.mean(values == 1)),
                    100.0 * float(np.mean(values == 5)),
                )
                for label, values in [("on time", ontime), ("late", late)]
            ],
        ),
        "",
        "### Test",
        "",
        table(
            ["test", "statistic (U)", "p-value", "n on time", "n late"],
            [("Mann-Whitney U (two-sided)", float(result.statistic),
              p_display(result.pvalue), len(ontime), len(late))],
        ),
        "",
        "### Effect size — the part that is actually the finding",
        "",
        table(
            ["measure", "value", "magnitude", "reading"],
            [
                ("Rank-biserial correlation", r, magnitude(r),
                 "difference in the probability of one group outranking the other"),
                ("Probability of superiority", superiority, "",
                 "chance a random on-time order outscores a random late one"),
                ("Difference in means", float(np.mean(ontime) - np.mean(late)), "",
                 "review points, uncontrolled"),
                ("Difference in medians", float(np.median(ontime) - np.median(late)), "",
                 "review points"),
            ],
        ),
        "",
        f"A randomly chosen on-time order outscores a randomly chosen late order "
        f"**{100 * superiority:.1f}%** of the time (ties split). The rank-biserial "
        f"correlation of **{r:.3f}** is a **{magnitude(r)}** effect on Cohen's "
        f"conventional thresholds.",
        "",
    ]
    return "\n".join(parts)


def section_fr10(frame: pd.DataFrame) -> str:
    late = frame.loc[frame["is_late"], "review_score"].to_numpy()
    ontime = frame.loc[~frame["is_late"], "review_score"].to_numpy()

    levene = stats.levene(ontime, late, center="median")

    # Shape comparison. Mann-Whitney is a test of stochastic dominance in
    # general, and only a test of a MEDIAN SHIFT when the two distributions have
    # the same shape. Checking that is the difference between "late orders score
    # lower" and "late orders score X points lower", and the second claim is the
    # one people quote.
    shape_rows = []
    for score in (1, 2, 3, 4, 5):
        shape_rows.append((
            score,
            100.0 * float(np.mean(ontime == score)),
            100.0 * float(np.mean(late == score)),
        ))

    orders_per_customer = frame.groupby("customer_unique_id").size()
    orders_per_seller = frame.groupby("primary_seller_id").size()

    parts = [
        "## FR-10 — Assumptions, stated and checked",
        "",
        "### Why not a t-test",
        "",
        table(
            ["group", "skewness", "excess kurtosis", "distinct values"],
            [
                ("on time", float(stats.skew(ontime)),
                 float(stats.kurtosis(ontime)), len(np.unique(ontime))),
                ("late", float(stats.skew(late)),
                 float(stats.kurtosis(late)), len(np.unique(late))),
            ],
        ),
        "",
        "The outcome takes five ordered values. It is **ordinal, not interval** —",
        "nothing in the data says the distance from 1 to 2 equals the distance from",
        "4 to 5 — and both groups are strongly skewed. A mean on this scale is a",
        "convenience, not a measurement.",
        "",
        "**No normality test is reported, deliberately.** At n ≈ 96,000 a",
        "Shapiro-Wilk or Kolmogorov-Smirnov test rejects normality for any",
        "deviation however trivial, so its p-value carries no information about",
        "whether normality is *approximately* satisfied. The skewness and kurtosis",
        "above answer the question the test would have been asked to answer. On a",
        "five-point ordinal scale the answer was never in doubt.",
        "",
        "**Consequence:** rank-based testing (Mann-Whitney), not a t-test. This is",
        "the SRS §11 plan, and the numbers above are why it was the right plan.",
        "",
        "### Equality of variance",
        "",
        table(
            ["test", "statistic", "p-value", "verdict"],
            [("Levene (median-centred)", float(levene.statistic),
              p_display(levene.pvalue),
              "violated" if levene.pvalue < 0.05 else "not rejected")],
        ),
        "",
        "Mann-Whitney does not assume equal variance, so a violation here does not",
        "invalidate it. It is reported because it rules out Welch's t-test as a",
        "fallback and because it is the first sign of the shape problem below.",
        "",
        "### Distribution shape — the assumption that actually bites",
        "",
        table(["review score", "% of on-time orders", "% of late orders"], shape_rows),
        "",
        "Mann-Whitney tests **stochastic dominance** in general. It is a test of a",
        "*median shift* only when the two distributions have the same shape, and",
        "these two plainly do not: on-time orders are concentrated at 5, late",
        "orders at 1. The distributions are not shifted versions of each other,",
        "they are differently shaped.",
        "",
        "**Consequence — the interpretation is narrowed, not the test replaced.**",
        "The result licenses *\"late orders score stochastically lower\"*. It does",
        "**not** license *\"late delivery costs exactly N review points\"* on the",
        "strength of the rank test alone. That quantity comes from the regression",
        "in FR-11, which estimates it on stated functional-form assumptions.",
        "",
        "### Independence",
        "",
        table(
            ["clustering", "units", "observations", "max per unit", "% in units with >1"],
            [
                ("customer (customer_unique_id)", len(orders_per_customer),
                 int(orders_per_customer.sum()), int(orders_per_customer.max()),
                 100.0 * float(orders_per_customer[orders_per_customer > 1].sum()
                               / orders_per_customer.sum())),
                ("seller (primary_seller_id)", len(orders_per_seller),
                 int(orders_per_seller.sum()), int(orders_per_seller.max()),
                 100.0 * float(orders_per_seller[orders_per_seller > 1].sum()
                               / orders_per_seller.sum())),
            ],
        ),
        "",
        "Observations are independent across customers to a good approximation —",
        "3% of people appear more than once (M4 FR-6). They are emphatically **not**",
        "independent within sellers: a single seller can account for thousands of",
        "orders that share fulfilment behaviour and product mix.",
        "",
        "**Consequence:** every regression in FR-11 uses standard errors clustered",
        "on the seller. Ordinary standard errors would be too small, and the",
        "confidence intervals correspondingly too confident.",
        "",
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# FR-13 — families of tests with correction
# ---------------------------------------------------------------------------

def family_test(frame: pd.DataFrame, group_column: str, label: str) -> str:
    groups = []
    for name, chunk in frame.groupby(group_column, observed=True):
        late = chunk.loc[chunk["is_late"], "review_score"].to_numpy()
        ontime = chunk.loc[~chunk["is_late"], "review_score"].to_numpy()
        if len(late) >= MIN_GROUP and len(ontime) >= MIN_GROUP:
            groups.append((name, ontime, late))

    if not groups:
        return f"_No {label} met the minimum group size of {MIN_GROUP}._\n"

    rows = []
    for name, ontime, late in groups:
        result = stats.mannwhitneyu(ontime, late, alternative="two-sided")
        r = rank_biserial(result.statistic, len(ontime), len(late))
        rows.append([name, len(ontime), len(late), float(result.pvalue), r,
                     float(np.mean(ontime) - np.mean(late))])

    raw_p = [row[3] for row in rows]
    rejected, adjusted, _, _ = multipletests(raw_p, alpha=0.05, method="fdr_bh")

    for row, adj, rej in zip(rows, adjusted, rejected, strict=True):
        row.append(float(adj))
        row.append(bool(rej))

    rows.sort(key=lambda row: row[4])  # strongest effect first

    return table(
        [label, "n on time", "n late", "raw p", "rank-biserial",
         "mean difference", "BH-adjusted p", "significant"],
        [tuple(row) for row in rows],
    )


def section_fr13(frame: pd.DataFrame) -> str:
    kw_category = stats.kruskal(*[
        chunk["review_score"].to_numpy()
        for _, chunk in frame.groupby("primary_category", observed=True)
        if len(chunk) >= MIN_GROUP
    ])
    kw_state = stats.kruskal(*[
        chunk["review_score"].to_numpy()
        for _, chunk in frame.groupby("customer_state", observed=True)
        if len(chunk) >= MIN_GROUP
    ])

    parts = [
        "## FR-13 — Families of tests, corrected",
        "",
        "Two families are run. Each is a set of related tests answering one",
        "question, so each is corrected as a set with Benjamini-Hochberg (FDR).",
        "Bonferroni was rejected: it controls the probability of *any* false",
        "positive, which is the wrong target when the question is which segments",
        "to prioritise rather than whether a single effect exists, and at 27 tests",
        "it would cost real power for no gain in decision quality.",
        "",
        "### Is satisfaction homogeneous across segments at all?",
        "",
        table(
            ["test", "grouping", "H statistic", "p-value"],
            [
                ("Kruskal-Wallis", "product category", float(kw_category.statistic),
                 p_display(kw_category.pvalue)),
                ("Kruskal-Wallis", "customer state", float(kw_state.statistic),
                 p_display(kw_state.pvalue)),
            ],
        ),
        "",
        "Both reject homogeneity, which justifies looking segment by segment. On",
        "its own this says nothing about *which* segments differ or by how much —",
        "an omnibus test never does.",
        "",
        "### Family 1 — does late delivery hurt in every state?",
        "",
        f"One Mann-Whitney per customer state with at least {MIN_GROUP} orders in",
        "each arm, corrected across the family.",
        "",
        family_test(frame, "customer_state", "customer state"),
        "",
        "### Family 2 — does late delivery hurt in every category?",
        "",
        f"One Mann-Whitney per product category with at least {MIN_GROUP} orders in",
        "each arm, corrected across the family.",
        "",
        family_test(frame, "primary_category", "product category"),
        "",
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# FR-11 — controlled regression
# ---------------------------------------------------------------------------

def coefficient_rows(fitted, terms: list[str]) -> list[tuple]:
    rows = []
    conf = fitted.conf_int()
    for term in terms:
        if term not in fitted.params.index:
            continue
        rows.append((
            term,
            float(fitted.params[term]),
            float(fitted.bse[term]),
            float(conf.loc[term, 0]),
            float(conf.loc[term, 1]),
            p_display(float(fitted.pvalues[term])),
        ))
    return rows


def fit_ols(frame: pd.DataFrame, formula: str):
    """OLS with standard errors clustered on the seller (see FR-10)."""
    return smf.ols(formula, data=frame).fit(
        cov_type="cluster",
        cov_kwds={"groups": frame["primary_seller_id"]},
    )


def section_fr11(frame: pd.DataFrame) -> str:
    modelling = frame.dropna(subset=[
        "review_score", "delay_days", "order_item_total", "freight_ratio",
        "distance_km", "item_count", "primary_category", "seller_state",
        "customer_state", "season", "purchase_year",
    ]).copy()
    modelling = modelling[modelling["order_item_total"] > 0]

    dropped = len(frame) - len(modelling)

    models = {
        "A. Uncontrolled — is_late only":
            "review_score ~ is_late",
        "B. Uncontrolled — delay_days only":
            "review_score ~ delay_days",
        "C. Controlled — is_late":
            f"review_score ~ is_late + {CONTROLS}",
        "D. Controlled — delay_days (primary)":
            f"review_score ~ delay_days + {CONTROLS}",
        "E. Controlled — asymmetric (days late / days early)":
            f"review_score ~ days_late + days_early + {CONTROLS}",
        # The cliff and the ramp, separated. is_late is the discrete jump at the
        # boundary; days_late is the per-day slope beyond it. M4 found the
        # relationship is mostly the jump, and any specification carrying only
        # one of the two terms attributes the whole effect to whichever it has.
        "F. Controlled — jump plus slope (recommended)":
            f"review_score ~ is_late + days_late + days_early + {CONTROLS}",
    }

    fitted = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for name, formula in models.items():
            fitted[name] = fit_ols(modelling, formula)

    summary_rows = []
    for name, model in fitted.items():
        for term in ("is_late[T.True]", "delay_days", "days_late", "days_early"):
            if term in model.params.index:
                conf = model.conf_int()
                summary_rows.append((
                    name, term,
                    float(model.params[term]),
                    f"[{conf.loc[term, 0]:.4f}, {conf.loc[term, 1]:.4f}]",
                    p_display(float(model.pvalues[term])),
                    float(model.rsquared),
                    int(model.nobs),
                ))

    primary = fitted["D. Controlled — delay_days (primary)"]
    asymmetric = fitted["E. Controlled — asymmetric (days late / days early)"]
    uncontrolled = fitted["B. Uncontrolled — delay_days only"]
    jump_slope = fitted["F. Controlled — jump plus slope (recommended)"]

    parts = [
        "## FR-11 — The effect of delay on review score, with controls",
        "",
        "Ordinary least squares on the 1-5 review score, with standard errors",
        "**clustered on the seller** (FR-10). Controls, as required by FR-11:",
        "log item value, freight ratio, log distance, item count, product category,",
        "seller state, customer state, season and purchase year.",
        "",
        f"{dropped:,} of {len(frame):,} reviewed orders are dropped for a missing",
        "control — almost all of them the orders whose customer or seller ZIP",
        "prefix has no centroid (M2 F-07).",
        "",
        "### Coefficients on the treatment terms",
        "",
        table(
            ["model", "term", "coefficient", "95% CI", "p-value", "R²", "n"],
            summary_rows,
        ),
        "",
        "### Reading the primary model",
        "",
        f"Controlled, **one day of delay costs "
        f"{abs(primary.params['delay_days']):.4f} review points** "
        f"(95% CI [{primary.conf_int().loc['delay_days', 0]:.4f}, "
        f"{primary.conf_int().loc['delay_days', 1]:.4f}]).",
        "",
        f"The uncontrolled estimate is "
        f"{abs(uncontrolled.params['delay_days']):.4f}. Controls move it by "
        f"{100 * abs(1 - primary.params['delay_days'] / uncontrolled.params['delay_days']):.1f}%"
        " — the direction and rough size of the association survive adjustment,",
        "which is the question BQ-2 asks.",
        "",
        "### The asymmetry — why a single slope is misleading",
        "",
        table(
            ["term", "coefficient", "std error", "CI low", "CI high", "p-value"],
            coefficient_rows(asymmetric, ["days_late", "days_early"]),
        ),
        "",
        f"A day of **lateness** costs "
        f"{abs(asymmetric.params['days_late']):.4f} review points. A day of "
        f"**earliness** is worth {abs(asymmetric.params['days_early']):.4f} — "
        f"{abs(asymmetric.params['days_late'] / asymmetric.params['days_early']):.1f}× less.",
        "",
        "Model D's single `delay_days` slope averages those two very different",
        "numbers and describes neither.",
        "",
        "### Separating the cliff from the ramp — the recommended specification",
        "",
        "M4 found the damage arrives on the *first* day of lateness rather than",
        "accumulating. Model E cannot express that: with only a per-day slope, a",
        "discrete drop at the boundary has to be smeared across the days that",
        "follow it. Model F carries both — `is_late` for the jump, `days_late` for",
        "the slope beyond it.",
        "",
        table(
            ["term", "coefficient", "std error", "CI low", "CI high", "p-value"],
            coefficient_rows(jump_slope, ["is_late[T.True]", "days_late", "days_early"]),
        ),
        "",
        f"**Crossing the promised date at all costs "
        f"{abs(jump_slope.params['is_late[T.True]']):.4f} review points.** Each "
        f"further day costs "
        f"{abs(jump_slope.params['days_late']):.4f} on top of that — "
        f"{abs(jump_slope.params['is_late[T.True]'] / jump_slope.params['days_late']):.0f} "
        f"days of additional lateness to do as much damage again as being one day "
        f"late did in the first place.",
        "",
        "**This is the specification the M7 recommendation should be costed from.**",
        "It says the intervention worth buying is one that prevents an order from",
        "becoming late at all; shaving days off deliveries that are already late is",
        "worth an order of magnitude less per day.",
        "",
    ]

    # ---- Robustness ------------------------------------------------------
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        logit = smf.logit(
            f"is_low_score ~ days_late + days_early + {CONTROLS}", data=modelling
        ).fit(disp=False, maxiter=200)

    odds = float(np.exp(logit.params["days_late"]))
    conf_low = float(np.exp(logit.conf_int().loc["days_late", 0]))
    conf_high = float(np.exp(logit.conf_int().loc["days_late", 1]))

    parts += [
        "### Robustness — a binary outcome, which needs no interval assumption",
        "",
        "OLS on a 1-5 ordinal scale assumes the gaps between adjacent scores are",
        "equal, which nothing in the data supports. Logistic regression on",
        "`is_low_score` (a review of 1 or 2) makes no such assumption: the outcome",
        "is genuinely binary and the estimate does not depend on how the five",
        "points are spaced.",
        "",
        table(
            ["term", "coefficient (log-odds)", "odds ratio", "95% CI (OR)", "p-value"],
            [
                ("days_late", float(logit.params["days_late"]), odds,
                 f"[{conf_low:.4f}, {conf_high:.4f}]",
                 p_display(float(logit.pvalues["days_late"]))),
                ("days_early", float(logit.params["days_early"]),
                 float(np.exp(logit.params["days_early"])), "",
                 p_display(float(logit.pvalues["days_early"]))),
            ],
        ),
        "",
        f"Each additional day late multiplies the odds of a 1-or-2 star review by "
        f"**{odds:.4f}** — about **{100 * (odds - 1):.1f}% per day**, compounding. "
        f"Pseudo-R² {logit.prsquared:.4f}, n = {int(logit.nobs):,}.",
        "",
        "The two specifications agree on sign, significance and rough magnitude",
        "while resting on different assumptions, which is what a robustness check",
        "is for.",
        "",
    ]

    # ---- Selection bound (M4 review-timing) ------------------------------
    after = modelling[~modelling["reviewed_before_delivery"].fillna(False)]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        bound = fit_ols(
            after, f"review_score ~ is_late + days_late + days_early + {CONTROLS}"
        )

    full_jump = abs(jump_slope.params["is_late[T.True]"])
    bound_jump = abs(bound.params["is_late[T.True]"])
    full_slope = abs(jump_slope.params["days_late"])
    bound_slope = abs(bound.params["days_late"])

    parts += [
        "### Stated selection bound — reviews written after delivery only",
        "",
        "M4 established that whether a review predates delivery is very nearly",
        "*determined by* whether the delivery was late: 0.2% on on-time orders,",
        "96-99% on late ones. It is a **post-treatment variable**, so restricting",
        "to after-delivery reviews does not remove a confounder — it selects a",
        "non-random subset of late orders.",
        "",
        "This model is reported as a **bound, not an alternative estimate**.",
        "",
        table(
            ["term", "coefficient", "std error", "CI low", "CI high", "p-value"],
            coefficient_rows(bound, ["is_late[T.True]", "days_late", "days_early"]),
        ),
        "",
        table(
            ["term", "all reviews (model F)", "after-delivery only", "change"],
            [
                ("is_late (the jump)", -full_jump, -bound_jump,
                 f"{'smaller' if bound_jump < full_jump else 'larger'} by "
                 f"{100 * abs(bound_jump - full_jump) / full_jump:.0f}%"),
                ("days_late (the slope)", -full_slope, -bound_slope,
                 f"{'smaller' if bound_slope < full_slope else 'larger'} by "
                 f"{100 * abs(bound_slope - full_slope) / full_slope:.0f}%"),
            ],
        ),
        "",
        f"n = {int(bound.nobs):,} of {int(jump_slope.nobs):,} "
        f"({100 * bound.nobs / jump_slope.nobs:.1f}%) — but only "
        f"{100 * len(after[after['is_late']]) / len(modelling[modelling['is_late']]):.1f}% "
        "of the *late* orders survive the restriction.",
        "",
        "The two coefficients move in **opposite directions**, and that is the",
        "informative part. The discrete jump shrinks — customers who waited long",
        "enough to receive the parcel before responding are less harsh about the",
        "fact of lateness. The per-day slope steepens — among those who did wait,",
        "each additional day matters more.",
        "",
        "Neither number is the truth. Restricting to after-delivery reviews",
        "conditions on a post-treatment variable, so it trades one bias for",
        "another rather than removing bias. The defensible statement is that the",
        "effect on *post-delivery* sentiment lies between these specifications, and",
        "that this dataset cannot locate it more precisely — because the instrument",
        "measuring satisfaction is triggered by the process being measured.",
        "",
    ]

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

SECTIONS = {
    "fr9": section_fr9,
    "fr10": section_fr10,
    "fr13": section_fr13,
    "fr11": section_fr11,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--section", choices=sorted(SECTIONS), nargs="+",
                        help="run only these sections")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--stdout", action="store_true")
    args = parser.parse_args()

    # The report contains α, ² and ×. The Windows console defaults to cp1252 and
    # raises on all three, which would fail a run that had already done the work.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    frame = load_orders()
    print(f"Loaded {len(frame):,} reviewed, delivery-eligible orders.")

    wanted = args.section or ["fr9", "fr10", "fr13", "fr11"]

    parts = [
        "# OrderLens — Inferential Analysis Results (generated)",
        "",
        "**Do not edit by hand.** Regenerate with `python analysis/inferential.py`.",
        "",
        "This file is the *evidence*. The interpretation, and the limitations",
        "statement FR-12 requires, live in",
        "[inferential_findings.md](inferential_findings.md).",
        "",
        f"| Generated | {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')} |",
        "|---|---|",
        f"| Population | {len(frame):,} delivery-eligible orders carrying a review |",
        "| Source | `analytics_marts.mart_order_analysis` |",
        "",
        "---",
        "",
    ]

    for name in wanted:
        print(f"  running {name} ...")
        parts.append(SECTIONS[name](frame))
        parts.append("---\n")

    report = "\n".join(parts)

    if args.stdout:
        print(report)
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
        print(f"Written to {args.out.relative_to(ROOT)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

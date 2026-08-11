"""M7 — the costed decision (SRS FR-20, FR-21).

Produces every number in the decision memo. Four questions, in the order they
have to be answered:

    1. MECHANISM   Is the damage caused by breaking the promise, or by the wait?
                   M5 controlled for price, distance, category, geography and
                   season — but not for how long the customer actually waited.
                   Until that is settled, "set a promise you can keep" and
                   "deliver faster" are indistinguishable recommendations with
                   very different price tags.

    2. POLICY      What promise policy actually reduces breaches? Simulated
                   out-of-sample: rules are fitted on 2017 and scored on 2018.

    3. CURRENCY    What is it worth, and what would have to be true for it to be
                   a bad idea? (FR-21)

    4. VALIDATION  The A/B test that would confirm it, with the sample size
                   computed from observed variance rather than a rule of thumb.
                   (FR-20)

Reads marts only. Writes `docs/decision_results.md`.

Usage:
    python analysis/decision.py
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
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "docs" / "decision_results.md"

# Rules are fitted on data before this date and scored after it. An in-sample
# promise policy is a promise policy that has seen the answers.
POLICY_SPLIT = pd.Timestamp("2018-01-01")

# A route needs this much history before its breach rate means anything.
MIN_ROUTE_ORDERS = 30

# Extend the promise only where the route demonstrably breaches. Never shorten:
# a shorter promise buys a fraction of a review point per day and risks a breach
# worth 1.56, which is the wrong side of a very lopsided trade.
BREACH_THRESHOLDS = [0.08, 0.10, 0.12]
RECOMMENDED_THRESHOLD = 0.08
PROMISE_QUANTILE = 0.95

CONTROLS = (
    "np.log(order_item_total) + freight_ratio + np.log1p(distance_km) "
    "+ item_count + C(primary_category) + C(seller_state) + C(customer_state) "
    "+ C(season) + C(purchase_year)"
)

# The dataset's full-coverage window is 2017-01 to 2018-08 (M2 F-06) — 20 months.
COVERAGE_MONTHS = 20


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_orders() -> pd.DataFrame:
    load_dotenv(ROOT / ".env")
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is not set. Copy .env.example to .env.")

    from sqlalchemy import create_engine

    engine = create_engine(
        database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    )
    try:
        with engine.connect() as connection:
            frame = pd.read_sql("""
                select order_id, purchase_date, customer_state, seller_state,
                       delivery_days, estimated_days, delay_days, is_late,
                       review_score, is_low_score, order_value, order_item_total,
                       freight_ratio, distance_km, item_count, primary_category,
                       season, purchase_year, primary_seller_id
                from analytics_marts.mart_order_analysis
            """, connection)
    finally:
        engine.dispose()

    numeric = ["delivery_days", "estimated_days", "delay_days", "review_score",
               "order_value", "order_item_total", "freight_ratio", "distance_km",
               "item_count", "purchase_year"]
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame["purchase_date"] = pd.to_datetime(frame["purchase_date"])
    frame["is_low_score"] = frame["is_low_score"].astype("boolean")
    return frame.dropna(subset=["delivery_days", "estimated_days"])


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
        return f"{value:,.4f}"
    return str(value)


def table(columns: list[str], rows: list[tuple]) -> str:
    if not rows:
        return "_No rows._\n"
    lines = ["| " + " | ".join(columns) + " |",
             "|" + "|".join("---" for _ in columns) + "|"]
    lines += ["| " + " | ".join(fmt(v) for v in row) + " |" for row in rows]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# 1. Mechanism
# ---------------------------------------------------------------------------

def section_mechanism(frame: pd.DataFrame) -> tuple[str, float]:
    modelling = frame.dropna(subset=[
        "review_score", "delay_days", "order_item_total", "freight_ratio",
        "distance_km", "item_count", "primary_category", "season", "purchase_year",
    ]).copy()
    modelling = modelling[modelling["order_item_total"] > 0]
    modelling["days_late"] = modelling["delay_days"].clip(lower=0)
    modelling["days_early"] = (-modelling["delay_days"]).clip(lower=0)
    modelling["is_low"] = modelling["is_low_score"].astype(int)

    specs = {
        "M5 specification (no control for the wait)":
            f"review_score ~ is_late + days_late + days_early + {CONTROLS}",
        "Adding the actual wait":
            f"review_score ~ is_late + days_late + days_early + delivery_days + {CONTROLS}",
        "Adding the wait and the promise length":
            f"review_score ~ is_late + days_late + days_early + delivery_days "
            f"+ estimated_days + {CONTROLS}",
    }

    rows = []
    fitted = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for name, formula in specs.items():
            model = smf.ols(formula, data=modelling).fit(
                cov_type="cluster", cov_kwds={"groups": modelling["primary_seller_id"]})
            fitted[name] = model
            conf = model.conf_int()
            rows.append((
                name,
                float(model.params["is_late[T.True]"]),
                f"[{conf.loc['is_late[T.True]', 0]:.4f}, {conf.loc['is_late[T.True]', 1]:.4f}]",
                float(model.params.get("delivery_days", np.nan)),
                float(model.rsquared),
            ))

    with_wait = fitted["Adding the actual wait"]
    breach_effect = float(with_wait.params["is_late[T.True]"])
    naive = float(fitted["M5 specification (no control for the wait)"].params["is_late[T.True]"])

    # Same wait, different promise. The regression above is an adjustment; this
    # is the comparison itself, and it needs no functional form to believe.
    band_rows = []
    for low, high in [(6, 9), (10, 13), (14, 18), (19, 25), (26, 40)]:
        band = modelling[(modelling["delivery_days"] >= low)
                         & (modelling["delivery_days"] <= high)]
        late = band[band["is_late"]]
        ontime = band[~band["is_late"]]
        if len(late) >= 50 and len(ontime) >= 50:
            band_rows.append((
                f"{low}–{high} days", len(ontime), len(late),
                float(ontime["review_score"].mean()),
                float(late["review_score"].mean()),
                float(ontime["review_score"].mean() - late["review_score"].mean()),
            ))

    # The breach's effect on the probability of a low review — a marginal effect,
    # which is what converts "breaches prevented" into "bad reviews prevented".
    # The full control set makes the logit's Hessian singular — 74 category
    # dummies against a binary outcome leaves cells with no variation. The
    # fallback drops the category fixed effects rather than the model, and says
    # which one was used, because silently reporting a different specification
    # than the one documented is worse than the singularity.
    slim_controls = (
        "np.log(order_item_total) + freight_ratio + np.log1p(distance_km) "
        "+ item_count + C(seller_state) + C(customer_state) + C(season) "
        "+ C(purchase_year)"
    )
    logit_spec = "full control set"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            logit = smf.logit(
                f"is_low ~ is_late + days_late + days_early + delivery_days + {CONTROLS}",
                data=modelling,
            ).fit(disp=False, maxiter=200)
        except np.linalg.LinAlgError:
            logit_spec = "control set without category fixed effects (singular with them)"
            logit = smf.logit(
                f"is_low ~ is_late + days_late + days_early + delivery_days "
                f"+ {slim_controls}",
                data=modelling,
            ).fit(disp=False, maxiter=200)

    counterfactual = modelling.copy()
    counterfactual["is_late"] = False
    counterfactual["days_late"] = 0.0
    breaching = modelling["is_late"]
    predicted_now = logit.predict(modelling[breaching])
    predicted_if_kept = logit.predict(counterfactual[breaching])
    marginal = float((predicted_now - predicted_if_kept).mean())

    text = "\n".join([
        "## 1. Mechanism — is it the broken promise, or the wait?",
        "",
        "M5 estimated that breaching the promised date costs 1.71 review points,",
        "controlling for price, freight, distance, category, both geographies,",
        "season and year. It did **not** control for how long the customer",
        "actually waited — and until that is settled, two very different",
        "recommendations are indistinguishable:",
        "",
        "- If the harm comes from the **wait**, only faster delivery helps, and",
        "  changing the promise is cosmetic.",
        "- If the harm comes from the **broken promise**, then a promise the",
        "  business can keep is a real intervention, and a cheap one.",
        "",
        "### The adjustment",
        "",
        table(["specification", "is_late coefficient", "95% CI",
               "delivery_days coefficient", "R²"], rows),
        "",
        f"Adding the actual wait moves the breach effect from {naive:.4f} to "
        f"**{breach_effect:.4f}** — an attenuation of only "
        f"{100 * (1 - breach_effect / naive):.0f}%. The wait matters "
        f"({float(with_wait.params['delivery_days']):.4f} points per day) and it is "
        "not what is doing the damage.",
        "",
        "### Same wait, different promise",
        "",
        "The comparison without a functional form: orders that took a similar",
        "time to arrive, split by whether that time broke the promise.",
        "",
        table(["actual wait", "n on time", "n late", "mean score (on time)",
               "mean score (late)", "gap"], band_rows),
        "",
        "**A customer who waits ten days and was promised eight is markedly less",
        "satisfied than a customer who waits ten days and was promised fifteen.**",
        "The wait is identical. The promise is not.",
        "",
        "### Converting breaches into bad reviews",
        "",
        "Average marginal effect of a breach on the probability of a 1-or-2 star",
        f"review, controlling for the wait: **{marginal:.4f}** — so preventing one",
        f"breach prevents about **{marginal:.3f}** of a bad review. Fitted with the",
        f"{logit_spec}. This is the",
        "conversion factor used throughout §3, and it is much smaller than the raw",
        "62.4%-vs-9.3% difference because that gap includes everything else that",
        "differs between late and on-time orders.",
        "",
    ])
    return text, marginal


# ---------------------------------------------------------------------------
# 2. Policy
# ---------------------------------------------------------------------------

def simulate_policy(train: pd.DataFrame, test: pd.DataFrame,
                    threshold: float) -> tuple[pd.DataFrame, pd.Series]:
    route = ["seller_state", "customer_state"]
    stats = train.groupby(route).agg(
        route_orders=("order_id", "size"),
        route_breach_rate=("is_late", "mean"),
        route_quantile=("delivery_days", lambda s: s.quantile(PROMISE_QUANTILE)),
    )
    national = train["delivery_days"].quantile(PROMISE_QUANTILE)

    scored = test.merge(stats, left_on=route, right_index=True, how="left")
    scored["route_quantile"] = scored["route_quantile"].fillna(national)
    scored["route_breach_rate"] = scored["route_breach_rate"].fillna(0.0)
    scored["route_orders"] = scored["route_orders"].fillna(0)

    targeted = (
        (scored["route_orders"] >= MIN_ROUTE_ORDERS)
        & (scored["route_breach_rate"] > threshold)
    )
    # Extend only — never shorten.
    extended = scored[["estimated_days", "route_quantile"]].max(axis=1).round()
    scored["new_promise"] = scored["estimated_days"].where(~targeted, extended)
    scored["targeted"] = targeted
    scored["breach_now"] = scored["delivery_days"] > scored["estimated_days"]
    scored["breach_new"] = scored["delivery_days"] > scored["new_promise"]
    return scored, targeted


def section_policy(frame: pd.DataFrame) -> tuple[str, pd.DataFrame]:
    train = frame[frame["purchase_date"] < POLICY_SPLIT]
    test = frame[frame["purchase_date"] >= POLICY_SPLIT]

    # The rejected policy, reported because it is the obvious one.
    route = ["seller_state", "customer_state"]
    p90 = train.groupby(route)["delivery_days"].quantile(0.90)
    naive = test.merge(p90.rename("p90"), left_on=route, right_index=True, how="left")
    naive["p90"] = naive["p90"].fillna(train["delivery_days"].quantile(0.90)).round()

    rows = [(
        "Current promise",
        float(test["estimated_days"].mean()),
        100.0 * float((test["delivery_days"] > test["estimated_days"]).mean()),
        int((test["delivery_days"] > test["estimated_days"]).sum()),
    ), (
        "Replace with route p90 (rejected)",
        float(naive["p90"].mean()),
        100.0 * float((naive["delivery_days"] > naive["p90"]).mean()),
        int((naive["delivery_days"] > naive["p90"]).sum()),
    )]

    policy_rows = []
    scored_recommended = None
    for threshold in BREACH_THRESHOLDS:
        scored, targeted = simulate_policy(train, test, threshold)
        policy_rows.append((
            f"> {threshold:.0%}",
            100.0 * float(targeted.mean()),
            float(scored["new_promise"].mean()),
            float(scored.loc[targeted, "estimated_days"].mean()),
            float(scored.loc[targeted, "new_promise"].mean()),
            100.0 * float(scored["breach_new"].mean()),
            int(scored["breach_now"].sum() - scored["breach_new"].sum()),
        ))
        if threshold == RECOMMENDED_THRESHOLD:
            scored_recommended = scored

    by_state = scored_recommended.groupby("customer_state").agg(
        orders=("order_id", "size"),
        promise_now=("estimated_days", "mean"),
        promise_new=("new_promise", "mean"),
        breach_now=("breach_now", "mean"),
        breach_new=("breach_new", "mean"),
    )
    by_state = by_state[by_state["orders"] >= 300].sort_values(
        "breach_now", ascending=False)
    state_rows = [
        (state, int(row["orders"]), float(row["promise_now"]), float(row["promise_new"]),
         100.0 * float(row["breach_now"]), 100.0 * float(row["breach_new"]))
        for state, row in by_state.head(10).iterrows()
    ]

    text = "\n".join([
        "## 2. Policy — what actually reduces breaches",
        "",
        f"Rules are fitted on orders before {POLICY_SPLIT.date()} and scored on",
        f"the {len(test):,} orders after it. An in-sample promise policy is one",
        "that has already seen the answers.",
        "",
        "### The obvious policy is worse than doing nothing",
        "",
        table(["policy", "mean promise (days)", "breach rate %", "breaches"], rows),
        "",
        "**Setting the promise from route history makes things worse.** A p90",
        "promise targets a 10% breach rate by construction, and the platform's",
        "current promise already achieves 8.76% — it is *more* conservative than",
        "route history would suggest. Replacing it shortens the average promise",
        "and buys more breaches, which is the wrong side of a lopsided trade.",
        "",
        "This is worth stating plainly because it is the recommendation an",
        "analyst would reach for first, and it is wrong.",
        "",
        "### Extend only where the route demonstrably breaches",
        "",
        f"Promise becomes `max(current, route p{int(PROMISE_QUANTILE * 100)})`, and",
        "only on routes whose measured breach rate exceeds a threshold. Never",
        "shortened anywhere.",
        "",
        table(["breach threshold", "% orders touched", "mean promise (all)",
               "promise before (touched)", "promise after (touched)",
               "breach rate after %", "breaches prevented"], policy_rows),
        "",
        f"At the recommended **>{RECOMMENDED_THRESHOLD:.0%}** threshold the average",
        "promise across all orders moves by under two days, because the change is",
        "concentrated: it touches a fifth of orders and leaves four fifths",
        "untouched.",
        "",
        "### Where it lands",
        "",
        table(["customer state", "orders", "promise now", "promise after",
               "breach now %", "breach after %"], state_rows),
        "",
    ])
    return text, scored_recommended


# ---------------------------------------------------------------------------
# 3. Currency (FR-21)
# ---------------------------------------------------------------------------

def section_currency(scored: pd.DataFrame, marginal: float,
                     frame: pd.DataFrame) -> str:
    months_tested = (
        scored["purchase_date"].max() - scored["purchase_date"].min()
    ).days / 30.44
    scale = 12.0 / months_tested

    prevented = int(scored["breach_now"].sum() - scored["breach_new"].sum())
    prevented_year = prevented * scale
    bad_reviews_year = prevented_year * marginal

    touched = scored[scored["targeted"]]
    touched_revenue_year = float(touched["order_value"].sum()) * scale
    all_revenue_year = float(scored["order_value"].sum()) * scale

    rows = [
        ("Orders scored", int(len(scored)), "the out-of-sample window"),
        ("Months covered", round(months_tested, 1), ""),
        ("Breaches prevented (window)", prevented, ""),
        ("Breaches prevented (annualised)", round(prevented_year), ""),
        ("Bad reviews prevented (annualised)", round(bad_reviews_year),
         f"at {marginal:.4f} per breach, controlled"),
        ("Revenue on touched routes (annualised)", round(touched_revenue_year, 2), "R$"),
        ("Revenue, all orders (annualised)", round(all_revenue_year, 2), "R$"),
    ]

    # The intervention costs nothing to run. What it risks is conversion: a
    # longer quoted date may lose the sale, and this dataset cannot measure that
    # because it contains only completed orders. So the break-even is expressed
    # in the currency of that risk.
    sensitivity = []
    for loss_pct in [0.1, 0.25, 0.5, 1.0, 2.0]:
        revenue_lost = touched_revenue_year * loss_pct / 100.0
        sensitivity.append((
            f"{loss_pct:.2f}%",
            round(revenue_lost, 2),
            round(revenue_lost / bad_reviews_year, 2) if bad_reviews_year else float("nan"),
        ))

    return "\n".join([
        "## 3. What it is worth (FR-21)",
        "",
        table(["quantity", "value", "note"], rows),
        "",
        "### The intervention is free to run. The risk is conversion.",
        "",
        "Changing a delivery estimate costs nothing operationally — it is a",
        "change to a number shown at checkout. What it risks is the sale: a",
        "longer quoted date may lose customers who would have bought under the",
        "shorter one.",
        "",
        "**This dataset cannot measure that.** It contains completed orders only.",
        "There is no browse, no cart, no abandonment — so the conversion effect of",
        "a longer promise is not merely unmeasured here, it is unmeasurable here.",
        "Any number claiming otherwise would be invented.",
        "",
        "So the decision is expressed as the trade it actually is:",
        "",
        table(["conversion lost on touched routes", "revenue forgone per year (R$)",
               "implied cost per bad review prevented (R$)"], sensitivity),
        "",
        f"Preventing roughly **{round(bad_reviews_year):,} bad reviews a year** is",
        "worth doing if a prevented 1-or-2 star review is worth more than the",
        "figure in the right-hand column at whatever conversion loss the business",
        "believes it would suffer.",
        "",
        "**At a 0.5% conversion loss the implied cost is around R$"
        f"{touched_revenue_year * 0.005 / bad_reviews_year:,.0f} per prevented bad review.**",
        "The business does not have to accept that number — it has to decide",
        "whether a 1-star review costs more or less than it, which is a judgement",
        "it is far better placed to make than this analysis is.",
        "",
        "That is why the recommendation is to **test**, not to roll out: the",
        "benefit is estimated from observational data and the risk is unmeasured,",
        "and an experiment settles both at once.",
        "",
    ])


# ---------------------------------------------------------------------------
# 4. The A/B test (FR-20)
# ---------------------------------------------------------------------------

def section_experiment(scored: pd.DataFrame, frame: pd.DataFrame,
                       marginal: float) -> str:
    touched = scored[scored["targeted"]].copy()

    reviewed = frame.dropna(subset=["is_low_score"])
    route = ["seller_state", "customer_state"]
    touched_routes = set(map(tuple, touched[route].drop_duplicates().to_numpy()))
    on_route = reviewed[[tuple(r) in touched_routes
                         for r in reviewed[route].to_numpy()]]

    baseline = float(on_route["is_low_score"].astype(int).mean())

    breach_reduction = float(
        (touched["breach_now"].sum() - touched["breach_new"].sum()) / len(touched)
    )
    expected_absolute = breach_reduction * marginal
    expected_treatment = baseline - expected_absolute

    power_solver = NormalIndPower()
    rows = []
    for mde_multiplier, label in [(1.0, "expected effect"),
                                  (0.75, "75% of expected"),
                                  (0.5, "half the expected effect")]:
        treatment = baseline - expected_absolute * mde_multiplier
        effect = proportion_effectsize(baseline, treatment)
        n = power_solver.solve_power(
            effect_size=effect, alpha=0.05, power=0.80, ratio=1.0,
            alternative="two-sided")
        rows.append((
            label,
            baseline * 100,
            treatment * 100,
            (baseline - treatment) * 100,
            int(np.ceil(n)),
            int(np.ceil(n) * 2),
        ))

    orders_per_month = len(touched) / (
        (scored["purchase_date"].max() - scored["purchase_date"].min()).days / 30.44
    )

    duration_rows = [
        (row[0], row[5], round(row[5] / orders_per_month, 1)) for row in rows
    ]

    return "\n".join([
        "## 4. The experiment that would settle it (FR-20)",
        "",
        "### Design",
        "",
        table(["element", "specification"], [
            ("Hypothesis",
             "Extending the delivery promise on high-breach routes reduces the "
             "share of orders receiving a 1-or-2 star review"),
            ("H₀", "The low-score rate is the same under both promises"),
            ("Primary metric", "Share of delivered orders scoring 1 or 2"),
            ("Unit of randomisation", "The order, assigned at checkout"),
            ("Assignment", "50/50, on the high-breach routes only"),
            ("Secondary metrics",
             "Breach rate (the mechanism); mean review score"),
            ("Guardrail metric",
             "Checkout conversion — the risk this test exists to measure"),
            ("Alpha / power", "0.05 two-sided / 0.80"),
        ]),
        "",
        "**Why the order and not the customer.** The promise is set per order at",
        "checkout, so the order is the level at which the treatment is actually",
        "applied. Customer-level assignment would be the safer choice if repeat",
        "purchase were common enough for one customer's orders to interfere with",
        "each other — but only 2.24% of customers ever return (M4 FR-6), so the",
        "contamination that would justify the loss of power does not exist here.",
        "",
        "**Why conversion is a guardrail and not the primary metric.** The",
        "benefit is what this analysis can estimate; the risk is what it cannot.",
        "Powering on the benefit and monitoring the risk is the honest split, and",
        "the test should stop early if conversion moves materially against the",
        "treatment arm regardless of what the primary metric is doing.",
        "",
        "### Sample size",
        "",
        f"Baseline low-score rate on the affected routes: **{baseline:.2%}**.",
        f"The policy prevents a breach on **{breach_reduction:.2%}** of those",
        f"orders, and a breach carries **{marginal:.4f}** of a bad review, so the",
        f"expected absolute reduction is **{expected_absolute:.2%}**",
        f"({baseline:.2%} → {expected_treatment:.2%}).",
        "",
        table(["detectable effect", "control %", "treatment %", "absolute change (pp)",
               "orders per arm", "orders total"], rows),
        "",
        table(["detectable effect", "orders total", "months at current volume"],
              duration_rows),
        "",
        "At the observed volume on those routes — roughly",
        f"**{orders_per_month:,.0f} orders a month** — the expected effect is",
        "detectable in a run of a few months. The half-effect row is the one to",
        "plan against: it is the size the test should be able to rule out, not",
        "the size hoped for.",
        "",
        "**Attrition.** The metric is only observed on delivered, reviewed orders",
        f"— about {100 * len(reviewed) / len(frame):.0f}% of eligible orders carry a",
        "review — and delivery itself takes weeks on these routes. The enrolment",
        "window must run ahead of the measurement window by at least the p95",
        "delivery time, or the last cohort will be measured before it has arrived.",
        "",
    ])


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def build_report(frame: pd.DataFrame) -> str:
    print("  1/4 mechanism ...")
    mechanism, marginal = section_mechanism(frame)
    print("  2/4 policy ...")
    policy, scored = section_policy(frame)
    print("  3/4 currency ...")
    currency = section_currency(scored, marginal, frame)
    print("  4/4 experiment ...")
    experiment = section_experiment(scored, frame, marginal)

    header = "\n".join([
        "# OrderLens — Decision Analysis Results (generated)",
        "",
        "**Do not edit by hand.** Regenerate with `python analysis/decision.py`.",
        "",
        "This file is the *evidence* behind the decision memo. The memo itself is",
        "[decision_memo.md](decision_memo.md).",
        "",
        f"| Generated | {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')} |",
        "|---|---|",
        "| Source | `analytics_marts.mart_order_analysis` |",
        f"| Policy fitted on | orders before {POLICY_SPLIT.date()} |",
        f"| Policy scored on | orders from {POLICY_SPLIT.date()} |",
        "",
        "---",
        "",
    ])
    return header + "\n---\n\n".join([mechanism, policy, currency, experiment])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--stdout", action="store_true")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    frame = load_orders()
    print(f"Loaded {len(frame):,} delivery-eligible orders.")
    report = build_report(frame)

    if args.stdout:
        print(report)
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
        print(f"Written to {args.out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

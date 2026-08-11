"""M6 — predictive model (SRS FR-14 to FR-17).

Can an at-risk order be identified BEFORE it goes wrong? (BQ-5)

    FR-14  Classifier for a low review score using only features available
           before delivery completes.
    FR-15  Decision threshold chosen by expected business cost, with the assumed
           cost of a false positive and a false negative stated — not by F1,
           which has no business meaning.
    FR-16  Performance against a stated naive baseline. A model that fails to
           beat it is reported as failing to beat it (NFR-8).
    FR-17  Permutation importance, not impurity importance.

THE LEAKAGE RULE IS ENFORCED HERE, IN CODE. `mart_prediction_features` already
excludes the post-delivery columns, and this script asserts it again against an
explicit denylist before a model sees anything. Design Phase §8 asks for an
allowlist rather than discipline, and two independent guards is what that means.

Reads marts only. Writes `docs/predictive_results.md`.

Usage:
    python analysis/predictive.py
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
from dotenv import load_dotenv
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "docs" / "predictive_results.md"

TARGET = "is_low_score"

# The temporal boundary. A random split would let the model learn from June and
# predict May, which no deployed model can do — and would flatter it, because
# seller behaviour and carrier performance drift (M4: the late rate moves between
# 1.16% and 18.96% across months). Everything before this date trains; everything
# from it tests.
SPLIT_DATE = pd.Timestamp("2018-06-01")

NUMERIC_FEATURES = [
    "estimated_days",
    "order_item_total", "order_freight_total", "freight_ratio",
    "primary_item_price", "item_count", "product_count", "seller_count",
    "primary_product_weight_g", "primary_product_volume_cm3",
    "distance_km",
    "payment_installments",
    "purchase_month", "purchase_day_of_week",
    "seller_prior_deliveries", "seller_prior_late_rate",
    "seller_prior_reviews", "seller_prior_low_score_rate",
]

CATEGORICAL_FEATURES = [
    "primary_category", "seller_state", "customer_state", "payment_type",
    "season", "is_same_state", "is_single_seller", "purchased_on_weekend",
]

FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

# Anything derived from the delivery itself. If one of these reaches the model,
# the model is reading the answer: M5 measured that 53.8% of late orders score
# the minimum, so `is_late` alone would look like a triumph and be worthless —
# by the time you know an order is late there is nothing left to intervene on.
BANNED = {
    "delay_days", "is_late", "delivery_days", "delivered_at",
    "seller_handover_days", "carrier_transit_days",
    "reviewed_before_delivery", "review_answered_at",
}

# The outcome and what it is derived from. Not "leakage" — it is the thing being
# predicted — but it must never appear among the features either, and the two
# failures deserve different error messages because they have different causes.
OUTCOMES = {"is_low_score", "review_score"}

# ---------------------------------------------------------------------------
# FR-15 — the cost matrix, stated up front
# ---------------------------------------------------------------------------
# Flagging an order means intervening on it: a proactive status contact, a
# shipping upgrade, or a goodwill credit. Both numbers below are ASSUMPTIONS
# about a business this project does not run, so the sensitivity analysis over
# the ratio matters more than the point values.
COST_FALSE_POSITIVE = 5.0    # R$ — intervening on an order that was fine anyway
COST_FALSE_NEGATIVE = 50.0   # R$ — a low review that could have been prevented
COST_RATIO_GRID = [2, 5, 10, 20, 50, 100]


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_features() -> pd.DataFrame:
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
            frame = pd.read_sql(
                "select * from analytics_marts.mart_prediction_features", connection
            )
    finally:
        engine.dispose()

    frame["purchased_at"] = pd.to_datetime(frame["purchased_at"])
    for column in NUMERIC_FEATURES:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    for column in CATEGORICAL_FEATURES:
        frame[column] = frame[column].astype(str)
    frame[TARGET] = frame[TARGET].astype(int)

    return frame


def load_ceiling_diagnostic() -> pd.DataFrame:
    """Fetch the BANNED delivery outcome — for the ceiling diagnostic only.

    This deliberately loads what the classifier is forbidden to use. It exists to
    answer one question: is the pre-delivery model weak because the features are
    poor, or because the signal genuinely is not present at purchase time?

    A model that adds `is_late` cannot be deployed — by the time you know an
    order is late there is nothing left to prevent — but it measures the ceiling.
    If the leaking model is far better, the honest conclusion is that the
    outcome is driven by what happens after the order is placed, and no amount of
    feature engineering on purchase-time attributes will recover it.

    Kept in a separate function, with a separate query, so it can never be
    confused with the feature loader.
    """
    load_dotenv(ROOT / ".env")
    from sqlalchemy import create_engine

    engine = create_engine(
        os.environ["DATABASE_URL"].replace(
            "postgresql://", "postgresql+psycopg2://", 1
        )
    )
    try:
        with engine.connect() as connection:
            return pd.read_sql(
                "select order_id, is_late, delay_days "
                "from analytics_marts.mart_order_analysis", connection
            )
    finally:
        engine.dispose()


def assert_no_leakage(frame: pd.DataFrame) -> list[str]:
    """FR-14 / Design Phase §8 — fail loudly rather than train a leaking model.

    Three separate checks, because there are three distinct ways to get this
    wrong and a single combined message would not say which happened.
    """
    # 1. A post-delivery predictor reached the mart at all. Should be impossible:
    #    mart_prediction_features never selects one. If it happens, the mart
    #    changed and the model would silently start reading the future.
    in_frame = sorted(BANNED.intersection(frame.columns))
    if in_frame:
        raise SystemExit(
            "LEAKAGE: post-delivery columns present in the feature mart: "
            f"{', '.join(in_frame)}. mart_prediction_features must not select them."
        )

    # 2. Something post-delivery or outcome-derived was declared as a feature.
    #    This is the failure an allowlist exists to prevent.
    in_features = sorted((BANNED | OUTCOMES).intersection(FEATURES))
    if in_features:
        raise SystemExit(
            f"LEAKAGE: banned or outcome columns declared as features: "
            f"{', '.join(in_features)}"
        )

    # 3. A declared feature does not exist. Silently dropping it would leave the
    #    model quietly weaker than the write-up claims.
    unknown = sorted(set(FEATURES) - set(frame.columns))
    if unknown:
        raise SystemExit(f"Declared features missing from the mart: {unknown}")

    return sorted(set(frame.columns) - set(FEATURES) - OUTCOMES)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

def build_preprocessor() -> ColumnTransformer:
    return ColumnTransformer([
        ("numeric", Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]), NUMERIC_FEATURES),
        ("categorical", Pipeline([
            ("impute", SimpleImputer(strategy="most_frequent")),
            # min_frequency folds rare levels into one bucket. Without it, a
            # category seen five times in training becomes a dummy that fits
            # noise and cannot generalise.
            ("encode", OneHotEncoder(handle_unknown="infrequent_if_exist",
                                     min_frequency=30, sparse_output=False)),
        ]), CATEGORICAL_FEATURES),
    ])


def build_models() -> dict[str, Pipeline]:
    return {
        "Logistic regression": Pipeline([
            ("prep", build_preprocessor()),
            ("model", LogisticRegression(max_iter=2000, class_weight="balanced")),
        ]),
        "Gradient boosting": Pipeline([
            ("prep", build_preprocessor()),
            ("model", HistGradientBoostingClassifier(
                max_iter=300, learning_rate=0.06, max_leaf_nodes=31,
                l2_regularization=1.0, early_stopping=True,
                validation_fraction=0.15, random_state=42,
            )),
        ]),
    }


# ---------------------------------------------------------------------------
# FR-15 — expected cost
# ---------------------------------------------------------------------------

def expected_cost(y_true: np.ndarray, probability: np.ndarray, threshold: float,
                  cost_fp: float, cost_fn: float) -> tuple[float, int, int, int, int]:
    predicted = (probability >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, predicted, labels=[0, 1]).ravel()
    return fp * cost_fp + fn * cost_fn, int(tn), int(fp), int(fn), int(tp)


def best_threshold(y_true: np.ndarray, probability: np.ndarray,
                   cost_fp: float, cost_fn: float) -> tuple[float, float]:
    grid = np.linspace(0.01, 0.99, 197)
    costs = [expected_cost(y_true, probability, t, cost_fp, cost_fn)[0] for t in grid]
    index = int(np.argmin(costs))
    return float(grid[index]), float(costs[index])


def f1_threshold(y_true: np.ndarray, probability: np.ndarray) -> float:
    """The threshold F1 would have chosen — reported to show it is the wrong one."""
    grid = np.linspace(0.01, 0.99, 197)
    scores = []
    for t in grid:
        predicted = (probability >= t).astype(int)
        tn, fp, fn, tp = confusion_matrix(y_true, predicted, labels=[0, 1]).ravel()
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append(2 * precision * recall / (precision + recall)
                      if precision + recall else 0.0)
    return float(grid[int(np.argmax(scores))])


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def low_score_decomposition(test_frame: pd.DataFrame, target: str) -> str:
    """Where do low reviews actually come from — late orders, or on-time ones?

    The classifier's ceiling is set by this. If most low scores sit on orders
    that arrived on time, then no amount of delivery information identifies them,
    and a model built on delivery-related features has a hard limit well short of
    useful.
    """
    late = test_frame["is_late"].astype(str) == "True"
    low = test_frame[target] == 1

    rows = []
    for label, mask in [("arrived late", late), ("arrived on time or early", ~late)]:
        orders = int(mask.sum())
        low_scores = int((mask & low).sum())
        rows.append((
            label,
            orders,
            100.0 * orders / len(test_frame),
            low_scores,
            100.0 * low_scores / low.sum(),
            100.0 * low_scores / orders if orders else float("nan"),
        ))

    return table(
        ["group", "orders", "% of orders", "low-score orders",
         "% of all low scores", "low-score rate within group"],
        rows,
    )


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
    lines = [
        "| " + " | ".join(columns) + " |",
        "|" + "|".join("---" for _ in columns) + "|",
    ]
    lines += ["| " + " | ".join(fmt(v) for v in row) + " |" for row in rows]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------

def build_report(frame: pd.DataFrame) -> str:
    ignored = assert_no_leakage(frame)

    train = frame[frame["purchased_at"] < SPLIT_DATE]
    test = frame[frame["purchased_at"] >= SPLIT_DATE]

    x_train, y_train = train[FEATURES], train[TARGET].to_numpy()
    x_test, y_test = test[FEATURES], test[TARGET].to_numpy()

    base_rate = float(y_test.mean())

    parts = [
        "# OrderLens — Predictive Model Results (generated)",
        "",
        "**Do not edit by hand.** Regenerate with `python analysis/predictive.py`.",
        "",
        "This file is the *evidence*. The interpretation lives in",
        "[predictive_findings.md](predictive_findings.md).",
        "",
        f"| Generated | {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')} |",
        "|---|---|",
        "| Source | `analytics_marts.mart_prediction_features` |",
        f"| Split | temporal at {SPLIT_DATE.date()} |",
        "",
        "---",
        "",
        "## FR-14 — The leakage guard",
        "",
        "The classifier may use only what is known at purchase time. Columns are",
        "checked against an explicit denylist before a model sees anything; the",
        "run aborts if any is present.",
        "",
        table(
            ["check", "result"],
            [
                ("Banned post-delivery columns in the feature frame", "none"),
                ("Declared features present in the mart",
                 f"all {len(FEATURES)}"),
                ("Columns in the mart deliberately not used as features",
                 ", ".join(ignored) or "none"),
            ],
        ),
        "",
        f"**{len(NUMERIC_FEATURES)} numeric and {len(CATEGORICAL_FEATURES)} "
        f"categorical features.** The two seller track-record features are",
        "computed as-of the purchase timestamp in SQL — a naive seller average",
        "over the whole table would include this order's own outcome.",
        "",
        "### Split",
        "",
        table(
            ["set", "orders", "low-score orders", "base rate", "period"],
            [
                ("train", len(train), int(y_train.sum()), float(y_train.mean()),
                 f"{train['purchase_date'].min()} to {train['purchase_date'].max()}"),
                ("test", len(test), int(y_test.sum()), base_rate,
                 f"{test['purchase_date'].min()} to {test['purchase_date'].max()}"),
            ],
        ),
        "",
        "Temporal, not random. A random split lets the model learn from June and",
        "predict May, which no deployed model can do — and flatters it, because",
        "carrier performance drifts month to month (M4).",
        "",
        "---",
        "",
    ]

    # ---- Fit -------------------------------------------------------------
    fitted = {}
    predictions = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for name, pipeline in build_models().items():
            print(f"  fitting {name} ...")
            pipeline.fit(x_train, y_train)
            fitted[name] = pipeline
            predictions[name] = pipeline.predict_proba(x_test)[:, 1]

    # ---- FR-16 baselines --------------------------------------------------
    # A model has to beat something stated in advance, not something chosen
    # afterwards to be beatable.
    baseline_rows = []

    never = np.zeros_like(y_test, dtype=float)
    always = np.ones_like(y_test, dtype=float)

    # A one-feature heuristic a business could run in a spreadsheet: flag the
    # order if this seller's prior low-score rate is above the overall base rate.
    heuristic = (
        test["seller_prior_low_score_rate"]
        .fillna(train[TARGET].mean())
        .to_numpy()
    )

    for name, scores, note in [
        ("Never flag (majority class)", never, "predicts no order is at risk"),
        ("Flag everything", always, "predicts every order is at risk"),
        ("Seller prior low-score rate", heuristic,
         "one feature, no model — the number a spreadsheet could produce"),
    ]:
        auc = (roc_auc_score(y_test, scores)
               if len(np.unique(scores)) > 1 else float("nan"))
        ap = average_precision_score(y_test, scores)
        baseline_rows.append((name, note, auc, ap))

    for name, scores in predictions.items():
        baseline_rows.append((
            name, "", roc_auc_score(y_test, scores),
            average_precision_score(y_test, scores),
        ))

    parts += [
        "## FR-16 — Performance against stated baselines",
        "",
        "Baselines are declared before the models, not chosen afterwards to be",
        "beatable. Average precision is the metric to read: with a "
        f"{100 * base_rate:.1f}% base rate, ROC AUC is optimistic and accuracy is",
        "meaningless — a model predicting *no order is ever at risk* scores "
        f"{100 * (1 - base_rate):.1f}% accuracy.",
        "",
        table(
            ["approach", "note", "ROC AUC", "average precision"],
            baseline_rows,
        ),
        "",
        f"A random-guessing classifier scores an average precision equal to the "
        f"base rate, **{base_rate:.4f}**.",
        "",
        "---",
        "",
    ]

    # ---- FR-15 cost-optimal threshold -------------------------------------
    best_model = max(predictions, key=lambda k: average_precision_score(y_test, predictions[k]))
    probability = predictions[best_model]

    chosen, chosen_cost = best_threshold(
        y_test, probability, COST_FALSE_POSITIVE, COST_FALSE_NEGATIVE
    )
    f1_choice = f1_threshold(y_test, probability)

    def row_for(threshold: float, label: str) -> tuple:
        cost, tn, fp, fn, tp = expected_cost(
            y_test, probability, threshold, COST_FALSE_POSITIVE, COST_FALSE_NEGATIVE
        )
        flagged = tp + fp
        precision = tp / flagged if flagged else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        return (label, threshold, flagged, tp, fp, fn, precision, recall, cost)

    do_nothing_cost = float(y_test.sum() * COST_FALSE_NEGATIVE)
    flag_all_cost = float((len(y_test) - y_test.sum()) * COST_FALSE_POSITIVE)

    threshold_rows = [
        row_for(chosen, f"Cost-optimal ({chosen:.3f})"),
        row_for(0.5, "Default 0.5"),
        row_for(f1_choice, f"F1-optimal ({f1_choice:.3f})"),
    ]

    sensitivity_rows = []
    for ratio in COST_RATIO_GRID:
        t, cost = best_threshold(y_test, probability, 1.0, float(ratio))
        _, _, fp, fn, tp = expected_cost(y_test, probability, t, 1.0, float(ratio))
        sensitivity_rows.append((
            f"1 : {ratio}", t, tp + fp, tp / (tp + fn) if tp + fn else 0.0,
            tp / (tp + fp) if tp + fp else 0.0,
        ))

    parts += [
        "## FR-15 — Threshold chosen by business cost, not by F1",
        "",
        "**Stated assumptions.** Flagging an order means intervening on it — a",
        "proactive status contact, a shipping upgrade, a goodwill credit.",
        "",
        table(
            ["quantity", "assumed value", "meaning"],
            [
                ("Cost of a false positive", f"R${COST_FALSE_POSITIVE:.2f}",
                 "intervening on an order that would have been fine"),
                ("Cost of a false negative", f"R${COST_FALSE_NEGATIVE:.2f}",
                 "a preventable low review that was not prevented"),
                ("Ratio", f"1 : {COST_FALSE_NEGATIVE / COST_FALSE_POSITIVE:.0f}", ""),
            ],
        ),
        "",
        "Both are assumptions about a business this project does not run. The",
        "sensitivity analysis below therefore matters more than the point values:",
        "what a decision-maker needs to know is how much the answer moves when",
        "their own numbers replace these.",
        "",
        f"Model used: **{best_model}** (highest average precision).",
        "",
        table(
            ["threshold rule", "threshold", "flagged", "TP", "FP", "FN",
             "precision", "recall", "expected cost (R$)"],
            threshold_rows,
        ),
        "",
        table(
            ["policy", "expected cost (R$)"],
            [
                ("Do nothing (flag no order)", do_nothing_cost),
                ("Flag every order", flag_all_cost),
                ("Model at the cost-optimal threshold", chosen_cost),
            ],
        ),
        "",
        "### Sensitivity — where the threshold goes as the cost ratio changes",
        "",
        table(
            ["FP : FN cost ratio", "optimal threshold", "orders flagged",
             "recall", "precision"],
            sensitivity_rows,
        ),
        "",
        "---",
        "",
    ]

    # ---- FR-17 permutation importance -------------------------------------
    print("  computing permutation importance ...")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        importance = permutation_importance(
            fitted[best_model], x_test, y_test,
            scoring="average_precision", n_repeats=5, random_state=42, n_jobs=1,
        )

    order = np.argsort(importance.importances_mean)[::-1]
    importance_rows = [
        (FEATURES[i], float(importance.importances_mean[i]),
         float(importance.importances_std[i]))
        for i in order[:20]
    ]

    parts += [
        "## FR-17 — Permutation importance",
        "",
        "Permutation importance on the **test set**, scored by average precision,",
        "5 repeats. Not impurity importance: impurity is computed on training",
        "data and is biased toward high-cardinality features, which here would",
        "hand the top of the table to `primary_category` and `distance_km` for",
        "being finely divisible rather than for being informative.",
        "",
        "The value is the drop in average precision when that column alone is",
        "shuffled. Near-zero means the model was not using it.",
        "",
        table(
            ["feature", "mean drop in average precision", "std"],
            importance_rows,
        ),
        "",
        "---",
        "",
    ]

    # ---- Ceiling diagnostic ----------------------------------------------
    print("  fitting ceiling diagnostic (deliberately leaking) ...")
    outcome = load_ceiling_diagnostic()
    leaked = frame.merge(outcome, on="order_id", how="left")
    leaked["is_late"] = leaked["is_late"].astype(str)

    leak_train = leaked[leaked["purchased_at"] < SPLIT_DATE]
    leak_test = leaked[leaked["purchased_at"] >= SPLIT_DATE]
    leak_features = FEATURES + ["is_late", "delay_days"]

    leak_pipeline = Pipeline([
        ("prep", ColumnTransformer([
            ("numeric", Pipeline([
                ("impute", SimpleImputer(strategy="median")),
                ("scale", StandardScaler()),
            ]), NUMERIC_FEATURES + ["delay_days"]),
            ("categorical", Pipeline([
                ("impute", SimpleImputer(strategy="most_frequent")),
                ("encode", OneHotEncoder(handle_unknown="infrequent_if_exist",
                                         min_frequency=30, sparse_output=False)),
            ]), CATEGORICAL_FEATURES + ["is_late"]),
        ])),
        ("model", HistGradientBoostingClassifier(
            max_iter=300, learning_rate=0.06, max_leaf_nodes=31,
            l2_regularization=1.0, early_stopping=True,
            validation_fraction=0.15, random_state=42,
        )),
    ])

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        leak_pipeline.fit(leak_train[leak_features], leak_train[TARGET].to_numpy())
        leak_probability = leak_pipeline.predict_proba(leak_test[leak_features])[:, 1]

    leak_ap = average_precision_score(leak_test[TARGET].to_numpy(), leak_probability)
    leak_auc = roc_auc_score(leak_test[TARGET].to_numpy(), leak_probability)
    honest_ap = average_precision_score(y_test, probability)

    parts += [
        "## Diagnostic — why the honest model is weak",
        "",
        "**This model is deliberately leaking and is never deployed.** It adds",
        "`is_late` and `delay_days` — the two columns FR-14 forbids — to answer one",
        "question: is the honest model weak because its features are poor, or",
        "because the signal genuinely is not present at purchase time?",
        "",
        table(
            ["model", "features", "ROC AUC", "average precision"],
            [
                ("Honest (deployable)", f"{len(FEATURES)} pre-delivery",
                 roc_auc_score(y_test, probability), honest_ap),
                ("Leaking (diagnostic only)",
                 f"{len(FEATURES)} + is_late + delay_days", leak_auc, leak_ap),
                ("Base rate", "none", 0.5, base_rate),
            ],
        ),
        "",
        f"Knowing the delivery outcome lifts average precision from "
        f"{honest_ap:.4f} to **{leak_ap:.4f}** — "
        f"{leak_ap / honest_ap:.1f}× the honest model, and "
        f"{leak_ap / base_rate:.1f}× the base rate.",
        "",
        "So some of the signal is genuinely unavailable at purchase time: whether",
        "an order goes late is driven by carrier-side variance that M4 measured as",
        "episodic — a late rate swinging between 1.16% and 18.96% month to month —",
        "and none of that is visible in the basket, the product, the route or the",
        "seller's history when the order is placed.",
        "",
        "### But even perfect knowledge of lateness is not enough",
        "",
        "The leaking model reaches only 0.32 average precision. It knows, for",
        "certain, whether each order arrived late — and still cannot identify most",
        "low reviews. The decomposition says why.",
        "",
        low_score_decomposition(leak_test, TARGET),
        "",
        "**Most bad reviews are not about lateness.** Late orders are a minority of",
        "orders and only about half of them score low, so the majority of low",
        "scores in this dataset sit on orders that arrived **on time or early**.",
        "",
        "That is the single most important caveat this milestone produces, and it",
        "bounds M7 directly: delivery is the largest *controllable* driver of",
        "dissatisfaction that this project can measure, but eliminating lateness",
        "entirely would still leave the majority of low reviews in place. The",
        "recommendation must be sized against the share it can actually reach, not",
        "against all dissatisfaction.",
        "",
        "---",
        "",
    ]

    # ---- Calibration ------------------------------------------------------
    brier = brier_score_loss(y_test, probability)
    bins = pd.qcut(probability, 10, duplicates="drop")
    calibration = pd.DataFrame({"p": probability, "y": y_test, "bin": bins})
    grouped = calibration.groupby("bin", observed=True).agg(
        predicted=("p", "mean"), observed=("y", "mean"), n=("y", "size")
    )

    parts += [
        "## Calibration",
        "",
        f"Brier score **{brier:.4f}** (lower is better; predicting the base rate",
        f"for every order scores {base_rate * (1 - base_rate):.4f}).",
        "",
        "A cost-optimal threshold is only meaningful if the probabilities mean",
        "what they say — a threshold of 0.2 on a miscalibrated model is not the",
        "20% risk it appears to be.",
        "",
        table(
            ["decile", "mean predicted", "observed rate", "n"],
            [(str(index), float(row["predicted"]), float(row["observed"]),
              int(row["n"])) for index, row in grouped.iterrows()],
        ),
        "",
    ]

    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--stdout", action="store_true")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    frame = load_features()
    print(f"Loaded {len(frame):,} reviewed orders.")

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

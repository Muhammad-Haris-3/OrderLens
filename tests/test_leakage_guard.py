"""Guard the M6 leakage rule (SRS FR-14, Design Phase §8).

The rule: the classifier may use only features known before delivery completes.
Break it and the model looks superb and is worthless — M5 measured that 53.8% of
late orders score the minimum, so `is_late` alone would carry most of the target.

`analysis/predictive.py` asserts this at runtime, but that assertion only fires
when someone runs the model against a live warehouse. These tests run in CI on
every push, without a database, so a leak cannot reach `main` unnoticed.

The feature mart is checked too: SQL is where the leak would actually be
introduced, by adding a column to a select list.
"""

from __future__ import annotations

import re
from pathlib import Path

from analysis.predictive import (
    BANNED,
    CATEGORICAL_FEATURES,
    FEATURES,
    NUMERIC_FEATURES,
    OUTCOMES,
    TARGET,
)

ROOT = Path(__file__).resolve().parent.parent
FEATURE_MART = ROOT / "dbt_orderlens" / "models" / "marts" / "mart_prediction_features.sql"


def mart_sql() -> str:
    """The mart body with comments stripped — they discuss the banned columns."""
    text = FEATURE_MART.read_text(encoding="utf-8")
    return re.sub(r"--[^\n]*", " ", text)


def test_no_banned_column_is_declared_as_a_feature():
    """The allowlist must not contain anything post-delivery."""
    overlap = sorted(BANNED.intersection(FEATURES))
    assert not overlap, (
        f"post-delivery columns declared as model features: {overlap}. "
        "By the time these are known there is nothing left to intervene on."
    )


def test_the_outcome_is_not_also_a_feature():
    overlap = sorted(OUTCOMES.intersection(FEATURES))
    assert not overlap, f"outcome columns declared as features: {overlap}"


def test_feature_lists_do_not_overlap():
    both = sorted(set(NUMERIC_FEATURES).intersection(CATEGORICAL_FEATURES))
    assert not both, f"features declared as both numeric and categorical: {both}"

    assert len(FEATURES) == len(set(FEATURES)), "duplicate entries in the allowlist"


def test_target_is_not_in_the_feature_list():
    assert TARGET not in FEATURES


def test_feature_mart_selects_no_banned_column():
    """The leak would be introduced here — one line added to a select list.

    The mart legitimately *reads* is_late and is_low_score to build the as-of
    seller history, so the check is on what the final select projects, not on
    whether the words appear anywhere in the file.
    """
    body = mart_sql()
    final_select = body[body.rindex("select"):]

    for column in sorted(BANNED):
        assert not re.search(rf"\ba\.{re.escape(column)}\b", final_select), (
            f"mart_prediction_features projects the post-delivery column "
            f"{column!r}. It must not reach the feature table."
        )


def test_feature_mart_computes_seller_history_as_of_purchase():
    """The as-of construction is the whole defence against the subtle leak.

    A naive `avg(is_late) group by seller` would include this order's own outcome
    and every later order's. The window formulation is what makes the feature
    honest, so its absence is a regression worth failing on.
    """
    body = mart_sql().lower()

    assert "partition by primary_seller_id" in body, (
        "seller history is no longer partitioned by seller"
    )
    assert "rows between unbounded preceding and current row" in body, (
        "seller history is no longer a running total as-of the purchase — it may "
        "now include outcomes that had not happened when the order was placed"
    )
    assert "review_answered_at" in body, (
        "the low-score history no longer keys on when the review was ANSWERED; a "
        "review that exists but has not been written yet is not information"
    )

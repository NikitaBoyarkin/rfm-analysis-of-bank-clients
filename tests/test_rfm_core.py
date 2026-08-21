"""Unit tests for the pure functions in rfm_analysis.py.

Covers: build_rfm_table, score_quartiles, assign_segment, lorenz_gini,
segment_revenue_concentration, segment_summary. Uses synthetic mini-dataframes
so tests are independent of generate_data.py output.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import rfm_analysis as rfm

REPO_ROOT = Path(rfm.REPO_ROOT)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def sample_tx() -> pd.DataFrame:
    """Four customers with known recency/frequency/monetary ordering."""
    return pd.DataFrame(
        {
            "customer_id": [
                "a",
                "a",
                "a",  # recent, frequent, high spend
                "b",
                "b",  # recent, mid freq, mid spend
                "c",  # old, rare, low spend
                "d",
                "d",
                "d",
                "d",  # old, frequent, high spend (at-risk pattern)
            ],
            "transaction_date": pd.to_datetime(
                [
                    "2024-03-25",
                    "2024-03-20",
                    "2024-03-01",
                    "2024-03-28",
                    "2024-02-15",
                    "2023-02-01",
                    "2023-01-10",
                    "2023-01-20",
                    "2023-02-05",
                    "2023-03-30",
                ]
            ),
            "amount": [
                1000,
                2000,
                3000,
                1500,
                1500,
                100,
                5000,
                5000,
                5000,
                5000,
            ],
            "is_anomaly": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        }
    )


# ---------------------------------------------------------------------------
# build_rfm_table
# ---------------------------------------------------------------------------
def test_build_rfm_table_aggregates_correctly(sample_tx: pd.DataFrame) -> None:
    snapshot = pd.Timestamp("2024-04-01")
    out = rfm.build_rfm_table(sample_tx, snapshot_date=snapshot)
    assert set(out.columns) == {"customer_id", "recency", "frequency", "monetary_value"}
    row_a = out.set_index("customer_id").loc["a"]
    assert row_a["frequency"] == 3
    assert row_a["monetary_value"] == 6000
    # last txn of a is 2024-03-25 -> 7 days to snapshot
    assert row_a["recency"] == 7


def test_build_rfm_table_default_snapshot_is_max_plus_one(sample_tx: pd.DataFrame) -> None:
    out = rfm.build_rfm_table(sample_tx)
    max_date = sample_tx["transaction_date"].max().normalize()
    expected_snapshot = max_date + pd.Timedelta(days=1)
    min_recency = out["recency"].min()
    assert min_recency == (expected_snapshot - sample_tx["transaction_date"].max().normalize()).days


# ---------------------------------------------------------------------------
# score_quartiles
# ---------------------------------------------------------------------------
def test_score_quartiles_range_and_types(sample_tx: pd.DataFrame) -> None:
    scored = rfm.score_quartiles(rfm.build_rfm_table(sample_tx))
    for col in ("R_Quartile", "F_Quartile", "M_Quartile"):
        assert scored[col].between(1, 4).all()
        assert scored[col].dtype == int
    assert scored["RFMClass"].str.len().eq(3).all()
    assert scored["RFMScore"].between(3, 12).all()


def test_score_quartiles_recency_inverted(sample_tx: pd.DataFrame) -> None:
    """Most recent customer (lowest recency days) must get R_Quartile=4."""
    scored = rfm.score_quartiles(rfm.build_rfm_table(sample_tx))
    most_recent_id = scored.loc[scored["recency"].idxmin(), "customer_id"]
    assert scored.loc[scored["customer_id"] == most_recent_id, "R_Quartile"].iloc[0] == 4


# ---------------------------------------------------------------------------
# assign_segment
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("r", "f", "m", "expected"),
    [
        (4, 4, 4, "Champions"),
        (3, 3, 3, "Loyal"),
        (3, 2, 3, "Potential Loyalists"),
        (2, 3, 1, "At Risk"),
        (1, 2, 1, "Hibernating"),
        (3, 2, 2, "Need Attention"),
    ],
)
def test_assign_segment_combos(r: int, f: int, m: int, expected: str) -> None:
    row = pd.Series({"R_Quartile": r, "F_Quartile": f, "M_Quartile": m})
    assert rfm.assign_segment(row) == expected


def test_segments_cover_all_scored_rows(sample_tx: pd.DataFrame) -> None:
    scored = rfm.segment_rfm(rfm.score_quartiles(rfm.build_rfm_table(sample_tx)))
    valid = {
        "Champions",
        "Loyal",
        "Potential Loyalists",
        "At Risk",
        "Hibernating",
        "Need Attention",
    }
    assert set(scored["Segment"].unique()).issubset(valid)


# ---------------------------------------------------------------------------
# lorenz_gini
# ---------------------------------------------------------------------------
def test_lorenz_gini_uniform_is_near_zero() -> None:
    """Equal monetary values -> Gini ~ 0 (tiny positive bias: curve starts at 1/n, not origin)."""
    df = pd.DataFrame({"monetary_value": np.full(100, 10.0)})
    gini, cum_c, cum_r = rfm.lorenz_gini(df)
    assert gini == pytest.approx(0.0, abs=1e-2)
    assert cum_r[-1] == pytest.approx(1.0)
    assert cum_c[-1] == pytest.approx(1.0)


def test_lorenz_gini_one_holds_all_is_near_one() -> None:
    """One customer holds all revenue -> Gini approaches 1 for large n."""
    vals = np.zeros(1000)
    vals[-1] = 1e6
    df = pd.DataFrame({"monetary_value": vals})
    gini, _, _ = rfm.lorenz_gini(df)
    assert gini > 0.99


def test_lorenz_gini_monotonic_cum_revenue(sample_tx: pd.DataFrame) -> None:
    _, _, cum_r = rfm.lorenz_gini(rfm.build_rfm_table(sample_tx))
    assert np.all(np.diff(cum_r) >= 0)


# ---------------------------------------------------------------------------
# segment_revenue_concentration
# ---------------------------------------------------------------------------
def test_concentration_ratio_sign(sample_tx: pd.DataFrame) -> None:
    scored = rfm.segment_rfm(rfm.score_quartiles(rfm.build_rfm_table(sample_tx)))
    conc = rfm.segment_revenue_concentration(scored)
    # shares sum to 100
    assert conc["share_customers_%"].sum() == pytest.approx(100.0)
    assert conc["share_revenue_%"].sum() == pytest.approx(100.0)
    # concentration_ratio = revenue_share / customer_share
    expected = (conc["share_revenue_%"] / conc["share_customers_%"]).round(2)
    pd.testing.assert_series_equal(
        conc["concentration_ratio"].reset_index(drop=True),
        expected.reset_index(drop=True),
        check_names=False,
    )


# ---------------------------------------------------------------------------
# segment_summary
# ---------------------------------------------------------------------------
def test_segment_summary_counts_match(sample_tx: pd.DataFrame) -> None:
    scored = rfm.segment_rfm(rfm.score_quartiles(rfm.build_rfm_table(sample_tx)))
    summary = rfm.segment_summary(scored)
    assert summary["customers"].sum() == len(scored)
    # sorted by avg_rfm_score descending
    assert summary["avg_rfm_score"].is_monotonic_decreasing


# ---------------------------------------------------------------------------
# drop_anomalies
# ---------------------------------------------------------------------------
def test_drop_anomalies_removes_flagged(sample_tx: pd.DataFrame) -> None:
    tx = sample_tx.copy()
    tx.loc[0, "is_anomaly"] = 1
    out = rfm.drop_anomalies(tx)
    assert len(out) == len(tx) - 1
    assert (out["is_anomaly"] == 0).all()


def test_drop_anomalies_no_column_passthrough(sample_tx: pd.DataFrame) -> None:
    tx = sample_tx.drop(columns=["is_anomaly"])
    out = rfm.drop_anomalies(tx)
    assert len(out) == len(tx)

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
def test_lorenz_gini_uniform_is_exactly_zero() -> None:
    """Equal monetary values -> Gini exactly 0. The curve must start at the origin."""
    df = pd.DataFrame({"monetary_value": np.full(100, 10.0)})
    gini, cum_c, cum_r = rfm.lorenz_gini(df)
    assert gini == pytest.approx(0.0, abs=1e-12)
    assert cum_r[-1] == pytest.approx(1.0)
    assert cum_c[-1] == pytest.approx(1.0)


def test_lorenz_gini_two_equal_values_is_zero() -> None:
    """n=2 equal values: an unanchored curve reports 0.25 here instead of 0."""
    df = pd.DataFrame({"monetary_value": [5.0, 5.0]})
    gini, _, _ = rfm.lorenz_gini(df)
    assert gini == pytest.approx(0.0)


def test_lorenz_curve_starts_at_origin() -> None:
    df = pd.DataFrame({"monetary_value": [1.0, 2.0, 3.0]})
    _, cum_c, cum_r = rfm.lorenz_gini(df)
    assert (cum_c[0], cum_r[0]) == (0.0, 0.0)


def test_lorenz_gini_zero_revenue_is_safe() -> None:
    """All-zero monetary returns a defined 0.0 rather than nan or a ZeroDivisionError."""
    df = pd.DataFrame({"monetary_value": [0.0, 0.0, 0.0]})
    gini, cum_c, cum_r = rfm.lorenz_gini(df)
    assert gini == 0.0
    assert cum_c.size == cum_r.size


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
def test_concentration_ratio_ranks_by_revenue_per_customer(sample_tx: pd.DataFrame) -> None:
    """The ratio must order segments the same way revenue-per-customer does.

    This is not a restatement of the formula — the ratio is normalised by the
    overall revenue-per-customer, so preserving that ordering is an independent
    consequence of the metric being right.
    """
    scored = rfm.segment_rfm(rfm.score_quartiles(rfm.build_rfm_table(sample_tx)))
    conc = rfm.segment_revenue_concentration(scored).set_index("Segment")

    assert conc["share_customers_%"].sum() == pytest.approx(100.0)
    assert conc["share_revenue_%"].sum() == pytest.approx(100.0)

    revenue_per_customer = conc["revenue"] / conc["customers"]
    assert conc["concentration_ratio"].rank().equals(revenue_per_customer.rank())


def test_concentration_ratio_of_equal_segments_is_one() -> None:
    """Two identical segments must both land exactly on ratio 1.0."""
    scored = pd.DataFrame(
        {
            "customer_id": ["a", "b"],
            "monetary_value": [100.0, 100.0],
            "Segment": ["X", "Y"],
        }
    )
    conc = rfm.segment_revenue_concentration(scored).set_index("Segment")
    assert (conc["concentration_ratio"] == 1.0).all()


def test_concentration_survives_a_zero_revenue_segment() -> None:
    """A segment with no spend gets ratio 0.0, not a division error or a nan."""
    scored = pd.DataFrame(
        {
            "customer_id": ["a", "b", "c"],
            "monetary_value": [100.0, 80.0, 0.0],
            "Segment": ["Rich", "Mid", "Broke"],
        }
    )
    conc = rfm.segment_revenue_concentration(scored).set_index("Segment")
    assert conc.loc["Broke", "concentration_ratio"] == 0.0
    assert conc["concentration_ratio"].notna().all()


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


# ---------------------------------------------------------------------------
# Degenerate inputs — every case below raised before the corresponding fix
# ---------------------------------------------------------------------------
def test_build_rfm_table_empty_raises_value_error() -> None:
    """An empty frame must raise a named error, not AttributeError on NaT."""
    empty = pd.DataFrame({"customer_id": [], "transaction_date": pd.to_datetime([]), "amount": []})
    with pytest.raises(ValueError, match="empty input"):
        rfm.build_rfm_table(empty)


def test_quartiles_survive_heavy_ties() -> None:
    """Half the customers sharing frequency == 1 made pd.qcut raise on duplicate edges."""
    n = 40
    frame = pd.DataFrame(
        {
            "customer_id": [f"c{i}" for i in range(n)],
            "recency": np.arange(1, n + 1),
            "frequency": [1] * (n // 2) + list(range(2, n // 2 + 2)),
            "monetary_value": [10.0] * (n // 2) + list(np.arange(11, n // 2 + 11, dtype=float)),
        }
    )
    scored = rfm.score_quartiles(frame)
    for col in ("R_Quartile", "F_Quartile", "M_Quartile"):
        assert scored[col].between(1, 4).all()


def test_quartiles_survive_identical_monetary() -> None:
    """All-equal monetary collapses the quantile edges onto each other."""
    frame = pd.DataFrame(
        {
            "customer_id": [f"c{i}" for i in range(10)],
            "recency": np.arange(1, 11),
            "frequency": np.arange(1, 11),
            "monetary_value": np.full(10, 100.0),
        }
    )
    assert rfm.score_quartiles(frame)["M_Quartile"].between(1, 4).all()


def test_quartiles_survive_a_single_day_window() -> None:
    """Every transaction on one day leaves recency constant across customers."""
    same_day = pd.DataFrame(
        {
            "customer_id": [f"c{i}" for i in range(6)],
            "transaction_date": pd.to_datetime(["2024-01-01"] * 6),
            "amount": np.arange(10.0, 70.0, 10.0),
        }
    )
    scored = rfm.score_quartiles(rfm.build_rfm_table(same_day))
    assert scored["R_Quartile"].between(1, 4).all()


def test_single_customer_does_not_crash() -> None:
    one = pd.DataFrame(
        {
            "customer_id": ["solo", "solo"],
            "transaction_date": pd.to_datetime(["2024-01-01", "2024-01-05"]),
            "amount": [10.0, 20.0],
        }
    )
    scored = rfm.segment_rfm(rfm.score_quartiles(rfm.build_rfm_table(one)))
    assert len(scored) == 1
    assert scored["RFMScore"].iloc[0] == (
        scored["R_Quartile"].iloc[0] + scored["F_Quartile"].iloc[0] + scored["M_Quartile"].iloc[0]
    )


def test_recency_is_never_zero(sample_tx: pd.DataFrame) -> None:
    """The snapshot is the last txn day + 1, so the freshest customer scores 1, never 0."""
    out = rfm.build_rfm_table(sample_tx)
    assert out["recency"].min() >= 1


# ---------------------------------------------------------------------------
# assign_segment boundaries
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("r", "f", "m", "expected"),
    [
        (4, 1, 4, "Need Attention"),  # one purchase, high spend: not a loyalist
        (3, 1, 3, "Need Attention"),  # same shape, one quartile down
        (2, 2, 2, "Hibernating"),  # boundary: r <= 2 and f <= 2
        (2, 3, 4, "At Risk"),  # boundary: stale but historically frequent
    ],
)
def test_assign_segment_boundaries(r: int, f: int, m: int, expected: str) -> None:
    row = pd.Series({"R_Quartile": r, "F_Quartile": f, "M_Quartile": m})
    assert rfm.assign_segment(row) == expected


# ---------------------------------------------------------------------------
# load_transactions
# ---------------------------------------------------------------------------
def test_load_transactions_parses_dates_and_values(tmp_path: Path) -> None:
    csv = tmp_path / "tx.csv"
    csv.write_text(
        "customer_id,transaction_date,amount,product_category,payment_method,is_anomaly\n"
        "user_1,2024-01-01 10:00:00,100.5,Кредит,карта,0\n",
        encoding="utf-8",
    )
    df = rfm.load_transactions(csv)
    assert pd.api.types.is_datetime64_any_dtype(df["transaction_date"])
    assert df["amount"].iloc[0] == 100.5
    assert df["is_anomaly"].iloc[0] == 0


# ---------------------------------------------------------------------------
# build_rfm end to end
# ---------------------------------------------------------------------------
def test_build_rfm_writes_csv_and_excel(sample_tx: pd.DataFrame, tmp_path: Path) -> None:
    source = tmp_path / "in.csv"
    sample_tx.to_csv(source, index=False)
    out_csv = tmp_path / "rfm.csv"
    out_xlsx = tmp_path / "rfm.xlsx"

    scored = rfm.build_rfm(source, out_csv, out_xlsx, make_charts=False)

    assert out_csv.stat().st_size > 0
    assert out_xlsx.stat().st_size > 0

    back = pd.read_csv(out_csv)
    expected_columns = {
        "customer_id",
        "recency",
        "frequency",
        "monetary_value",
        "R_Quartile",
        "F_Quartile",
        "M_Quartile",
        "RFMClass",
        "RFMScore",
        "Segment",
    }
    assert expected_columns.issubset(back.columns)
    assert len(back) == len(scored)

    from openpyxl import load_workbook

    # Regression: the metrics sheet was silently renamed to Summary1 because its
    # key collided with the metadata sheet.
    assert load_workbook(out_xlsx).sheetnames == [
        "Summary",
        "Overview",
        "Segments",
        "Customer_RFM",
    ]


# ---------------------------------------------------------------------------
# plot_* smoke tests
# ---------------------------------------------------------------------------
def _scored(sample_tx: pd.DataFrame) -> pd.DataFrame:
    return rfm.segment_rfm(rfm.score_quartiles(rfm.build_rfm_table(sample_tx)))


@pytest.mark.parametrize(
    ("func", "filename"),
    [
        (rfm.plot_segment_distribution, "segment.png"),
        (rfm.plot_monetary_by_segment, "monetary.png"),
        (rfm.plot_rfm_scatter, "scatter.png"),
        (rfm.plot_rfm_score_distribution, "score.png"),
        (rfm.plot_rfm_matrix_heatmap, "matrix.png"),
        (rfm.plot_revenue_vs_customers_share, "share.png"),
        (rfm.plot_aov_by_segment, "aov.png"),
    ],
)
def test_plot_functions_write_a_file(
    sample_tx: pd.DataFrame, tmp_path: Path, func, filename: str
) -> None:
    out = tmp_path / filename
    func(_scored(sample_tx), out)
    assert out.stat().st_size > 0


def test_plot_lorenz_curve_returns_the_gini_it_drew(
    sample_tx: pd.DataFrame, tmp_path: Path
) -> None:
    scored = _scored(sample_tx)
    out = tmp_path / "lorenz.png"
    drawn = rfm.plot_lorenz_curve(scored, out)
    assert out.stat().st_size > 0
    assert drawn == pytest.approx(rfm.lorenz_gini(scored)[0])


def test_plot_monthly_activity_writes_a_file(sample_tx: pd.DataFrame, tmp_path: Path) -> None:
    out = tmp_path / "monthly.png"
    rfm.plot_monthly_activity(sample_tx, _scored(sample_tx), out)
    assert out.stat().st_size > 0


def test_heatmap_annotation_lands_on_its_own_cell(tmp_path: Path, monkeypatch) -> None:
    """Regression: the monetary label was positionally indexed against a
    differently ordered pivot, flipping every cell's value vertically."""
    rows = [
        {
            "customer_id": f"c{r}{f}",
            "R_Quartile": r,
            "F_Quartile": f,
            # the marker cell; every other cell holds a unique, distinct value
            "monetary_value": 999.0 if (r, f) == (4, 1) else float(r * 100 + f),
        }
        for r in (1, 2, 3, 4)
        for f in (1, 2, 3, 4)
    ]
    captured: dict = {}
    monkeypatch.setattr(rfm.plt, "close", lambda fig: captured.setdefault("fig", fig))

    rfm.plot_rfm_matrix_heatmap(pd.DataFrame(rows), tmp_path / "matrix.png")

    texts = [t.get_text() for t in captured["fig"].axes[0].texts]
    # seaborn's own count annotations come first, then the 16 monetary labels,
    # drawn row-major from the top row = R quartile 4.
    monetary_labels = texts[len(rows) :]
    assert monetary_labels[0] == "999", f"row 0 is R=4; got {monetary_labels[0]!r}"

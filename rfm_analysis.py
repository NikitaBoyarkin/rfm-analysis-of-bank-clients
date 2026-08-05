"""RFM analysis of bank clients.

Canonical pipeline: load -> clean -> RFM table -> quartile scoring -> segment -> export (CSV + Excel + charts).

Scoring convention (industry standard, higher = better):
    R_Quartile: 4 = most recent, 1 = longest ago
    F_Quartile: 4 = most frequent, 1 = rarest
    M_Quartile: 4 = highest spend, 1 = lowest
    RFMClass: 3-digit string, "444" = Champion, "111" = Lost
    RFMScore:  sum 3..12, higher = better
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from utils.report_generator import generate_rfm_excel

sns.set_theme(style="whitegrid")
plt.rcParams["figure.figsize"] = (10, 6)

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = REPO_ROOT / "data" / "bank_rfm_dataset_10k_fixed.csv"
DEFAULT_OUTPUT_CSV = REPO_ROOT / "data" / "rfm_output.csv"
DEFAULT_OUTPUT_XLSX = REPO_ROOT / "data" / "rfm_output_report.xlsx"
CHARTS_DIR = REPO_ROOT / "images"


def load_transactions(csv_path: Path | str) -> pd.DataFrame:
    """Load source transactions and parse dates."""
    df = pd.read_csv(csv_path)
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    return df


def drop_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """Drop flagged anomaly transactions if the column exists."""
    if "is_anomaly" in df.columns:
        return df[df["is_anomaly"] == 0].copy()
    return df.copy()


def build_rfm_table(df: pd.DataFrame, snapshot_date: pd.Timestamp | None = None) -> pd.DataFrame:
    """Aggregate per-customer Recency / Frequency / Monetary value."""
    if snapshot_date is None:
        snapshot_date = df["transaction_date"].max().normalize() + pd.Timedelta(days=1)
    rfm = (
        df.groupby("customer_id")
        .agg(
            recency=("transaction_date", lambda x: (snapshot_date - x.max()).days),
            frequency=("transaction_date", "count"),
            monetary_value=("amount", "sum"),
        )
        .reset_index()
    )
    return rfm


def score_quartiles(rfm: pd.DataFrame) -> pd.DataFrame:
    """Assign 1..4 quartile scores. Higher = better for all three."""
    scored = rfm.copy()
    # Recency: small value (recent) = good -> label 4
    scored["R_Quartile"] = pd.qcut(scored["recency"], 4, labels=[4, 3, 2, 1]).astype(int)
    # Frequency, Monetary: large value = good -> label 4
    scored["F_Quartile"] = pd.qcut(scored["frequency"], 4, labels=[1, 2, 3, 4]).astype(int)
    scored["M_Quartile"] = pd.qcut(scored["monetary_value"], 4, labels=[1, 2, 3, 4]).astype(int)
    scored["RFMClass"] = (
        scored["R_Quartile"].astype(str)
        + scored["F_Quartile"].astype(str)
        + scored["M_Quartile"].astype(str)
    )
    scored["RFMScore"] = scored["R_Quartile"] + scored["F_Quartile"] + scored["M_Quartile"]
    return scored


def assign_segment(row: pd.Series) -> str:
    """Map R/F/M quartile combo to a named segment.

    Combo-based (not sum-based): preserves which dimension drives the label,
    so "444" and "233" no longer collapse into one bucket.
    """
    r, f, m = row["R_Quartile"], row["F_Quartile"], row["M_Quartile"]
    if r >= 4 and f >= 4 and m >= 4:
        return "Champions"
    if r >= 3 and f >= 3 and m >= 3:
        return "Loyal"
    if r >= 3 and m >= 3:
        return "Potential Loyalists"
    if r <= 2 and f >= 3:
        return "At Risk"
    if r <= 2 and f <= 2:
        return "Hibernating"
    return "Need Attention"


def segment_rfm(scored: pd.DataFrame) -> pd.DataFrame:
    scored["Segment"] = scored.apply(assign_segment, axis=1)
    return scored


def segment_summary(scored: pd.DataFrame) -> pd.DataFrame:
    """Per-segment counts and mean RFM metrics."""
    summary = (
        scored.groupby("Segment")
        .agg(
            customers=("customer_id", "count"),
            avg_recency=("recency", "mean"),
            avg_frequency=("frequency", "mean"),
            avg_monetary=("monetary_value", "mean"),
            avg_rfm_score=("RFMScore", "mean"),
        )
        .round(2)
        .reset_index()
        .sort_values("avg_rfm_score", ascending=False)
    )
    return summary


def plot_segment_distribution(scored: pd.DataFrame, out_path: Path) -> None:
    """Bar chart: customer count per segment."""
    order = scored["Segment"].value_counts().index
    fig, ax = plt.subplots()
    sns.countplot(data=scored, y="Segment", order=order, ax=ax, color="#3a6ea5")
    ax.set_title("RFM segment distribution")
    ax.set_xlabel("Customers")
    for p in ax.patches:
        ax.annotate(int(p.get_width()), (p.get_width(), p.get_y() + p.get_height() / 2),
                    ha="left", va="center", xytext=(4, 0), textcoords="offset points")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_monetary_by_segment(scored: pd.DataFrame, out_path: Path) -> None:
    """Boxplot: monetary value per segment (log scale)."""
    fig, ax = plt.subplots()
    sns.boxplot(data=scored, x="avg_monetary" if False else "monetary_value", y="Segment", ax=ax,
                order=scored.groupby("Segment")["monetary_value"].median().sort_values(ascending=False).index)
    ax.set_xscale("log")
    ax.set_title("Monetary value by segment (log scale)")
    ax.set_xlabel("Monetary value")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_rfm_scatter(scored: pd.DataFrame, out_path: Path) -> None:
    """Scatter: recency vs frequency, coloured by monetary."""
    fig, ax = plt.subplots()
    sns.scatterplot(
        data=scored, x="recency", y="frequency", hue="Segment",
        size="monetary_value", sizes=(15, 120), alpha=0.7, ax=ax,
    )
    ax.set_title("Recency vs Frequency (size = Monetary)")
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def build_rfm(
    input_csv: Path | str = DEFAULT_INPUT,
    output_csv: Path | str = DEFAULT_OUTPUT_CSV,
    output_xlsx: Path | str = DEFAULT_OUTPUT_XLSX,
    exclude_anomalies: bool = True,
    make_charts: bool = True,
) -> pd.DataFrame:
    """Full pipeline: load -> clean -> RFM -> score -> segment -> export."""
    df = load_transactions(input_csv)
    df = drop_anomalies(df) if exclude_anomalies else df
    rfm = build_rfm_table(df)
    scored = segment_rfm(score_quartiles(rfm))

    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
    scored.to_csv(output_csv, index=False)

    summary = segment_summary(scored)
    generate_rfm_excel(scored, summary, str(output_xlsx))

    if make_charts:
        CHARTS_DIR.mkdir(parents=True, exist_ok=True)
        plot_segment_distribution(scored, CHARTS_DIR / "segment_distribution.png")
        plot_monetary_by_segment(scored, CHARTS_DIR / "monetary_by_segment.png")
        plot_rfm_scatter(scored, CHARTS_DIR / "rfm_scatter.png")

    print(f"Rows: {len(scored)} customers across {scored['Segment'].nunique()} segments")
    print(summary.to_string(index=False))
    print(f"\nCSV : {output_csv}")
    print(f"XLSX: {output_xlsx}")
    if make_charts:
        print(f"Charts: {CHARTS_DIR}")
    return scored


if __name__ == "__main__":
    if not DEFAULT_INPUT.exists():
        raise SystemExit(
            f"Dataset not found: {DEFAULT_INPUT}\n"
            "Generate it first:  python generate_data.py"
        )
    build_rfm()

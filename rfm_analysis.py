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
import numpy as np
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


def lorenz_gini(rfm: pd.DataFrame) -> tuple[float, np.ndarray, np.ndarray]:
    """Lorenz curve and Gini coefficient of monetary concentration.

    Top-X% of customers generating Y% of revenue verifies that segmentation
    has business sense (vs. uniform revenue). Pattern from olist reference.
    Returns (gini, cumulative_customers_share, cumulative_revenue_share).
    """
    m = rfm["monetary_value"].sort_values().values
    n = m.size
    cum_customers = np.arange(1, n + 1) / n
    cum_revenue = np.cumsum(m) / m.sum()
    # Version-agnostic trapezoidal integral (np.trapz was removed in numpy 2.0).
    area = float(np.sum(np.diff(cum_customers) * (cum_revenue[:-1] + cum_revenue[1:]) / 2))
    gini = 1 - 2 * area
    return gini, cum_customers, cum_revenue


def plot_lorenz_curve(rfm: pd.DataFrame, out_path: Path) -> float:
    """Plot Lorenz curve + Gini coefficient of monetary value concentration.

    Annotates the top-20% customers' share of revenue. Returns the Gini.
    """
    gini, cum_c, cum_r = lorenz_gini(rfm)
    fig, ax = plt.subplots()
    ax.plot(cum_c, cum_r, color="#3a6ea5", label="Lorenz curve")
    ax.plot([0, 1], [0, 1], "--", color="grey", label="Equality line")
    # Top-20% of customers (richest) hold 1 - cum_r[0.8n] of revenue.
    idx80 = max(int(np.ceil(0.8 * len(cum_c))) - 1, 0)
    top20_share = 1 - cum_r[idx80]
    ax.axvline(0.8, color="#d33", linestyle=":", alpha=0.6)
    ax.scatter([0.8], [cum_r[idx80]], color="#d33", zorder=5)
    ax.annotate(
        f"Top-20% → {top20_share:.0%} of revenue",
        xy=(0.8, cum_r[idx80]),
        xytext=(0.4, 0.25),
        fontsize=9,
        arrowprops={"arrowstyle": "->", "color": "#d33", "alpha": 0.7},
    )
    ax.set_title(f"Lorenz curve — monetary concentration (Gini = {gini:.3f})")
    ax.set_xlabel("Cumulative customers (poorest → richest)")
    ax.set_ylabel("Cumulative revenue")
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return gini


def segment_revenue_concentration(scored: pd.DataFrame) -> pd.DataFrame:
    """Per-segment share of customers vs share of revenue (olist pattern).

    concentration_ratio = revenue_share / customer_share. > 1 means the segment
    over-indexes on revenue; < 1 means it under-indexes. A segment with a high
    customer share but low revenue share is a candidate for cost cutting, not
    investment.
    """
    seg = (
        scored.groupby("Segment")
        .agg(customers=("customer_id", "count"), revenue=("monetary_value", "sum"))
        .reset_index()
    )
    seg["share_customers_%"] = (seg["customers"] / seg["customers"].sum() * 100).round(2)
    seg["share_revenue_%"] = (seg["revenue"] / seg["revenue"].sum() * 100).round(2)
    seg["concentration_ratio"] = (seg["share_revenue_%"] / seg["share_customers_%"]).round(2)
    return seg.sort_values("share_revenue_%", ascending=False)


def plot_segment_distribution(scored: pd.DataFrame, out_path: Path) -> None:
    """Bar chart: customer count per segment."""
    order = scored["Segment"].value_counts().index
    fig, ax = plt.subplots()
    sns.countplot(data=scored, y="Segment", order=order, ax=ax, color="#3a6ea5")
    ax.set_title("RFM segment distribution")
    ax.set_xlabel("Customers")
    for p in ax.patches:
        ax.annotate(
            int(p.get_width()),
            (p.get_width(), p.get_y() + p.get_height() / 2),
            ha="left",
            va="center",
            xytext=(4, 0),
            textcoords="offset points",
        )
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_monetary_by_segment(scored: pd.DataFrame, out_path: Path) -> None:
    """Boxplot: monetary value per segment (log scale)."""
    fig, ax = plt.subplots()
    sns.boxplot(
        data=scored,
        x="monetary_value",
        y="Segment",
        ax=ax,
        order=scored.groupby("Segment")["monetary_value"]
        .median()
        .sort_values(ascending=False)
        .index,
    )
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
        data=scored,
        x="recency",
        y="frequency",
        hue="Segment",
        size="monetary_value",
        sizes=(15, 120),
        alpha=0.7,
        ax=ax,
    )
    ax.set_title("Recency vs Frequency (size = Monetary)")
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_rfm_score_distribution(scored: pd.DataFrame, out_path: Path) -> None:
    """Histogram of RFM score (3..12) with the mean highlighted."""
    fig, ax = plt.subplots()
    bins = np.arange(2.5, 13.5, 1)
    sns.histplot(scored["RFMScore"], bins=bins, color="#3a6ea5", edgecolor="white", ax=ax)
    mean_score = scored["RFMScore"].mean()
    ax.axvline(mean_score, color="#d33", linestyle="--", linewidth=1.2)
    ax.text(
        mean_score + 0.15,
        ax.get_ylim()[1] * 0.95,
        f"mean = {mean_score:.2f}",
        color="#d33",
        fontsize=9,
        va="top",
    )
    ax.set_title("RFM score distribution")
    ax.set_xlabel("RFM score (3–12)")
    ax.set_ylabel("Customers")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_rfm_matrix_heatmap(scored: pd.DataFrame, out_path: Path) -> None:
    """Heatmap: customers per (Recency × Frequency) quartile combo.

    The classic RFM matrix grid. Rows = recency quartile (1 = long ago,
    4 = recent), columns = frequency quartile (1 = rare, 4 = frequent).
    Annotates the average monetary value inside each cell.
    """
    pivot = scored.pivot_table(
        index="R_Quartile", columns="F_Quartile", values="customer_id", aggfunc="count"
    ).sort_index(ascending=False)
    avg_m = scored.pivot_table(
        index="R_Quartile", columns="F_Quartile", values="monetary_value", aggfunc="mean"
    )
    fig, ax = plt.subplots()
    sns.heatmap(
        pivot,
        annot=True,
        fmt="d",
        cmap="viridis",
        cbar_kws={"label": "Customers"},
        ax=ax,
    )
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            ax.text(
                j + 0.5,
                i + 0.78,
                f"{avg_m.iloc[i, j]:,.0f}",
                ha="center",
                va="center",
                fontsize=7,
                color="white",
                alpha=0.9,
            )
    ax.set_title(
        "RFM matrix — customers per (Recency × Frequency) quartile\n(avg monetary in cell)"
    )
    ax.set_xlabel("Frequency quartile (1 = rare → 4 = frequent)")
    ax.set_ylabel("Recency quartile (1 = long ago → 4 = recent)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_revenue_vs_customers_share(scored: pd.DataFrame, out_path: Path) -> None:
    """Grouped bar: customer share % vs revenue share % per segment.

    Visual version of the concentration ratio. A segment whose revenue bar
    visibly exceeds its customer bar over-indexes on revenue.
    """
    conc = segment_revenue_concentration(scored).sort_values("share_customers_%")
    y = np.arange(len(conc))
    height = 0.35
    fig, ax = plt.subplots()
    ax.barh(
        y + height / 2,
        conc["share_customers_%"],
        height=height,
        color="#3a6ea5",
        label="Customers, %",
    )
    ax.barh(
        y - height / 2,
        conc["share_revenue_%"],
        height=height,
        color="#d33",
        alpha=0.85,
        label="Revenue, %",
    )
    for yi, (cs, rs) in enumerate(
        zip(conc["share_customers_%"], conc["share_revenue_%"], strict=True)
    ):
        ax.text(cs + 0.4, yi + height / 2, f"{cs:.1f}%", va="center", fontsize=8)
        ax.text(rs + 0.4, yi - height / 2, f"{rs:.1f}%", va="center", fontsize=8)
    ax.set_yticks(y, conc["Segment"])
    ax.set_xlabel("Share of total, %")
    ax.set_title("Customer share vs revenue share by segment")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_aov_by_segment(scored: pd.DataFrame, out_path: Path) -> None:
    """Boxplot: average transaction value (monetary / frequency) per segment."""
    aov = scored.assign(aov=scored["monetary_value"] / scored["frequency"])
    order = aov.groupby("Segment")["aov"].median().sort_values(ascending=False).index
    fig, ax = plt.subplots()
    sns.boxplot(data=aov, x="aov", y="Segment", order=order, ax=ax, color="#3a6ea5")
    ax.set_xscale("log")
    ax.set_title("Average transaction value by segment (log scale)")
    ax.set_xlabel("AOV = monetary / frequency")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_monthly_activity(tx: pd.DataFrame, scored: pd.DataFrame, out_path: Path) -> None:
    """Monthly revenue and transaction-count trend by segment."""
    merged = tx.merge(scored[["customer_id", "Segment"]], on="customer_id", how="inner")
    merged["month"] = merged["transaction_date"].dt.to_period("M")
    revenue = merged.groupby(["month", "Segment"])["amount"].sum().unstack(fill_value=0)
    count = merged.groupby(["month", "Segment"]).size().unstack(fill_value=0)

    fig, axs = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    revenue.plot(ax=axs[0], marker="o", markersize=3, linewidth=1.5)
    axs[0].set_title("Monthly revenue by segment")
    axs[0].set_ylabel("Revenue")
    count.plot(ax=axs[1], marker="o", markersize=3, linewidth=1.5)
    axs[1].set_title("Monthly transaction count by segment")
    axs[1].set_ylabel("Transactions")
    axs[1].legend(ncols=3, fontsize=8, loc="upper left")
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

    concentration = segment_revenue_concentration(scored)
    print("\nSegment revenue concentration (customers vs revenue):")
    print(concentration.to_string(index=False))

    if make_charts:
        CHARTS_DIR.mkdir(parents=True, exist_ok=True)
        plot_segment_distribution(scored, CHARTS_DIR / "segment_distribution.png")
        plot_monetary_by_segment(scored, CHARTS_DIR / "monetary_by_segment.png")
        plot_rfm_scatter(scored, CHARTS_DIR / "rfm_scatter.png")
        gini = plot_lorenz_curve(scored, CHARTS_DIR / "lorenz_curve.png")
        plot_rfm_score_distribution(scored, CHARTS_DIR / "rfm_score_distribution.png")
        plot_rfm_matrix_heatmap(scored, CHARTS_DIR / "rfm_matrix_heatmap.png")
        plot_revenue_vs_customers_share(scored, CHARTS_DIR / "revenue_vs_customers_share.png")
        plot_aov_by_segment(scored, CHARTS_DIR / "aov_by_segment.png")
        plot_monthly_activity(df, scored, CHARTS_DIR / "monthly_activity.png")
        print(f"\nGini coefficient (monetary concentration): {gini:.3f}")

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
            f"Dataset not found: {DEFAULT_INPUT}\nGenerate it first:  python generate_data.py"
        )
    build_rfm()

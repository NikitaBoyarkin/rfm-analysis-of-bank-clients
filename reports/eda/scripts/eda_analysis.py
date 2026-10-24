"""EDA full cycle for rfm-analysis-of-bank-clients (slug: rfm-bank).

Reproducible analysis of:
  data/bank_rfm_dataset_10k_fixed.csv  (grain = transaction)
  data/rfm_output.csv                  (grain = client, derived)

Produces:
  reports/eda/figures/*.png
  reports/eda/scripts/analysis_stats.json

Run:
  /Users/nikitaboarkin/Desktop/00 ide/00 portfolio/.eda-tools/.venv/bin/python \
      reports/eda/scripts/eda_analysis.py
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
plt.style.use("seaborn-v0_8-whitegrid")
plt.rcParams.update(
    {
        "font.family": ["DejaVu Sans", "sans-serif"],
        "axes.unicode_minus": False,
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "axes.titlesize": 13,
        "axes.labelsize": 11,
    }
)

REPO = Path(__file__).resolve().parents[3]  # .../rfm-analysis-of-bank-clients
DATA = REPO / "data" / "bank_rfm_dataset_10k_fixed.csv"
RFM = REPO / "data" / "rfm_output.csv"
OUT = REPO / "reports" / "eda"
FIG = OUT / "figures"
FIG.mkdir(parents=True, exist_ok=True)

BLUE = "#3a6ea5"
RED = "#d33"
GREEN = "#2a9d8f"
ORANGE = "#e76f51"
SEG_COLORS = {
    "Champions": "#2a9d8f",
    "Loyal": "#3a6ea5",
    "Potential Loyalists": "#8ab17d",
    "At Risk": "#e76f51",
    "Need Attention": "#e9c46a",
    "Hibernating": "#b07aa1",
}


def gini_top20(monetary: np.ndarray) -> tuple[float, float, np.ndarray, np.ndarray]:
    m = np.sort(monetary)
    n = m.size
    cc = np.concatenate([[0.0], np.arange(1, n + 1) / n])
    cr = np.concatenate([[0.0], np.cumsum(m) / m.sum()])
    area = float(np.sum(np.diff(cc) * (cr[:-1] + cr[1:]) / 2))
    gini = 1 - 2 * area
    idx80 = max(int(np.ceil(0.8 * len(cc))) - 1, 0)
    return gini, 1 - cr[idx80], cc, cr


def save(fig, name: str) -> None:
    fig.savefig(FIG / name, dpi=300, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


# ---------------------------------------------------------------- load
tx = pd.read_csv(DATA)
tx["transaction_date"] = pd.to_datetime(tx["transaction_date"])
rfm = pd.read_csv(RFM)

stats: dict = {}

# ---------------------------------------------------------------- Phase 1/2
stats["raw_rows"] = int(len(tx))
stats["raw_unique_customers"] = int(tx["customer_id"].nunique())
stats["anomaly_rows"] = int((tx["is_anomaly"] == 1).sum())
clean = tx[tx["is_anomaly"] == 0].copy()
stats["clean_rows"] = int(len(clean))
stats["clean_unique_customers"] = int(clean["customer_id"].nunique())
stats["full_row_dupes"] = int(tx.duplicated().sum())
stats["key_dupes"] = int(tx.duplicated(subset=["customer_id", "transaction_date"]).sum())
stats["nulls_total"] = int(tx.isna().sum().sum())
stats["date_min"] = str(tx["transaction_date"].min())
stats["date_max"] = str(tx["transaction_date"].max())

# customers that exist only through anomaly transactions
grp = tx.groupby("customer_id")["is_anomaly"].agg(["sum", "count"])
only_anom = grp[grp["sum"] == grp["count"]]
stats["customers_only_anomaly"] = int(len(only_anom))
stats["customers_only_anomaly_ids"] = sorted(only_anom.index.tolist())

# validity ranges
stats["amount_min"] = float(tx["amount"].min())
stats["amount_max"] = float(tx["amount"].max())
stats["amount_nonpositive"] = int((tx["amount"] <= 0).sum())
stats["future_dates"] = int((tx["transaction_date"] > pd.Timestamp.now()).sum())
stats["product_categories"] = sorted(tx["product_category"].unique().tolist())
stats["payment_methods"] = sorted(tx["payment_method"].unique().tolist())

# ---------------------------------------------------------------- anomaly label vs outliers
s = tx["amount"]
q1, q3 = s.quantile([0.25, 0.75])
iqr = q3 - q1
iqr_lo, iqr_hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
iqr_flag = (s < iqr_lo) | (s > iqr_hi)
z_flag = ((s - s.mean()) / s.std()).abs() > 3
label = tx["is_anomaly"] == 1


def pr(flag: pd.Series, pos: pd.Series) -> dict:
    tp = int((flag & pos).sum())
    return {
        "tp": tp,
        "fp": int(flag.sum() - tp),
        "fn": int(pos.sum() - tp),
        "precision": round(tp / flag.sum(), 3) if flag.sum() else 0.0,
        "recall": round(tp / pos.sum(), 3) if pos.sum() else 0.0,
    }


stats["iqr_bounds"] = [round(float(iqr_lo), 2), round(float(iqr_hi), 2)]
stats["iqr_outlier_share"] = round(float(iqr_flag.mean()), 4)
stats["z_outlier_share"] = round(float(z_flag.mean()), 4)
stats["label_share"] = round(float(label.mean()), 4)
stats["iqr_vs_label"] = pr(iqr_flag, label)
stats["z_vs_label"] = pr(z_flag, label)
stats["anom_amount_mean"] = round(float(tx.loc[label, "amount"].mean()), 2)
stats["clean_amount_mean"] = round(float(tx.loc[~label, "amount"].mean()), 2)
stats["anom_amount_min"] = float(tx.loc[label, "amount"].min())
stats["clean_amount_max"] = float(tx.loc[~label, "amount"].max())
stats["corr_amount_anomaly"] = round(float(tx["amount"].corr(tx["is_anomaly"])), 4)

# ---------------------------------------------------------------- Phase 3 univariate/bivariate
stats["amount_skew"] = round(float(tx["amount"].skew()), 3)
stats["amount_mean"] = round(float(tx["amount"].mean()), 2)
stats["amount_median"] = round(float(tx["amount"].median()), 2)
stats["amount_p95"] = round(float(tx["amount"].quantile(0.95)), 2)
stats["clean_amount_median"] = round(float(clean["amount"].median()), 2)


# ---------------------------------------------------------------- Phase 4 metric by segment
def seg_table(df: pd.DataFrame, col: str) -> pd.DataFrame:
    g = df.groupby(col)["amount"].agg(["count", "mean", "median", "sum"])
    g["share_%"] = (g["sum"] / g["sum"].sum() * 100).round(2)
    g["vs_overall_%"] = ((g["mean"] / df["amount"].mean() - 1) * 100).round(2)
    return g.sort_values("median", ascending=False)


prod = seg_table(tx, "product_category")
pay = seg_table(tx, "payment_method")
stats["product_median_gap"] = round(float(prod["median"].max() / prod["median"].min()), 3)
stats["payment_median_gap"] = round(float(pay["median"].max() / pay["median"].min()), 3)

# customer-level segment gap from derived RFM output
segm = rfm.groupby("Segment").agg(
    customers=("customer_id", "count"),
    avg_recency=("recency", "mean"),
    avg_frequency=("frequency", "mean"),
    avg_monetary=("monetary_value", "mean"),
    revenue=("monetary_value", "sum"),
    avg_rfm=("RFMScore", "mean"),
)
segm["share_customers_%"] = (segm["customers"] / segm["customers"].sum() * 100).round(2)
segm["share_revenue_%"] = (segm["revenue"] / segm["revenue"].sum() * 100).round(2)
segm["concentration_ratio"] = (segm["share_revenue_%"] / segm["share_customers_%"]).round(2)
segm = segm.sort_values("avg_monetary", ascending=False)
stats["segment_monetary_gap"] = round(
    float(segm["avg_monetary"].max() / segm["avg_monetary"].min()), 3
)
stats["segment_table"] = segm.round(2).reset_index().to_dict(orient="records")

# ---------------------------------------------------------------- README truth check
gini, top20, cum_c, cum_r = gini_top20(rfm["monetary_value"].to_numpy())
stats["gini"] = round(gini, 4)
stats["top20_revenue_share"] = round(top20, 4)
stats["mean_rfm_score"] = round(float(rfm["RFMScore"].mean()), 4)
stats["rfm_customers"] = int(len(rfm))
stats["readme"] = {
    "clients_1983": {"claim": 1983, "recomputed": int(clean["customer_id"].nunique())},
    "transactions_9492": {"claim": 9492, "recomputed": int(len(clean))},
    "gini_0.324": {"claim": 0.324, "recomputed": round(gini, 3)},
    "top20_38.2": {"claim": 38.2, "recomputed": round(top20 * 100, 1)},
    "mean_rfm_7.50": {"claim": 7.50, "recomputed": round(float(rfm["RFMScore"].mean()), 2)},
}

# ---------------------------------------------------------------- Phase 5 trend
weekly = (
    clean.set_index("transaction_date")
    .resample("W")
    .agg(value=("amount", "sum"), count=("amount", "size"), per_unit=("amount", "mean"))
)
weekly["d_value"] = weekly["value"].pct_change() * 100
weekly["d_count"] = weekly["count"].pct_change() * 100
weekly["d_per_unit"] = weekly["per_unit"].pct_change() * 100
# first (partial) week: data starts on a Sunday -> only 1 day of coverage
stats["first_week_partial"] = bool(
    weekly["count"].iloc[0] < 0.4 * weekly["count"].iloc[1:].median()
)
flag = weekly.iloc[1:][weekly.iloc[1:]["d_value"].abs() >= 30]
stats["trend_flags"] = [
    {
        "week": str(idx.date()),
        "d_value_%": round(float(row["d_value"]), 1),
        "d_count_%": round(float(row["d_count"]), 1),
        "d_per_unit_%": round(float(row["d_per_unit"]), 1),
        "driver": "behaviour" if abs(row["d_per_unit"]) > abs(row["d_count"]) else "flow",
    }
    for idx, row in flag.iterrows()
]

# ---------------------------------------------------------------- FIGURES
# 1. amount distribution (linear + log)
fig, axs = plt.subplots(1, 2, figsize=(12, 4.5), layout="constrained")
axs[0].hist(tx["amount"], bins=60, color=BLUE, edgecolor="white")
axs[0].axvline(
    tx["amount"].median(), color=RED, ls="--", lw=1.4, label=f"median {tx['amount'].median():,.0f}"
)
axs[0].axvline(
    tx["amount"].mean(), color=ORANGE, ls=":", lw=1.4, label=f"mean {tx['amount'].mean():,.0f}"
)
axs[0].set(xlabel="Amount", ylabel="Transactions", title="Transaction amount — linear scale")
axs[0].legend(frameon=False, fontsize=9)
axs[1].hist(tx["amount"], bins=60, color=BLUE, edgecolor="white")
axs[1].set_yscale("log")
axs[1].set(xlabel="Amount", ylabel="Transactions (log)", title="Transaction amount — log y")
fig.suptitle(f"Amount is heavily right-skewed (skew = {tx['amount'].skew():.2f})", fontsize=13)
save(fig, "01_amount_distribution.png")

# 2. median amount by product_category (sorted bar)
fig, ax = plt.subplots(figsize=(9, 4.5), layout="constrained")
d = prod.sort_values("median")
ax.barh(d.index, d["median"], color=BLUE, edgecolor="black", linewidth=0.4)
ax.bar_label(ax.containers[0], fmt="%.0f", padding=3, fontsize=9)
ax.axvline(tx["amount"].median(), color=RED, ls="--", lw=1.2, label="overall median")
ax.set(
    xlabel="Median transaction amount",
    ylabel="",
    title="Median amount by product category (near-flat)",
)
ax.legend(frameon=False)
save(fig, "02_amount_by_product.png")

# 3. weekly trend of transaction amount (flow vs behaviour)
fig, axs = plt.subplots(2, 1, figsize=(12, 7), sharex=True, layout="constrained")
axs[0].plot(
    weekly.index, weekly["value"], color=BLUE, marker="o", ms=3, lw=1.4, label="weekly revenue"
)
for idx, row in flag.iterrows():
    axs[0].scatter([idx], [row["value"]], color=RED, zorder=5, s=45)
    axs[0].annotate(
        f"{row['d_value']:+.0f}%",
        (idx, row["value"]),
        xytext=(0, 10),
        textcoords="offset points",
        ha="center",
        fontsize=8,
        color=RED,
    )
axs[0].set(ylabel="Weekly revenue", title="Weekly transaction revenue — flagged weeks annotated")
axs[0].legend(frameon=False)
axs[1].plot(
    weekly.index, weekly["count"], color=GREEN, marker="o", ms=3, lw=1.4, label="flow: transactions"
)
ax2 = axs[1].twinx()
ax2.plot(
    weekly.index,
    weekly["per_unit"],
    color=ORANGE,
    marker="s",
    ms=3,
    lw=1.2,
    ls="--",
    label="behaviour: mean ticket",
)
axs[1].set(
    xlabel="Week",
    ylabel="Transactions (flow)",
    title="Flow (count) vs behaviour (per-transaction mean)",
)
axs[1].legend(frameon=False, loc="upper left")
ax2.set_ylabel("Mean ticket", color=ORANGE)
axs[1].annotate(
    "partial first week (ramp-up)",
    xy=(weekly.index[0], weekly["count"].iloc[0]),
    xytext=(weekly.index[3], weekly["count"].iloc[0] + 40),
    fontsize=8,
    arrowprops={"arrowstyle": "->", "color": "grey"},
)
save(fig, "03_weekly_amount_trend.png")

# 4. anomaly structure: amount by label (project-specific lead finding)
fig, axs = plt.subplots(1, 2, figsize=(12, 4.5), layout="constrained")
groups = [tx.loc[tx.is_anomaly == 0, "amount"], tx.loc[tx.is_anomaly == 1, "amount"]]
bp = axs[0].boxplot(
    groups,
    tick_labels=["is_anomaly=0", "is_anomaly=1"],
    patch_artist=True,
    medianprops={"color": "black"},
)
for patch, c in zip(bp["boxes"], [BLUE, RED], strict=True):
    patch.set_facecolor(c)
    patch.set_alpha(0.7)
axs[0].set_yscale("log")
axs[0].set(ylabel="Amount (log)", title="Amount by anomaly label")
axs[0].text(
    0.02,
    0.95,
    "label = amount threshold, not independent",
    transform=axs[0].transAxes,
    fontsize=8.5,
    va="top",
    color="#555",
)
# overlap histogram
bins = np.logspace(np.log10(tx.amount.min()), np.log10(tx.amount.max()), 45)
axs[1].hist(groups[0], bins=bins, color=BLUE, alpha=0.6, label="is_anomaly=0")
axs[1].hist(groups[1], bins=bins, color=RED, alpha=0.6, label="is_anomaly=1")
axs[1].set_xscale("log")
axs[1].axvspan(
    stats["anom_amount_min"],
    stats["clean_amount_max"],
    color="grey",
    alpha=0.2,
    label="overlap zone",
)
axs[1].set(
    xlabel="Amount (log)", ylabel="Transactions", title="Overlap zone: clean max vs anomaly min"
)
axs[1].legend(frameon=False, fontsize=9)
save(fig, "04_anomaly_amount_structure.png")

# 5. Lorenz curve
fig, ax = plt.subplots(figsize=(7.5, 6), layout="constrained")
ax.plot(cum_c, cum_r, color=BLUE, lw=2, label=f"Lorenz curve (Gini = {gini:.3f})")
ax.plot([0, 1], [0, 1], "--", color="grey", label="equality line")
ax.axvline(0.8, color=RED, ls=":", alpha=0.7)
ax.scatter([0.8], [cum_r[max(int(np.ceil(0.8 * len(cum_c))) - 1, 0)]], color=RED, zorder=5)
ax.annotate(
    f"top 20% -> {top20:.1%} of revenue",
    xy=(0.8, 1 - top20),
    xytext=(0.35, 0.25),
    fontsize=9,
    arrowprops={"arrowstyle": "->", "color": RED},
)
ax.set(
    xlabel="Cumulative customers (poorest -> richest)",
    ylabel="Cumulative revenue share",
    title="Monetary concentration — Lorenz curve",
)
ax.legend(loc="upper left", frameon=False)
save(fig, "05_lorenz_curve.png")

# 6. avg monetary by RFM segment (project-specific lead finding)
fig, ax = plt.subplots(figsize=(9.5, 5), layout="constrained")
order = segm.sort_values("avg_monetary")
bars = ax.barh(
    order.index,
    order["avg_monetary"],
    color=[SEG_COLORS.get(s, BLUE) for s in order.index],
    edgecolor="black",
    linewidth=0.4,
)
ax.bar_label(
    bars,
    labels=[
        f"{v:,.0f}  (x{c:.2f})"
        for v, c in zip(order["avg_monetary"], order["concentration_ratio"], strict=True)
    ],
    padding=4,
    fontsize=9,
)
ax.axvline(rfm["monetary_value"].mean(), color=RED, ls="--", lw=1.2, label="overall mean")
ax.set(
    xlabel="Average monetary value per client",
    ylabel="",
    title="Avg monetary by RFM segment (label = value, concentration ratio)",
)
ax.legend(frameon=False)
save(fig, "06_monetary_by_segment.png")

(OUT / "scripts" / "analysis_stats.json").write_text(
    json.dumps(stats, indent=2, ensure_ascii=False)
)
print(json.dumps(stats, indent=2, ensure_ascii=False))

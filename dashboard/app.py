"""Interactive RFM dashboard.

Run after the pipeline has produced data/rfm_output.csv:
    streamlit run dashboard/app.py

Tabs:
  - Overview      : KPI cards + segment distribution + revenue concentration
  - Segments      : per-segment table + monetary boxplot
  - RFM map       : recency x frequency scatter, colored by segment
  - Concentration : Lorenz curve + Gini
  - Raw           : filterable customer table

Filters: segment multiselect + recency / monetary ranges.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent
RFM_CSV = REPO_ROOT / "data" / "rfm_output.csv"

st.set_page_config(page_title="RFM — bank clients", page_icon="🏦", layout="wide")


# ---------------------------------------------------------------------------
# Data loading (cached)
# ---------------------------------------------------------------------------
@st.cache_data
def load_rfm(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    return df


def lorenz_gini(m: pd.Series) -> tuple[float, np.ndarray, np.ndarray]:
    vals = m.sort_values().values
    n = vals.size
    cum_c = np.arange(1, n + 1) / n
    cum_r = np.cumsum(vals) / vals.sum()
    area = float(np.sum(np.diff(cum_c) * (cum_r[:-1] + cum_r[1:]) / 2))
    gini = 1 - 2 * area
    return gini, cum_c, cum_r


if not RFM_CSV.exists():
    st.error(f"RFM output not found: {RFM_CSV}\nRun first: `python rfm_analysis.py`")
    st.stop()

df = load_rfm(str(RFM_CSV))

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
st.sidebar.header("Filters")
segments_all = sorted(df["Segment"].unique())
seg_sel = st.sidebar.multiselect("Segment", segments_all, default=segments_all)

r_min, r_max = int(df["recency"].min()), int(df["recency"].max())
recency_range = st.sidebar.slider("Recency (days)", r_min, r_max, (r_min, r_max))

m_min, m_max = float(df["monetary_value"].min()), float(df["monetary_value"].max())
monetary_range = st.sidebar.slider(
    "Monetary value", float(m_min), float(m_max), (float(m_min), float(m_max))
)

mask = (
    df["Segment"].isin(seg_sel)
    & df["recency"].between(*recency_range)
    & df["monetary_value"].between(*monetary_range)
)
fdf = df[mask].copy()

st.sidebar.caption(f"Showing **{len(fdf)}** / {len(df)} customers")

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("RFM segmentation — bank clients")
st.caption(
    f"Synthetic transaction log • snapshot = max txn + 1 day • "
    f"{len(df)} active customers • Gini = "
    f"{lorenz_gini(df['monetary_value'])[0]:.3f}"
)

tab_overview, tab_seg, tab_map, tab_lorenz, tab_raw = st.tabs(
    ["Overview", "Segments", "RFM map", "Concentration", "Raw"]
)

# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------
with tab_overview:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Customers", f"{len(fdf):,}")
    c2.metric("Segments", f"{fdf['Segment'].nunique()}")
    c3.metric("Avg RFM score", f"{fdf['RFMScore'].mean():.2f}")
    c4.metric("Total monetary", f"{fdf['monetary_value'].sum():,.0f}")

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Segment distribution")
        order = fdf["Segment"].value_counts().index
        fig, ax = plt.subplots(figsize=(7, 4))
        counts = fdf["Segment"].value_counts().reindex(order)
        ax.barh(counts.index, counts.values, color="#3a6ea5")
        for i, v in enumerate(counts.values):
            ax.text(v, i, f" {int(v)}", va="center", fontsize=9)
        ax.set_xlabel("Customers")
        ax.invert_yaxis()
        st.pyplot(fig, use_container_width=True)

    with col_b:
        st.subheader("Revenue concentration")
        conc = (
            fdf.groupby("Segment")
            .agg(customers=("customer_id", "count"), revenue=("monetary_value", "sum"))
            .reset_index()
        )
        conc["share_customers_%"] = (conc["customers"] / conc["customers"].sum() * 100).round(2)
        conc["share_revenue_%"] = (conc["revenue"] / conc["revenue"].sum() * 100).round(2)
        conc["concentration_ratio"] = (conc["share_revenue_%"] / conc["share_customers_%"]).round(2)
        st.dataframe(
            conc.sort_values("share_revenue_%", ascending=False),
            use_container_width=True,
            hide_index=True,
        )

# ---------------------------------------------------------------------------
# Segments
# ---------------------------------------------------------------------------
with tab_seg:
    st.subheader("Per-segment summary")
    summary = (
        fdf.groupby("Segment")
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
    st.dataframe(summary, use_container_width=True, hide_index=True)

    st.subheader("Monetary value by segment (log scale)")
    import seaborn as sns

    fig, ax = plt.subplots(figsize=(8, 4))
    order = fdf.groupby("Segment")["monetary_value"].median().sort_values(ascending=False).index
    sns.boxplot(data=fdf, x="monetary_value", y="Segment", order=order, ax=ax)
    ax.set_xscale("log")
    st.pyplot(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# RFM map
# ---------------------------------------------------------------------------
with tab_map:
    st.subheader("Recency vs Frequency (size = Monetary)")
    import seaborn as sns

    fig, ax = plt.subplots(figsize=(9, 5))
    sns.scatterplot(
        data=fdf,
        x="recency",
        y="frequency",
        hue="Segment",
        size="monetary_value",
        sizes=(15, 120),
        alpha=0.7,
        ax=ax,
    )
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
    st.pyplot(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Concentration
# ---------------------------------------------------------------------------
with tab_lorenz:
    gini, cum_c, cum_r = lorenz_gini(fdf["monetary_value"])
    st.subheader(f"Lorenz curve — Gini = {gini:.3f}")
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.plot(cum_c, cum_r, color="#3a6ea5", label="Lorenz curve")
    ax.plot([0, 1], [0, 1], "--", color="grey", label="Equality line")
    idx20 = max(int(np.ceil(0.8 * len(cum_c))) - 1, 0)
    top20_share = 1 - cum_r[idx20]
    ax.axvline(0.8, color="#d33", linestyle=":", alpha=0.6)
    ax.scatter([0.8], [cum_r[idx20]], color="#d33", zorder=5)
    ax.annotate(
        f"Top-20% → {top20_share:.0%} of revenue",
        xy=(0.8, cum_r[idx20]),
        xytext=(0.4, 0.25),
        fontsize=9,
        arrowprops={"arrowstyle": "->", "color": "#d33", "alpha": 0.7},
    )
    ax.set_xlabel("Cumulative customers (poorest → richest)")
    ax.set_ylabel("Cumulative revenue")
    ax.legend(loc="upper left")
    st.pyplot(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Raw
# ---------------------------------------------------------------------------
with tab_raw:
    st.subheader("Customer-level RFM")
    st.dataframe(
        fdf[
            [
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
            ]
        ].sort_values("RFMScore", ascending=False),
        use_container_width=True,
        hide_index=True,
    )

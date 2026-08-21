"""Test the hypotheses declared for this project.

Dataset schema: customer_id, transaction_date, amount, product_category,
payment_method, is_anomaly. Five hypotheses were originally declared (see git
history of the project description); only two are testable on this schema.
The rest require fields that do not exist here and are flagged accordingly.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_RFM = REPO_ROOT / "data" / "rfm_output.csv"
DEFAULT_TX = REPO_ROOT / "data" / "bank_rfm_dataset_10k_fixed.csv"


def _load(rfm_path: Path | str, tx_path: Path | str) -> tuple[pd.DataFrame, pd.DataFrame]:
    rfm = pd.read_csv(rfm_path)
    tx = pd.read_csv(tx_path)
    tx["transaction_date"] = pd.to_datetime(tx["transaction_date"])
    return rfm, tx


def h1_product_diversity_vs_monetary(rfm: pd.DataFrame, tx: pd.DataFrame) -> dict:
    """H1: High-Monetary clients use more distinct product categories.

    Test: Spearman correlation between monetary_value and product diversity
    (distinct product_category count per customer).
    """
    diversity = tx.groupby("customer_id")["product_category"].nunique().rename("product_diversity")
    merged = rfm.set_index("customer_id").join(diversity).dropna()
    rho, p = stats.spearmanr(merged["monetary_value"], merged["product_diversity"])
    return {
        "hypothesis": "H1: higher Monetary <-> more distinct products",
        "test": "Spearman correlation",
        "rho": round(rho, 3),
        "p_value": round(p, 4),
        "supported": p < 0.05,
    }


def h5_payment_method_vs_monetary(rfm: pd.DataFrame, tx: pd.DataFrame) -> dict:
    """H5: Mobile-bank users (Apple Pay / Google Pay) have higher Monetary.

    Test: Mann-Whitney U on per-customer monetary_value,
    mobile payers vs non-mobile payers.
    """
    mobile = {"Apple Pay", "Google Pay"}
    tx_mobile = tx.assign(is_mobile=tx["payment_method"].isin(mobile).astype(int))
    customer_mobile = tx_mobile.groupby("customer_id")["is_mobile"].max()
    merged = rfm.set_index("customer_id").join(customer_mobile).dropna()

    mobile_grp = merged[merged["is_mobile"] == 1]["monetary_value"]
    other_grp = merged[merged["is_mobile"] == 0]["monetary_value"]
    u, p = stats.mannwhitneyu(mobile_grp, other_grp, alternative="greater")
    return {
        "hypothesis": "H5: mobile-bank users have higher Monetary",
        "test": "Mann-Whitney U (one-sided)",
        "n_mobile": int(mobile_grp.shape[0]),
        "n_other": int(other_grp.shape[0]),
        "median_mobile": round(float(mobile_grp.median()), 2),
        "median_other": round(float(other_grp.median()), 2),
        "p_value": round(p, 4),
        "supported": p < 0.05,
    }


def h6_segment_vs_product_category(rfm: pd.DataFrame, tx: pd.DataFrame) -> dict:
    """H6: Segment and product-category mix are not independent.

    Test: chi-square independence on segment x product_category contingency
    (transaction counts). A significant result means different segments prefer
    different products, which supports segment-targeted cross-sell.
    """
    merged = tx.merge(rfm[["customer_id", "Segment"]], on="customer_id", how="inner")
    crosstab = pd.crosstab(merged["Segment"], merged["product_category"])
    chi2, p, dof, _ = stats.chi2_contingency(crosstab)
    # Cramer's V for effect size
    n = crosstab.values.sum()
    k = min(crosstab.shape)
    cramers_v = round(float(np.sqrt(chi2 / (n * (k - 1)))), 3)
    return {
        "hypothesis": "H6: segment and product-category mix are associated",
        "test": "chi-square independence",
        "dof": int(dof),
        "chi2": round(float(chi2), 2),
        "cramers_v": cramers_v,
        "p_value": round(p, 4),
        "supported": p < 0.05,
    }


def h7_recency_vs_payment_method(rfm: pd.DataFrame, tx: pd.DataFrame) -> dict:
    """H7: Mobile-bank users have lower Recency (more recent activity).

    Test: Mann-Whitney U (one-sided, alternative='less') on per-customer
    recency, mobile payers vs non-mobile payers. Lower recency = more recent.
    """
    mobile = {"Apple Pay", "Google Pay"}
    tx_mobile = tx.assign(is_mobile=tx["payment_method"].isin(mobile).astype(int))
    customer_mobile = tx_mobile.groupby("customer_id")["is_mobile"].max()
    merged = rfm.set_index("customer_id").join(customer_mobile).dropna()

    mobile_grp = merged[merged["is_mobile"] == 1]["recency"]
    other_grp = merged[merged["is_mobile"] == 0]["recency"]
    u, p = stats.mannwhitneyu(mobile_grp, other_grp, alternative="less")
    return {
        "hypothesis": "H7: mobile-bank users have lower Recency (more recent)",
        "test": "Mann-Whitney U (one-sided, less)",
        "n_mobile": int(mobile_grp.shape[0]),
        "n_other": int(other_grp.shape[0]),
        "median_recency_mobile": round(float(mobile_grp.median()), 2),
        "median_recency_other": round(float(other_grp.median()), 2),
        "p_value": round(p, 4),
        "supported": p < 0.05,
    }


def h8_anomaly_rate_by_segment(rfm: pd.DataFrame, tx: pd.DataFrame) -> dict:
    """H8: Anomaly transaction rate differs across segments.

    Test: chi-square independence on segment x is_anomaly (using ALL tx,
    including anomalies, since the rate itself is the signal). A significant
    result flags segments with unusual transaction patterns worth a fraud/
    data-quality look.
    """
    full = tx.merge(rfm[["customer_id", "Segment"]], on="customer_id", how="inner")
    crosstab = pd.crosstab(full["Segment"], full["is_anomaly"])
    chi2, p, dof, _ = stats.chi2_contingency(crosstab)
    rates = (full.groupby("Segment")["is_anomaly"].mean() * 100).round(2)
    return {
        "hypothesis": "H8: anomaly rate differs across segments",
        "test": "chi-square independence",
        "dof": int(dof),
        "chi2": round(float(chi2), 2),
        "p_value": round(p, 4),
        "anomaly_rate_%_by_segment": rates.to_dict(),
        "supported": p < 0.05,
    }


UNTESTABLE = [
    {
        "hypothesis": "H2: low Recency -> higher Retention Rate",
        "status": "untestable",
        "reason": "Retention requires a cohort panel over multiple periods; "
        "this dataset is a single transaction log with no retention label.",
    },
    {
        "hypothesis": "H3: Hibernating clients reactivate via email",
        "status": "untestable",
        "reason": "No campaign/exposure data; would need an A/B test on reactivation.",
    },
    {
        "hypothesis": "H4: high Frequency -> higher NPS",
        "status": "untestable",
        "reason": "No NPS / satisfaction field in the schema.",
    },
]


def run_all(rfm_path: Path | str = DEFAULT_RFM, tx_path: Path | str = DEFAULT_TX) -> list[dict]:
    rfm, tx = _load(rfm_path, tx_path)
    results = [
        h1_product_diversity_vs_monetary(rfm, tx),
        h5_payment_method_vs_monetary(rfm, tx),
        h6_segment_vs_product_category(rfm, tx),
        h7_recency_vs_payment_method(rfm, tx),
        h8_anomaly_rate_by_segment(rfm, tx),
    ]
    results.extend(UNTESTABLE)
    return results


if __name__ == "__main__":
    if not DEFAULT_RFM.exists():
        raise SystemExit(f"RFM output not found: {DEFAULT_RFM}\nRun first:  python rfm_analysis.py")
    for r in run_all():
        print("-" * 60)
        for k, v in r.items():
            print(f"{k:>18}: {v}")

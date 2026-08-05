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
    diversity = (
        tx.groupby("customer_id")["product_category"].nunique().rename("product_diversity")
    )
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
    results = [h1_product_diversity_vs_monetary(rfm, tx),
               h5_payment_method_vs_monetary(rfm, tx)]
    results.extend(UNTESTABLE)
    return results


if __name__ == "__main__":
    if not DEFAULT_RFM.exists():
        raise SystemExit(
            f"RFM output not found: {DEFAULT_RFM}\nRun first:  python rfm_analysis.py"
        )
    for r in run_all():
        print("-" * 60)
        for k, v in r.items():
            print(f"{k:>18}: {v}")

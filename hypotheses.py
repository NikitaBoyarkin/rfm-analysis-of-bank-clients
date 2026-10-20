"""Test the hypotheses declared for this project.

Dataset schema: customer_id, transaction_date, amount, product_category,
payment_method, is_anomaly. Five of the eight declared hypotheses are testable
on this schema; the other three need fields that do not exist here and are
flagged as untestable rather than silently dropped.

Methodology notes, each one a fix for a defect that made an earlier version of
this file report a number it could not support:

* Customer-level attributes (segment, product mix, channel mix) are tested on
  ONE ROW PER CUSTOMER. Running a chi-square on 10k transaction rows for an
  attribute that varies per customer is pseudoreplication: the row count, not
  the sample size, drives the p-value. H6 flips from p=0.96 to p=0.09 once the
  unit is the customer.
* "Ever used mobile pay" is a proxy for transaction count, not for a channel
  preference (P(ever) climbs 0.57 -> 0.99 with n_tx). H5/H7 use majority share
  and report frequency by group so the confound is visible.
* Five tests at alpha=0.05 give a ~23% family-wise error rate, so `run_all`
  reports Holm-adjusted p-values alongside the raw ones.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

# Cramér's V below this is treated as practically negligible even when p < 0.05:
# with n in the thousands, a V of ~0.07 is a real association and a useless one.
PRACTICAL_V = 0.10

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_RFM = REPO_ROOT / "data" / "rfm_output.csv"
DEFAULT_TX = REPO_ROOT / "data" / "bank_rfm_dataset_10k_fixed.csv"

MOBILE_METHODS = {"Apple Pay", "Google Pay"}
PERMUTATIONS = 2000


def _load(
    rfm_path: Path | str, tx_path: Path | str
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load the RFM output plus transactions in two forms.

    Returns (rfm, tx_clean, tx_raw). The RFM table was built from the anomaly-
    dropped frame, so every test that joins segments back onto transactions
    must use `tx_clean`; joining raw transactions onto clean-data segments
    would compare two different universes. H8 is the one test that needs
    `tx_raw`, because the anomaly rate is its signal.
    """
    rfm = pd.read_csv(rfm_path)
    tx = pd.read_csv(tx_path)
    tx["transaction_date"] = pd.to_datetime(tx["transaction_date"])
    if "is_anomaly" in tx.columns:
        return rfm, tx[tx["is_anomaly"] == 0].copy(), tx
    return rfm, tx.copy(), tx


def _mobile_majority(tx: pd.DataFrame) -> pd.Series:
    """1 for customers whose transactions are majority mobile-pay.

    Dividing by the customer's own transaction count is what separates a
    channel preference from transaction volume — "ever used mobile pay" is
    satisfied by a single transaction out of twenty.
    """
    is_mobile = tx["payment_method"].isin(MOBILE_METHODS).astype(int)
    share = tx.assign(is_mobile=is_mobile).groupby("customer_id")["is_mobile"].mean()
    return (share > 0.5).astype(int)


def _dominant_category(tx: pd.DataFrame) -> pd.DataFrame:
    """One row per customer: their most-used product category.

    Collapses transactions to the customer unit so a chi-square test counts
    customers, not rows. Ties break on category name for determinism.
    """
    counts = tx.groupby(["customer_id", "product_category"]).size().rename("n_tx").reset_index()
    counts = counts.sort_values(
        ["customer_id", "n_tx", "product_category"], ascending=[True, False, True]
    )
    return counts.drop_duplicates("customer_id")[["customer_id", "product_category"]]


def _association_test(
    frame: pd.DataFrame, col_a: str, col_b: str, label: str
) -> tuple[float, float, int, str]:
    """chi-square independence, with a permutation null when cells are thin.

    Below ~5 expected observations per cell the chi-square *approximation* to
    the null distribution breaks down — the asymptotic p-value is then wrong
    rather than merely imprecise. The honest fix is not to merge categories
    until the table flatters the test, but to get the null distribution by
    permuting one label column, which keeps the real categories intact. The
    chi-square statistic itself is unchanged; only the reference distribution
    is. A fixed seed keeps the reported p reproducible.
    """
    crosstab = pd.crosstab(frame[col_a], frame[col_b])
    chi2, p, dof, expected = stats.chi2_contingency(crosstab)
    thin = int((expected < 5).sum())
    if not thin:
        return float(chi2), float(p), int(dof), "chi-square independence (asymptotic)"

    rng = np.random.default_rng(42)
    b_values = frame[col_b].to_numpy()
    a_values = frame[col_a].to_numpy()
    drawn = np.empty(PERMUTATIONS, dtype=float)
    for i in range(PERMUTATIONS):
        shuffled = pd.crosstab(a_values, rng.permutation(b_values))
        drawn[i] = stats.chi2_contingency(shuffled)[0]
    p_perm = (1 + int((drawn >= chi2).sum())) / (PERMUTATIONS + 1)
    method = f"chi-square + permutation p ({thin} cell(s) with expected < 5)"
    return float(chi2), float(p_perm), int(dof), method


def _holm(p_values: list[float]) -> list[float]:
    """Holm-Bonferroni step-down adjusted p-values.

    Controls the family-wise error rate without assuming the tests are
    independent, which these five cannot claim.
    """
    m = len(p_values)
    order = np.argsort(p_values)
    adjusted = np.empty(m, dtype=float)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * p_values[idx])
        adjusted[idx] = min(running, 1.0)
    return [round(float(v), 4) for v in adjusted]


def h1_product_diversity_vs_monetary(rfm: pd.DataFrame, tx: pd.DataFrame) -> dict:
    """H1: High-Monetary clients use more distinct product categories.

    Test: Spearman correlation between monetary_value and product diversity
    (distinct product_category count per customer). Customer level by
    construction — both variables are per-customer.
    """
    diversity = tx.groupby("customer_id")["product_category"].nunique().rename("product_diversity")
    merged = rfm.set_index("customer_id").join(diversity).dropna()
    rho, p = stats.spearmanr(merged["monetary_value"], merged["product_diversity"])
    return {
        "hypothesis": "H1: higher Monetary <-> more distinct products",
        "test": "Spearman correlation",
        "n": int(merged.shape[0]),
        "rho": round(float(rho), 3),
        "p_value": round(float(p), 4),
        "supported": p < 0.05,
    }


def h5_payment_method_vs_monetary(rfm: pd.DataFrame, tx: pd.DataFrame) -> dict:
    """H5: Mobile-bank users (Apple Pay / Google Pay) have higher Monetary.

    Test: Mann-Whitney U (two-sided) on per-customer monetary_value, majority-
    mobile payers vs the rest. Frequency medians are reported alongside because
    the two groups differ in transaction count, which is a plausible rival
    explanation for any monetary gap.
    """
    merged = rfm.set_index("customer_id").join(_mobile_majority(tx)).dropna()
    merged["n_tx"] = tx.groupby("customer_id").size()

    mobile_grp = merged[merged["is_mobile"] == 1]
    other_grp = merged[merged["is_mobile"] == 0]
    u, p = stats.mannwhitneyu(mobile_grp["monetary_value"], other_grp["monetary_value"])
    return {
        "hypothesis": "H5: mobile-bank users (majority) have higher Monetary",
        "test": "Mann-Whitney U (two-sided)",
        "n_mobile": int(mobile_grp.shape[0]),
        "n_other": int(other_grp.shape[0]),
        "median_monetary_mobile": round(float(mobile_grp["monetary_value"].median()), 2),
        "median_monetary_other": round(float(other_grp["monetary_value"].median()), 2),
        "median_frequency_mobile": round(float(mobile_grp["n_tx"].median()), 2),
        "median_frequency_other": round(float(other_grp["n_tx"].median()), 2),
        "p_value": round(float(p), 4),
        "supported": p < 0.05,
    }


def h6_segment_vs_product_category(rfm: pd.DataFrame, tx: pd.DataFrame) -> dict:
    """H6: Segment and product-category mix are not independent.

    Test: chi-square independence on segment x dominant-product contingency,
    one row per customer. Significance only says the association is detectable;
    with a large n it can be detectable and still too weak to act on. The result
    therefore carries Cramér's V and an `actionable` flag (V >= PRACTICAL_V):
    segment-targeted cross-sell needs a non-negligible association, not just a
    small p-value.
    """
    merged = _dominant_category(tx).merge(rfm[["customer_id", "Segment"]], on="customer_id")
    crosstab = pd.crosstab(merged["Segment"], merged["product_category"])
    chi2, p, dof, method = _association_test(merged, "Segment", "product_category", "H6")
    n = crosstab.values.sum()
    k = min(crosstab.shape)
    cramers_v = round(float(np.sqrt(chi2 / (n * (k - 1)))), 3)
    return {
        "hypothesis": "H6: segment and product-category mix are associated",
        "test": method,
        "n_customers": int(n),
        "dof": dof,
        "chi2": round(chi2, 2),
        "cramers_v": cramers_v,
        "p_value": round(p, 4),
        "supported": p < 0.05,
        "practically_negligible": cramers_v < PRACTICAL_V,
        "actionable": (p < 0.05) and (cramers_v >= PRACTICAL_V),
        "interpretation": (
            "detectable but too weak to act on"
            if cramers_v < PRACTICAL_V
            else "association large enough to act on"
        ),
    }


def h7_recency_vs_payment_method(rfm: pd.DataFrame, tx: pd.DataFrame) -> dict:
    """H7: Mobile-bank users have lower Recency (more recent activity).

    Test: Mann-Whitney U (two-sided) on per-customer recency, majority-mobile
    payers vs the rest. Lower recency = more recent. Frequency medians are
    reported for the same confound reason as H5.
    """
    merged = rfm.set_index("customer_id").join(_mobile_majority(tx)).dropna()
    merged["n_tx"] = tx.groupby("customer_id").size()

    mobile_grp = merged[merged["is_mobile"] == 1]
    other_grp = merged[merged["is_mobile"] == 0]
    u, p = stats.mannwhitneyu(mobile_grp["recency"], other_grp["recency"])
    return {
        "hypothesis": "H7: mobile-bank users (majority) have lower Recency",
        "test": "Mann-Whitney U (two-sided)",
        "n_mobile": int(mobile_grp.shape[0]),
        "n_other": int(other_grp.shape[0]),
        "median_recency_mobile": round(float(mobile_grp["recency"].median()), 2),
        "median_recency_other": round(float(other_grp["recency"].median()), 2),
        "median_frequency_mobile": round(float(mobile_grp["n_tx"].median()), 2),
        "median_frequency_other": round(float(other_grp["n_tx"].median()), 2),
        "p_value": round(float(p), 4),
        "supported": p < 0.05,
    }


def h8_anomaly_flag_independence(rfm: pd.DataFrame, tx: pd.DataFrame) -> dict:
    """H8: the large-amount flag is a data-quality artifact, not a behaviour.

    `is_anomaly` marks a large one-off amount (the generator's >15,000 branch),
    not a customer trait. Test: chi-square independence between `is_anomaly` and
    `payment_method` at transaction level. Neither variable goes into a segment
    definition, so nothing about this comparison is self-referential — a
    significant result would mean large amounts cluster in a channel (a real
    data problem worth chasing), while independence is the evidence that
    dropping these rows before scoring is hygiene, not a behavioural filter.

    Deliberately NOT tested: anomaly rate by segment. Segments are built on the
    anomaly-dropped frame, so dropping a transaction lowers its customer's
    frequency and can move that customer into a lower segment. That mechanical
    link makes the segment comparison significant for a reason unrelated to the
    amounts (on this data: Hibernating 7.5% vs Champions 2.4%, chi2=68) — a
    selection artifact that reads like a fraud finding if published as one.
    """
    crosstab = pd.crosstab(tx["payment_method"], tx["is_anomaly"])
    chi2, p, dof, method = _association_test(tx, "payment_method", "is_anomaly", "H8")
    rates = (tx.groupby("payment_method")["is_anomaly"].mean() * 100).round(2)
    return {
        "hypothesis": "H8: large-amount flag is independent of payment channel",
        "test": method,
        "n_tx": int(crosstab.values.sum()),
        "dof": dof,
        "chi2": round(chi2, 2),
        "anomaly_rate_%_by_channel": rates.to_dict(),
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
    """Run the five testable hypotheses and attach Holm-adjusted p-values.

    The untestable three are appended unchanged — they have no p-value and take
    no part in the correction.
    """
    rfm, tx_clean, tx_raw = _load(rfm_path, tx_path)
    results = [
        h1_product_diversity_vs_monetary(rfm, tx_clean),
        h5_payment_method_vs_monetary(rfm, tx_clean),
        h6_segment_vs_product_category(rfm, tx_clean),
        h7_recency_vs_payment_method(rfm, tx_clean),
        h8_anomaly_flag_independence(rfm, tx_raw),
    ]
    adjusted = _holm([r["p_value"] for r in results])
    for result, p_adj in zip(results, adjusted, strict=True):
        result["p_value_holm"] = p_adj
        result["supported_holm"] = p_adj < 0.05
    results.extend(UNTESTABLE)
    return results


if __name__ == "__main__":
    if not DEFAULT_RFM.exists():
        raise SystemExit(f"RFM output not found: {DEFAULT_RFM}\nRun first:  python rfm_analysis.py")
    for r in run_all():
        print("-" * 60)
        for k, v in r.items():
            print(f"{k:>30}: {v}")

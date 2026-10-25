"""A/B test analyzer for EXP-001 (win-back campaign).

Three modes:

    python scripts/ab_test_analyzer.py --design
        Audit the pre-registered design: sample size, realized power, MDE.

    python scripts/ab_test_analyzer.py --baseline
        Estimate the control reactivation rate from the transaction log by
        replaying the segmentation at an earlier cutoff (no exposure data
        exists, so this is a proxy for p1, not a measured control arm).

    python scripts/ab_test_analyzer.py --results data/exp001_results.csv
        Full readout. Required columns:
            customer_id, variant (control|test), converted (0/1)
        Optional: revenue_30d, unsubscribed (0/1), offer_cost

Every statistic is computed here; nothing is hand-calculated.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rfm_analysis import (  # noqa: E402
    build_rfm_table,
    drop_anomalies,
    load_transactions,
    score_quartiles,
    segment_rfm,
)

ALPHA = 0.05
POWER_TARGET = 0.80

# Pre-registered design inputs (docs/experiment_winback.md)
DESIGN = {
    "p_control": 0.06,
    "mde_hypothesis": 0.03,  # the stated hypothesis: +3 pp
    "mde_planned": 0.04,  # the relaxed MDE the doc recommends
    "eligible": 992,
    "split": 0.5,
}


def srm_check(n_control: int, n_test: int, planned_share: float = 0.5) -> dict:
    """Chi-squared SRM against the PLANNED split, not an assumed 50/50."""
    observed = np.array([n_control, n_test], dtype=float)
    total = observed.sum()
    expected = np.array([total * planned_share, total * (1 - planned_share)])
    chi2, p = stats.chisquare(observed, expected)
    return {
        "n_control": int(n_control),
        "n_test": int(n_test),
        "planned_share": planned_share,
        "observed_share": round(n_test / total, 4),
        "chi2": round(float(chi2), 4),
        "p_value": round(float(p), 6),
        "srm_detected": bool(p < 0.001),
    }


def two_proportion_test(n_c: int, x_c: int, n_t: int, x_t: int, alpha: float = ALPHA) -> dict:
    """Two-sided z-test on rates (pooled SE for the test, unpooled for the CI)."""
    p_c, p_t = x_c / n_c, x_t / n_t
    pooled = (x_c + x_t) / (n_c + n_t)
    se_pooled = np.sqrt(pooled * (1 - pooled) * (1 / n_c + 1 / n_t))
    z = (p_t - p_c) / se_pooled if se_pooled else 0.0
    p_value = 2 * (1 - stats.norm.cdf(abs(z)))

    se_diff = np.sqrt(p_c * (1 - p_c) / n_c + p_t * (1 - p_t) / n_t)
    z_crit = stats.norm.ppf(1 - alpha / 2)
    diff = p_t - p_c
    return {
        "control_rate": round(p_c, 5),
        "test_rate": round(p_t, 5),
        "abs_diff_pp": round(diff * 100, 3),
        "rel_lift_%": round(diff / p_c * 100, 2) if p_c else None,
        "ci95_diff_pp": [round((diff - z_crit * se_diff) * 100, 3),
                         round((diff + z_crit * se_diff) * 100, 3)],
        "z": round(float(z), 4),
        "p_value": round(float(p_value), 6),
        "significant": bool(p_value < alpha),
    }


def power_two_proportion(p1: float, p2: float, n1: int, n2: int, alpha: float = ALPHA) -> float:
    se = np.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    if se == 0:
        return 1.0
    return float(stats.norm.cdf(abs(p2 - p1) / se - stats.norm.ppf(1 - alpha / 2)))


def required_n_per_arm(p1: float, p2: float, alpha: float = ALPHA,
                       power: float = POWER_TARGET) -> int:
    z_a = stats.norm.ppf(1 - alpha / 2)
    z_b = stats.norm.ppf(power)
    num = (z_a + z_b) ** 2 * (p1 * (1 - p1) + p2 * (1 - p2))
    return int(np.ceil(num / (p2 - p1) ** 2))


def holm(p_values: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values (guardrail family)."""
    order = np.argsort(p_values)
    m = len(p_values)
    adjusted = [0.0] * m
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p_values[idx]))
        adjusted[idx] = running
    return adjusted


def welch_ttest(control: pd.Series, test: pd.Series) -> dict:
    t, p = stats.ttest_ind(test.dropna(), control.dropna(), equal_var=False)
    return {
        "control_mean": round(float(control.mean()), 2),
        "test_mean": round(float(test.mean()), 2),
        "rel_lift_%": round((test.mean() - control.mean()) / control.mean() * 100, 2)
        if control.mean() else None,
        "t": round(float(t), 4),
        "p_value": round(float(p), 6),
        "significant": bool(p < ALPHA),
    }


def audit_design() -> dict:
    n_per_arm = int(DESIGN["eligible"] * DESIGN["split"])
    p1 = DESIGN["p_control"]
    out = {
        "eligible": DESIGN["eligible"],
        "n_per_arm": n_per_arm,
        "p_control_assumed": p1,
        "sample_size": {},
        "realized_power": {},
    }
    for label, mde in (("hypothesis_+3pp", DESIGN["mde_hypothesis"]),
                       ("planned_+4pp", DESIGN["mde_planned"])):
        p2 = p1 + mde
        out["sample_size"][label] = {
            "p_test": p2,
            "required_n_per_arm": required_n_per_arm(p1, p2),
            "feasible_with_current_population": required_n_per_arm(p1, p2) <= n_per_arm,
        }
        out["realized_power"][label] = {
            "mde_pp": mde * 100,
            "power_at_n_per_arm": round(power_two_proportion(p1, p2, n_per_arm, n_per_arm), 3),
        }

    # Smallest effect detectable with 80% power at the realizable sample size
    lo, hi = 1e-4, 0.5
    for _ in range(60):
        mid = (lo + hi) / 2
        if power_two_proportion(p1, p1 + mid, n_per_arm, n_per_arm) < POWER_TARGET:
            lo = mid
        else:
            hi = mid
    out["mde_at_80pct_power_pp"] = round(hi * 100, 2)
    out["verdict"] = (
        "underpowered for the stated +3 pp hypothesis"
        if out["realized_power"]["hypothesis_+3pp"]["power_at_n_per_arm"] < POWER_TARGET
        else "adequately powered"
    )
    return out


def sensitivity(p1_grid: list[float] | None = None, mde: float = 0.03) -> dict:
    """How required sample and realized power move with the true control rate."""
    p1_grid = p1_grid or [0.02, 0.03, 0.05, 0.06, 0.10, 0.15, 0.25]
    n_per_arm = int(DESIGN["eligible"] * DESIGN["split"])
    rows = {}
    for p1 in p1_grid:
        lo, hi = 1e-4, 0.5
        for _ in range(60):
            mid = (lo + hi) / 2
            if power_two_proportion(p1, p1 + mid, n_per_arm, n_per_arm) < POWER_TARGET:
                lo = mid
            else:
                hi = mid
        rows[f"p1={p1:.2f}"] = {
            "required_n_per_arm_mde_+3pp": required_n_per_arm(p1, p1 + mde),
            "power_at_496_per_arm_+3pp": round(power_two_proportion(p1, p1 + mde, n_per_arm, n_per_arm), 3),
            "mde_pp_at_80pct_power": round(hi * 100, 2),
        }
    return rows


def baseline_reactivation(
    cutoff: str = "2023-12-31",
    window_days: int = 30,
    data_path: Path | None = None,
) -> dict:
    """Replay EXP-001 eligibility at an earlier cutoff and measure the 30-day
    reactivation rate that a control arm would plausibly have shown."""
    source = data_path or (ROOT / "data" / "bank_rfm_dataset_10k_fixed.csv")
    tx = drop_anomalies(load_transactions(source))
    cutoff_ts = pd.Timestamp(cutoff)

    past = tx[tx["transaction_date"] <= cutoff_ts]
    rfm = segment_rfm(score_quartiles(build_rfm_table(past, snapshot_date=cutoff_ts)))

    eligible = rfm[rfm["Segment"].isin(["At Risk", "Hibernating"])]
    window_end = cutoff_ts + pd.Timedelta(days=window_days)
    active = tx[(tx["transaction_date"] > cutoff_ts)
                & (tx["transaction_date"] <= window_end)]
    reactivated = set(active["customer_id"])

    per_segment = {}
    for seg, grp in eligible.groupby("Segment"):
        n = len(grp)
        x = int(grp["customer_id"].isin(reactivated).sum())
        per_segment[seg] = {
            "n": n,
            "reactivated": x,
            "rate": round(x / n, 4) if n else None,
        }

    n_all = len(eligible)
    x_all = int(eligible["customer_id"].isin(reactivated).sum())
    rate = x_all / n_all if n_all else None
    return {
        "cutoff": cutoff,
        "window_days": window_days,
        "eligible": {
            "n": n_all,
            "reactivated": x_all,
            "rate": round(rate, 4) if rate is not None else None,
            "ci95_rate": [round(v, 4) for v in
                          stats.beta.ppf([0.025, 0.975], x_all + 0.5, n_all - x_all + 0.5)] if n_all else None,
            "avg_txn_amount": round(float(past[past["customer_id"].isin(eligible["customer_id"])]
                                          ["amount"].mean()), 2) if n_all else None,
        },
        "per_segment": per_segment,
        "power_if_p1_is_measured": {
            "n_per_arm": n_all // 2,
            "hypothesis_+3pp": round(
                power_two_proportion(rate, rate + 0.03, n_all // 2, n_all // 2), 3)
            if rate is not None else None,
            "planned_+4pp": round(
                power_two_proportion(rate, rate + 0.04, n_all // 2, n_all // 2), 3)
            if rate is not None else None,
            "required_n_per_arm_+3pp": required_n_per_arm(rate, rate + 0.03)
            if rate is not None else None,
            "required_n_per_arm_+4pp": required_n_per_arm(rate, rate + 0.04)
            if rate is not None else None,
        },
    }


def analyze_results(path: Path) -> dict:
    df = pd.read_csv(path)
    required = {"customer_id", "variant", "converted"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"missing columns: {sorted(missing)}")
    if not set(df["variant"].unique()) <= {"control", "test"}:
        raise SystemExit(f"unexpected variant labels: {sorted(df['variant'].unique())}")

    ctrl = df[df["variant"] == "control"]
    test = df[df["variant"] == "test"]
    report = {
        "srm": srm_check(len(ctrl), len(test), DESIGN["split"]),
        "primary": two_proportion_test(
            len(ctrl), int(ctrl["converted"].sum()),
            len(test), int(test["converted"].sum()),
        ),
    }

    guardrails = []
    if "unsubscribed" in df.columns:
        guardrails.append(("unsubscribe_rate", two_proportion_test(
            len(ctrl), int(ctrl["unsubscribed"].sum()),
            len(test), int(test["unsubscribed"].sum()))))
    if "offer_cost" in df.columns:
        cost = test["offer_cost"].sum()
        reactivated = int(test["converted"].sum())
        guardrails.append(("cost_per_reactivated", {
            "value": round(cost / reactivated, 2) if reactivated else None,
            "threshold": 600,
            "breached": bool(reactivated and cost / reactivated > 600),
        }))
    if guardrails:
        rate_tests = [g[1] for g in guardrails if "p_value" in g[1]]
        adjusted = holm([g["p_value"] for g in rate_tests])
        for g, p_adj in zip([g for g in guardrails if "p_value" in g[1]], adjusted, strict=True):
            g[1]["p_value_holm"] = round(p_adj, 6)
        report["guardrails"] = dict(guardrails)

    if "revenue_30d" in df.columns:
        report["secondary_revenue_30d"] = welch_ttest(ctrl["revenue_30d"], test["revenue_30d"])

    if report["srm"]["srm_detected"]:
        report["recommendation"] = "BLOCK — investigate assignment pipeline before interpreting"
    elif any(isinstance(g, dict) and g.get("breached") for g in report.get("guardrails", {}).values()):
        report["recommendation"] = "INVESTIGATE — guardrail breached"
    elif report["primary"]["significant"] and report["primary"]["abs_diff_pp"] > 0:
        report["recommendation"] = "SHIP — significant positive lift, guardrails clean"
    elif report["primary"]["significant"]:
        report["recommendation"] = "DON'T SHIP — significant negative lift"
    elif report["primary"]["abs_diff_pp"] > 0:
        report["recommendation"] = "EXTEND — positive trend, not significant"
    else:
        report["recommendation"] = "STOP — flat"
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--design", action="store_true", help="audit pre-registered design")
    parser.add_argument("--baseline", action="store_true", help="estimate control rate from data")
    parser.add_argument("--sensitivity", action="store_true",
                        help="required sample / power across candidate control rates")
    parser.add_argument("--cutoff", default="2023-12-31", help="baseline replay cutoff date")
    parser.add_argument("--window-days", type=int, default=30, help="reactivation window")
    parser.add_argument("--data", type=Path, help="transaction CSV for --baseline (default: data/bank_rfm_dataset_10k_fixed.csv)")
    parser.add_argument("--results", type=Path, help="CSV with experimental readout")
    args = parser.parse_args()

    if not (args.design or args.baseline or args.results or args.sensitivity):
        parser.print_help()
        return

    out = {}
    if args.design:
        out["design_audit"] = audit_design()
    if args.sensitivity:
        out["sensitivity"] = sensitivity()
    if args.baseline:
        out["baseline"] = baseline_reactivation(args.cutoff, args.window_days, args.data)
    if args.results:
        out["results"] = analyze_results(args.results)
    print(json.dumps(out, indent=2, ensure_ascii=False, default=float))


if __name__ == "__main__":
    main()

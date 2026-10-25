"""Generate the synthetic bank-transaction dataset used by the RFM pipeline.

Run first:  python generate_data.py
Then:       python rfm_analysis.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = REPO_ROOT / "data" / "bank_rfm_dataset_10k_fixed.csv"
DEFAULT_BEHAVIOURAL_OUTPUT = REPO_ROOT / "data" / "bank_rfm_dataset_behavioural.csv"

PRODUCTS = ["Кредит", "Дебетовая карта", "Вклад", "Страхование", "Инвестиции", "Ипотека"]
PRODUCT_PROBS = [0.30, 0.25, 0.15, 0.10, 0.10, 0.10]
PAYMENTS = ["карта", "Apple Pay", "Google Pay", "криптовалюта", "банковский перевод"]
PAYMENT_PROBS = [0.50, 0.20, 0.15, 0.10, 0.05]


def _transaction_date(rng: np.random.Generator) -> str:
    """Random transaction timestamp between 2023-01-01 and 2024-03-30."""
    base = np.datetime64("2023-01-01")
    offset = rng.integers(0, 455)
    hour = rng.integers(9, 21)
    minute = rng.integers(0, 60)
    ts = (
        base + np.timedelta64(offset, "D") + np.timedelta64(hour, "h") + np.timedelta64(minute, "m")
    )
    return pd.Timestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def generate_and_save_dataset(
    n_rows: int = 10000,
    n_customers: int = 2000,
    output: Path | str = DEFAULT_OUTPUT,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate synthetic bank transactions and save to CSV.

    Args:
        n_rows: number of transactions.
        n_customers: number of unique customer ids.
        output: destination CSV path.
        seed: RNG seed for reproducibility.

    Returns:
        Generated DataFrame.
    """
    print(f"Generating {n_rows} rows, {n_customers} customers...")
    rng = np.random.default_rng(seed)

    # 5% of transactions are large anomalies. One mask drives both the amount
    # and the flag, so is_anomaly marks exactly the rows it claims to.
    anomaly_mask = rng.random(n_rows) < 0.05
    amount = np.where(
        anomaly_mask,
        rng.uniform(15000, 100000, n_rows),
        rng.exponential(scale=2500, size=n_rows) + 500,
    ).round(2)

    data = {
        "customer_id": [f"user_{rng.integers(1, n_customers + 1)}" for _ in range(n_rows)],
        "transaction_date": [_transaction_date(rng) for _ in range(n_rows)],
        "amount": amount,
        "product_category": rng.choice(PRODUCTS, p=PRODUCT_PROBS, size=n_rows),
        "payment_method": rng.choice(PAYMENTS, p=PAYMENT_PROBS, size=n_rows),
        "is_anomaly": anomaly_mask.astype(int),
    }
    df = pd.DataFrame(data)

    for col, values in data.items():
        assert len(values) == n_rows, f"Length mismatch in {col}"

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False, encoding="utf-8")
    print(f"Saved {len(df)} rows -> {output}")
    print(df.head())
    return df


def generate_behavioural_dataset(
    n_rows: int = 10000,
    n_customers: int = 2000,
    output: Path | str = DEFAULT_BEHAVIOURAL_OUTPUT,
    seed: int = 42,
    churn_share: float = 0.45,
    rate_sigma: float = 0.9,
) -> pd.DataFrame:
    """Generate a log with customer heterogeneity and an actual churn process.

    The default dataset draws every transaction independently, so per-customer
    counts are Poisson and no customer ever leaves. Here each customer gets a
    latent rate and an active window that may end before the horizon — which is
    the minimum required for a reactivation baseline to measure anything but the
    generator itself (see docs/exp001_analysis_plan.md §2.1).
    """
    rng = np.random.default_rng(seed)
    horizon = 455

    rate = rng.lognormal(mean=0.0, sigma=rate_sigma, size=n_customers)
    start = rng.uniform(0, 90, n_customers)
    churned = rng.random(n_customers) < churn_share
    end = np.where(churned, rng.uniform(120, horizon, n_customers), float(horizon))
    span = np.clip(end - start, 1.0, None)

    expected = rate * span
    expected = expected * (n_rows / expected.sum())
    counts = rng.poisson(expected)

    base = np.datetime64("2023-01-01")
    customer_ids: list[str] = []
    dates: list[str] = []
    for idx in range(n_customers):
        n_i = int(counts[idx])
        if n_i == 0:
            continue
        offsets = rng.uniform(start[idx], end[idx], n_i)
        days = np.floor(offsets).astype("timedelta64[D]")
        hours = rng.integers(9, 21, n_i).astype("timedelta64[h]")
        minutes = rng.integers(0, 60, n_i).astype("timedelta64[m]")
        stamps = base + days + hours + minutes
        customer_ids.extend([f"user_{idx + 1}"] * n_i)
        dates.extend(pd.Timestamp(s).strftime("%Y-%m-%d %H:%M:%S") for s in stamps)

    total = len(dates)
    anomaly_mask = rng.random(total) < 0.05
    amount = np.where(
        anomaly_mask,
        rng.uniform(15000, 100000, total),
        rng.exponential(scale=2500, size=total) + 500,
    ).round(2)

    df = pd.DataFrame(
        {
            "customer_id": customer_ids,
            "transaction_date": dates,
            "amount": amount,
            "product_category": rng.choice(PRODUCTS, p=PRODUCT_PROBS, size=total),
            "payment_method": rng.choice(PAYMENTS, p=PAYMENT_PROBS, size=total),
            "is_anomaly": anomaly_mask.astype(int),
        }
    )

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False, encoding="utf-8")
    print(f"Saved {len(df)} rows -> {output}")
    return df


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate a synthetic bank transaction log.")
    parser.add_argument(
        "--behavioural",
        action="store_true",
        help="Generate the heterogeneous/churn version instead of the default i.i.d. log.",
    )
    args = parser.parse_args()

    if args.behavioural:
        generate_behavioural_dataset()
    else:
        generate_and_save_dataset()

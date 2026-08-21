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

PRODUCTS = ["Кредит", "Дебетовая карта", "Вклад", "Страхование", "Инвестиции", "Ипотека"]
PRODUCT_PROBS = [0.30, 0.25, 0.15, 0.10, 0.10, 0.10]
PAYMENTS = ["карта", "Apple Pay", "Google Pay", "криптовалюта", "банковский перевод"]
PAYMENT_PROBS = [0.50, 0.20, 0.15, 0.10, 0.05]


def _transaction_date(rng: np.random.Generator) -> str:
    """Random transaction timestamp between 2023-01-01 and 2024-04-01."""
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

    # 5% of transactions are large anomalies
    amount = np.where(
        rng.random(n_rows) < 0.05,
        rng.uniform(15000, 100000, n_rows),
        rng.exponential(scale=2500, size=n_rows) + 500,
    ).round(2)

    data = {
        "customer_id": [f"user_{rng.integers(1, n_customers + 1)}" for _ in range(n_rows)],
        "transaction_date": [_transaction_date(rng) for _ in range(n_rows)],
        "amount": amount,
        "product_category": rng.choice(PRODUCTS, p=PRODUCT_PROBS, size=n_rows),
        "payment_method": rng.choice(PAYMENTS, p=PAYMENT_PROBS, size=n_rows),
        "is_anomaly": np.where(rng.random(n_rows) < 0.05, 1, 0),
    }
    df = pd.DataFrame(data)

    for col, values in data.items():
        assert len(values) == n_rows, f"Length mismatch in {col}"

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False, encoding="utf-8-sig")
    print(f"Saved {len(df)} rows -> {output}")
    print(df.head())
    return df


if __name__ == "__main__":
    generate_and_save_dataset()

"""Bind the two data generators: the default log is frozen, the behavioural one has behaviour."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from generate_data import (
    DEFAULT_OUTPUT,
    generate_and_save_dataset,
    generate_behavioural_dataset,
)
from rfm_analysis import (
    build_rfm_table,
    drop_anomalies,
    load_transactions,
    score_quartiles,
    segment_rfm,
)


@pytest.fixture(scope="module")
def behavioural_csv(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("behavioural") / "tx.csv"
    generate_behavioural_dataset(output=out)
    return out


def test_default_generator_reproduces_the_committed_dataset(tmp_path: Path) -> None:
    """The i.i.d. log must stay byte-identical — README numbers and tests depend on it."""
    out = tmp_path / "default.csv"
    generate_and_save_dataset(output=out)
    assert hashlib.sha256(out.read_bytes()).hexdigest() == hashlib.sha256(
        DEFAULT_OUTPUT.read_bytes()
    ).hexdigest()


def test_behavioural_generator_is_overdispersed(behavioural_csv: Path) -> None:
    """Per-customer counts must be overdispersed, unlike the Poisson i.i.d. log."""
    tx = pd.read_csv(behavioural_csv)
    tx = tx[tx["is_anomaly"] == 0]
    ids = [f"user_{i}" for i in range(1, 2001)]
    counts = tx.groupby("customer_id").size().reindex(ids, fill_value=0)
    assert counts.var() / counts.mean() > 2.0


def test_behavioural_generator_produces_dormant_customers(behavioural_csv: Path) -> None:
    """Churn must leave customers who stopped transacting well before the horizon."""
    tx = pd.read_csv(behavioural_csv)
    tx["transaction_date"] = pd.to_datetime(tx["transaction_date"])
    tx = tx[tx["is_anomaly"] == 0]
    last = tx.groupby("customer_id")["transaction_date"].max()
    horizon = tx["transaction_date"].max()
    dormant = (horizon - last).dt.days > 120
    assert 0.15 < dormant.mean() < 0.50


def test_behavioural_reactivation_is_lower_than_uniform_predicts(behavioural_csv: Path) -> None:
    """A real churn process breaks the uniform-date model that fully explains the i.i.d. log."""
    tx = drop_anomalies(load_transactions(behavioural_csv))
    cutoff = pd.Timestamp("2023-12-31")
    past = tx[tx["transaction_date"] <= cutoff]
    rfm = segment_rfm(score_quartiles(build_rfm_table(past, snapshot_date=cutoff)))
    eligible = rfm[rfm["Segment"].isin(["At Risk", "Hibernating"])]

    window_end = cutoff + pd.Timedelta(days=30)
    active = set(tx.loc[
        (tx["transaction_date"] > cutoff) & (tx["transaction_date"] <= window_end), "customer_id"
    ])

    counts = past.groupby("customer_id").size().reindex(eligible["customer_id"])
    uniform_pred = float(np.mean(1 - (1 - 30 / 455) ** counts))
    observed = float(eligible["customer_id"].isin(active).mean())

    assert observed < uniform_pred - 0.05

"""Smoke + interaction tests for the Streamlit dashboard.

The dashboard imports data/rfm_output.csv, which is gitignored, so the whole
module skips on a fresh clone exactly like tests/test_readme_numbers.py does.
Expected numbers are re-derived from that CSV rather than hardcoded, so the
test goes red when the dashboard and the pipeline disagree.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

streamlit_testing = pytest.importorskip(
    "streamlit.testing.v1", reason="streamlit not installed (uv sync --all-extras)"
)
AppTest = streamlit_testing.AppTest

REPO_ROOT = Path(__file__).resolve().parent.parent
APP = REPO_ROOT / "dashboard" / "app.py"
OUT_CSV = REPO_ROOT / "data" / "rfm_output.csv"

pytestmark = pytest.mark.skipif(
    not OUT_CSV.exists(),
    reason="data/rfm_output.csv not generated (run: python rfm_analysis.py)",
)

TIMEOUT = 60


def _run() -> AppTest:
    return AppTest.from_file(str(APP), default_timeout=TIMEOUT).run()


def _metrics(at: AppTest) -> dict[str, str]:
    return {m.label: m.value for m in at.metric}


def test_dashboard_renders_without_exceptions() -> None:
    df = pd.read_csv(OUT_CSV)
    at = _run()

    assert at.exception == []
    assert at.title[0].value == "RFM segmentation — bank clients"
    assert len(at.tabs) == 5

    metrics = _metrics(at)
    assert metrics["Customers"] == f"{len(df):,}"
    assert metrics["Segments"] == str(df["Segment"].nunique())

    assert at.multiselect[0].options == sorted(str(s) for s in df["Segment"].unique())


def test_segment_filter_narrows_metrics_to_the_selected_segment() -> None:
    df = pd.read_csv(OUT_CSV)
    target = "Champions"
    expected = int((df["Segment"] == target).sum())
    assert expected > 0, "fixture CSV has no Champions — regenerate the pipeline output"

    at = _run()
    at.multiselect[0].set_value([target]).run()

    assert at.exception == []
    metrics = _metrics(at)
    assert metrics["Customers"] == f"{expected:,}"
    assert metrics["Segments"] == "1"


def test_empty_selection_warns_instead_of_crashing() -> None:
    at = _run()
    at.multiselect[0].set_value([]).run()

    assert at.exception == []
    assert any("No customers match" in w.value for w in at.warning)

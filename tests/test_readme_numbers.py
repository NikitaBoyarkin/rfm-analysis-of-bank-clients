"""Bind the README results table to the regenerated pipeline output.

The README quotes per-segment counts and averages. Without a mechanism those
are prose that rots the moment the pipeline is re-run — which is exactly what
happened before this test existed. Here each quoted figure is re-derived from
data/rfm_output.csv and the test goes red when they disagree.

Skips when the gitignored CSV is absent (a fresh clone that has not run the
pipeline yet), rather than failing for the wrong reason.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import rfm_analysis as rfm

REPO_ROOT = Path(rfm.REPO_ROOT)
README = REPO_ROOT / "README.md"
OUT_CSV = REPO_ROOT / "data" / "rfm_output.csv"

pytestmark = pytest.mark.skipif(
    not OUT_CSV.exists(),
    reason="data/rfm_output.csv not generated (run: python rfm_analysis.py)",
)

# Columns: Segment | Customers | Avg recency | Avg frequency | Avg monetary | Avg RFM
TOLERANCES = (0.05, 0.05, 0.5, 0.005)


def _number(text: str) -> float:
    """Parse a README cell like '27,608.83' or '11.4'."""
    return float(text.replace(",", "").replace("%", "").strip())


def _results_table_rows() -> list[list[str]]:
    """Table rows between the '## Results' and '## Chart gallery' headings."""
    text = README.read_text(encoding="utf-8")
    section = text[text.index("## Results") : text.index("## Chart gallery")]

    rows: list[list[str]] = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells or set("".join(cells)) <= set("-: "):
            continue  # markdown separator row
        rows.append(cells)
    return rows[1:]  # drop the header row


def test_readme_results_table_matches_pipeline_output() -> None:
    truth = rfm.segment_summary(pd.read_csv(OUT_CSV)).set_index("Segment")
    rows = _results_table_rows()
    assert rows, "no results table found in README"

    seen: set[str] = set()
    for cells in rows:
        name = cells[0].replace("**", "").strip()
        assert name in truth.index, f"README lists a segment the pipeline never emits: {name!r}"
        seen.add(name)

        expected = truth.loc[name]
        assert int(_number(cells[1])) == int(expected["customers"]), f"{name}: customers"
        for cell, column, tol in zip(
            cells[2:6],
            ("avg_recency", "avg_frequency", "avg_monetary", "avg_rfm_score"),
            TOLERANCES,
            strict=True,
        ):
            assert _number(cell) == pytest.approx(expected[column], abs=tol), f"{name}: {column}"

    assert seen == set(truth.index), "README omits a segment the pipeline produced"


def test_readme_gini_line_matches_the_pipeline() -> None:
    """The prose Gini must equal the value the pipeline computes for the same CSV."""
    gini, _, _ = rfm.lorenz_gini(pd.read_csv(OUT_CSV)[["monetary_value"]])
    text = README.read_text(encoding="utf-8")
    assert f"{gini:.3f}" in text, f"README does not quote the pipeline's Gini ({gini:.3f})"

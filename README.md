# RFM analysis of bank clients

Segment bank clients by transaction behavior using **Recency, Frequency, Monetary** scoring, then map quartile combos to named segments and export CSV + Excel + charts + an interactive dashboard.

## Background

Synthetic transaction log for 2,000 clients of a retail bank. The goal is to identify high-value clients, flag at-risk ones, and give marketing a targetable segment per customer.

- **Time period:** 2023-01-01 → 2024-04-01 (synthetic, reproducible via `generate_data.py`, seed 42)
- **Volume:** 10,000 transactions, ~1,981 unique active clients after anomaly drop
- **Schema:** `customer_id, transaction_date, amount, product_category, payment_method, is_anomaly`

## Quick start

```bash
uv sync --all-extras          # or: python -m venv .venv && pip install -r requirements.txt

python generate_data.py       # builds data/bank_rfm_dataset_10k_fixed.csv
python rfm_analysis.py        # writes data/rfm_output.csv, data/rfm_output_report.xlsx, images/*.png
python hypotheses.py          # runs the testable hypotheses over the RFM output
pytest                        # 18 unit tests on the pure pipeline functions
streamlit run dashboard/app.py   # interactive dashboard (5 tabs)
```

## Method

1. **Load & clean** — parse dates, drop rows flagged `is_anomaly == 1`.
2. **RFM table** — per `customer_id`: `recency` (days since last txn vs snapshot +1d), `frequency` (txn count), `monetary_value` (sum).
3. **Score quartiles 1..4** (higher = better):
   - `R_Quartile`: 4 = most recent, 1 = longest ago
   - `F_Quartile`: 4 = most frequent, 1 = rarest
   - `M_Quartile`: 4 = highest spend, 1 = lowest
   - `RFMClass`: 3-digit string (`444` = best, `111` = worst); `RFMScore` = sum (3..12)
4. **Segment** — combo-based (not sum-based), so `444` and `233` no longer share a bucket:

| Condition | Segment |
|---|---|
| R≥4 & F≥4 & M≥4 | Champions |
| R≥3 & F≥3 & M≥3 | Loyal |
| R≥3 & M≥3 | Potential Loyalists |
| R≤2 & F≥3 | At Risk |
| R≤2 & F≤2 | Hibernating |
| else | Need Attention |

5. **Concentration** — Lorenz curve + Gini coefficient verify segmentation has business sense; per-segment `concentration_ratio = revenue_share / customer_share` flags over/under-indexing.
6. **Export** — CSV (`data/rfm_output.csv`), formatted Excel (`data/rfm_output_report.xlsx`), charts (`images/`), interactive dashboard (`dashboard/`).

## Results

| Segment | Customers | Avg recency | Avg frequency | Avg monetary | Avg RFM |
|---|---:|---:|---:|---:|---:|
| Champions | 83 | 11.2 | 8.4 | 74,641 | 12.00 |
| Loyal | 311 | 29.1 | 7.1 | 40,997 | 10.41 |
| Potential Loyalists | 208 | 29.8 | 4.3 | 49,030 | 8.85 |
| At Risk | 232 | 115.9 | 7.0 | 40,172 | 8.43 |
| Need Attention | 395 | 29.1 | 4.3 | 9,816 | 7.01 |
| Hibernating | 752 | 171.5 | 3.2 | 17,459 | 4.81 |

**Monetary concentration:** Gini = 0.533 — Champions over-index on revenue (ratio 2.66), Hibernating under-indexes (ratio 0.62).

![Segment distribution](images/segment_distribution.png)
![Monetary by segment](images/monetary_by_segment.png)
![Recency vs Frequency](images/rfm_scatter.png)
![Lorenz curve](images/lorenz_curve.png)

## Hypotheses

Five original + three added hypotheses; seven testable on this schema.

| # | Hypothesis | Test | Result |
|---|---|---|---|
| H1 | Higher Monetary ↔ more distinct products | Spearman ρ | **ρ=0.498, p<0.001 — supported** |
| H5 | Mobile-bank users (Apple/Google Pay) have higher Monetary | Mann-Whitney U (one-sided) | **median 16,262 vs 10,053, p<0.001 — supported** |
| H6 | Segment × product-category associated | χ² independence | χ²=14.1, p=0.96 — **not supported (independent)** |
| H7 | Mobile users have lower Recency (more recent) | Mann-Whitney U (one-sided) | **median 59 vs 100, p<0.001 — supported** |
| H8 | Anomaly rate differs by segment | χ² independence | **χ²=68.8, p<0.001 — supported** (Hibernating 7.4%) |
| H2 | Low Recency → higher retention | — | untestable: no cohort panel / retention label |
| H3 | Hibernating clients reactivate via email | — | untestable: no campaign exposure data |
| H4 | High Frequency → higher NPS | — | untestable: no NPS / satisfaction field |

Run `python hypotheses.py` to reproduce.

## Recommendations

- **Champions (83):** retention rewards + referral asks; they drive the bulk of monetary value.
- **At Risk (232):** recent drop-off but historically frequent + high spend — re-engagement campaign before they slide into Hibernating (see `docs/experiment_winback.md`).
- **Hibernating (752, 38%):** the largest pool; cheap win-back emails, but don't over-invest — avg monetary is low.
- **Need Attention (395):** recent but low frequency/spend — upsell to lift M, or they churn quietly.
- **Potential Loyalists (208):** high spend, moderate frequency — upsell premium products to grow F.

## Docs & artifacts

| File | What |
|---|---|
| `docs/data_dictionary.md` | Field catalog for source + RFM tables |
| `docs/sql_templates.md` | SQL equivalents of the pipeline (PostgreSQL/ClickHouse) |
| `docs/metrics_framework.md` | Input→Output→Outcome, leading/lagging per segment |
| `docs/experiment_winback.md` | A/B design for a win-back campaign (FINER, sample size) |
| `docs/prd_segment_targeting.md` | PRD — expose `rfm_segment` to marketing |
| `dashboard/app.py` | Streamlit dashboard (Overview / Segments / RFM map / Concentration / Raw) |
| `presentation/slides.md` | Marp deck summarizing the project |

## Caveats

- Data is **synthetic** (see `generate_data.py`); segment sizes and correlations reflect the generator, not a real bank.
- Quartile thresholds define "high/low" mechanically; validate against business expectations before acting.
- `recency` is computed against a snapshot date (max txn + 1 day), not today.

## Project layout

```
rfm_analysis.py       canonical pipeline (load -> score -> segment -> export)
generate_data.py      synthetic dataset generator
hypotheses.py         testable + untestable hypothesis checks
utils/                Excel report generation
dashboard/            Streamlit interactive dashboard
presentation/         Marp slide deck
docs/                 data dictionary, SQL templates, A/B design, PRD, metrics
tests/                pytest unit tests (18)
data/                 dataset + outputs (gitignored where regenerable)
images/               charts
notebooks/            exploratory notebooks
```

## License

MIT — see [LICENSE](LICENSE).

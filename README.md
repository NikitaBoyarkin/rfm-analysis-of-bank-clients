# RFM analysis of bank clients

Segment bank clients by transaction behavior using **Recency, Frequency, Monetary** scoring, then map quartile combos to named segments and export CSV + Excel + charts.

## Background

Synthetic transaction log for 2,000 clients of a retail bank. The goal is to identify high-value clients, flag at-risk ones, and give marketing a targetable segment per customer.

- **Time period:** 2023-01-01 → 2024-04-01 (synthetic, reproducible via `generate_data.py`, seed 42)
- **Volume:** 10,000 transactions, ~1,981 unique active clients after anomaly drop
- **Schema:** `customer_id, transaction_date, amount, product_category, payment_method, is_anomaly`

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt      # or: uv sync

python generate_data.py     # builds data/bank_rfm_dataset_10k_fixed.csv
python rfm_analysis.py      # writes data/rfm_output.csv, data/rfm_output_report.xlsx, images/*.png
python hypotheses.py        # runs the testable hypotheses over the RFM output
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

5. **Export** — CSV (`data/rfm_output.csv`), formatted Excel (`data/rfm_output_report.xlsx`), charts (`images/`).

## Results

| Segment | Customers | Avg recency | Avg frequency | Avg monetary | Avg RFM |
|---|---:|---:|---:|---:|---:|
| Champions | 83 | 11.2 | 8.4 | 74,641 | 12.00 |
| Loyal | 311 | 29.1 | 7.1 | 40,997 | 10.41 |
| Potential Loyalists | 208 | 29.8 | 4.3 | 49,030 | 8.85 |
| At Risk | 232 | 115.9 | 7.0 | 40,172 | 8.43 |
| Need Attention | 395 | 29.1 | 4.3 | 9,816 | 7.01 |
| Hibernating | 752 | 171.5 | 3.2 | 17,459 | 4.81 |

![Segment distribution](images/segment_distribution.png)
![Monetary by segment](images/monetary_by_segment.png)
![Recency vs Frequency](images/rfm_scatter.png)

## Hypotheses

Five hypotheses were declared; two are testable on this schema, three require data not present here.

| # | Hypothesis | Test | Result |
|---|---|---|---|
| H1 | Higher Monetary ↔ more distinct products | Spearman ρ | **ρ=0.498, p<0.001 — supported** |
| H5 | Mobile-bank users (Apple/Google Pay) have higher Monetary | Mann-Whitney U (one-sided) | **median 16,262 vs 10,053, p<0.001 — supported** |
| H2 | Low Recency → higher retention | — | untestable: no cohort panel / retention label |
| H3 | Hibernating clients reactivate via email | — | untestable: no campaign exposure data |
| H4 | High Frequency → higher NPS | — | untestable: no NPS / satisfaction field |

Run `python hypotheses.py` to reproduce.

## Recommendations

- **Champions (83):** retention rewards + referral asks; they drive the bulk of monetary value.
- **At Risk (232):** recent drop-off but historically frequent + high spend — re-engagement campaign before they slide into Hibernating.
- **Hibernating (752, 38%):** the largest pool; cheap win-back emails, but don't over-invest — avg monetary is low.
- **Need Attention (395):** recent but low frequency/spend — upsell to lift M, or they churn quietly.
- **Potential Loyalists (208):** high spend, moderate frequency — upsell premium products to grow F.

## Caveats

- Data is **synthetic** (see `generate_data.py`); segment sizes and correlations reflect the generator, not a real bank.
- Quartile thresholds define "high/low" mechanically; validate against business expectations before acting.
- `recency` is computed against a snapshot date (max txn + 1 day), not today.

## Project layout

```
rfm_analysis.py       canonical pipeline (load -> score -> segment -> export)
generate_data.py      synthetic dataset generator
hypotheses.py         testable hypothesis checks
utils/                Excel report generation
data/                 dataset + outputs (gitignored where regenerable)
images/               charts
notebooks/            exploratory notebooks
```

## License

MIT — see [LICENSE](LICENSE).

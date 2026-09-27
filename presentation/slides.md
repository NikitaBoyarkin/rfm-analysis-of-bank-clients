---
marp: true
theme: default
paginate: true
size: 16:9
header: "RFM segmentation — bank clients"
footer: "Synthetic data • seed 42 • 1 983 customers"
---

<!-- _paginate: false -->

# RFM segmentation of bank clients
## Recency · Frequency · Monetary

Nikita Boyarkin · Product analytics portfolio

---

## Problem

Marketing gets a flat customer list and targets everyone the same way.

- No per-customer segment label
- Duplicated ad-hoc segment definitions
- No way to measure segment-level lift

**Goal:** give marketing a targetable segment per customer.

---

## Data

Synthetic transaction log (`generate_data.py`, seed 42).

| | |
|---|---|
| Period | 2023-01-01 → 2024-03-30 |
| Volume | 10 000 txns → 9 492 after anomaly drop → **1 983** active clients |
| Schema | `customer_id, transaction_date, amount, product_category, payment_method, is_anomaly` |

⚠️ Synthetic — segment sizes reflect the generator, not a real bank.

---

## Method

1. **Load & clean** — drop `is_anomaly == 1`
2. **RFM table** — per customer: recency (days), frequency (count), monetary (sum)
3. **Quartile score 1–4** — higher = better; `RFMClass` = 3-digit combo
4. **Segment** — combo-based (not sum-based), so `444` ≠ `233`

```
R≥4 & F≥4 & M≥4 → Champions
R≥3 & F≥3 & M≥3 → Loyal
R≥3 & F≥2 & M≥3 → Potential Loyalists
R≤2 & F≥3       → At Risk
R≤2 & F≤2       → Hibernating
else            → Need Attention
```

---

## Results — segments

| Segment | Customers | Avg recency | Avg freq | Avg monetary | Avg RFM |
|---|---:|---:|---:|---:|---:|
| Champions | 126 | 11.35 | 8.16 | 27 608.83 | 12.00 |
| Loyal | 376 | 32.13 | 6.40 | 20 692.31 | 10.32 |
| Potential Loyalists | 79 | 32.62 | 3.97 | 16 777.17 | 8.57 |
| At Risk | 349 | 123.85 | 6.30 | 19 381.56 | 8.37 |
| Need Attention | 410 | 30.39 | 4.07 | 8 962.92 | 7.20 |
| Hibernating | 643 | 177.47 | 2.92 | 8 786.79 | 4.56 |

---

## Results — revenue concentration

Gini = **0.324** — monetary value is moderately concentrated; the top 20% of customers hold 38.2% of revenue.

- **Champions** (6.4% of base) → 12.1% of revenue, concentration ratio **1.91**
- **At Risk** (17.6%) → 23.6% of revenue, ratio **1.34** — the highest-leverage win-back pool
- **Potential Loyalists** (4.0%) → 4.6% of revenue, ratio **1.16**
- **Hibernating** (32.4% of base) → 19.7% of revenue, ratio **0.61** — under-indexes now
- **Need Attention** (20.7%) → 12.8% of revenue, ratio **0.62**

→ Invest in Champions/Loyal/At Risk; cheap win-back for Hibernating; don't over-spend on Need Attention.

---

## Hypotheses

| # | Hypothesis | Test | Result |
|---|---|---|---|
| H1 | Higher Monetary ↔ more distinct products | Spearman ρ | **ρ=0.61, p<0.001 ✅** (Holm 0.000) |
| H5 | Mobile-bank users have higher Monetary | Mann-Whitney U (two-sided) | **med 11 840 vs 13 445, p=0.0003 — significant but OPPOSITE direction ❌** |
| H6 | Segment × product-category associated | χ² (customer level), dof 25 | **χ²=52.3, Cramér's V=0.073, p=0.002 ✅** (Holm 0.006) |
| H7 | Mobile users have lower Recency | Mann-Whitney U (two-sided) | **med 69 vs 66, p=0.43 ❌** (Holm 0.80) |
| H8 | Large-amount flag independent of channel | χ² (dof 4) | **χ²=4.04, p=0.40 ❌ — independent, as expected** |
| H2/H3/H4 | retention / email reactivation / NPS | — | untestable (no fields) |

⚠️ H8 was reframed: segments are built on the anomaly-dropped frame, so the old "anomaly rate by segment" comparison was a selection artifact, not a fraud signal.

---

## Recommendations

- **Champions (126, 6.4%):** retention rewards + referral asks.
- **At Risk (349, 17.6%):** re-engagement campaign before they slide to Hibernating — see [EXP-001].
- **Hibernating (643, 32.4%):** cheap win-back emails, don't over-invest.
- **Need Attention (410, 20.7%):** upsell to lift M, or silent churn risk.
- **Potential Loyalists (79, 4.0%):** highest AOV — upsell premium products to grow F.

---

## What's in the repo

```
rfm_analysis.py       pipeline: load → score → segment → export
generate_data.py      synthetic dataset (seed 42)
hypotheses.py         5 testable + 3 untestable checks
dashboard/app.py      Streamlit dashboard (5 tabs)
docs/                 data dictionary, SQL templates, A/B design, PRD, metrics
tests/                47 tests (pytest)
presentation/         this deck (Marp)
```

`uv sync --all-extras` · `pytest` · `streamlit run dashboard/app.py`

---

<!-- _paginate: false -->

# Thank you

Questions?

Nikita Boyarkin · MIT License

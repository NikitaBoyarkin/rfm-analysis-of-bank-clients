---
marp: true
theme: default
paginate: true
size: 16:9
header: "RFM segmentation — bank clients"
footer: "Synthetic data • seed 42 • 1 981 customers"
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
| Period | 2023-01-01 → 2024-04-01 |
| Volume | 10 000 txns → **1 981** active clients |
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
R≥3 & M≥3       → Potential Loyalists
R≤2 & F≥3       → At Risk
R≤2 & F≤2       → Hibernating
else            → Need Attention
```

---

## Results — segments

| Segment | Customers | Avg recency | Avg freq | Avg monetary | Avg RFM |
|---|---:|---:|---:|---:|---:|
| Champions | 83 | 11.2 | 8.4 | 74 641 | 12.00 |
| Loyal | 311 | 29.1 | 7.1 | 41 097 | 10.41 |
| Potential Loyalists | 208 | 29.8 | 4.3 | 49 030 | 8.85 |
| At Risk | 232 | 115.9 | 7.0 | 40 172 | 8.43 |
| Need Attention | 395 | 29.1 | 4.3 | 9 816 | 7.01 |
| Hibernating | 752 | 171.5 | 3.2 | 17 459 | 4.81 |

---

## Results — revenue concentration

Gini = **0.533** — monetary value is concentrated.

- **Champions** (4% of base) → 11% of revenue, concentration ratio **2.66**
- **Potential Loyalists** (11%) → 18% of revenue, ratio **1.75**
- **Hibernating** (38% of base) → 24% of revenue (historical), ratio **0.62** — under-indexes now
- **Need Attention** (20%) → only 7% of revenue, ratio **0.35**

→ Invest in Champions/Loyal/Potential; cheap win-back for Hibernating; don't over-spend on Need Attention.

---

## Hypotheses

| # | Hypothesis | Test | Result |
|---|---|---|---|
| H1 | Higher Monetary ↔ more distinct products | Spearman ρ | **ρ=0.50, p<0.001 ✅** |
| H5 | Mobile-bank users have higher Monetary | Mann-Whitney U | **med 16 262 vs 10 053 ✅** |
| H6 | Segment × product-category associated | χ² | χ²=14, p=0.96 ❌ (independent) |
| H7 | Mobile users have lower Recency | Mann-Whitney U | **med 59 vs 100 ✅** |
| H8 | Anomaly rate differs by segment | χ² | **χ²=68.8, p<0.001 ✅** (Hibernating 7.4%) |
| H2/H3/H4 | retention / email reactivation / NPS | — | untestable (no fields) |

---

## Recommendations

- **Champions (83):** retention rewards + referral asks.
- **At Risk (232):** re-engagement campaign before they slide to Hibernating — see [EXP-001].
- **Hibernating (752, 38%):** cheap win-back emails, don't over-invest.
- **Need Attention (395):** upsell to lift M, or silent churn risk.
- **Potential Loyalists (208):** upsell premium products to grow F.

---

## What's in the repo

```
rfm_analysis.py       pipeline: load → score → segment → export
generate_data.py      synthetic dataset (seed 42)
hypotheses.py         5 testable + 3 untestable checks
dashboard/app.py      Streamlit dashboard (5 tabs)
docs/                 data dictionary, SQL templates, A/B design, PRD, metrics
tests/                18 unit tests (pytest)
presentation/         this deck (Marp)
```

`uv sync --all-extras` · `pytest` · `streamlit run dashboard/app.py`

---

<!-- _paginate: false -->

# Thank you

Questions?

Nikita Boyarkin · MIT License

# EDA Report

**Rows:** 1983 · **Columns:** 10 · **Memory:** 0.19 MB

## Profile

| Column | dtype |
|---|---|
| customer_id | str |
| recency | int64 |
| frequency | int64 |
| monetary_value | float64 |
| R_Quartile | int64 |
| F_Quartile | int64 |
| M_Quartile | int64 |
| RFMClass | int64 |
| RFMScore | int64 |
| Segment | str |

## Data Quality

- Duplicated rows: **0**
- Constant columns: **0**
- Пропусков нет.

## Numeric Distributions

| Column | n | mean | median | std | p25 | p75 | p95 | outliers | skew |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| recency | 1983 | 93.7398 | 66.0 | 87.8626 | 27.0 | 135.5 | 281.0 | 4.1% | 1.3933 |
| frequency | 1983 | 4.7867 | 5.0 | 2.1 | 3.0 | 6.0 | 8.0 | 0.8% | 0.496 |
| monetary_value | 1983 | 14459.5479 | 13121.9 | 8447.8257 | 8065.165 | 19636.985 | 30198.171 | 1.1% | 0.8056 |
| R_Quartile | 1983 | 2.4992 | 2.0 | 1.1181 | 1.5 | 3.0 | 4.0 | 0.0% | 0.0008 |
| F_Quartile | 1983 | 2.5008 | 3.0 | 1.1181 | 2.0 | 3.5 | 4.0 | 0.0% | -0.0008 |
| M_Quartile | 1983 | 2.5008 | 3.0 | 1.1181 | 2.0 | 3.5 | 4.0 | 0.0% | -0.0008 |
| RFMClass | 1983 | 277.4327 | 244.0 | 116.881 | 177.5 | 344.0 | 444.0 | 0.0% | -0.0232 |
| RFMScore | 1983 | 7.5008 | 8.0 | 2.6661 | 5.0 | 10.0 | 12.0 | 0.0% | -0.0778 |

## Categorical Slices

**customer_id** — кардинальность 1983

| Value | Count | Share |
|---|---:|---:|
| user_1 | 1 | 0.1% |
| user_10 | 1 | 0.1% |
| user_100 | 1 | 0.1% |
| user_1000 | 1 | 0.1% |
| user_1001 | 1 | 0.1% |
| user_1002 | 1 | 0.1% |
| user_1003 | 1 | 0.1% |
| user_1004 | 1 | 0.1% |
| user_1005 | 1 | 0.1% |
| user_1006 | 1 | 0.1% |

**Segment** — кардинальность 6

| Value | Count | Share |
|---|---:|---:|
| Hibernating | 643 | 32.4% |
| Need Attention | 410 | 20.7% |
| Loyal | 376 | 19.0% |
| At Risk | 349 | 17.6% |
| Champions | 126 | 6.3% |
| Potential Loyalists | 79 | 4.0% |

## Correlations

| Pair | r | Note |
|---|---:|---|
| R_Quartile ~ RFMClass | 0.9955 | multicollinearity |
| frequency ~ F_Quartile | 0.9186 | multicollinearity |
| monetary_value ~ M_Quartile | 0.9141 | multicollinearity |
| F_Quartile ~ RFMScore | 0.8749 | multicollinearity |
| recency ~ RFMClass | -0.8639 | multicollinearity |
| recency ~ R_Quartile | -0.8586 | multicollinearity |
| frequency ~ RFMScore | 0.8455 | multicollinearity |
| M_Quartile ~ RFMScore | 0.8229 | multicollinearity |
| monetary_value ~ RFMScore | 0.791 | moderate |
| frequency ~ monetary_value | 0.7491 | moderate |
| RFMClass ~ RFMScore | 0.7485 | moderate |
| frequency ~ M_Quartile | 0.7121 | moderate |

## Metric by Segment

### Segment (overall mean = 14459.5479, gap x3.1421)

| Value | Count | Mean | Sum | Share | vs overall |
|---|---:|---:|---:|---:|---:|
| Loyal | 376 | 20692.309 | 7780308.18 | 27.1% | +43.1% |
| At Risk | 349 | 19381.5574 | 6764163.52 | 23.6% | +34.0% |
| Hibernating | 643 | 8786.7867 | 5649903.84 | 19.7% | -39.2% |
| Need Attention | 410 | 8962.9227 | 3674798.32 | 12.8% | -38.0% |
| Champions | 126 | 27608.8346 | 3478713.16 | 12.1% | +90.9% |
| Potential Loyalists | 79 | 16777.1714 | 1325396.54 | 4.6% | +16.0% |


## Findings

- **[WARN]** customer_id: кардинальность 1983 (100% строк) — похоже на ID, не группировать
- **[WARN]** R_Quartile ~ RFMClass: r=0.9955 — мультиколлинеарность или дубль признака
- **[WARN]** frequency ~ F_Quartile: r=0.9186 — мультиколлинеарность или дубль признака
- **[WARN]** monetary_value ~ M_Quartile: r=0.9141 — мультиколлинеарность или дубль признака
- **[WARN]** F_Quartile ~ RFMScore: r=0.8749 — мультиколлинеарность или дубль признака
- **[WARN]** recency ~ RFMClass: r=-0.8639 — мультиколлинеарность или дубль признака
- **[WARN]** recency ~ R_Quartile: r=-0.8586 — мультиколлинеарность или дубль признака
- **[WARN]** frequency ~ RFMScore: r=0.8455 — мультиколлинеарность или дубль признака
- **[WARN]** M_Quartile ~ RFMScore: r=0.8229 — мультиколлинеарность или дубль признака
- **[INFO]** Разрыв по Segment: x3.1421 между сегментами — кандидат в главный вывод

## What We Did Not Cover

- Причинность: корреляции не доказывают влияние.
- Внешние источники и бизнес-контекст, которых нет в датасете.
- Формальные тесты гипотез (это CDA / A-B testing).

## Reproducibility

```bash
uv run python .claude/skills/eda/scripts/eda_profile.py --input <dataset> \
    [--metric <col>] [--segments <a,b>] [--time-col <col>] [--top <n>]
```

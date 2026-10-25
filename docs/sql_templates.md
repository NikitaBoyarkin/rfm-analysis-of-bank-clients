# SQL templates

Canonical SQL equivalents of the RFM pipeline, for portfolios that store transactions in a warehouse (PostgreSQL / ClickHouse / BigQuery). The Python pipeline (`rfm_analysis.py`) computes the same thing in pandas; these templates show the SQL a product analyst would write against the raw `transactions` table.

Schema assumed (see `docs/data_dictionary.md`):

```sql
transactions(customer_id TEXT, transaction_date TIMESTAMP, amount NUMERIC,
             product_category TEXT, payment_method TEXT, is_anomaly INT)
```

---

## 1. RFM table (per-customer)

```sql
WITH snapshot AS (
  SELECT MAX(transaction_date)::date + 1 AS snap_date FROM transactions
)
SELECT
  customer_id,
  (SELECT snap_date FROM snapshot) - MAX(transaction_date)::date AS recency,
  COUNT(*)                                                   AS frequency,
  SUM(amount)                                                AS monetary_value
FROM transactions
WHERE is_anomaly = 0
GROUP BY customer_id;
```

## 2. Quartile scoring (PostgreSQL `ntile`)

```sql
WITH rfm AS ( /* query 1 */ ),
scored AS (
  SELECT
    customer_id, recency, frequency, monetary_value,
    5 - NTILE(4) OVER (ORDER BY recency)        AS r_quartile,  -- recent -> 4
    NTILE(4) OVER (ORDER BY frequency)          AS f_quartile,
    NTILE(4) OVER (ORDER BY monetary_value)     AS m_quartile
  FROM rfm
)
SELECT
  customer_id, recency, frequency, monetary_value,
  r_quartile, f_quartile, m_quartile,
  (r_quartile::text || f_quartile::text || m_quartile::text) AS rfm_class,
  r_quartile + f_quartile + m_quartile                       AS rfm_score
FROM scored;
```

> ClickHouse: replace `NTILE` with `quantilesExactExclusive` bucketing, e.g.
> `if(recency < quantile(0.25)(recency), 4, if(recency < quantile(0.5)(recency), 3, ...))`.

## 3. Named segments (combo-based)

```sql
WITH scored AS ( /* query 2 */ )
SELECT
  customer_id, r_quartile, f_quartile, m_quartile, rfm_class, rfm_score,
  CASE
    WHEN r_quartile >= 4 AND f_quartile >= 4 AND m_quartile >= 4 THEN 'Champions'
    WHEN r_quartile >= 3 AND f_quartile >= 3 AND m_quartile >= 3 THEN 'Loyal'
    WHEN r_quartile >= 3 AND f_quartile >= 2 AND m_quartile >= 3 THEN 'Potential Loyalists'
    WHEN r_quartile <= 2 AND f_quartile >= 3                    THEN 'At Risk'
    WHEN r_quartile <= 2 AND f_quartile <= 2                    THEN 'Hibernating'
    ELSE 'Need Attention'
  END AS segment
FROM scored;
```

## 4. Segment summary

```sql
WITH segmented AS ( /* query 3 */ )
SELECT
  segment,
  COUNT(*)                       AS customers,
  ROUND(AVG(recency), 2)         AS avg_recency,
  ROUND(AVG(frequency), 2)       AS avg_frequency,
  ROUND(AVG(monetary_value), 2)  AS avg_monetary,
  ROUND(AVG(rfm_score), 2)       AS avg_rfm_score
FROM segmented
GROUP BY segment
ORDER BY avg_rfm_score DESC;
```

## 5. Revenue concentration (share of customers vs share of revenue)

```sql
WITH segmented AS ( /* query 3 */ ),
seg AS (
  SELECT segment,
         COUNT(*)            AS customers,
         SUM(monetary_value) AS revenue
  FROM segmented GROUP BY segment
)
SELECT
  segment,
  customers,
  revenue,
  ROUND(customers * 100.0 / SUM(customers)  OVER (), 2) AS share_customers_pct,
  ROUND(revenue   * 100.0 / SUM(revenue)    OVER (), 2) AS share_revenue_pct,
  ROUND(revenue * 100.0 / SUM(revenue) OVER ()
        / (customers * 100.0 / SUM(customers) OVER ()), 2) AS concentration_ratio
FROM seg
ORDER BY share_revenue_pct DESC;
```

## 6. Cohort retention (monthly, by first-transaction cohort)

Requires a multi-period panel; included as the SQL template H2 would need.

```sql
WITH first_tx AS (
  SELECT customer_id, DATE_TRUNC('month', MIN(transaction_date)) AS cohort_month
  FROM transactions GROUP BY customer_id
),
active AS (
  SELECT customer_id, DATE_TRUNC('month', transaction_date) AS active_month
  FROM transactions WHERE is_anomaly = 0 GROUP BY 1, 2
)
SELECT
  cohort_month,
  active_month,
  AGE(active_month, cohort_month) AS period_number,
  COUNT(DISTINCT a.customer_id)   AS active_users
FROM active a JOIN first_tx f USING (customer_id)
GROUP BY 1, 2, 3
ORDER BY 1, 3;
```

## 7. Funnel (product adoption order)

```sql
WITH product_first AS (
  SELECT customer_id, product_category,
         MIN(transaction_date) AS first_seen
  FROM transactions WHERE is_anomaly = 0
  GROUP BY 1, 2
)
SELECT product_category,
       COUNT(*) AS users_with_product,
       RANK() OVER (ORDER BY COUNT(*) DESC) AS funnel_rank
FROM product_first
GROUP BY 1
ORDER BY funnel_rank;
```

## 8. Gini coefficient (monetary concentration)

```sql
-- PostgreSQL: cumulative shares via window functions
WITH ranked AS (
  SELECT customer_id, monetary_value,
         ROW_NUMBER() OVER (ORDER BY monetary_value)  AS rn,
         COUNT(*)     OVER ()                         AS n,
         SUM(monetary_value) OVER ()                  AS total
  FROM rfm  /* query 1 */
)
SELECT
  1 - 2 * SUM((monetary_value / total)
              * ((rn - 1) * 1.0 / n + rn * 1.0 / n) / 2) AS gini
FROM ranked;
```

## 9. Campaign exposure + reactivation readout (EXP-001)

The readout for `docs/experiment_winback.md`. Assumes two tables the campaign
platform must produce — they are **not** derivable from `transactions`:

```text
campaign_exposure(campaign_id, customer_id, variant, sent_at, delivered, channel)
campaign_optout  (campaign_id, customer_id, opted_out_at)   -- NULL = still subscribed
```

### 9.1 Assignment audit (SRM input)

```sql
SELECT variant,
       COUNT(*)                                            AS n,
       ROUND(COUNT(*)::numeric / SUM(COUNT(*)) OVER (), 4) AS observed_share
FROM campaign_exposure
WHERE campaign_id = 'EXP-001' AND delivered
GROUP BY 1
ORDER BY 1;
```

Feed `n` per arm to `scripts/ab_test_analyzer.py` — it runs the chi-squared test
against the **planned** 50/50 split, not an assumed one.

### 9.2 Per-customer readout (the analyzer's input)

```sql
WITH send AS (
  SELECT MIN(sent_at) AS send_ts
  FROM campaign_exposure
  WHERE campaign_id = 'EXP-001' AND delivered
),
arm AS (
  SELECT e.customer_id, e.variant, s.send_ts
  FROM campaign_exposure e CROSS JOIN send s
  WHERE e.campaign_id = 'EXP-001' AND e.delivered
),
react AS (
  SELECT a.customer_id,
         a.variant,
         COUNT(t.customer_id)       AS txns_30d,
         COALESCE(SUM(t.amount), 0) AS revenue_30d
  FROM arm a
  LEFT JOIN transactions t
    ON  t.customer_id      = a.customer_id
    AND t.is_anomaly       = 0
    AND t.transaction_date >  a.send_ts
    AND t.transaction_date <= a.send_ts + INTERVAL '30 days'
  GROUP BY 1, 2
),
opt AS (
  SELECT customer_id,
         MAX(CASE WHEN opted_out_at IS NOT NULL THEN 1 ELSE 0 END) AS unsubscribed
  FROM campaign_optout
  WHERE campaign_id = 'EXP-001'
  GROUP BY 1
)
SELECT r.customer_id,
       r.variant,
       CASE WHEN r.txns_30d > 0 THEN 1 ELSE 0 END          AS converted,
       r.revenue_30d,
       COALESCE(o.unsubscribed, 0)                         AS unsubscribed,
       CASE WHEN r.variant = 'test' THEN 455.00 ELSE 0 END AS offer_cost
FROM react r
LEFT JOIN opt o USING (customer_id)
ORDER BY 1;
```

`offer_cost` here is the *modelled* cashback (5% × 3 txns × 3 030 ₽ mean ticket
≈ 455 ₽). Replace it with actual cashback paid before trusting the cost guardrail.

Export the result as CSV and run:

```bash
python scripts/ab_test_analyzer.py --results data/exp001_results.csv
```

### 9.3 Guardrail roll-up

```sql
WITH readout AS ( /* query 9.2 */ )
SELECT variant,
       COUNT(*)                                               AS assigned,
       SUM(converted)                                         AS reactivated,
       ROUND(AVG(converted::numeric) * 100, 2)                AS reactivation_pct,
       SUM(unsubscribed)                                      AS optouts,
       ROUND(AVG(unsubscribed::numeric) * 100, 3)             AS unsubscribe_pct,
       SUM(offer_cost) / NULLIF(SUM(converted), 0)            AS cost_per_reactivated,
       ROUND(AVG(revenue_30d) FILTER (WHERE converted = 1), 2) AS revenue_per_reactivated
FROM readout
GROUP BY 1
ORDER BY 1;
```

---

All templates are reproducible: run `python rfm_analysis.py` to verify the pandas output matches the SQL result row-for-row against the same CSV.

# Metrics framework — RFM segments

Maps the RFM segmentation to a product metrics system using **Input → Output → Outcome** and **Leading → Lagging**. Use this to pick which metric each segment should move, and to avoid optimizing a lagging metric that you cannot act on in time.

## Segment → metric focus

| Segment | Size | Revenue share | Primary lever | Leading metric to move | Lagging metric to protect |
|---|---:|---:|---|---|---|
| Champions | 83 (4%) | 11% | Retention / referral | Referral invites sent, NPS | 90-day churn, LTV |
| Loyal | 311 (16%) | 23% | Cross-sell depth | Distinct product categories | 90-day churn |
| Potential Loyalists | 208 (11%) | 18% | Frequency lift | Txns / month | Monetary per quarter |
| At Risk | 232 (12%) | 17% | Re-engagement | Time-to-next-txn | 30-day reactivation rate |
| Need Attention | 395 (20%) | 7% | Upsell to lift M | Avg txn amount | Silent churn (no txn 60d) |
| Hibernating | 752 (38%) | 24%* | Cheap win-back | Email reactivation rate | Cost per reactivation |

*Hibernating's 24% revenue share is historical; going forward it contributes little — the concentration ratio is 0.62 (under-indexes vs customer share).

## Input → Output → Outcome

```
INPUT (what we do)            OUTPUT (what we get)         OUTCOME (business result)
─────────────────             ────────────────             ────────────────────────
Win-back emails sent  →       Reactivation rate     →      Recovered revenue
Cross-sell offers     →       Product diversity     →      Share of wallet
Referral asks         →       Referral rate         →      New-customer CAC offset
```

## Leading vs Lagging

| Type | Metric | Why | When it signals |
|---|---|---|---|
| **Leading** | Click-through on win-back email | Early intent | Day 1–3 |
| **Leading** | Time-to-next-txn (At Risk) | Reactivation momentum | Day 1–30 |
| **Leading** | Distinct categories / month (Loyal) | Cross-sell adoption | Weekly |
| **Lagging** | 30-day reactivation rate | Confirms win-back worked | Day 30+ |
| **Lagging** | 90-day churn | Confirms retention | Day 90 |
| **Lagging** | Cohort LTV | Confirms monetization | Quarter+ |

**Rule:** never run an experiment whose only success metric is lagging — you'll stop too early or too late. Pair every lagging North Star with a leading secondary.

## Dashboard tiles (maps to `dashboard/app.py`)

| Tile | Metric | Type |
|---|---|---|
| KPI card: Customers | Active base size | Context |
| KPI card: Avg RFM score | Health signal | Leading |
| KPI card: Total monetary | Outcome snapshot | Lagging |
| Segment distribution | Customer share | Context |
| Revenue concentration | share_revenue / share_customers | Outcome |
| Lorenz + Gini | Monetary inequality | Context |
| RFM scatter | Segment placement | Leading (movement over time) |

## Caveats

- All metrics here are computed on a **synthetic** dataset; absolute numbers reflect the generator, not a real bank. The *framework* (which metric per segment, leading/lagging pairing) is the reusable artifact.
- The dataset has no cohort panel, NPS, or campaign-exposure fields, so several lagging metrics (true churn, LTV curve, NPS lift) are **untestable here** — see `hypotheses.py` UNTESTABLE list. They are listed as the metrics a real deployment would track.

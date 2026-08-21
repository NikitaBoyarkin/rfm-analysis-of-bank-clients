# [EXP-001] Win-back campaign for At Risk + Hibernating

A/B experiment design for a re-engagement campaign targeting the two largest churn-risk segments. Uses the FINER framework and guardrail/north-star/secondary metric structure from the product-analyst-toolkit.

## Hypothesis

**If** we send a personalized win-back offer (cashback 5% on next 3 transactions) to At Risk and Hibernating clients, **then** 30-day reactivation rate will increase by ≥3 pp, **because** these segments have historical frequency/spend but dropped recency — a monetary nudge lowers the activation friction.

## FINER check

| Criterion | Check |
|---|---|
| **Feasible** | ✅ ~984 customers in At Risk + Hibernating; enough for a powered test (see sample size). |
| **Interesting** | ✅ These two segments are 50% of the base but only ~25% of revenue — reactivating even 3% lifts total revenue meaningfully. |
| **Novel** | ✅ No prior win-back A/B run on this segment definition. |
| **Ethical** | ✅ Cashback is a benefit, not a dark pattern; no debt-incentivizing for Hibernating low-spenders. |
| **Relevant** | ✅ Maps to OKR "Reduce inactive-customer churn by 10% Q-o-Q". |

## Metrics

| Type | Metric | Baseline | Target | Calculation |
|---|---|---|---|---|
| **Guardrail** | 30-day unsubscribe / complaint rate | 0.4% | ≤ 0.6% (not worse) | opt-outs ÷ delivered |
| **Guardrail** | Cost per reactivated customer | — | ≤ 600 RUB | offer cost ÷ reactivated |
| **North Star** | 30-day reactivation rate (≥1 txn in 30d after send) | ~6% (control est.) | ≥ 9% (+3 pp) | reactivated ÷ assigned |
| **Secondary** | Reactivated-customer monetary (30d) | — | ≥ control | sum(amount 30d) ÷ reactivated |
| **Secondary** | Product-category diversity of reactivated | — | ≥ control | distinct categories ÷ reactivated |
| **Counter** | 30-day churn of *Champions/Loyal* (unaffected) | baseline | no change | sanity that spill-over is contained |

## Design

- **Platform:** Email + push (mobile-bank app)
- **Population:** At Risk (232) + Hibernating (752) = 984 customers
- **Traffic:** 100% of eligible (984) — 50/50 split
  - Control: standard monthly newsletter (no offer)
  - Test: cashback 5% on next 3 transactions, 30-day window
- **Duration:** 30 days post-send + 14-day observation tail = 44 days
  - Account for day-of-week seasonality (start on a Tuesday)
- **Method:** Fixed-horizon (not sequential — guardrails are cheap, peeking risk low)
- **Assignment:** customer_id hash → bucket, stable across the window

## Sample size

Two-proportion z-test, α=0.05, power=0.8, baseline p=0.06, MDE=+0.03 (p=0.09).

```text
n per arm = (z_{0.975} + z_{0.8})^2 * (p1(1-p1) + p2(1-p2)) / (p2-p1)^2
         ≈  (1.96 + 0.84)^2 * (0.06*0.94 + 0.09*0.91) / 0.03^2
         ≈  7.84 * 0.1359 / 0.0009
         ≈  1 184 per arm
```

⚠️ **984 eligible < 2 368 needed.** Options:
1. **Widen the funnel** — include Need Attention (395) → 1 379 eligible, still short.
2. **Lower the bar** — relax MDE to +4 pp (p2=0.10) → n ≈ 666/arm ✅ feasible with 984.
3. **Run longer** — extend to 60-day reactivation window to lift baseline p; re-power.
4. **Accept underpowering** — ship as a pilot, treat as exploratory, pre-register the MDE.

**Recommended:** Option 2 — set MDE = +4 pp, keep 30-day window, 50/50 of 984 (492/arm, power ≈ 0.72). Accept slightly reduced power; guardrails protect downside.

## Results (template)

| Metric | Control | Test | Δ | p-value | Sig |
|---|---|---|---|---|---|
| Reactivation rate (30d) | | | | | |
| Reactivated monetary (30d) | | | | | |
| Unsubscribe rate | | | | | |
| Cost / reactivated | | | | | |

## Conclusions

_To be filled after run._

## Next steps

- [ ] Pre-register the analysis plan (MDE, metrics, decision rule)
- [ ] Build the exposure + reactivation tracking query (see `docs/sql_templates.md` §6)
- [ ] Launch pilot on Hibernating only (largest, cheapest to learn) if power is binding

## Links

- **Up:** `docs/metrics_framework.md`
- **Lateral:** `docs/prd_segment_targeting.md`
- **Data:** `docs/data_dictionary.md`

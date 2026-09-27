# [EXP-001] Win-back campaign for At Risk + Hibernating

A/B experiment design for a re-engagement campaign targeting the two largest churn-risk segments. Uses the FINER framework and guardrail/north-star/secondary metric structure from the product-analyst-toolkit.

## Hypothesis

**If** we send a personalized win-back offer (cashback 5% on next 3 transactions) to At Risk and Hibernating clients, **then** 30-day reactivation rate will increase by ≥3 pp, **because** these segments have historical frequency/spend but dropped recency — a monetary nudge lowers the activation friction.

## FINER check

| Criterion | Check |
|---|---|
| **Feasible** | ✅ 992 customers in At Risk (349) + Hibernating (643); enough for a powered test at the recommended MDE (see sample size). |
| **Interesting** | ✅ These two segments are 50% of the base (992 of 1,983) and 43.3% of revenue (At Risk 23.59% + Hibernating 19.70%) — reactivating even 3% lifts total revenue meaningfully. |
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
- **Population:** At Risk (349) + Hibernating (643) = 992 customers
- **Traffic:** 100% of eligible (992) — 50/50 split
  - Control: standard monthly newsletter (no offer)
  - Test: cashback 5% on next 3 transactions, 30-day window
- **Duration:** 30 days post-send + 14-day observation tail = 44 days
  - Account for day-of-week seasonality (start on a Tuesday)
- **Method:** Fixed-horizon (not sequential — guardrails are cheap, peeking risk low)
- **Assignment:** customer_id hash → bucket, stable across the window

## Sample size

Normal approximation for two proportions, two-sided test. Every input is stated explicitly:

| Input | Symbol | Value | Source |
|---|---|---|---|
| Control reactivation rate (30d) | p₁ | 0.06 | historical baseline estimate for At Risk + Hibernating |
| Test reactivation rate at MDE = +3 pp | p₂ | 0.09 | p₁ + 0.03 |
| Two-sided significance level | α | 0.05 | standard |
| Critical value | z₁₋α/₂ | 1.96 | normal quantile |
| Power | 1−β | 0.80 | standard |
| Power critical value | z₁₋β | 0.84 | normal quantile |
| Eligible population | N | 992 | At Risk (349) + Hibernating (643) |

**Formula** (per arm):

```text
n per arm = (z₁₋α/₂ + z₁₋β)² · [ p₁(1−p₁) + p₂(1−p₂) ] / (p₂ − p₁)²
```

**At MDE = +3 pp (p₂ = 0.09):**

```text
n = (1.96 + 0.84)² · [0.06·0.94 + 0.09·0.91] / 0.03²
  = 7.84 · [0.0564 + 0.0819] / 0.0009
  = 7.84 · 0.1383 / 0.0009
  = 1.0843 / 0.0009
  ≈ 1 205 per arm        (total 2 410)
```

⚠️ **992 eligible < 2 410 needed.** Options:
1. **Widen the funnel** — include Need Attention (410) → 1 402 eligible, still short of 2 410.
2. **Lower the bar** — relax MDE to +4 pp (p₂=0.10) → n ≈ 717/arm, total ≈ 1 434 ✅ feasible with 992 at reduced power.
3. **Run longer** — extend to a 60-day reactivation window to lift baseline p; re-power.
4. **Accept underpowering** — ship as a pilot, treat as exploratory, pre-register the MDE.

**At MDE = +4 pp (p₂ = 0.10):**

```text
n = 7.84 · [0.06·0.94 + 0.10·0.90] / 0.04²
  = 7.84 · [0.0564 + 0.0900] / 0.0016
  = 7.84 · 0.1464 / 0.0016
  = 1.1478 / 0.0016
  ≈ 717 per arm          (total ≈ 1 434; round up to 718/arm for planning)
```

**Realized power at the feasible size** (992 eligible → 496 per arm, MDE = +4 pp):

```text
power = Φ( (p₂ − p₁) / sqrt( p₁(1−p₁)/n + p₂(1−p₂)/n ) − z₁₋α/₂ )
      = Φ( 0.04 / sqrt(0.0564/496 + 0.09/496) − 1.96 )
      = Φ( 0.04 / 0.01718 − 1.96 )
      = Φ( 2.328 − 1.96 )
      = Φ( 0.368 )
      ≈ 0.64
```

**Recommended:** Option 2 — set MDE = +4 pp, keep the 30-day window, 50/50 of 992 (496/arm, **power ≈ 0.64**). Accept the reduced power; guardrails protect the downside. Under Option 2 the test is a directional pilot, not a confirmatory one — report it as such.

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

# EXP-001 — Pre-registered analysis plan

**Status:** pre-registration, v1 (2026-10-25). Frozen before launch — deviations go to the log at the end, never into the body.
**Extends:** `docs/experiment_winback.md` (design) · **Readout:** `scripts/ab_test_analyzer.py --results` · **SQL:** `docs/sql_templates.md` §9
**Audit that produced this plan:** `reports/ab_test/EXP-001_design_audit.md`

## 1. Decision taken

**Run as an exploratory pilot on the full 992 eligible customers, 50/50, with a pre-registered MDE of +5 pp.**

Why this and not the design doc's +4 pp: the doc relaxed the MDE to +4 pp to fit the population, but +4 pp is *larger* than the +3 pp the hypothesis claims, and at 496/arm it still only reaches 0.64 power. At +5 pp the required sample is 485/arm — inside the available 496 — for 0.81 power. One number, honestly powered, beats a threshold nobody believes in.

| MDE | n/arm required (p₁=0.06) | Power at 496/arm | Verdict |
|---|---|---|---|
| +3 pp (hypothesis) | 1 207 | 0.435 | not runnable at this population |
| +4 pp (design doc) | 719 | 0.644 | underpowered, and above the hypothesis |
| **+5 pp (this plan)** | **485** | **0.809** | **feasible, 80% power** |
| +6 pp | 354 | 0.913 | feasible, conservative |

**Explicit downgrade:** this test *cannot* confirm the +3 pp hypothesis. If the observed lift lands at +3–4 pp the result is "directionally positive, below pre-registered MDE" — not a confirmation. Do not report it as one.

## 2. Power is conditional on p₁, and p₁ is unverified

Every number above assumes p₁ = 0.06, which appears in the design doc as an unsourced "historical baseline estimate". Power at +5 pp moves sharply with the true baseline:

| p₁ | Power at 496/arm, +5 pp |
|---|---|
| 0.03 | 0.94 |
| 0.05 | 0.85 |
| 0.06 (assumed) | 0.81 |
| 0.10 | 0.67 |
| 0.15 | 0.55 |
| 0.25 | 0.42 |

**Pre-launch requirement:** replace 0.06 with the measured 30-day reactivation rate of At Risk + Hibernating from campaign history, and re-run `--design --sensitivity`. If the real p₁ ≥ 0.10, this plan is underpowered as written — choose then (before launch, not after) between widening the population to include Need Attention and accepting a directional-only readout. Do not silently proceed.

### 2.1 Update (2026-10-25): the measured p₁ is not usable — status BLOCKED

`scripts/ab_test_analyzer.py --baseline` (cutoff 2023-12-31, 30-day window) measured **p₁ = 0.254, 95% CI 0.228–0.282, n = 983** (At Risk 0.240, Hibernating 0.263).

This number cannot replace 0.06. It reproduces the data generator, not customer behaviour:

| Check | Result |
|---|---|
| Uniform-date model prediction `1 − (1 − 30/455)^k` | 0.271 — inside the observed CI |
| Per-customer transaction counts | mean 4.746, variance 4.566, ratio 0.96 against Poisson, overdispersion p = 0.886 |
| Monthly volume | 589–673, flat — no seasonality |
| Weekday share | 13.6–14.7% — no weekend trough |

`generate_data.py:65` draws `customer_id` independently per row, so there is no customer identity and no churn process in the data. A customer with five transactions reacts within 30 days because 5 × 30/455 ≈ 33% of their transactions fall in any 30-day window — not because anyone comes back.

**Status: §2 pre-launch check BLOCKED** — the dataset cannot supply a real control rate. p₁ remains 0.06 as an explicitly unsourced assumption, and the 0.254 is rejected as a generator artifact rather than adopted. Any readout must state that power is conditional on an unverified baseline. Unblocking requires real campaign history (exposure + conversion), which the project does not have.

## 3. Primary metric

| Field | Value |
|---|---|
| Definition | `converted = 1` iff ≥1 non-anomaly transaction in `(send_ts, send_ts + 30 days]` |
| Estimator | two-proportion z-test, pooled SE; 95% CI on the difference with unpooled SE |
| Sidedness | two-sided, α = 0.05 |
| Reported alongside | absolute diff (pp), relative lift, CI — never the p-value alone |
| Analysis population | `delivered = 1` only; assignment as randomised, no exclusions |
| Unit | customer (metric and randomisation unit coincide → no delta method needed) |

## 4. Guardrails (Holm-corrected across the two)

| Guardrail | Threshold | Failure action |
|---|---|---|
| 30-day unsubscribe / complaint rate | ≤ 0.6% (control baseline 0.4%) | primary cannot rescue it |
| Cost per reactivated customer | ≤ 600 ₽ | primary cannot rescue it |

`cost_per_reactivated` uses **actual cashback paid**, not the modelled 455 ₽ in `sql_templates.md` §9.2. A significant primary with a breached guardrail is **Investigate**, never **Ship**.

## 5. Secondary (descriptive, no decision weight)

- 30-day monetary of reactivated customers (Welch's t-test, per-customer revenue)
- Product-category diversity of reactivated customers

Both are reported with effect sizes. Neither can flip the recommendation.

## 6. Subgroups

At Risk (349) vs Hibernating (643) are reported separately, labelled **exploratory**. No per-subgroup significance claims, no subgroup-based shipping decision — neither arm has the n for it.

## 7. Pre-readout data checks (each one can block the readout)

| Check | Rule | On failure |
|---|---|---|
| SRM | chi-squared vs planned 50/50; block if p < 0.001 | investigate assignment before any metric |
| Duplicate exposure rows | one row per `customer_id` per campaign | dedupe on earliest `sent_at`, log deviation |
| Variant stability | one variant per customer across the window | exclude the customer, log count |
| Send-date spread | all sends within 7 days | re-anchor each customer's window to their own `send_ts` |
| Delivery rate | report per arm; flag if the arms differ by >2 pp | treat as SRM-adjacent, investigate |

## 8. Stopping rule

Single fixed-horizon analysis at day 44 (30-day metric window + 14-day observation tail). **No interim peeking, no early stopping on the primary metric.** The one exception: unsubscribe rate above 1.2% (2× threshold) at any point halts the campaign and is reported as such.

## 9. Decision matrix (pre-committed)

| Primary | Guardrails | Recommendation |
|---|---|---|
| p < 0.05, diff ≥ +5 pp | clean | **Ship** — roll out to segments beyond the pilot |
| p < 0.05, diff ≥ +5 pp | breached | **Investigate** — fix cost/opt-out before any roll-out |
| p < 0.05, diff < +5 pp | clean | **Below pre-registered MDE** — do not scale; run a larger test |
| p ≥ 0.05, positive | clean | **Extend or enlarge** — the pilot cannot resolve it |
| p ≥ 0.05, flat | clean | **Stop** — no detectable effect |
| p < 0.05, diff < 0 | any | **Don't ship** — revert to control, analyse why |

## 10. Reproducibility

```bash
python scripts/ab_test_analyzer.py --results data/exp001_results.csv
```

Required columns: `customer_id`, `variant` (`control`|`test`), `converted` (0/1). Optional: `revenue_30d`, `unsubscribed`, `offer_cost` — with them the analyzer adds Holm-corrected guardrails, the Welch test, and the recommendation. Data comes from `docs/sql_templates.md` §9.2.

The analyzer's SRM check uses the planned share (0.5), so a deliberately unequal rollout must pass its share explicitly rather than failing a hard-coded 50/50 test.

## 11. Deviations log

Append-only. Every change to this plan during the run is recorded here with date and reason.

| Date | Deviation | Reason |
|---|---|---|
| 2026-10-25 | §2 pre-launch check marked BLOCKED; measured p₁ = 0.254 rejected as a generator artifact (§2.1) | Synthetic data has Poisson transaction counts and uniform dates — there is no churn process to measure, so 0.06 stays an explicit assumption |

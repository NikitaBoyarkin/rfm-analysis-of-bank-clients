# [PRD] Segment-targeting field for marketing

## Problem

Marketing currently receives a flat customer list. They have no per-customer segment label, so every campaign targets "everyone" and re-derives segments ad hoc in their own queries — inconsistent definitions, duplicated work, and no way to measure segment-level lift. The RFM pipeline already computes `Segment` per customer, but it is not exposed to downstream campaign tools.

## Goal (SMART)

Expose a `rfm_segment` attribute on every customer record in the CRM export, refreshed weekly, so that ≥80% of marketing campaigns launched in the next quarter are segment-scoped and their reactivation/revenue lift is measurable per segment.

**Specific** • `rfm_segment` column on CRM export
**Measurable** • ≥80% of campaigns segment-scoped; segment-level lift reported
**Achievable** • RFM already computed; this is an ETL + export change
**Relevant** • Ties to OKR "Reduce inactive-customer churn by 10%"
**Time-bound** • Next quarter

## Success = metric

| Metric | Today | Target | Source |
|---|---|---|---|
| % campaigns segment-scoped | 0% | ≥80% | campaign registry |
| `rfm_segment` freshness | n/a | ≤7 days | export audit |
| Segment-level lift reported | 0 | ≥1 per quarter | experiment reports |

## Solution

1. **Weekly ETL step** — after `rfm_analysis.py` writes `rfm_output.csv`, join `customer_id → Segment` into the CRM customer table (`UPDATE customers SET rfm_segment = ...`).
2. **CRM export** — add `rfm_segment` as a selectable attribute in the campaign-builder UI and the flat CSV export.
3. **Segment dictionary** — ship the 6-segment definitions (see `docs/data_dictionary.md`) into the campaign tool's tooltip/help.
4. **Guardrail** — `rfm_segment` must never be blank for active customers; backfill Hibernating as default for missing IDs.

## Out of scope

- Real-time segment updates (weekly cadence is enough for retention campaigns).
- Adding new segments beyond the 6 defined.
- NPS / satisfaction integration (separate PRD).

## Risks & mitigations

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Segment drift between weekly refreshes | Med | Low | Document refresh cadence; campaigns read at send time |
| Marketing over-targets Champions (burnout) | Med | Med | Add a per-segment contact-frequency cap in the campaign tool |
| CRM join misses new customers (no txn history) | Low | Low | Default new IDs to "Need Attention" until first RFM run |
| Wrong segment drives wrong offer (e.g. cashback to Champions) | Low | High | UI warning when offer ≠ recommended action for segment |

## A/B test

See `docs/experiment_winback.md` — [EXP-001] is the first campaign that consumes `rfm_segment`.

## Links

- **Up:** `docs/metrics_framework.md`
- **Lateral:** `docs/experiment_winback.md`
- **Data:** `docs/data_dictionary.md`

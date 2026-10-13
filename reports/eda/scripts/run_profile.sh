#!/usr/bin/env bash
# Reproducible profiling command for rfm-bank EDA (Phase 1).
# Run from the project root: bash reports/eda/scripts/run_profile.sh
set -euo pipefail

EDA="/Users/nikitaboarkin/Desktop/00 ide/00 portfolio/.eda-tools/.venv/bin/python"
PROF="/Users/nikitaboarkin/Desktop/00 obsidian/obsidian/.claude/skills/eda/scripts/eda_profile.py"

cd "$(dirname "$0")/../../.."   # -> rfm-analysis-of-bank-clients/

# Primary dataset: transaction grain (raw, includes the is_anomaly label).
"$EDA" "$PROF" \
  --input data/bank_rfm_dataset_10k_fixed.csv \
  --metric amount \
  --segments product_category,payment_method \
  --time-col transaction_date \
  --out reports/eda/scripts/profile_transactions.md

# Derived dataset: client grain (RFM output).
"$EDA" "$PROF" \
  --input data/rfm_output.csv \
  --metric monetary_value \
  --segments Segment \
  --out reports/eda/scripts/profile_rfm_output.md

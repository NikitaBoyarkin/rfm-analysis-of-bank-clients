# Dashboard

Interactive Streamlit dashboard over the RFM output.

## Run

```bash
# 1. Make sure the pipeline output exists
python rfm_analysis.py

# 2. Launch the dashboard
streamlit run dashboard/app.py
```

## What it shows

| Tab | Content |
|---|---|
| **Overview** | KPI cards (customers, segments, avg RFM, total monetary) + segment distribution bar + revenue concentration table |
| **Segments** | Per-segment summary table + monetary boxplot (log scale) |
| **RFM map** | Recency × Frequency scatter, colored by segment, sized by monetary |
| **Concentration** | Lorenz curve + Gini coefficient, top-20% revenue share |
| **Raw** | Filterable customer-level RFM table |

## Filters (sidebar)

- **Segment** multiselect
- **Recency** range slider (days)
- **Monetary value** range slider

All charts react to the filters live.

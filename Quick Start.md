## Quick Start

```bash
# 1. Environment
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,dashboard]"    # or: uv sync --all-extras

# 2. Generate the synthetic dataset
python generate_data.py

# 3. Run the RFM pipeline (CSV + Excel + charts)
python rfm_analysis.py

# 4. Run the testable hypotheses
python hypotheses.py
```

Outputs land in `data/` (CSV, Excel) and `images/` (PNG charts).

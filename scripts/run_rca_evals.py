"""CLI entry point for the offline RCA evaluation runner.

Usage::

    python scripts/run_rca_evals.py
    python scripts/run_rca_evals.py --provider mistral --model mistral-large-latest
    python scripts/run_rca_evals.py --dataset data/rca_eval/v1 --output reports/
    python scripts/run_rca_evals.py --quiet
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.evals.rca_eval_runner import main  # noqa: E402

if __name__ == "__main__":
    main()

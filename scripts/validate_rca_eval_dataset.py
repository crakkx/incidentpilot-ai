import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.evals.rca_dataset import (  # noqa: E402
    load_rca_eval_dataset,
)


DATASET_ROOT = (
    PROJECT_ROOT
    / "data"
    / "rca_eval"
    / "v1"
)


def main() -> None:
    manifest, cases = load_rca_eval_dataset(
        DATASET_ROOT
    )

    scenario_counts = Counter(
        case.scenario_type
        for case in cases
    )

    difficulty_counts = Counter(
        case.difficulty
        for case in cases
    )

    print("RCA evaluation dataset is valid.")
    print(
        f"Dataset: {manifest.dataset_id}"
    )
    print(
        f"Version: {manifest.dataset_version}"
    )
    print(f"Cases: {len(cases)}")

    print("\nScenario types:")

    for key, value in sorted(
        scenario_counts.items()
    ):
        print(f"- {key}: {value}")

    print("\nDifficulty:")

    for key, value in sorted(
        difficulty_counts.items()
    ):
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
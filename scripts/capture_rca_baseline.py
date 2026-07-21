import argparse
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from app.llm.prompts import RCA_SYSTEM_PROMPT
from app.schemas.analysis import RCAReport


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, default=str),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture the current IncidentPilot RCA baseline."
    )
    parser.add_argument(
        "--release",
        required=True,
        help="Release identifier such as v0.1.0.",
    )
    args = parser.parse_args()

    output_dir = (
        PROJECT_ROOT
        / "reports"
        / "baselines"
        / args.release
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    demo_report_path = (
        PROJECT_ROOT / "reports" / "demo_rca.json"
    )

    if not demo_report_path.exists():
        raise RuntimeError(
            "reports/demo_rca.json does not exist. "
            "Run `make demo` before capturing the baseline."
        )

    configuration = {
        "model": settings.ollama_model,
        "ollama_num_ctx": settings.ollama_num_ctx,
        "ollama_num_predict": settings.ollama_num_predict,
        "ollama_temperature": settings.ollama_temperature,
        "ollama_seed": settings.ollama_seed,
        "embedding_model": settings.embedding_model_name,
        "embedding_dimensions": settings.embedding_dimensions,
        "rca_max_logs": settings.rca_max_logs,
        "rca_max_metrics": settings.rca_max_metrics,
        "rca_max_deployments": settings.rca_max_deployments,
        "rca_runbook_top_k": settings.rca_runbook_top_k,
    }

    metadata = {
        "release": args.release,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": os.getenv("GIT_COMMIT", "unknown"),
    }

    write_json(
        output_dir / "metadata.json",
        metadata,
    )
    write_json(
        output_dir / "generation_config.json",
        configuration,
    )
    write_json(
        output_dir / "rca_schema.json",
        RCAReport.model_json_schema(),
    )

    (output_dir / "prompt.txt").write_text(
        RCA_SYSTEM_PROMPT + "\n",
        encoding="utf-8",
    )

    shutil.copyfile(
        demo_report_path,
        output_dir / "demo_rca.json",
    )

    print(f"Baseline captured at: {output_dir}")


if __name__ == "__main__":
    main()
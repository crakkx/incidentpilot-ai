import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

BASELINE_TAG = "v0.1.0"
ARTIFACT_FORMAT_VERSION = "baseline-artifacts/1.0.0"

# Existing location created during the earlier implementation.
LEGACY_BASELINE_DIR = (
    PROJECT_ROOT
    / "reports"
    / "baselines"
    / BASELINE_TAG
)

# Canonical long-term location.
BASELINE_DIR = (
    PROJECT_ROOT
    / "baselines"
    / BASELINE_TAG
)

# Map existing artifact names to canonical names.
ARTIFACT_FILE_MAP = {
    "demo_rca.json": "rca_output.json",
    "generation_config.json": "generation_config.json",
    "prompt.txt": "prompt.txt",
    "metadata.json": "metadata.json",
    "rca_schema.json": "rca_schema.json",
}

OPTIONAL_RETRIEVAL_REPORT = (
    PROJECT_ROOT
    / "reports"
    / "retrieval_eval_latest.json"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file_handle:
        for block in iter(
            lambda: file_handle.read(65536),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def read_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON file: {path}\n{exc}"
        ) from exc


def write_json(
    path: Path,
    value: Any,
) -> None:
    path.write_text(
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )


def git_output(*args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        error_message = (
            exc.stderr.strip()
            or exc.stdout.strip()
            or str(exc)
        )

        raise RuntimeError(
            f"Git command failed: git {' '.join(args)}\n"
            f"{error_message}"
        ) from exc

    return completed.stdout.strip()


def copy_artifact(
    source: Path,
    destination: Path,
    *,
    force: bool,
) -> None:
    if not source.exists():
        raise FileNotFoundError(
            f"Required baseline artifact not found: {source}"
        )

    if destination.exists():
        source_hash = sha256_file(source)
        destination_hash = sha256_file(destination)

        if source_hash == destination_hash:
            print(
                f"Already up to date: "
                f"{destination.relative_to(PROJECT_ROOT)}"
            )
            return

        if not force:
            raise FileExistsError(
                "A different baseline artifact already exists:\n"
                f"  {destination}\n\n"
                "Baseline files are immutable by default. "
                "Inspect the difference first. Use --force only "
                "when you are certain the existing baseline is wrong."
            )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copy2(
        source,
        destination,
    )

    print(
        f"Copied: "
        f"{source.relative_to(PROJECT_ROOT)}"
        " -> "
        f"{destination.relative_to(PROJECT_ROOT)}"
    )


def validate_baseline_files() -> None:
    required_files = [
        BASELINE_DIR / "rca_output.json",
        BASELINE_DIR / "generation_config.json",
        BASELINE_DIR / "prompt.txt",
        BASELINE_DIR / "metadata.json",
        BASELINE_DIR / "rca_schema.json",
    ]

    missing_files = [
        path
        for path in required_files
        if not path.exists()
    ]

    if missing_files:
        formatted = "\n".join(
            f"- {path}"
            for path in missing_files
        )

        raise FileNotFoundError(
            "The baseline is incomplete:\n"
            f"{formatted}"
        )

    rca_output = read_json(
        BASELINE_DIR / "rca_output.json"
    )

    # The saved file may be the complete endpoint response.
    # When it includes status, it must be completed.
    if isinstance(rca_output, dict):
        status = rca_output.get("status")

        if (
            status is not None
            and status != "completed"
        ):
            raise ValueError(
                "The frozen RCA output must represent a "
                f"completed run. Found status={status!r}."
            )

    generation_config = read_json(
        BASELINE_DIR / "generation_config.json"
    )

    if not isinstance(generation_config, dict):
        raise ValueError(
            "generation_config.json must contain "
            "a JSON object."
        )

    metadata = read_json(
        BASELINE_DIR / "metadata.json"
    )

    if not isinstance(metadata, dict):
        raise ValueError(
            "metadata.json must contain a JSON object."
        )

    schema = read_json(
        BASELINE_DIR / "rca_schema.json"
    )

    if not isinstance(schema, dict):
        raise ValueError(
            "rca_schema.json must contain a JSON object."
        )

    prompt_text = (
        BASELINE_DIR / "prompt.txt"
    ).read_text(
        encoding="utf-8"
    ).strip()

    if not prompt_text:
        raise ValueError(
            "prompt.txt cannot be empty."
        )


def build_manifest() -> dict[str, Any]:
    tag_commit = git_output(
        "rev-parse",
        f"{BASELINE_TAG}^{{}}",
    )

    artifact_paths = sorted(
        path
        for path in BASELINE_DIR.iterdir()
        if (
            path.is_file()
            and path.name != "manifest.json"
        )
    )

    return {
        "artifact_format_version": (
            ARTIFACT_FORMAT_VERSION
        ),
        "baseline_tag": BASELINE_TAG,
        "git_commit": tag_commit,
        "captured_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "description": (
            "First working end-to-end local RCA baseline "
            "before claim-grounding and RCA evaluation changes."
        ),
        "source_directory": str(
            LEGACY_BASELINE_DIR.relative_to(
                PROJECT_ROOT
            )
        ),
        "files": {
            path.name: {
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
            for path in artifact_paths
        },
    }


def migrate_existing_baseline(
    *,
    force: bool,
) -> None:
    if not LEGACY_BASELINE_DIR.exists():
        print(
            "Legacy baseline directory was not found. "
            "Checking the canonical baseline directory instead."
        )
        return

    BASELINE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    for source_name, destination_name in (
        ARTIFACT_FILE_MAP.items()
    ):
        copy_artifact(
            LEGACY_BASELINE_DIR / source_name,
            BASELINE_DIR / destination_name,
            force=force,
        )


def copy_optional_retrieval_report(
    *,
    force: bool,
) -> None:
    if not OPTIONAL_RETRIEVAL_REPORT.exists():
        print(
            "Optional retrieval evaluation report was not found. "
            "Skipping retrieval_eval.json."
        )
        return

    copy_artifact(
        OPTIONAL_RETRIEVAL_REPORT,
        BASELINE_DIR / "retrieval_eval.json",
        force=force,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Migrate and finalize immutable v0.1.0 "
            "baseline artifacts."
        )
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Overwrite different files already present in "
            "baselines/v0.1.0. Use cautiously."
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Ensure the release tag exists before writing a manifest.
    git_output(
        "rev-parse",
        f"{BASELINE_TAG}^{{}}",
    )

    migrate_existing_baseline(
        force=args.force,
    )

    copy_optional_retrieval_report(
        force=args.force,
    )

    validate_baseline_files()

    manifest = build_manifest()

    manifest_path = (
        BASELINE_DIR / "manifest.json"
    )

    write_json(
        manifest_path,
        manifest,
    )

    print()
    print("Baseline migration completed.")
    print(
        f"Location: "
        f"{BASELINE_DIR.relative_to(PROJECT_ROOT)}"
    )
    print()

    for path in sorted(
        BASELINE_DIR.iterdir()
    ):
        if path.is_file():
            print(
                f"- {path.name} "
                f"({path.stat().st_size} bytes)"
            )

    print()
    print(
        "The original files remain under reports/ "
        "until you verify and remove them manually."
    )


if __name__ == "__main__":
    main()

"""Fail-closed recovery planning backed by SHA-256 output manifests.

This module never starts jobs. Manifest evidence is checked at planning time;
operators must still validate lineage, inputs, locks, and idempotency.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.output_manifest import ManifestError, verify
from src.pipeline_monitor import summarize_events
from src.pipeline_recovery import RecoveryNotSafe, plan_recovery


def plan_manifest_gated_recovery(
    summary: dict,
    run_id: str,
    stage_artifacts: dict[int, tuple[str | Path, str | Path]],
) -> dict:
    """Require matching artifacts for every upstream stage that would be skipped.

    stage_artifacts maps a one-based stage number to (output_directory,
    manifest_json_path). Manifests must be stored outside their output tree.
    """
    if not isinstance(stage_artifacts, dict):
        raise ValueError("stage_artifacts must be a stage-number mapping")
    # First determine the boundary without claiming any artifacts are verified.
    initial = plan_recovery(summary, run_id)
    if initial["action"] == "none":
        return initial

    verified = []
    for stage in initial["skipped_stages"]:
        if stage not in stage_artifacts:
            raise RecoveryNotSafe(f"Missing output manifest for stage {stage}")
        pair = stage_artifacts[stage]
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise RecoveryNotSafe(f"Invalid output/manifest pair for stage {stage}")
        output_dir, manifest_path = map(Path, pair)
        if output_dir.is_symlink() or manifest_path.is_symlink():
            raise RecoveryNotSafe(f"Symlink in stage {stage} evidence")
        try:
            with manifest_path.open("r", encoding="utf-8") as handle:
                manifest = json.load(handle)
            if not verify(output_dir, manifest):
                raise RecoveryNotSafe(f"Output manifest mismatch at stage {stage}")
        except (OSError, ValueError, TypeError, ManifestError) as exc:
            raise RecoveryNotSafe(f"Cannot verify stage {stage}: {exc}") from exc
        verified.append(stage)

    return plan_recovery(summary, run_id, verified_stage_outputs=verified)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-stages", type=int, default=2)
    parser.add_argument(
        "--stage-artifact", nargs=3, action="append", metavar=("STAGE", "OUTPUT_DIR", "MANIFEST"),
        default=[], help="Repeat for each upstream stage to be skipped",
    )
    args = parser.parse_args()
    artifacts = {}
    try:
        for stage_text, output, manifest in args.stage_artifact:
            stage = int(stage_text)
            if stage < 1 or stage in artifacts:
                raise ValueError("Stage identifiers must be unique positive integers")
            artifacts[stage] = (output, manifest)
        summary = summarize_events(args.events, expected_stages=args.expected_stages)
        result = plan_manifest_gated_recovery(summary, args.run_id, artifacts)
    except (OSError, ValueError, RecoveryNotSafe) as exc:
        parser.exit(2, f"Recovery planning refused: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

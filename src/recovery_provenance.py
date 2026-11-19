"""Fail-closed, run-bound provenance checks for manual recovery plans.

SHA-256 checks detect accidental changes, not malicious edits by someone who
can rewrite both manifests and evidence. No automatic job execution occurs.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

from src.manifest_recovery import plan_manifest_gated_recovery
from src.output_manifest import ManifestError, verify
from src.pipeline_recovery import RecoveryNotSafe


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record_evidence(
    *, run_id: str, stage: int, output_dir: str | Path,
    output_manifest: str | Path, input_dir: str | Path,
    input_manifest: str | Path, created_at: datetime | None = None,
) -> dict:
    """Capture immutable *values* for a stage after its successful completion.

    Store the returned JSON outside all input/output directories. The caller
    is responsible for binding it to a trusted run record.
    """
    if not isinstance(run_id, str) or not run_id.strip() or type(stage) is not int or stage < 1:
        raise ValueError("run_id and positive integer stage are required")
    timestamp = created_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("created_at must be timezone-aware")
    for root, manifest in ((input_dir, input_manifest), (output_dir, output_manifest)):
        root, manifest = Path(root), Path(manifest)
        if manifest.is_symlink():
            raise RecoveryNotSafe("Manifest symlinks are not trusted")
        try:
            with manifest.open("r", encoding="utf-8") as stream:
                value = json.load(stream)
            if not verify(root, value):
                raise RecoveryNotSafe("Artifact tree does not match manifest")
        except (OSError, ValueError, TypeError, ManifestError) as exc:
            raise RecoveryNotSafe(f"Cannot verify evidence: {exc}") from exc
    return {
        "schema_version": 1,
        "run_id": run_id,
        "stage": stage,
        "created_at_utc": timestamp.astimezone(timezone.utc).isoformat(),
        "input_manifest_sha256": _sha256(Path(input_manifest)),
        "output_manifest_sha256": _sha256(Path(output_manifest)),
    }


def plan_with_provenance(
    summary: dict, run_id: str, stage_artifacts: dict,
    evidence: dict, *, max_age_seconds: int = 86400,
    now: datetime | None = None,
) -> dict:
    """Gate skipped stages on run identity, input/output hashes and age.

    stage_artifacts maps stage numbers to (output_dir, output_manifest,
    input_dir, input_manifest). evidence maps stage numbers to records
    returned by record_evidence. Fail closed on any missing evidence.
    """
    if type(max_age_seconds) is not int or max_age_seconds <= 0:
        raise ValueError("max_age_seconds must be a positive integer")
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None or clock.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    clock = clock.astimezone(timezone.utc)
    plan = plan_manifest_gated_recovery(
        summary, run_id,
        {stage: (items[0], items[1]) for stage, items in stage_artifacts.items()
         if isinstance(items, (tuple, list)) and len(items) == 4},
    )
    if plan["action"] == "none":
        return plan
    for stage in plan["skipped_stages"]:
        if stage not in stage_artifacts or stage not in evidence:
            raise RecoveryNotSafe(f"Missing provenance for skipped stage {stage}")
        paths = stage_artifacts[stage]
        if not isinstance(paths, (tuple, list)) or len(paths) != 4:
            raise RecoveryNotSafe(f"Invalid artifact paths for stage {stage}")
        record = evidence[stage]
        if not isinstance(record, dict) or record.get("schema_version") != 1:
            raise RecoveryNotSafe(f"Invalid provenance schema for stage {stage}")
        if record.get("run_id") != run_id or type(record.get("stage")) is not int or record["stage"] != stage:
            raise RecoveryNotSafe(f"Run/stage mismatch for stage {stage}")
        try:
            stamp = datetime.fromisoformat(record["created_at_utc"])
            if stamp.tzinfo is None or stamp.utcoffset() is None:
                raise ValueError("naive timestamp")
            age = clock - stamp.astimezone(timezone.utc)
            if age < timedelta(0) or age > timedelta(seconds=max_age_seconds):
                raise RecoveryNotSafe(f"Expired or future-dated provenance for stage {stage}")
            for key, path in (
                ("output_manifest_sha256", paths[1]),
                ("input_manifest_sha256", paths[3]),
            ):
                file = Path(path)
                if file.is_symlink() or _sha256(file) != record.get(key):
                    raise RecoveryNotSafe(f"Manifest provenance mismatch at stage {stage}")
            with Path(paths[3]).open("r", encoding="utf-8") as stream:
                if not verify(paths[2], json.load(stream)):
                    raise RecoveryNotSafe(f"Input tree changed at stage {stage}")
        except (OSError, KeyError, TypeError, ValueError, ManifestError) as exc:
            raise RecoveryNotSafe(f"Cannot validate provenance for stage {stage}: {exc}") from exc
    return {**plan, "provenance_verified_stages": list(plan["skipped_stages"])}

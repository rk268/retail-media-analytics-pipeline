"""Verifiable local output manifests for manual pipeline recovery.

Only regular files inside a resolved output directory are inventoried. Manifests
are evidence of byte-level stability, not proof of semantic correctness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile


class ManifestError(ValueError):
    """Unsafe or inconsistent output snapshot."""


def _files(root: Path) -> list[Path]:
    if not root.is_dir() or root.is_symlink():
        raise ManifestError("Output root must be a real directory")
    result = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in dirs + files:
            if (base / name).is_symlink():
                raise ManifestError("Symlink encountered in output tree")
        for name in files:
            path = base / name
            if not path.is_file():
                raise ManifestError("Nonregular output entry")
            result.append(path)
    return sorted(result, key=lambda p: p.relative_to(root).as_posix())


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot(root: str | Path) -> dict:
    """Hash every file in a local output tree; reject empty snapshots."""
    root = Path(root).absolute()
    entries = []
    for path in _files(root):
        before = path.stat()
        digest = _digest(path)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ManifestError("Output changed while being hashed")
        entries.append({
            "path": path.relative_to(root).as_posix(),
            "bytes": after.st_size,
            "sha256": digest,
        })
    if not entries:
        raise ManifestError("Cannot certify an empty output directory")
    return {"schema_version": 1, "algorithm": "sha256", "files": entries}


def verify(root: str | Path, manifest: dict) -> bool:
    """Return True only when file names, lengths and digests all match."""
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ManifestError("Unsupported manifest version")
    if manifest.get("algorithm") != "sha256" or not isinstance(manifest.get("files"), list):
        raise ManifestError("Invalid manifest format")
    expected = manifest["files"]
    names = [item.get("path") for item in expected if isinstance(item, dict)]
    if len(names) != len(expected) or len(names) != len(set(names)):
        raise ManifestError("Malformed or duplicate manifest entries")
    return snapshot(root) == manifest


def write_manifest(root: str | Path, destination: str | Path) -> dict:
    """Atomically publish a snapshot outside the output tree."""
    root = Path(root).resolve()
    destination = Path(destination).absolute()
    if destination == root or root in destination.parents:
        raise ManifestError("Manifest destination must be outside the output tree")
    manifest = snapshot(root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=destination.parent,
            prefix=".manifest-", suffix=".tmp", delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(manifest, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir")
    parser.add_argument("manifest_json")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        with open(args.manifest_json, encoding="utf-8") as stream:
            manifest = json.load(stream)
        if not verify(args.output_dir, manifest):
            parser.exit(1, "Output does not match manifest\n")
        print("Output matches manifest")
    else:
        result = write_manifest(args.output_dir, args.manifest_json)
        print(f"Recorded {len(result['files'])} files")


if __name__ == "__main__":
    main()

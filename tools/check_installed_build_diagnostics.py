from __future__ import annotations

import argparse
import json
from pathlib import Path
from zipfile import ZipFile

import geoworkbench
from geoworkbench import __version__
from geoworkbench.services.application_logging import ApplicationLogManager
from geoworkbench.services.build_identity import resolve_build_identity


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate diagnostics from a wheel-installed build outside a Git checkout."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-commit", required=True)
    return parser.parse_args()


def _has_git_ancestor(path: Path) -> bool:
    current = path if path.is_dir() else path.parent
    return any((directory / ".git").exists() for directory in (current, *current.parents))


def main() -> int:
    args = _parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    package_file = Path(geoworkbench.__file__).resolve()
    if _has_git_ancestor(package_file):
        raise RuntimeError(
            "Installed-build acceptance must run from a package outside every Git checkout"
        )

    expected_commit = str(args.expected_commit).strip().lower()
    artifact_identity = resolve_build_identity(
        __version__,
        environ={},
        checkout_start=package_file,
    )
    if artifact_identity.commit != expected_commit:
        raise RuntimeError(
            "Installed wheel did not preserve the expected stamped build commit"
        )
    if artifact_identity.source != "package-build-info":
        raise RuntimeError(
            f"Unexpected installed build identity source: {artifact_identity.source}"
        )

    log_directory = output_dir / "logs"
    bundle_path = output_dir / "installed-diagnostics.zip"
    manager = ApplicationLogManager(
        log_directory,
        application_version=__version__,
        build_identity=artifact_identity,
        session_id="installed-build-acceptance",
    )
    try:
        manager.build_diagnostic_bundle(
            bundle_path,
            runtime_context={"installed_build_acceptance": True},
        )
    finally:
        manager.close()

    with ZipFile(bundle_path, "r") as archive:
        report = json.loads(archive.read("system-report.json").decode("utf-8"))

    expected_report = {
        "application_version": __version__,
        "application_commit": expected_commit,
        "build_identity": artifact_identity.display,
        "build_identity_source": "package-build-info",
        "session_id": "installed-build-acceptance",
    }
    for key, expected in expected_report.items():
        if report.get(key) != expected:
            raise RuntimeError(
                f"Installed diagnostics mismatch for {key}: "
                f"expected {expected!r}, got {report.get(key)!r}"
            )
    if report.get("runtime_context") != {"installed_build_acceptance": True}:
        raise RuntimeError("Installed diagnostics runtime context was not preserved")

    summary = {
        "package_file": str(package_file),
        "version": __version__,
        "commit": artifact_identity.commit,
        "identity_source": artifact_identity.source,
        "bundle": str(bundle_path),
    }
    (output_dir / "installed-build-acceptance.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

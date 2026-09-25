from __future__ import annotations

from pathlib import Path

import geoworkbench.services.build_identity as build_identity_module
from geoworkbench.services.build_identity import BuildIdentity, resolve_build_identity


_MISSING_DISTRIBUTION = "geolog-gasratio-pixler-test-missing"


def test_build_identity_prefers_explicit_build_environment(tmp_path: Path) -> None:
    commit = "A" * 40

    identity = resolve_build_identity(
        "0.7.96-test",
        environ={"GEOLOG_BUILD_COMMIT": commit},
        distribution_name=_MISSING_DISTRIBUTION,
        checkout_start=tmp_path / "installed" / "module.py",
    )

    assert identity == BuildIdentity(
        version="0.7.96-test",
        commit=commit.lower(),
        source="environment:GEOLOG_BUILD_COMMIT",
    )
    assert identity.display == f"0.7.96-test+{commit[:12].lower()}"


def test_build_identity_prefers_stamped_package_artifact(
    tmp_path: Path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    commit = "abcdef1234567890abcdef1234567890abcdef12"
    (tmp_path / "_build_identity.json").write_text(
        '{"schema_version":1,"commit":"' + commit + '"}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(build_identity_module.resources, "files", lambda _package: tmp_path)

    identity = resolve_build_identity(
        "0.7.96-test",
        environ={},
        distribution_name=_MISSING_DISTRIBUTION,
        checkout_start=tmp_path / "installed" / "module.py",
    )

    assert identity == BuildIdentity(
        version="0.7.96-test",
        commit=commit,
        source="package-build-info",
    )


def test_build_identity_reads_checkout_head_without_invoking_git(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    git_directory = repository / ".git"
    ref = git_directory / "refs" / "heads" / "main"
    ref.parent.mkdir(parents=True)
    commit = "1234567890abcdef1234567890abcdef12345678"
    (git_directory / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    ref.write_text(commit + "\n", encoding="utf-8")

    identity = resolve_build_identity(
        "0.7.96-test",
        environ={},
        distribution_name=_MISSING_DISTRIBUTION,
        checkout_start=repository / "src" / "geoworkbench" / "module.py",
    )

    assert identity.commit == commit
    assert identity.source == "git-checkout"


def test_installed_build_without_metadata_or_git_is_explicitly_unknown(
    tmp_path: Path,
) -> None:
    identity = resolve_build_identity(
        "0.7.96-test",
        environ={},
        distribution_name=_MISSING_DISTRIBUTION,
        checkout_start=tmp_path / "site-packages" / "geoworkbench" / "module.py",
    )

    assert identity.commit == "unknown"
    assert identity.source == "unknown"
    assert identity.display == "0.7.96-test+unknown"


def test_same_package_version_with_different_commits_has_distinct_build_identity() -> None:
    first = BuildIdentity("0.7.96", "a" * 40, "test")
    second = BuildIdentity("0.7.96", "b" * 40, "test")

    assert first.display != second.display
    assert first.as_dict()["version"] == second.as_dict()["version"]
    assert first.as_dict()["commit"] != second.as_dict()["commit"]


def test_release_gate_verifies_stamped_wheel_outside_source_checkout() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "release-gate.yml").read_text(
        encoding="utf-8"
    )
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")

    assert "tools/stamp_build_identity.py" in workflow
    assert "tools/check_installed_build_diagnostics.py" in workflow
    assert "build --wheel --no-isolation" in workflow
    assert "RUNNER_TEMP" in workflow
    assert "_build_identity.json" in pyproject

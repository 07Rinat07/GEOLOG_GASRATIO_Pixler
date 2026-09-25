from __future__ import annotations

from pathlib import Path

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

"""Validate multilingual documentation and localization contracts.

The checker intentionally has no Qt dependencies, so it can run in a minimal
CI or packaging environment before the desktop stack is installed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

LANGUAGES = ("ru", "kk", "en")
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)
PACKAGE_VERSION_RE = re.compile(r'^__version__\s*=\s*"([^"]+)"', re.MULTILINE)


@dataclass(frozen=True)
class AuditIssue:
    """One actionable documentation audit failure."""

    category: str
    message: str


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def localized_markdown_sets(root: Path) -> dict[str, set[str]]:
    """Return the localized Markdown filenames for every supported language."""

    return {
        language: {path.name for path in (root / "docs" / language).glob("*.md")}
        for language in LANGUAGES
    }


def audit_localized_file_parity(root: Path) -> list[AuditIssue]:
    """Require exactly the same user-document set in RU, KK, and EN."""

    issues: list[AuditIssue] = []
    file_sets = localized_markdown_sets(root)
    union = set().union(*file_sets.values())
    for filename in sorted(union):
        missing = [language for language, names in file_sets.items() if filename not in names]
        if missing:
            issues.append(
                AuditIssue(
                    "localized-files",
                    f"{filename} is missing in: {', '.join(missing)}",
                )
            )
    return issues



def audit_localized_document_structure(root: Path) -> list[AuditIssue]:
    """Detect materially incomplete current guides while allowing historical note variance."""

    issues: list[AuditIssue] = []
    file_sets = localized_markdown_sets(root)
    common = set.intersection(*file_sets.values())
    for filename in sorted(common):
        if filename.startswith("RELEASE_NOTES_"):
            continue

        texts = {
            language: _read_text(root / "docs" / language / filename)
            for language in LANGUAGES
        }
        for language, text in texts.items():
            if not text.lstrip().startswith("#"):
                issues.append(
                    AuditIssue(
                        "localized-structure",
                        f"docs/{language}/{filename} has no Markdown heading",
                    )
                )
            if len(text.strip()) < 200:
                issues.append(
                    AuditIssue(
                        "localized-structure",
                        f"docs/{language}/{filename} is unexpectedly short",
                    )
                )

        heading_counts = {
            language: len(re.findall(r"^#{1,6}\s+", text, re.MULTILINE))
            for language, text in texts.items()
        }
        if max(heading_counts.values()) - min(heading_counts.values()) > 2:
            issues.append(
                AuditIssue(
                    "localized-structure",
                    f"{filename} heading counts diverge: {heading_counts}",
                )
            )

        lengths = {language: len(text) for language, text in texts.items()}
        if min(lengths.values()) < max(lengths.values()) * 0.65:
            issues.append(
                AuditIssue(
                    "localized-structure",
                    f"{filename} content lengths diverge: {lengths}",
                )
            )
    return issues

def _iter_local_markdown_links(path: Path) -> list[str]:
    targets: list[str] = []
    for raw_target in MARKDOWN_LINK_RE.findall(_read_text(path)):
        target = raw_target.split("#", 1)[0].strip()
        if not target or "://" in target or target.startswith("mailto:"):
            continue
        targets.append(target)
    return targets


def audit_markdown_links(root: Path) -> list[AuditIssue]:
    """Check relative links in the root README and every file under docs/."""

    issues: list[AuditIssue] = []
    markdown_files = [root / "README.md", *sorted((root / "docs").rglob("*.md"))]
    for path in markdown_files:
        for target in _iter_local_markdown_links(path):
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                issues.append(
                    AuditIssue(
                        "markdown-link",
                        f"{path.relative_to(root)} -> {target} does not exist",
                    )
                )
    return issues


def audit_i18n_key_parity(root: Path) -> list[AuditIssue]:
    """Require the same stable translation keys in all interface catalogs."""

    issues: list[AuditIssue] = []
    catalogs: dict[str, dict[str, object]] = {}
    for language in LANGUAGES:
        path = root / "src" / "geoworkbench" / "resources" / "i18n" / f"{language}.json"
        catalogs[language] = json.loads(_read_text(path))

    union = set().union(*(set(catalog) for catalog in catalogs.values()))
    for language, catalog in catalogs.items():
        missing = sorted(union - set(catalog))
        if missing:
            issues.append(
                AuditIssue(
                    "i18n-keys",
                    f"{language}.json misses {len(missing)} keys: {missing[:10]}",
                )
            )
    return issues


def _project_version(root: Path) -> str:
    match = VERSION_RE.search(_read_text(root / "pyproject.toml"))
    if match is None:
        raise ValueError("Project version was not found in pyproject.toml")
    return match.group(1)


def audit_version_contract(root: Path) -> list[AuditIssue]:
    """Keep package metadata and required current-version documents aligned."""

    issues: list[AuditIssue] = []
    project_version = _project_version(root)
    package_text = _read_text(root / "src" / "geoworkbench" / "__init__.py")
    package_match = PACKAGE_VERSION_RE.search(package_text)
    package_version = package_match.group(1) if package_match else None
    if package_version != project_version:
        issues.append(
            AuditIssue(
                "version",
                f"pyproject={project_version}, package={package_version or 'missing'}",
            )
        )

    required_root_docs = [
        root / "docs" / f"RELEASE_NOTES_{project_version}.md",
        root / "docs" / f"BUILD_MANIFEST_{project_version}.md",
    ]
    for path in required_root_docs:
        if not path.exists():
            issues.append(
                AuditIssue("version", f"Missing current document: {path.relative_to(root)}")
            )

    for language in LANGUAGES:
        path = root / "docs" / language / f"RELEASE_NOTES_{project_version}.md"
        if not path.exists():
            issues.append(
                AuditIssue("version", f"Missing current document: {path.relative_to(root)}")
            )
    return issues


def audit_user_workflow_coverage(root: Path) -> list[AuditIssue]:
    """Check the high-risk save/reopen and graph-symbol workflows in each guide."""

    issues: list[AuditIssue] = []
    required_files = {
        "README.md",
        "FEATURES.md",
        "ANNOTATIONS.md",
        "PROJECT_STATUS.md",
        "PROJECT_PLAN.md",
    }
    workflow_tokens = {
        "ru": ("Ctrl+S", "повторно", "Вставить значок", "FEATURES.md"),
        "kk": ("Ctrl+S", "қайта", "Белгі енгізу", "FEATURES.md"),
        "en": ("Ctrl+S", "reopen", "Insert symbol", "FEATURES.md"),
    }

    for language in LANGUAGES:
        language_dir = root / "docs" / language
        for filename in required_files:
            if not (language_dir / filename).exists():
                issues.append(
                    AuditIssue(
                        "user-workflow",
                        f"docs/{language}/{filename} is required",
                    )
                )

        combined = "\n".join(
            _read_text(language_dir / filename)
            for filename in ("README.md", "ANNOTATIONS.md", "FEATURES.md")
            if (language_dir / filename).exists()
        )
        for token in workflow_tokens[language]:
            if token not in combined:
                issues.append(
                    AuditIssue(
                        "user-workflow",
                        f"docs/{language} does not cover required token: {token}",
                    )
                )
    return issues


def run_audit(root: Path) -> list[AuditIssue]:
    """Run every documentation contract in a deterministic order."""

    checks = (
        audit_localized_file_parity,
        audit_localized_document_structure,
        audit_markdown_links,
        audit_i18n_key_parity,
        audit_version_contract,
        audit_user_workflow_coverage,
    )
    issues: list[AuditIssue] = []
    for check in checks:
        issues.extend(check(root))
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    root = args.root.resolve()

    issues = run_audit(root)
    if issues:
        for issue in issues:
            print(f"[{issue.category}] {issue.message}")
        print(f"Documentation audit failed: {len(issues)} issue(s).")
        return 1

    localized_count = len(next(iter(localized_markdown_sets(root).values())))
    i18n_count = len(
        json.loads(
            _read_text(
                root / "src" / "geoworkbench" / "resources" / "i18n" / "ru.json"
            )
        )
    )
    print(
        "Documentation audit passed: "
        f"{localized_count} localized files per language, {i18n_count} i18n keys."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

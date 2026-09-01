"""Validate multilingual documentation and localization contracts.

The checker intentionally has no Qt dependencies, so it can run in a minimal
CI or packaging environment before the desktop stack is installed.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

LANGUAGES = ("ru", "kk", "en")
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)
PACKAGE_VERSION_RE = re.compile(r'^__version__\s*=\s*"([^"]+)"', re.MULTILINE)
INTEGER_CONSTANT_RE = re.compile(r"^{name}\s*=\s*(\d+)\s*$", re.MULTILINE)
CANONICAL_LAUNCH_COMMAND = "python -m geoworkbench.app.main"
CANONICAL_PROJECT_PLAN = Path("docs/PROJECT_PLAN.md")
ALLOWED_VALIDATION_FILES = {
    Path("docs/validation/ETP12_INTEROPERABILITY_MATRIX_TEMPLATE.csv"),
}
FORBIDDEN_DOCUMENT_PATTERNS = (
    "RELEASE_NOTES_*",
    "BUILD_MANIFEST_*",
    "HOTFIX_REPORT_*",
    "IMPLEMENTATION_REPORT_*",
    "INCREMENT_*",
)
FORBIDDEN_DOCUMENT_NAMES = {
    "PRODUCT_AUDIT_2026.md",
    "PROJECT_STATUS.md",
    "ROADMAP.md",
}
FORBIDDEN_DOCUMENT_NAMES_CASEFOLD = {
    filename.casefold() for filename in FORBIDDEN_DOCUMENT_NAMES
}
PROJECT_LIFECYCLE_DOCUMENTS = ("PROJECT_WORKFLOW.md", "SESSION_SAVING.md")
PROJECT_LIFECYCLE_MODEL_MARKERS = {
    "ru": (("источник", "исходн"), ("проект",), ("экспорт",)),
    "kk": (("дереккөз", "бастапқы"), ("жоба",), ("экспорт",)),
    "en": (("source", "original"), ("project",), ("export",)),
}
PROJECT_LIFECYCLE_UNIFIED_EXPORT_MARKERS = {
    "ru": (
        "единый экспорт",
        "единый штатный экспорт",
        "единый диалог экспорта",
        "общий экспорт",
    ),
    "kk": (
        "бірыңғай экспорт",
        "бірыңғай штаттық экспорт",
        "ортақ экспорт",
        "бірдей экспорт",
    ),
    "en": (
        "unified export",
        "single export",
        "same export",
        "common export",
        "shared standard exporter",
    ),
}
PROJECT_LIFECYCLE_DIRTY_GUARD_MARKERS = {
    "ru": (
        ("dirty", "несохранён"),
        ("закры",),
        ("защит", "предлага"),
        ("сохран",),
        ("отмен",),
    ),
    "kk": (
        ("dirty", "сақталмаған"),
        ("жаб",),
        ("қорған", "ұсын"),
        ("сақта",),
        ("болдыр",),
    ),
    "en": (
        ("dirty", "unsaved"),
        ("clos",),
        ("guard", "offer"),
        ("save",),
        ("cancel",),
    ),
}
PROJECT_LIFECYCLE_DIRTY_CLOSE_MARKERS = {
    "ru": (
        "несохранённ",
        "закрыт",
        "четыре",
        "сохранить проект",
        "не сохранять",
        "отмена",
    ),
    "kk": (
        "сақталмаған",
        "жабу",
        "төрт",
        "жобаны сақтау",
        "сақтамау",
        "болдырмау",
    ),
    "en": (
        "unsaved",
        "closing",
        "four",
        "save project",
        "don't save",
        "cancel",
    ),
}
PROJECT_LIFECYCLE_FORBIDDEN_MARKERS = {
    "ru": (
        "не передаёт действие внутренней кнопки",
        "надёжного автосохранения пока нет",
        "нет надёжного автосохранения",
        "нет надёжного автосохранения и гарантированного запроса при закрытии",
        "не имеет надёжного автосохранения или гарантированного запроса при закрытии",
        "не гарантирует запрос на сохранение при закрытии",
    ),
    "kk": (
        "әрекетін қалыпты экспортқа жеткізбейді",
        "сенімді автосақтау әзірге жоқ",
        "сенімді автосақтау жоқ",
        "сенімді автосақтау және жабу кезінде міндетті сұрау жоқ",
        "сенімді автосақтау немесе жабу кезіндегі міндетті сұрау жоқ",
        "жабу кезінде сақтау сұрағын кепілдемейді",
    ),
    "en": (
        "does not propagate its inner",
        "dependable autosave is not available yet",
        "autosave and a separate save backup copy command are not yet implemented",
        "no dependable autosave or guaranteed close prompt",
        "does not guarantee a close-time save prompt",
    ),
}


@dataclass(frozen=True)
class AuditIssue:
    """One actionable documentation audit failure."""

    category: str
    message: str


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _normalized_prose(text: str) -> str:
    """Return case-insensitive prose with Markdown line wrapping removed."""

    return re.sub(r"\s+", " ", text).casefold()


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
    """Detect materially incomplete current guides."""

    issues: list[AuditIssue] = []
    file_sets = localized_markdown_sets(root)
    common = set.intersection(*file_sets.values())
    for filename in sorted(common):
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


def audit_documentation_hygiene(root: Path) -> list[AuditIssue]:
    """Keep generated reports, parallel plans, and validation output out of docs."""

    issues: list[AuditIssue] = []
    docs_root = root / "docs"
    if not docs_root.exists():
        return [AuditIssue("documentation-hygiene", "Missing docs directory")]

    for path in sorted(candidate for candidate in docs_root.rglob("*") if candidate.is_file()):
        relative = path.relative_to(root)
        filename = path.name
        reason: str | None = None

        if any(
            fnmatch.fnmatchcase(filename.casefold(), pattern.casefold())
            for pattern in FORBIDDEN_DOCUMENT_PATTERNS
        ):
            reason = "historical build report"
        elif filename.casefold().endswith("_plan.md") and relative != CANONICAL_PROJECT_PLAN:
            reason = f"parallel plan; use {CANONICAL_PROJECT_PLAN.as_posix()}"
        elif filename.casefold() in FORBIDDEN_DOCUMENT_NAMES_CASEFOLD:
            reason = "superseded status, roadmap, or audit"
        elif relative.parts[:2] == ("docs", "validation"):
            if relative not in ALLOWED_VALIDATION_FILES:
                reason = "generated validation output"
        elif (
            "validation" in path.stem.casefold()
            and path.suffix.casefold() in {".json", ".log", ".pdf", ".png", ".txt"}
        ):
            reason = "generated validation output"

        if reason is not None:
            issues.append(
                AuditIssue(
                    "documentation-hygiene",
                    f"{relative.as_posix()} is forbidden: {reason}",
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


def audit_documentation_navigation(root: Path) -> list[AuditIssue]:
    """Require every Markdown document to be reachable from the canonical index."""

    docs_root = (root / "docs").resolve()
    entrypoint = docs_root / "DOCUMENTATION_INDEX.md"
    if not entrypoint.exists():
        return [
            AuditIssue(
                "documentation-navigation",
                "Missing docs/DOCUMENTATION_INDEX.md",
            )
        ]

    all_documents = {
        path.resolve()
        for path in docs_root.rglob("*.md")
        if path.is_file()
    }
    reachable: set[Path] = set()
    pending = [entrypoint]
    while pending:
        path = pending.pop()
        if path in reachable or path not in all_documents:
            continue
        reachable.add(path)
        for target in _iter_local_markdown_links(path):
            resolved = (path.parent / target).resolve()
            try:
                resolved.relative_to(docs_root)
            except ValueError:
                continue
            if resolved.suffix.casefold() == ".md" and resolved not in reachable:
                pending.append(resolved)

    return [
        AuditIssue(
            "documentation-navigation",
            f"{path.relative_to(root).as_posix()} is not reachable from "
            "docs/DOCUMENTATION_INDEX.md",
        )
        for path in sorted(all_documents - reachable)
    ]


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


def _integer_constant(path: Path, name: str) -> int:
    pattern = re.compile(INTEGER_CONSTANT_RE.pattern.format(name=re.escape(name)), re.MULTILINE)
    match = pattern.search(_read_text(path))
    if match is None:
        raise ValueError(f"{name} was not found in {path}")
    return int(match.group(1))


def runtime_contract_marker(root: Path) -> str:
    """Build the machine-checkable current runtime contract from source constants."""

    project_format = _integer_constant(
        root / "src" / "geoworkbench" / "storage" / "project_codec.py",
        "PROJECT_FORMAT_VERSION",
    )
    form_schema = _integer_constant(
        root / "src" / "geoworkbench" / "forms" / "codec.py",
        "FORM_SCHEMA_VERSION",
    )
    layout_format = _integer_constant(
        root / "src" / "geoworkbench" / "tablet" / "layout_codec.py",
        "LAYOUT_FORMAT_VERSION",
    )
    return (
        "<!-- runtime-contract: "
        f"package={_project_version(root)}; "
        f"project=v{project_format}; "
        f"form=v{form_schema}; "
        f"layout=v{layout_format} -->"
    )


def audit_runtime_contract(root: Path) -> list[AuditIssue]:
    """Keep the canonical architecture and project plan aligned with runtime schemas."""

    marker = runtime_contract_marker(root)
    current_documents = (
        root / "docs" / "ARCHITECTURE.md",
        root / "docs" / "PROJECT_PLAN.md",
    )
    issues: list[AuditIssue] = []
    for path in current_documents:
        if not path.exists():
            issues.append(
                AuditIssue(
                    "runtime-contract",
                    f"Missing current document: {path.relative_to(root)}",
                )
            )
        elif marker not in _read_text(path):
            issues.append(
                AuditIssue(
                    "runtime-contract",
                    f"{path.relative_to(root)} must contain {marker}",
                )
            )
    return issues


def audit_version_contract(root: Path) -> list[AuditIssue]:
    """Keep package metadata aligned without requiring per-build documents."""

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
    return issues



def audit_startup_command_contract(root: Path) -> list[AuditIssue]:
    """Keep one canonical module startup command in code and current documentation."""

    issues: list[AuditIssue] = []
    required_documents = (
        root / "README.md",
        root / "docs" / "ru" / "README.md",
        root / "docs" / "kk" / "README.md",
        root / "docs" / "en" / "README.md",
        root / "docs" / "TESTING.md",
    )
    for path in required_documents:
        if not path.exists():
            issues.append(
                AuditIssue(
                    "startup-command",
                    f"Missing startup document: {path.relative_to(root)}",
                )
            )
            continue
        if CANONICAL_LAUNCH_COMMAND not in _read_text(path):
            issues.append(
                AuditIssue(
                    "startup-command",
                    f"{path.relative_to(root)} must contain {CANONICAL_LAUNCH_COMMAND!r}",
                )
            )

    main_path = root / "src" / "geoworkbench" / "app" / "main.py"
    if main_path.exists():
        main_text = _read_text(main_path)
        if 'if __name__ == "__main__":' not in main_text or "SystemExit(main())" not in main_text:
            issues.append(
                AuditIssue(
                    "startup-command",
                    "geoworkbench.app.main must expose an executable python -m guard",
                )
            )
    else:
        issues.append(AuditIssue("startup-command", "Missing src/geoworkbench/app/main.py"))

    pyproject_text = _read_text(root / "pyproject.toml")
    expected_entrypoint = 'geoworkbench.app.main:main'
    if pyproject_text.count(expected_entrypoint) < 1:
        issues.append(
            AuditIssue(
                "startup-command",
                f"pyproject scripts must target {expected_entrypoint}",
            )
        )
    return issues


def audit_current_documentation_contract(root: Path) -> list[AuditIssue]:
    """Keep the documentation index and testing guide on canonical entry points."""

    issues: list[AuditIssue] = []
    checks = {
        root / "docs" / "DOCUMENTATION_INDEX.md": (
            "PROJECT_PLAN.md",
            "ARCHITECTURE.md",
            "TESTING.md",
            "ru/README.md",
            "kk/README.md",
            "en/README.md",
        ),
        root / "docs" / "TESTING.md": (
            CANONICAL_LAUNCH_COMMAND,
            "test_module_entrypoint_contract_0790.py",
            "test_test_runner_contract_0790.py",
            "run_headless_tests.py",
        ),
        root / "README.md": (
            CANONICAL_LAUNCH_COMMAND,
            "docs/TESTING.md",
        ),
    }
    for path, tokens in checks.items():
        if not path.exists():
            issues.append(
                AuditIssue(
                    "current-documentation",
                    f"Missing current document: {path.relative_to(root)}",
                )
            )
            continue
        content = _read_text(path)
        for token in tokens:
            if token not in content:
                issues.append(
                    AuditIssue(
                        "current-documentation",
                        f"{path.relative_to(root)} does not reference current token: {token}",
                    )
                )
    return issues

def audit_user_workflow_coverage(root: Path) -> list[AuditIssue]:
    """Check the high-risk save/reopen and graph-symbol workflows in each guide."""

    issues: list[AuditIssue] = []
    required_files = {
        "README.md",
        "FEATURES.md",
        "ANNOTATIONS.md",
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


def audit_daily_project_workflow_coverage(root: Path) -> list[AuditIssue]:
    """Keep the portable-project and append instructions present in all languages."""

    issues: list[AuditIssue] = []
    guide_paths = {
        "ru": root / "docs" / "USER_GUIDE_RU.md",
        "kk": root / "docs" / "USER_GUIDE_KK.md",
        "en": root / "docs" / "USER_GUIDE_EN.md",
    }
    guide_tokens = {
        "ru": (
            ".geologpkg",
            "Ежедневно нарастить LAS",
            "Проверить прирост",
            "Нарастить",
            "Ctrl+S",
            "RU, KK и EN",
            "Центр печати",
            "двух компьютерах",
            ".geolog-backups",
            "сохраняется автоматически",
            "recovery-копию",
        ),
        "kk": (
            ".geologpkg",
            "LAS деректерін күнделікті өсіру",
            "Өсімді тексеру",
            "Өсіру",
            "Ctrl+S",
            "RU, KK және EN",
            "баспа орталығын",
            "екі компьютерде",
            ".geolog-backups",
            "автоматты сақталады",
            "қалпына келтіру",
        ),
        "en": (
            ".geologpkg",
            "Append daily LAS data",
            "Analyze growth",
            "Append",
            "Ctrl+S",
            "RU, KK, and EN",
            "Print Centre",
            "two computers",
            ".geolog-backups",
            "saved automatically",
            "Restore recovery copy",
        ),
    }
    workflow_tokens = {
        "ru": (
            "SHA-256",
            "локальную папку",
            "двух компьютерах",
            "index.v1.json",
            "пять последних",
            "блокирует перезапись",
        ),
        "kk": (
            "SHA-256",
            "жергілікті қалтаны",
            "екі компьютерде",
            "index.v1.json",
            "соңғы бес",
            "қайта жазуды блоктап",
        ),
        "en": (
            "SHA-256",
            "local folder",
            "two computers",
            "index.v1.json",
            "five newest",
            "blocks overwrite",
        ),
    }

    for language in LANGUAGES:
        paths_and_tokens = (
            (guide_paths[language], guide_tokens[language]),
            (
                root / "docs" / language / "PROJECT_WORKFLOW.md",
                workflow_tokens[language],
            ),
        )
        for path, tokens in paths_and_tokens:
            if not path.exists():
                issues.append(
                    AuditIssue(
                        "daily-project-workflow",
                        f"{path.relative_to(root).as_posix()} is required",
                    )
                )
                continue
            content = _read_text(path)
            for token in tokens:
                if token not in content:
                    issues.append(
                        AuditIssue(
                            "daily-project-workflow",
                            f"{path.relative_to(root).as_posix()} does not cover: {token}",
                        )
                    )
    return issues


def audit_project_lifecycle_contract(root: Path) -> list[AuditIssue]:
    """Keep source, project, export, and dirty-close guidance aligned with the UI."""

    issues: list[AuditIssue] = []
    for language in LANGUAGES:
        language_dir = root / "docs" / language
        documents: dict[str, str] = {}
        for filename in PROJECT_LIFECYCLE_DOCUMENTS:
            path = language_dir / filename
            if not path.exists():
                issues.append(
                    AuditIssue(
                        "project-lifecycle",
                        f"docs/{language}/{filename} is required for the project lifecycle",
                    )
                )
                continue
            documents[filename] = _normalized_prose(_read_text(path))

        for filename, content in documents.items():
            for marker_group in PROJECT_LIFECYCLE_MODEL_MARKERS[language]:
                if not any(marker in content for marker in marker_group):
                    choices = " / ".join(marker_group)
                    issues.append(
                        AuditIssue(
                            "project-lifecycle",
                            f"docs/{language}/{filename} does not explain the "
                            f"source/project/export model: {choices}",
                        )
                    )
            for product in ("gs2", "paradox"):
                if product not in content:
                    issues.append(
                        AuditIssue(
                            "project-lifecycle",
                            f"docs/{language}/{filename} does not cover {product.upper()}",
                        )
                    )
            if not any(
                marker in content
                for marker in PROJECT_LIFECYCLE_UNIFIED_EXPORT_MARKERS[language]
            ):
                issues.append(
                    AuditIssue(
                        "project-lifecycle",
                        f"docs/{language}/{filename} must describe one shared "
                        "GS2/Paradox export path",
                    )
                )
            for marker_group in PROJECT_LIFECYCLE_DIRTY_GUARD_MARKERS[language]:
                if not any(marker in content for marker in marker_group):
                    choices = " / ".join(marker_group)
                    issues.append(
                        AuditIssue(
                            "project-lifecycle",
                            f"docs/{language}/{filename} does not explain the dirty-close "
                            f"guard: {choices}",
                        )
                    )

        session_saving = documents.get("SESSION_SAVING.md")
        if session_saving is not None:
            for marker in PROJECT_LIFECYCLE_DIRTY_CLOSE_MARKERS[language]:
                if marker not in session_saving:
                    issues.append(
                        AuditIssue(
                            "project-lifecycle",
                            f"docs/{language}/SESSION_SAVING.md does not guarantee the "
                            f"dirty-close choice: {marker}",
                        )
                    )

        if not language_dir.exists():
            continue
        for path in sorted(language_dir.rglob("*.md")):
            content = _normalized_prose(_read_text(path))
            for marker in PROJECT_LIFECYCLE_FORBIDDEN_MARKERS[language]:
                if marker in content:
                    issues.append(
                        AuditIssue(
                            "project-lifecycle",
                            f"{path.relative_to(root).as_posix()} contains stale guidance: "
                            f"{marker}",
                        )
                    )
    return issues



def audit_compact_column_coverage(root: Path) -> list[AuditIssue]:
    """Require the compact-column and embedded-template workflow in every language."""

    issues: list[AuditIssue] = []
    required_documents = (
        "FORM_ENGINE.md",
        "FEATURES.md",
    )
    language_tokens = {
        "ru": ("50%", "48", "80", "готов", "пользователь", "v8", "v18"),
        "kk": ("50%", "48", "80", "дайын", "пайдаланушы", "v8", "v18"),
        "en": ("50%", "48", "80", "ready", "user", "v8", "v18"),
    }

    for language in LANGUAGES:
        language_dir = root / "docs" / language
        missing = [name for name in required_documents if not (language_dir / name).exists()]
        for filename in missing:
            issues.append(
                AuditIssue(
                    "compact-columns",
                    f"docs/{language}/{filename} is required for compact-column coverage",
                )
            )

        combined = "\n".join(
            _read_text(language_dir / filename)
            for filename in required_documents
            if (language_dir / filename).exists()
        )
        for token in language_tokens[language]:
            if token not in combined:
                issues.append(
                    AuditIssue(
                        "compact-columns",
                        f"docs/{language} does not cover required token: {token}",
                    )
                )
    return issues


def audit_form_creation_naming_coverage(root: Path) -> list[AuditIssue]:
    """Require the visible-library naming workflow in every user guide."""

    issues: list[AuditIssue] = []
    required_documents = (
        "README.md",
        "FEATURES.md",
        "FORM_ENGINE.md",
    )
    language_tokens = {
        "ru": ("Создать форму", "Сохранить пользовательскую форму", "все готовые", "пользовательские", "совпад", "пробел"),
        "kk": ("Пішін жасау", "Пайдаланушы пішінін сақтау", "барлық дайын", "пайдаланушы", "қайталан", "бос орын"),
        "en": ("Create form", "Save user form", "all ready", "user form", "duplicate", "whitespace"),
    }

    for language in LANGUAGES:
        language_dir = root / "docs" / language
        for filename in required_documents:
            if not (language_dir / filename).exists():
                issues.append(
                    AuditIssue(
                        "form-naming",
                        f"docs/{language}/{filename} is required for form naming coverage",
                    )
                )
        combined = "\n".join(
            _read_text(language_dir / filename)
            for filename in required_documents
            if (language_dir / filename).exists()
        )
        for token in language_tokens[language]:
            if token not in combined:
                issues.append(
                    AuditIssue(
                        "form-naming",
                        f"docs/{language} does not cover required token: {token}",
                    )
                )
    return issues



def audit_catalog_toolbar_diagnostics_coverage(root: Path) -> list[AuditIssue]:
    """Require the 0.7.66 catalog, responsive-toolbar, and cleanup workflows."""

    issues: list[AuditIssue] = []
    required_documents = (
        "APPLICATION_DIAGNOSTICS.md",
        "UI_WORKSPACE.md",
        "FORM_ENGINE.md",
        "FEATURES.md",
    )
    language_tokens = {
        "ru": ("18 заводских", "Сбросить данные диагностики", "адаптив", "Редактирование"),
        "kk": ("18 зауыттық", "Диагностика деректерін тазарту", "бейім", "Пішінді өңдеу"),
        "en": ("18 factory", "Clear diagnostics data", "responsive", "Form editing"),
    }
    for language in LANGUAGES:
        language_dir = root / "docs" / language
        for filename in required_documents:
            if not (language_dir / filename).exists():
                issues.append(
                    AuditIssue(
                        "catalog-toolbar-diagnostics",
                        f"docs/{language}/{filename} is required",
                    )
                )
        combined = "\n".join(
            _read_text(language_dir / filename)
            for filename in required_documents
            if (language_dir / filename).exists()
        )
        for token in language_tokens[language]:
            if token not in combined:
                issues.append(
                    AuditIssue(
                        "catalog-toolbar-diagnostics",
                        f"docs/{language} does not cover required token: {token}",
                    )
                )
    return issues


def audit_compact_curve_header_coverage(root: Path) -> list[AuditIssue]:
    """Require the parameter-labelled compact-ruler workflow in every language."""

    issues: list[AuditIssue] = []
    required_documents = (
        "README.md",
        "FEATURES.md",
        "TABLET_ENGINE_2.md",
        "UI_WORKSPACE.md",
    )
    language_tokens = {
        "ru": ("Нагрузка на долото", "44 px", "58", "заводск", "пользователь", "Шкала"),
        "kk": ("Қашауға түсетін жүктеме", "44 px", "58", "зауыттық", "пайдаланушы", "Шкала"),
        "en": ("Weight on bit", "44 px", "58", "factory", "user", "Scale"),
    }
    for language in LANGUAGES:
        language_dir = root / "docs" / language
        for filename in required_documents:
            if not (language_dir / filename).exists():
                issues.append(
                    AuditIssue(
                        "compact-curve-header",
                        f"docs/{language}/{filename} is required",
                    )
                )
        combined = "\n".join(
            _read_text(language_dir / filename)
            for filename in required_documents
            if (language_dir / filename).exists()
        )
        for token in language_tokens[language]:
            if token not in combined:
                issues.append(
                    AuditIssue(
                        "compact-curve-header",
                        f"docs/{language} does not cover required token: {token}",
                    )
                )
    return issues

def run_audit(root: Path) -> list[AuditIssue]:
    """Run every documentation contract in a deterministic order."""

    checks = (
        audit_documentation_hygiene,
        audit_localized_file_parity,
        audit_localized_document_structure,
        audit_markdown_links,
        audit_documentation_navigation,
        audit_i18n_key_parity,
        audit_version_contract,
        audit_runtime_contract,
        audit_startup_command_contract,
        audit_current_documentation_contract,
        audit_user_workflow_coverage,
        audit_daily_project_workflow_coverage,
        audit_project_lifecycle_contract,
        audit_compact_column_coverage,
        audit_form_creation_naming_coverage,
        audit_catalog_toolbar_diagnostics_coverage,
        audit_compact_curve_header_coverage,
    )
    issues: list[AuditIssue] = []
    for check in checks:
        issues.extend(check(root))
    return issues


def main(argv: list[str] | None = None) -> int:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(errors="backslashreplace")
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

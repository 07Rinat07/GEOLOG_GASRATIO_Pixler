from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from geoworkbench.services.import_jobs import (
    ImportJobController,
    ImportSourceKind,
)


@dataclass
class FakeImportJobPort:
    executed: list[tuple[ImportSourceKind, Path | None]] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)

    def execute_import(
        self, kind: ImportSourceKind, source: Path | None = None
    ) -> None:
        self.executed.append((kind, source))

    def report_unknown_source(self, selected_label: str) -> None:
        self.unknown.append(selected_label)


def localize(key: str) -> str:
    return {
        "import.source_las": "LAS",
        "import.source_csv": "CSV",
        "import.source_excel": "Excel",
        "import.source_paradox": "Paradox",
        "import.source_gs2": "GS2",
    }[key]


def test_choices_have_stable_kinds_and_localized_labels() -> None:
    choices = ImportJobController.choices(localize)

    assert [(choice.kind, choice.label) for choice in choices] == [
        (ImportSourceKind.LAS, "LAS"),
        (ImportSourceKind.CSV, "CSV"),
        (ImportSourceKind.EXCEL, "Excel"),
        (ImportSourceKind.PARADOX, "Paradox"),
        (ImportSourceKind.GS2, "GS2"),
    ]


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("LAS", ImportSourceKind.LAS),
        ("CSV", ImportSourceKind.CSV),
        ("Excel", ImportSourceKind.EXCEL),
        ("Paradox", ImportSourceKind.PARADOX),
        ("GS2", ImportSourceKind.GS2),
    ],
)
def test_dispatch_routes_every_supported_source(
    label: str,
    expected: ImportSourceKind,
) -> None:
    port = FakeImportJobPort()
    controller = ImportJobController(port)

    assert controller.dispatch(label, True, localize) is True
    assert port.executed == [(expected, None)]


def test_cancel_and_unknown_source_do_not_start_import() -> None:
    port = FakeImportJobPort()
    controller = ImportJobController(port)

    assert controller.dispatch("LAS", False, localize) is False
    assert controller.dispatch("Unknown", True, localize) is False

    assert port.executed == []
    assert port.unknown == ["Unknown"]


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("well.LAS", ImportSourceKind.LAS),
        ("table.csv", ImportSourceKind.CSV),
        ("table.TXT", ImportSourceKind.CSV),
        ("book.xlsx", ImportSourceKind.EXCEL),
        ("legacy.xls", ImportSourceKind.EXCEL),
        ("macro.xlsm", ImportSourceKind.EXCEL),
        ("geoscape.db", ImportSourceKind.PARADOX),
        ("container.gs2", ImportSourceKind.GS2),
    ],
)
def test_dispatch_path_detects_format_from_extension(
    filename: str,
    expected: ImportSourceKind,
) -> None:
    port = FakeImportJobPort()
    controller = ImportJobController(port)

    assert controller.dispatch_path(filename) is True
    assert port.executed == [(expected, Path(filename))]


def test_dispatch_path_reports_unknown_extension() -> None:
    port = FakeImportJobPort()
    controller = ImportJobController(port)

    assert controller.dispatch_path("notes.pdf") is False
    assert port.executed == []
    assert port.unknown == ["notes.pdf"]

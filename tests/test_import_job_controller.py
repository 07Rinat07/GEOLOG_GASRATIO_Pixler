from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import zipfile

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
        "import.source_geosight_form": "GeoSight",
        "import.source_gs2": "GS2",
    }[key]


def test_choices_have_stable_kinds_and_localized_labels() -> None:
    choices = ImportJobController.choices(localize)

    assert [(choice.kind, choice.label) for choice in choices] == [
        (ImportSourceKind.LAS, "LAS"),
        (ImportSourceKind.CSV, "CSV"),
        (ImportSourceKind.EXCEL, "Excel"),
        (ImportSourceKind.PARADOX, "Paradox"),
        (ImportSourceKind.GEOSIGHT_FORM, "GeoSight"),
        (ImportSourceKind.GS2, "GS2"),
    ]


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("LAS", ImportSourceKind.LAS),
        ("CSV", ImportSourceKind.CSV),
        ("Excel", ImportSourceKind.EXCEL),
        ("Paradox", ImportSourceKind.PARADOX),
        ("GeoSight", ImportSourceKind.GEOSIGHT_FORM),
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
        ("legacy.sd2", ImportSourceKind.GEOSIGHT_FORM),
        ("legacy.SF2", ImportSourceKind.GEOSIGHT_FORM),
        ("legacy.gsf", ImportSourceKind.GEOSIGHT_FORM),
        ("legacy.grc", ImportSourceKind.GEOSIGHT_FORM),
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


def test_dispatch_path_sniffs_textual_legacy_gs2_before_data_container(
    tmp_path: Path,
) -> None:
    source = tmp_path / "legacy.gs2"
    source.write_text(
        "object MainForm: TfmGSComplexForm\n"
        "  Caption = 'Legacy form'\n"
        "end\n",
        encoding="cp1251",
    )
    port = FakeImportJobPort()
    controller = ImportJobController(port)

    assert controller.dispatch_path(source) is True
    assert port.executed == [(ImportSourceKind.GEOSIGHT_FORM, source)]


def test_dispatch_path_keeps_zip_gs2_on_data_import_path(tmp_path: Path) -> None:
    source = tmp_path / "container.gs2"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("GS2.mdb", b"metadata")
        archive.writestr("GS2#1.db", b"table")
    port = FakeImportJobPort()
    controller = ImportJobController(port)

    assert controller.dispatch_path(source) is True
    assert port.executed == [(ImportSourceKind.GS2, source)]


def test_dispatch_path_reports_unknown_extension() -> None:
    port = FakeImportJobPort()
    controller = ImportJobController(port)

    assert controller.dispatch_path("notes.pdf") is False
    assert port.executed == []
    assert port.unknown == ["notes.pdf"]

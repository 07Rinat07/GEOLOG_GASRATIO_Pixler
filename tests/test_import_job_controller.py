from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from geoworkbench.ui.import_job_controller import (
    ImportJobController,
    ImportSourceKind,
)


@dataclass
class FakeImportJobPort:
    executed: list[ImportSourceKind] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)

    def execute_import(self, kind: ImportSourceKind) -> None:
        self.executed.append(kind)

    def report_unknown_source(self, selected_label: str) -> None:
        self.unknown.append(selected_label)


def localize(key: str) -> str:
    return {
        "import.source_las": "LAS",
        "import.source_csv": "CSV",
        "import.source_excel": "Excel",
        "import.source_paradox": "Paradox",
    }[key]


def test_choices_have_stable_kinds_and_localized_labels() -> None:
    choices = ImportJobController.choices(localize)

    assert [(choice.kind, choice.label) for choice in choices] == [
        (ImportSourceKind.LAS, "LAS"),
        (ImportSourceKind.CSV, "CSV"),
        (ImportSourceKind.EXCEL, "Excel"),
        (ImportSourceKind.PARADOX, "Paradox"),
    ]


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("LAS", ImportSourceKind.LAS),
        ("CSV", ImportSourceKind.CSV),
        ("Excel", ImportSourceKind.EXCEL),
        ("Paradox", ImportSourceKind.PARADOX),
    ],
)
def test_dispatch_routes_every_supported_source(
    label: str,
    expected: ImportSourceKind,
) -> None:
    port = FakeImportJobPort()
    controller = ImportJobController(port)

    assert controller.dispatch(label, True, localize) is True
    assert port.executed == [expected]


def test_cancel_and_unknown_source_do_not_start_import() -> None:
    port = FakeImportJobPort()
    controller = ImportJobController(port)

    assert controller.dispatch("LAS", False, localize) is False
    assert controller.dispatch("Unknown", True, localize) is False

    assert port.executed == []
    assert port.unknown == ["Unknown"]

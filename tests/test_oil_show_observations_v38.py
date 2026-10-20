"""DataLog independent tests: v38 persistence, legacy safety and UI/controller wiring."""

from __future__ import annotations

import json
from dataclasses import asdict

import pytest

from geoworkbench.domain.models import CuttingsSample, Project, Well
from geoworkbench.domain.oil_show_observations import (
    OilShowMethod, OilShowObservation, OilShowQuality,
    oil_show_observations_from_list, validate_oil_show_observations,
)
from geoworkbench.project.cuttings_controller import CuttingsController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.storage.atomic_json import save_project
from geoworkbench.storage.project_codec import (
    PROJECT_FORMAT_VERSION, ProjectFormatError, load_project,
)
from geoworkbench.ui.oil_show_observation_editor import OilShowObservationEditor
from geoworkbench.ui.sample_analysis_dialog import SampleAnalysisDialog


def _observations() -> list[OilShowObservation]:
    return [
        OilShowObservation(
            OilShowMethod.DIRECT_FLUORESCENCE_UV,
            area_percent=12.5, colour="БГ", brightness="weak",
            distribution="spotty", quality=OilShowQuality.SUSPECT,
            notes="Check drilling fluid fluorescence",
        ),
        OilShowObservation(
            OilShowMethod.SOLVENT_CUT_DAYLIGHT,
            colour="straw", reaction_speed="slow",
            quality=OilShowQuality.VERIFIED,
        ),
        OilShowObservation(
            OilShowMethod.SOLVENT_CUT_UV,
            colour="blue", brightness="medium",
            quality=OilShowQuality.UNCHECKED,
        ),
    ]


def _project() -> Project:
    sample = CuttingsSample(
        "sample-1", 500.0, 510.0,
        lba_group=1, lba_type_id="ЛБ", lba_color="БГ",
        lba_intensity=2, lba_residue_type="Trace",
        show_observations=_observations(),
    )
    return Project("project-1", "Test", wells={
        "well-1": Well("well-1", "Well 1", cuttings=[sample]),
    })


def test_v38_round_trip_keeps_uv_tests_independent_from_legacy_lba(tmp_path) -> None:
    target = tmp_path / "shows.geolog.json"
    save_project(_project(), target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["format_version"] == PROJECT_FORMAT_VERSION == 38
    raw = payload["project"]["wells"]["well-1"]["cuttings"][0]
    assert len(raw["show_observations"]) == 3
    assert raw["show_observations"][0]["method"] == "direct_fluorescence_uv"
    assert raw["show_observations"][0]["area_percent"] == 12.5
    assert raw["show_observations"][1]["method"] == "solvent_cut_daylight"
    assert raw["show_observations"][2]["method"] == "solvent_cut_uv"
    reopened = load_project(target).wells["well-1"].cuttings[0]
    assert reopened.show_observations == _observations()
    assert reopened.lba_intensity == 2
    assert reopened.lba_residue_type == "Trace"
    assert reopened.lba_color == "БГ"


def test_v37_project_reopens_without_fabricating_uv_observations(tmp_path) -> None:
    target = tmp_path / "v37.geolog.json"
    save_project(_project(), target)
    old = json.loads(target.read_text(encoding="utf-8"))
    old["format_version"] = 37
    old_sample = old["project"]["wells"]["well-1"]["cuttings"][0]
    old_sample.pop("show_observations")
    target.write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
    restored = load_project(target).wells["well-1"].cuttings[0]
    assert restored.show_observations == []
    assert restored.lba_intensity == 2
    assert restored.lba_residue_type == "Trace"


@pytest.mark.parametrize("corruption", ("unknown", "duplicate", "percent", "boolean", "extra"))
def test_v38_invalid_or_duplicate_observations_fail_closed(tmp_path, corruption: str) -> None:
    target = tmp_path / "invalid.geolog.json"
    save_project(_project(), target)
    raw = json.loads(target.read_text(encoding="utf-8"))
    rows = raw["project"]["wells"]["well-1"]["cuttings"][0]["show_observations"]
    if corruption == "unknown":
        rows[0]["method"] = "gas_proved"
    elif corruption == "duplicate":
        rows[1]["method"] = rows[0]["method"]
    elif corruption == "percent":
        rows[0]["area_percent"] = 101.0
    elif corruption == "boolean":
        rows[0]["area_percent"] = True
    else:
        rows[0]["oil_pay"] = True
    target.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ProjectFormatError, match="наблюдени"):
        load_project(target)


def test_observation_constraints_are_strict_and_snapshot_is_immutable() -> None:
    with pytest.raises(ValueError, match="range"):
        OilShowObservation(OilShowMethod.VISIBLE_STAIN, area_percent=-0.3)
    with pytest.raises(ValueError, match="one observation"):
        validate_oil_show_observations(_observations()[:1] * 2)
    with pytest.raises(ValueError, match="schema"):
        oil_show_observations_from_list([{"method": "visible_stain"}])
    assert OilShowObservation(OilShowMethod.ODOUR, brightness="none").brightness == "none"
    assert asdict(_observations()[0])["quality"] is OilShowQuality.SUSPECT


def test_editor_keeps_daylight_and_uv_records_separate_on_reopen(qapp) -> None:
    editor = OilShowObservationEditor(AppLanguage.RU, _observations())
    assert editor.objectName() != "datalog-independent-show-table"
    from PySide6.QtWidgets import QDoubleSpinBox, QLineEdit
    area = editor.findChild(QDoubleSpinBox, "show-direct_fluorescence_uv-area")
    uv_color = editor.findChild(QLineEdit, "show-solvent_cut_uv-colour")
    day_color = editor.findChild(QLineEdit, "show-solvent_cut_daylight-colour")
    assert area is not None and area.value() == 12.5
    assert uv_color is not None and uv_color.text() == "blue"
    assert day_color is not None and day_color.text() == "straw"
    uv_color.setText("orange")
    recorded = editor.observations()
    assert next(x for x in recorded if x.method is OilShowMethod.SOLVENT_CUT_UV).colour == "orange"
    assert next(x for x in recorded if x.method is OilShowMethod.SOLVENT_CUT_DAYLIGHT).colour == "straw"
    assert editor.observations() == recorded
    editor.close()


@pytest.mark.parametrize("language", list(AppLanguage))
def test_sample_dialog_returns_separate_shows_in_each_locale(qapp, language: AppLanguage) -> None:
    sample = _project().wells["well-1"].cuttings[0]
    dialog = SampleAnalysisDialog(500, 510, language=language, sample=sample)
    data = dialog.values()
    assert data["show_observations"] == _observations()
    assert data["lba_intensity"] == 2
    dialog.close()


def test_controller_preserves_old_lba_and_independent_shows_on_update() -> None:
    session = ProjectSession()
    session.load_project(_project(), well_id="well-1")
    controller = CuttingsController(session)
    sample = controller.get("sample-1")
    assert sample.show_observations == _observations()
    controller.update_analysis("sample-1", top_depth=500, bottom_depth=510,
                               lba_group=1, lba_intensity=2)
    assert sample.show_observations == _observations()
    with pytest.raises(ValueError, match="one observation"):
        controller.update_analysis(
            "sample-1", top_depth=500, bottom_depth=510,
            show_observations=_observations()[:1] * 2,
        )
    assert sample.show_observations == _observations()

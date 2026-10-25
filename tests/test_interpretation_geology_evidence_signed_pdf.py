"""Signed PDF includes measured geology only for current, operator-selected data."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import re

import fitz
import numpy as np
import pytest

from geoworkbench.printing.hydrocarbon_interpretation_report import (
    HydrocarbonInterpretationPdfError,
    export_hydrocarbon_interpretation_pdf_with_passport,
)
from geoworkbench.printing.hydrocarbon_interpretation_report_identity import (
    default_interpretation_report_identity,
)
from geoworkbench.services.hydrocarbon_interpretation import hydrocarbon_interpretation_html
from geoworkbench.services.interpretation_geology_interval_evidence import (
    correlate_gas_interval_with_well_geology,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.report_passport import passport_sidecar_path
from test_interpretation_geology_evidence_operator_ui import _candidate
from test_report_geology_snapshot import _report, _session


def _actual_source():
    session = _session()
    dataset = session.current_dataset
    assert dataset is not None
    report = replace(
        _report(),
        depth_axis_id=dataset.active_index_id,
        candidates=(_candidate(1002.0, 1010.0),),
    )
    observed = correlate_gas_interval_with_well_geology(
        session, top_depth=1002.0, bottom_depth=1010.0,
    )
    return session, report, observed


def _pdf_text(path: Path) -> str:
    with fitz.open(path) as document:
        return re.sub(r"\s+", " ", " ".join(page.get_text() for page in document))


@pytest.mark.parametrize(
    ("language", "title"),
    (
        (AppLanguage.RU, "Фактическое пересечение газового интервала"),
        (AppLanguage.KK, "Газ аралығы мен геологиялық деректердің нақты"),
        (AppLanguage.EN, "Measured gas interval and geological evidence"),
    ),
)
def test_real_signed_pdf_uses_one_current_selected_sample_only(
    qapp, tmp_path: Path, language: AppLanguage, title: str,
) -> None:
    session, report, observation = _actual_source()
    dataset = session.current_dataset
    assert dataset is not None
    depths = dataset.depth.copy()
    curves = {key: value.values.copy() for key, value in dataset.curves.items()}
    original_report = replace(report)
    identity = default_interpretation_report_identity(report, language)

    plain = export_hydrocarbon_interpretation_pdf_with_passport(
        session, report, tmp_path / "plain.pdf", identity=identity, language=language,
    )
    signed = export_hydrocarbon_interpretation_pdf_with_passport(
        session, report, tmp_path / "selected.pdf", identity=identity, language=language,
        geology_evidence=(observation,),
    )

    assert plain.primary_path.read_bytes().startswith(b"%PDF")
    assert signed.primary_path.read_bytes().startswith(b"%PDF")
    assert title not in _pdf_text(plain.primary_path)
    enriched = _pdf_text(signed.primary_path)
    assert title in enriched
    assert "sample-in" in enriched
    assert "1004.00" in enriched
    assert "1009.00" in enriched

    signed_passport = json.loads(
        passport_sidecar_path(signed.primary_path).read_text(encoding="utf-8")
    )
    plain_passport = json.loads(
        passport_sidecar_path(plain.primary_path).read_text(encoding="utf-8")
    )
    assert (
        "measured_geology_intervals", "1"
    ) in [tuple(item) for item in signed_passport["render"]["options"]]
    assert not any(
        item[0] == "measured_geology_intervals"
        for item in plain_passport["render"]["options"]
    )
    assert report == original_report
    np.testing.assert_array_equal(dataset.depth, depths)
    for key, samples in curves.items():
        np.testing.assert_array_equal(dataset.curves[key].values, samples)


def test_no_selected_geology_does_not_change_legacy_html_output() -> None:
    _, report, _ = _actual_source()
    assert hydrocarbon_interpretation_html(
        report, AppLanguage.EN,
    ) == hydrocarbon_interpretation_html(
        report, AppLanguage.EN, geology_evidence=(),
    )


@pytest.mark.parametrize("change", ("edit", "other_well", "other_dataset", "axis", "candidate"))
def test_signed_pdf_rejects_stale_evidence_before_creating_files(
    qapp, tmp_path: Path, change: str,
) -> None:
    session, report, observation = _actual_source()
    if change == "edit":
        session.current_well.cuttings[0].description = "New geological interpretation"
    elif change == "other_well":
        observation = replace(observation, well_id="foreign-well")
    elif change == "other_dataset":
        observation = replace(observation, dataset_id="unrelated-dataset")
    elif change == "axis":
        observation = replace(observation, depth_axis_id="tvd-axis")
    else:
        report = replace(report, candidates=())

    target = tmp_path / "must-not-exist.pdf"
    with pytest.raises(HydrocarbonInterpretationPdfError, match="evidence"):
        export_hydrocarbon_interpretation_pdf_with_passport(
            session, report, target,
            identity=default_interpretation_report_identity(report, AppLanguage.EN),
            language=AppLanguage.EN,
            geology_evidence=(observation,),
        )
    assert not target.exists()
    assert not passport_sidecar_path(target).exists()


@pytest.mark.parametrize("language", list(AppLanguage))
@pytest.mark.parametrize("existing", (False, True))
@pytest.mark.parametrize("change", ("nan", "inf", "negative_inf", "text", "object", "shape"))
def test_invalid_md_axis_preserves_pdf_and_passport(
    qapp, tmp_path: Path, language: AppLanguage, existing: bool, change: str,
) -> None:
    session, report, observation = _actual_source()
    dataset = session.current_dataset
    assert dataset is not None
    axis = dataset.active_index
    if change in {"nan", "inf", "negative_inf"}:
        axis.values[1] = {"nan": np.nan, "inf": np.inf, "negative_inf": -np.inf}[change]
    elif change == "text":
        axis.values = axis.values.astype(str)
    elif change == "object":
        axis.values = axis.values.astype(object)
    else:
        axis.values = axis.values.reshape(1, -1)
    depths = axis.values.copy()
    curves = {key: curve.values.copy() for key, curve in dataset.curves.items()}
    target = tmp_path / "protected.pdf"
    passport = passport_sidecar_path(target)
    if existing:
        target.write_bytes(b"%PDF-existing-approved-report")
        passport.write_bytes(b'{"existing": "approved passport"}')
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    with pytest.raises(HydrocarbonInterpretationPdfError, match="finite numeric MD axis"):
        export_hydrocarbon_interpretation_pdf_with_passport(
            session, report, target,
            identity=default_interpretation_report_identity(report, language),
            language=language, geology_evidence=(observation,),
        )
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before
    np.testing.assert_array_equal(axis.values, depths)
    for key, values in curves.items():
        np.testing.assert_array_equal(dataset.curves[key].values, values)


def test_measured_zero_and_missing_lba_are_not_synthesized_in_pdf(
    qapp, tmp_path: Path,
) -> None:
    session, report, _ = _actual_source()
    sample = session.current_well.cuttings[0]
    sample.calcite_percent = 0.0
    sample.lba_group = None
    sample.lba_type_id = None
    sample.lba_intensity = None
    sample.lba_color = None
    observation = correlate_gas_interval_with_well_geology(
        session, top_depth=1002.0, bottom_depth=1010.0,
    )
    exported = export_hydrocarbon_interpretation_pdf_with_passport(
        session, report, tmp_path / "zero.pdf",
        language=AppLanguage.EN, geology_evidence=(observation,),
    )
    text = _pdf_text(exported.primary_path)
    assert "Calcite, %: 0.0" in text
    assert "No measurement / record" in text
    assert "lba_group" not in text


@pytest.mark.parametrize("language", tuple(AppLanguage))
@pytest.mark.parametrize("existing", (False, True))
@pytest.mark.parametrize("source_kind", ("lithology", "cuttings", "stratigraphy"))
def test_corrupt_geology_record_md_preserves_signed_pdf_and_passport(
    qapp, tmp_path: Path, language: AppLanguage, existing: bool, source_kind: str,
) -> None:
    from geoworkbench.domain.models import StratigraphyInterval

    session, report, selected = _actual_source()
    well = session.current_well
    dataset = session.current_dataset
    assert well is not None and dataset is not None
    if source_kind == "stratigraphy":
        well.stratigraphy.append(StratigraphyInterval(
            "invalid-stratum", 1004.0, 1009.0, "C1",
        ))
    record = {
        "lithology": well.lithology,
        "cuttings": well.cuttings,
        "stratigraphy": well.stratigraphy,
    }[source_kind][0]
    record.top_depth = np.nan
    original_geology = repr(well)
    original_depth = dataset.depth.copy()
    original_curves = {key: curve.values.copy() for key, curve in dataset.curves.items()}

    target = tmp_path / "protected.pdf"
    passport = passport_sidecar_path(target)
    if existing:
        target.write_bytes(b"%PDF-previous-approved-report")
        passport.write_bytes(b'{"previous": "approved"}')
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}

    with pytest.raises(HydrocarbonInterpretationPdfError, match="finite numeric MD bounds"):
        export_hydrocarbon_interpretation_pdf_with_passport(
            session, report, target,
            identity=default_interpretation_report_identity(report, language),
            language=language, geology_evidence=(selected,),
        )

    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before
    assert repr(well) == original_geology
    np.testing.assert_array_equal(dataset.depth, original_depth)
    for key, values in original_curves.items():
        np.testing.assert_array_equal(dataset.curves[key].values, values)

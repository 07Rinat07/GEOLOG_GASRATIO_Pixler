from __future__ import annotations

from geoworkbench.calculations.opus_gasomer import OPUS_GASOMER_PROFILE_ID
from geoworkbench.calculations.pixler import build_all_sourced_formula_registry
from geoworkbench.services.formula_method_audit import (
    MethodEvidenceLevel,
    build_method_audit_manifest,
    method_audit_record,
)


def test_every_registered_sourced_formula_has_audit_record() -> None:
    registered = {
        profile.profile_id
        for profile in build_all_sourced_formula_registry().available()
    }
    audited = {record.method_id for record in build_method_audit_manifest()}

    assert registered <= audited


def test_primary_publication_profiles_remain_strict() -> None:
    assert method_audit_record("haworth.wetness").strict_primary_verified
    assert method_audit_record("pixler.c1_c2").strict_primary_verified
    assert method_audit_record("dexp.jorden_shirley").strict_primary_verified
    assert method_audit_record(
        "dexp.rehm_mcclendon_corrected"
    ).strict_primary_verified


def test_opus_gasomer_uses_less_strict_workbook_screening_tier() -> None:
    record = method_audit_record(OPUS_GASOMER_PROFILE_ID)

    assert record.evidence_level is MethodEvidenceLevel.WORKBOOK_REPRODUCED
    assert record.calculation_allowed is True
    assert record.strict_primary_verified is False
    assert "workbook" in record.report_disclosure.casefold()
    assert "primary-source verified" in record.report_disclosure.casefold()


def test_opus_detector_is_explicitly_field_calibration_pending() -> None:
    record = method_audit_record(f"{OPUS_GASOMER_PROFILE_ID}.detector")

    assert record.evidence_level is MethodEvidenceLevel.ENGINEERING_DEFAULT
    assert "field calibration" in record.report_disclosure.casefold()


def test_audit_records_have_rights_and_documentation_notes() -> None:
    for record in build_method_audit_manifest():
        rights = record.rights_note.casefold()
        assert record.source_locator
        assert record.documentation
        assert record.rights_note
        assert (
            "copyright" in rights
            or "redistribut" in rights
            or "proprietary" in rights
        )

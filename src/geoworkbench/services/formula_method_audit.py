from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from geoworkbench.calculations.gas_ratio import OPUS_SCREENING_PROFILE_ID
from geoworkbench.calculations.opus_gasomer import (
    OPUS_GASOMER_PROFILE_ID,
    OPUS_GASOMER_PROFILE_VERSION,
    load_opus_gasomer_profile,
)
from geoworkbench.calculations.pixler import (
    FormulaCategory,
    FormulaProfile,
    build_all_sourced_formula_registry,
)


class MethodEvidenceLevel(StrEnum):
    """Evidence tier used by calculation/report QA.

    The tiers are intentionally not binary. Historical/workbook methods such as
    OPUS may remain operational when they are reproducible and transparently
    disclosed even if an open primary publication is unavailable.
    """

    PRIMARY_PUBLICATION = "primary_publication"
    PUBLIC_PATENT_OR_STANDARD = "public_patent_or_standard"
    SECONDARY_CROSSCHECK = "secondary_crosscheck"
    WORKBOOK_REPRODUCED = "workbook_reproduced"
    ENGINEERING_DEFAULT = "engineering_default"


@dataclass(frozen=True, slots=True)
class MethodAuditRecord:
    method_id: str
    version: str
    evidence_level: MethodEvidenceLevel
    source_citation: str
    source_locator: str
    calculation_scope: str
    verification: str
    report_disclosure: str
    documentation: tuple[str, ...]
    rights_note: str
    calculation_allowed: bool = True

    def __post_init__(self) -> None:
        for name, value in (
            ("method_id", self.method_id),
            ("version", self.version),
            ("source_citation", self.source_citation),
            ("source_locator", self.source_locator),
            ("calculation_scope", self.calculation_scope),
            ("verification", self.verification),
            ("report_disclosure", self.report_disclosure),
            ("rights_note", self.rights_note),
        ):
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
        if not self.documentation or any(not item.strip() for item in self.documentation):
            raise ValueError("documentation must contain at least one path")

    @property
    def strict_primary_verified(self) -> bool:
        return self.evidence_level in {
            MethodEvidenceLevel.PRIMARY_PUBLICATION,
            MethodEvidenceLevel.PUBLIC_PATENT_OR_STANDARD,
        }


def build_method_audit_manifest() -> tuple[MethodAuditRecord, ...]:
    """Return the canonical auditable method inventory used by QA and reports."""

    records = [
        _formula_profile_record(profile)
        for profile in build_all_sourced_formula_registry().available()
    ]
    records.extend(_opus_records())
    _validate_manifest(records)
    return tuple(records)


def method_audit_record(method_id: str) -> MethodAuditRecord:
    for record in build_method_audit_manifest():
        if record.method_id == method_id:
            return record
    raise KeyError(f"Unknown method audit record: {method_id}")


def _formula_profile_record(profile: FormulaProfile) -> MethodAuditRecord:
    level = _formula_evidence_level(profile)
    disclosure = {
        MethodEvidenceLevel.PRIMARY_PUBLICATION: (
            "Published formula profile; cite the publication and profile version."
        ),
        MethodEvidenceLevel.PUBLIC_PATENT_OR_STANDARD: (
            "Public patent/standard-derived formula; cite the publication identifier and "
            "state the reference conditions/parameters."
        ),
        MethodEvidenceLevel.SECONDARY_CROSSCHECK: (
            "Secondary-source cross-check; report as screening/supporting evidence."
        ),
        MethodEvidenceLevel.WORKBOOK_REPRODUCED: (
            "Workbook-reproduced method; report as historical/screening evidence."
        ),
        MethodEvidenceLevel.ENGINEERING_DEFAULT: (
            "Engineering default pending field calibration; never present as a universal method."
        ),
    }[level]
    return MethodAuditRecord(
        method_id=profile.profile_id,
        version=profile.version,
        evidence_level=level,
        source_citation=profile.source,
        source_locator=_source_locator(profile.source),
        calculation_scope=(
            f"{profile.expression}; inputs={','.join(profile.required_inputs)}; "
            f"output={profile.output_mnemonic} [{profile.output_unit}]"
        ),
        verification=(
            "FormulaProfileRegistry validates the versioned control example at registration; "
            "input units and output shape are checked by the calculation contract."
        ),
        report_disclosure=disclosure,
        documentation=_documentation_for(profile),
        rights_note=(
            "Only bibliographic metadata, the computational expression and short factual "
            "method notes are stored. Full copyrighted publications are not redistributed."
        ),
    )


def _formula_evidence_level(profile: FormulaProfile) -> MethodEvidenceLevel:
    source = profile.source.casefold()
    if profile.category is FormulaCategory.DEXP:
        return MethodEvidenceLevel.PRIMARY_PUBLICATION
    if profile.profile_id.startswith(("haworth.", "pixler.")):
        return MethodEvidenceLevel.PRIMARY_PUBLICATION
    if "us20" in source or "ep" in source:
        return MethodEvidenceLevel.PUBLIC_PATENT_OR_STANDARD
    return MethodEvidenceLevel.SECONDARY_CROSSCHECK


def _source_locator(source: str) -> str:
    for marker in ("DOI:", "https://", "http://"):
        index = source.find(marker)
        if index >= 0:
            return source[index:].strip()
    return source.strip()


def _documentation_for(profile: FormulaProfile) -> tuple[str, ...]:
    if profile.category is FormulaCategory.DEXP:
        return ("docs/DEXP_FORMULAS.md", "docs/FORMULA_METHOD_AUDIT.md")
    return (
        "docs/MUD_GAS_FORMULAS.md",
        "resources/formulas/README.md",
        "docs/FORMULA_METHOD_AUDIT.md",
    )


def _opus_records() -> tuple[MethodAuditRecord, ...]:
    profile = load_opus_gasomer_profile()
    source = profile["source"]
    source_evidence = profile["source_evidence"]
    workbook_record = MethodAuditRecord(
        method_id=OPUS_GASOMER_PROFILE_ID,
        version=OPUS_GASOMER_PROFILE_VERSION,
        evidence_level=MethodEvidenceLevel.WORKBOOK_REPRODUCED,
        source_citation=(
            f"User-provided applied workbook {source['file_name']} / sheet {source['sheet']}; "
            f"SHA-256 {source['sha256']}. Public cross-checks are recorded in the profile."
        ),
        source_locator="src/geoworkbench/resources/opus_gasomer_profile_v1.json",
        calculation_scope=(
            "Five OPUS Gasomer workbook-derived indicators, data-driven classification bands, "
            "unique-mode production consensus and interval aggregation."
        ),
        verification=(
            "Pinned workbook SHA-256, scalar golden row, boundary tests, vectorized parity and "
            "public cross-checks for the subset documented in open materials."
        ),
        report_disclosure=(
            "OPUS Gasomer is allowed as a historical/workbook screening method. Reports must "
            "label it as workbook-derived/pending field validation; it is not presented as "
            "primary-source verified."
        ),
        documentation=(
            "docs/OPUS_GASOMER_IMPLEMENTATION.md",
            "resources/formulas/README.md",
            "docs/FORMULA_METHOD_AUDIT.md",
        ),
        rights_note=(
            "The source workbook itself is not redistributed by the application. The project "
            "stores a hash, extracted computational contract, errata and short provenance facts."
        ),
    )
    screening_record = MethodAuditRecord(
        method_id=OPUS_SCREENING_PROFILE_ID,
        version="1.0",
        evidence_level=MethodEvidenceLevel.SECONDARY_CROSSCHECK,
        source_citation=(
            "Historical Lukyanov OPUS screening: formulas/ranges cross-checked against available "
            "open industry/academic materials and bibliography; primary full text is not required "
            "for operational screening status."
        ),
        source_locator=str(
            source_evidence["historical_primary_reference"]["catalog_url"]
        ),
        calculation_scope=(
            "Historical C1-C5 relative OPUS screening curves and preliminary "
            "overlapping fluid bands."
        ),
        verification=(
            "Open cross-checks plus repository regression tests; unsupported/proprietary modern "
            "variants are not reconstructed as if published."
        ),
        report_disclosure=(
            "Use as preliminary screening/supporting evidence. Do not describe the historical "
            "palette as a universally validated or proprietary modern OPUS implementation."
        ),
        documentation=(
            "docs/MUD_GAS_FORMULAS.md",
            "resources/formulas/README.md",
            "docs/FORMULA_METHOD_AUDIT.md",
        ),
        rights_note=(
            "The project cites sources and stores only the computational expressions needed for "
            "interoperable calculation; no copyrighted full publication is bundled."
        ),
    )
    detector_record = MethodAuditRecord(
        method_id=f"{OPUS_GASOMER_PROFILE_ID}.detector",
        version=OPUS_GASOMER_PROFILE_VERSION,
        evidence_level=MethodEvidenceLevel.ENGINEERING_DEFAULT,
        source_citation=(
            "Project engineering detector defaults versioned inside opus_gasomer_profile_v1.json."
        ),
        source_locator="src/geoworkbench/resources/opus_gasomer_profile_v1.json#detector",
        calculation_scope=(
            "Robust local background, delta-gas, robust-z and contrast thresholds used to propose "
            "candidate intervals before OPUS interval screening."
        ),
        verification=(
            "Deterministic tests and versioned parameters; field calibration is still required."
        ),
        report_disclosure=(
            "Always state that detector thresholds are project engineering defaults pending field "
            "calibration, not universal Lukyanov/OPUS thresholds."
        ),
        documentation=(
            "docs/OPUS_GASOMER_IMPLEMENTATION.md",
            "docs/FORMULA_METHOD_AUDIT.md",
        ),
        rights_note=(
            "Project-authored engineering defaults; no third-party proprietary "
            "threshold set is claimed."
        ),
    )
    return workbook_record, screening_record, detector_record


def _validate_manifest(records: list[MethodAuditRecord]) -> None:
    identifiers: set[str] = set()
    for record in records:
        if record.method_id in identifiers:
            raise ValueError(f"Duplicate method audit record: {record.method_id}")
        identifiers.add(record.method_id)
        if not record.calculation_allowed:
            raise ValueError(f"Disabled method must not be in runtime manifest: {record.method_id}")


__all__ = [
    "MethodAuditRecord",
    "MethodEvidenceLevel",
    "build_method_audit_manifest",
    "method_audit_record",
]

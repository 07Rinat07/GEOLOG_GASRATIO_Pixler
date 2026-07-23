from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Sequence

import numpy as np

from geoworkbench import __version__
from geoworkbench.calculations.pixler import build_all_sourced_formula_registry
from geoworkbench.domain.models import CurveData, Dataset, MasterlogTemplate
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.coverage import (
    ChannelCoverage,
    analyze_curve_coverage,
    unavailable_channel_coverage,
)

if TYPE_CHECKING:
    from geoworkbench.forms.models import FormDocument
    from geoworkbench.tablet.models import TabletLayout


REPORT_PASSPORT_SCHEMA_VERSION = 2
REPORT_PASSPORT_SUFFIX = ".passport.json"


class ReportPassportError(RuntimeError):
    pass


class ReportKind(StrEnum):
    VIEW = "view"
    MASTERLOG = "masterlog"
    INTERPRETATION = "interpretation"
    INTERVAL = "interval"


@dataclass(frozen=True, slots=True)
class ReportIntervalSnapshot:
    index_id: str
    mnemonic: str
    role: str
    index_type: str
    unit: str | None
    start: float | str
    end: float | str
    sample_count: int
    index_values_sha256: str


@dataclass(frozen=True, slots=True)
class ReportSourceFingerprint:
    kind: str
    name: str
    sha256: str
    size_bytes: int
    capture: str


@dataclass(frozen=True, slots=True)
class ReportChannelSnapshot:
    curve_id: str
    original_mnemonic: str
    canonical_mnemonic: str | None
    canonical_kind: str | None
    quantity_class: str | None
    source_uom: str | None
    canonical_uom: str | None
    display_uom: str | None
    sensor_id: str | None
    semantic_source: str | None
    family: str | None
    category: str | None
    confidence: float | None
    matched_by: str | None
    aliases: tuple[str, ...]
    evidence: tuple[str, ...]
    source_dataset_id: str
    provenance: str
    version: int
    state: str
    values_sha256: str


@dataclass(frozen=True, slots=True)
class ReportCoverageSnapshot:
    channel_key: str
    mnemonic: str
    availability: str
    primary_state: str
    total_count: int
    observed_count: int
    zero_count: int
    missing_count: int
    unavailable_count: int
    coverage_percent: float
    missing_percent: float
    zero_percent: float
    zero_percent_of_observed: float


@dataclass(frozen=True, slots=True)
class ReportFormulaSnapshot:
    formula_kind: str
    formula_id: str
    version: str
    provenance: str
    curve_ids: tuple[str, ...]
    expression_sha256: str | None = None
    source: str | None = None


@dataclass(frozen=True, slots=True)
class ReportFormSnapshot:
    form_kind: str
    form_id: str
    name: str
    revision: str
    definition_sha256: str


@dataclass(frozen=True, slots=True)
class ReportRenderSettings:
    renderer: str
    output_format: str
    page_format: str | None = None
    orientation: str | None = None
    dpi: int | None = None
    image_quality: int | None = None
    fit_form_columns: bool | None = None
    margins_mm: tuple[float, float, float, float] | None = None
    range_mode: str | None = None
    units_per_page: float | None = None
    overlap: float | None = None
    show_page_numbers: bool | None = None
    show_page_range: bool | None = None
    strict_unicode: bool | None = None
    options: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.renderer.strip() or not self.output_format.strip():
            raise ValueError("Renderer и формат вывода Report Passport не должны быть пустыми")
        if self.dpi is not None and self.dpi <= 0:
            raise ValueError("DPI Report Passport должен быть положительным")
        if self.image_quality is not None and not 0 <= self.image_quality <= 100:
            raise ValueError("Качество изображения должно находиться в диапазоне 0–100")
        if self.margins_mm is not None and any(value < 0 for value in self.margins_mm):
            raise ValueError("Поля Report Passport не могут быть отрицательными")
        if self.units_per_page is not None and self.units_per_page <= 0:
            raise ValueError("Размер диапазона на странице должен быть положительным")
        if self.overlap is not None and self.overlap < 0:
            raise ValueError("Перекрытие страниц не может быть отрицательным")
        if any(not key.strip() for key, _value in self.options):
            raise ValueError("Имена дополнительных параметров рендера не должны быть пустыми")


@dataclass(frozen=True, slots=True)
class ReportPassport:
    schema_version: int
    application_version: str
    report_kind: ReportKind
    report_name: str
    project_id: str
    project_name: str
    well_id: str
    well_name: str
    dataset_id: str
    dataset_name: str
    dataset_sha256: str
    interval: ReportIntervalSnapshot | None
    sources: tuple[ReportSourceFingerprint, ...]
    channels: tuple[ReportChannelSnapshot, ...]
    coverage: tuple[ReportCoverageSnapshot, ...]
    formulas: tuple[ReportFormulaSnapshot, ...]
    form: ReportFormSnapshot
    language: str
    render: ReportRenderSettings
    warnings: tuple[str, ...]
    passport_sha256: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != REPORT_PASSPORT_SCHEMA_VERSION:
            raise ValueError("Неподдерживаемая версия Report Passport")
        if not self.report_name.strip():
            raise ValueError("Имя отчёта не должно быть пустым")
        for value in (
            self.project_id,
            self.project_name,
            self.well_id,
            self.well_name,
            self.dataset_id,
            self.dataset_name,
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Report Passport содержит пустой идентификатор или имя")
        _validate_sha256(self.dataset_sha256, "dataset_sha256")
        if self.interval is not None:
            if self.interval.sample_count <= 0:
                raise ValueError("Интервал Report Passport должен содержать хотя бы один отсчёт")
            _validate_sha256(
                self.interval.index_values_sha256, "interval.index_values_sha256"
            )
        for source in self.sources:
            _validate_sha256(source.sha256, "source.sha256")
            if source.size_bytes < 0:
                raise ValueError("Размер источника Report Passport не может быть отрицательным")
        for channel in self.channels:
            _validate_sha256(channel.values_sha256, "channel.values_sha256")
        for item in self.coverage:
            if item.total_count < 0:
                raise ValueError("Coverage Report Passport содержит отрицательный total_count")
        for formula in self.formulas:
            if formula.expression_sha256 is not None:
                _validate_sha256(formula.expression_sha256, "formula.expression_sha256")
        _validate_sha256(self.form.definition_sha256, "form.definition_sha256")
        _language_value(self.language)
        if self.passport_sha256:
            _validate_sha256(self.passport_sha256, "passport_sha256")

    def payload(self, *, include_digest: bool = True) -> dict[str, Any]:
        payload = _json_ready(asdict(self))
        if not include_digest:
            payload.pop("passport_sha256", None)
        return payload

    def canonical_json(self, *, include_digest: bool = True) -> str:
        return _canonical_json(self.payload(include_digest=include_digest))

    def verify(self) -> bool:
        return bool(self.passport_sha256) and self.passport_sha256 == _passport_digest(self)


@dataclass(frozen=True, slots=True)
class ReportPassportRequest:
    report_kind: ReportKind
    report_name: str
    language: str
    render: ReportRenderSettings
    interval: tuple[float | str, float | str] | None = None
    curve_mnemonics: tuple[str, ...] | None = None
    form: ReportFormSnapshot | None = None


class ReportPassportBuilder:
    """Build a deterministic provenance snapshot for one concrete report."""

    def build(self, session: ProjectSession, request: ReportPassportRequest) -> ReportPassport:
        well = session.current_well
        dataset = session.current_dataset
        if well is None or dataset is None:
            raise ReportPassportError("Для Report Passport требуется выбранный dataset")

        warnings: list[str] = []
        curves, missing_curves = _selected_curves(dataset, request.curve_mnemonics)
        warnings.extend(f"curve-not-found:{mnemonic}" for mnemonic in missing_curves)
        interval = _interval_snapshot(dataset, request.interval)
        interval_mask = _interval_mask(dataset.active_index.values, interval)
        channels = tuple(_channel_snapshot(curve, interval_mask) for curve in curves)
        coverage = tuple(
            _coverage_snapshot(analyze_curve_coverage(curve, np.flatnonzero(interval_mask)))
            for curve in curves
        ) + tuple(
            _coverage_snapshot(unavailable_channel_coverage(mnemonic, int(np.count_nonzero(interval_mask))))
            for mnemonic in missing_curves
        )
        form = request.form or tablet_layout_form_snapshot(
            session.current_tablet_layout,
            dataset_id=dataset.dataset_id,
            name=request.report_name,
        )
        formulas = _formula_snapshots(session, curves)
        dataset_digest = _dataset_digest(dataset, curves, interval, interval_mask)
        sources = _source_fingerprints(
            session,
            dataset,
            curves,
            dataset_digest,
            _report_data_size_bytes(dataset, curves, interval_mask),
            warnings,
        )

        unsigned = ReportPassport(
            schema_version=REPORT_PASSPORT_SCHEMA_VERSION,
            application_version=__version__,
            report_kind=request.report_kind,
            report_name=request.report_name.strip(),
            project_id=session.project.project_id,
            project_name=session.project.name,
            well_id=well.well_id,
            well_name=well.name,
            dataset_id=dataset.dataset_id,
            dataset_name=dataset.name,
            dataset_sha256=dataset_digest,
            interval=interval,
            sources=sources,
            channels=channels,
            coverage=coverage,
            formulas=formulas,
            form=form,
            language=_language_value(request.language),
            render=request.render,
            warnings=tuple(sorted(set(warnings))),
        )
        return replace(unsigned, passport_sha256=_passport_digest(unsigned))

    def build_artifact(
        self,
        session: ProjectSession,
        request: ReportPassportRequest,
        *,
        artifact_id: str,
        artifact_name: str,
        payload: Mapping[str, Any],
        interval: ReportIntervalSnapshot | None = None,
    ) -> ReportPassport:
        """Build a passport for a persisted well-level report without a required dataset."""

        well = session.current_well
        if well is None:
            raise ReportPassportError("Для Report Passport требуется выбранная скважина")
        if not artifact_id.strip() or not artifact_name.strip():
            raise ReportPassportError("Artifact ID и имя Report Passport не должны быть пустыми")
        normalized_payload = _json_ready(payload)
        encoded = _canonical_json(normalized_payload).encode("utf-8")
        artifact_digest = sha256(encoded).hexdigest()
        form = request.form or report_definition_snapshot(
            artifact_id, request.report_name, {"report_kind": request.report_kind.value}
        )
        source = ReportSourceFingerprint(
            "report-data-snapshot",
            artifact_name.strip(),
            artifact_digest,
            len(encoded),
            "normalized-project-data",
        )
        unsigned = ReportPassport(
            schema_version=REPORT_PASSPORT_SCHEMA_VERSION,
            application_version=__version__,
            report_kind=request.report_kind,
            report_name=request.report_name.strip(),
            project_id=session.project.project_id,
            project_name=session.project.name,
            well_id=well.well_id,
            well_name=well.name,
            dataset_id=artifact_id.strip(),
            dataset_name=artifact_name.strip(),
            dataset_sha256=artifact_digest,
            interval=interval,
            sources=(source,),
            channels=(),
            coverage=(),
            formulas=(),
            form=form,
            language=_language_value(request.language),
            render=request.render,
            warnings=(),
        )
        return replace(unsigned, passport_sha256=_passport_digest(unsigned))


def report_definition_snapshot(
    definition_id: str,
    name: str,
    definition: Mapping[str, Any],
    *,
    schema_version: int = 1,
) -> ReportFormSnapshot:
    return _form_snapshot(
        "report-definition",
        definition_id,
        name,
        f"schema:{schema_version}",
        definition,
        content_revision=True,
    )


def depth_interval_snapshot(
    intervals: Sequence[tuple[float, float]],
    *,
    index_id: str = "depth-intervals",
    mnemonic: str = "DEPTH",
    index_type: str = "md",
    unit: str | None = None,
) -> ReportIntervalSnapshot | None:
    if not intervals:
        return None
    values = np.asarray(intervals, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 2 or not np.all(np.isfinite(values)):
        raise ReportPassportError("Интервалы отчёта должны содержать конечные пары кровля–подошва")
    lower = float(np.min(values))
    upper = float(np.max(values))
    if lower == upper:
        raise ReportPassportError("Интервалы отчёта должны иметь ненулевую мощность")
    return ReportIntervalSnapshot(
        index_id=index_id,
        mnemonic=mnemonic,
        role="depth",
        index_type=index_type,
        unit=unit,
        start=lower,
        end=upper,
        sample_count=int(values.shape[0]),
        index_values_sha256=_array_digest(values.reshape(-1)),
    )


def form_document_snapshot(
    form: "FormDocument", *, schema_version: int = 4
) -> ReportFormSnapshot:
    return _form_snapshot(
        "form-document",
        form.form_id,
        form.name,
        f"schema:{schema_version}",
        asdict(form),
        content_revision=True,
    )


def tablet_layout_form_snapshot(
    layout: "TabletLayout | None",
    *,
    dataset_id: str,
    name: str,
) -> ReportFormSnapshot:
    if layout is None:
        return _form_snapshot(
            "view", dataset_id, name, "schema:1", {"name": name}, content_revision=True
        )
    return _form_snapshot(
        "tablet-layout",
        dataset_id,
        name,
        "schema:14",
        asdict(layout),
        content_revision=True,
    )


def masterlog_template_snapshot(template: MasterlogTemplate) -> ReportFormSnapshot:
    return _form_snapshot(
        "masterlog-template",
        template.template_id,
        template.name,
        f"version:{template.version}",
        asdict(template),
    )


def passport_sidecar_path(output: str | Path) -> Path:
    target = Path(output)
    return target.with_name(target.name + REPORT_PASSPORT_SUFFIX)


def write_report_passport(
    passport: ReportPassport,
    output: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    if not passport.verify():
        raise ReportPassportError("Report Passport имеет неверный контрольный SHA-256")
    destination = passport_sidecar_path(output)
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        passport.payload(),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    descriptor, name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        if isinstance(exc, FileExistsError):
            raise
        raise ReportPassportError(f"Не удалось записать Report Passport: {destination}") from exc
    return destination


def load_report_passport(source: str | Path) -> dict[str, Any]:
    path = Path(source)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReportPassportError(f"Не удалось прочитать Report Passport: {path}") from exc
    if not isinstance(payload, dict):
        raise ReportPassportError("Report Passport должен быть JSON-объектом")
    digest = payload.get("passport_sha256")
    if not isinstance(digest, str):
        raise ReportPassportError("Report Passport не содержит passport_sha256")
    unsigned = dict(payload)
    unsigned.pop("passport_sha256", None)
    if digest != sha256(_canonical_json(unsigned).encode("utf-8")).hexdigest():
        raise ReportPassportError("Контрольный SHA-256 Report Passport не совпадает")
    return payload


def _form_snapshot(
    kind: str,
    form_id: str,
    name: str,
    revision: str,
    definition: Mapping[str, Any] | dict[str, Any],
    *,
    content_revision: bool = False,
) -> ReportFormSnapshot:
    digest = sha256(_canonical_json(_json_ready(definition)).encode("utf-8")).hexdigest()
    resolved_revision = f"{revision}/content:{digest[:12]}" if content_revision else revision
    return ReportFormSnapshot(kind, form_id, name, resolved_revision, digest)


def _selected_curves(
    dataset: Dataset,
    mnemonics: tuple[str, ...] | None,
) -> tuple[tuple[CurveData, ...], tuple[str, ...]]:
    if mnemonics is None:
        curves = tuple(sorted(dataset.curves.values(), key=lambda item: item.metadata.curve_id))
        return curves, ()
    selected: dict[str, CurveData] = {}
    missing: list[str] = []
    for mnemonic in mnemonics:
        curve = dataset.curve_by_mnemonic(mnemonic)
        if curve is None:
            missing.append(mnemonic)
            continue
        selected[curve.metadata.curve_id] = curve
    return tuple(selected[key] for key in sorted(selected)), tuple(sorted(set(missing)))


def _interval_snapshot(
    dataset: Dataset,
    requested: tuple[float | str, float | str] | None,
) -> ReportIntervalSnapshot:
    index = dataset.active_index
    if requested is None:
        start, end = _index_bounds(index.values)
    else:
        start, end = requested
    if start == end:
        raise ReportPassportError("Интервал Report Passport должен иметь разные границы")
    normalized_start = _scalar_value(start)
    normalized_end = _scalar_value(end)
    provisional = ReportIntervalSnapshot(
        index.index_id,
        index.mnemonic,
        index.role.value,
        index.index_type.value,
        index.unit,
        normalized_start,
        normalized_end,
        1,
        "0" * 64,
    )
    mask = _interval_mask(index.values, provisional)
    selected = np.asarray(index.values)[mask]
    if selected.size == 0:
        raise ReportPassportError("Интервал отчёта не содержит отсчётов активного индекса")
    return replace(
        provisional,
        sample_count=int(selected.size),
        index_values_sha256=_array_digest(selected),
    )


def _index_bounds(values: np.ndarray[Any, Any]) -> tuple[float | str, float | str]:
    array = np.asarray(values)
    if array.size == 0:
        raise ReportPassportError("Активный индекс dataset пуст")
    if np.issubdtype(array.dtype, np.datetime64):
        valid = array[~np.isnat(array)]
        if valid.size == 0:
            raise ReportPassportError("Активный datetime-индекс не содержит значений")
        return (
            np.datetime_as_string(valid.min(), unit="ns"),
            np.datetime_as_string(valid.max(), unit="ns"),
        )
    try:
        numeric = np.asarray(array, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ReportPassportError("Активный индекс нельзя представить в паспорте") from exc
    finite = numeric[np.isfinite(numeric)]
    if finite.size == 0:
        raise ReportPassportError("Активный индекс не содержит конечных значений")
    return float(np.min(finite)), float(np.max(finite))


def _source_fingerprints(
    session: ProjectSession,
    dataset: Dataset,
    curves: Sequence[CurveData],
    report_data_sha256: str,
    report_data_size_bytes: int,
    warnings: list[str],
) -> tuple[ReportSourceFingerprint, ...]:
    sources: dict[tuple[str, str], ReportSourceFingerprint] = {}
    source_dataset_ids = {dataset.dataset_id}
    source_dataset_ids.update(curve.metadata.source_dataset_id for curve in curves)

    for dataset_id in sorted(source_dataset_ids):
        source_dataset = _project_dataset(session, dataset_id)
        if source_dataset is None:
            warnings.append(f"source-dataset-not-found:{dataset_id}")
            continue
        captured = False
        report = session.import_reports.get(dataset_id)
        if report is not None:
            snapshot = report.source
            sources[("import-source", snapshot.sha256)] = ReportSourceFingerprint(
                "import-source",
                snapshot.path.name,
                snapshot.sha256,
                snapshot.size_bytes,
                "stored-at-import",
            )
            captured = True
        document = session.source_documents.get(dataset_id)
        if document is not None:
            sources[("lossless-las", document.sha256)] = ReportSourceFingerprint(
                "lossless-las",
                (
                    source_dataset.source_path.name
                    if source_dataset.source_path is not None
                    else source_dataset.name
                ),
                document.sha256,
                document.size_bytes,
                "embedded-project-artifact",
            )
            captured = True

        if captured:
            continue
        external_captured = False
        for source in _external_source_paths(source_dataset):
            if not source.is_file() or source.is_symlink():
                continue
            try:
                digest, size = _file_digest(source)
            except OSError:
                warnings.append(f"source-unreadable:{source.name}")
                continue
            sources[("external-source", digest)] = ReportSourceFingerprint(
                "external-source", source.name, digest, size, "captured-at-report-time"
            )
            external_captured = True
        if external_captured:
            warnings.append(f"source-fingerprint-captured-at-report-time:{source_dataset.name}")
        elif source_dataset.source_path is not None or source_dataset.parameters.get(
            "SOURCE_BUNDLE", ""
        ):
            warnings.append(f"source-file-not-available:{source_dataset.name}")

    sources[("dataset-snapshot", report_data_sha256)] = ReportSourceFingerprint(
        "dataset-snapshot",
        dataset.name,
        report_data_sha256,
        report_data_size_bytes,
        "normalized-report-data",
    )
    return tuple(sorted(sources.values(), key=lambda item: (item.kind, item.name, item.sha256)))


def _project_dataset(session: ProjectSession, dataset_id: str) -> Dataset | None:
    for well in session.project.wells.values():
        found = well.datasets.get(dataset_id)
        if found is not None:
            return found
    return None


def _external_source_paths(dataset: Dataset) -> tuple[Path, ...]:
    paths: list[Path] = []
    if dataset.source_path is not None:
        paths.append(dataset.source_path)
    bundle = dataset.parameters.get("SOURCE_BUNDLE", "")
    if bundle:
        paths.extend(Path(item.strip()) for item in bundle.split(";") if item.strip())
    unique: dict[str, Path] = {}
    for path in paths:
        try:
            key = str(path.resolve(strict=False))
        except OSError:
            key = str(path)
        unique[key] = path
    return tuple(unique[key] for key in sorted(unique))


def _file_digest(path: Path) -> tuple[str, int]:
    digest = sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            size += len(chunk)
            digest.update(chunk)
    return digest.hexdigest(), size


def _channel_snapshot(
    curve: CurveData,
    interval_mask: np.ndarray[Any, Any] | None = None,
) -> ReportChannelSnapshot:
    metadata = curve.metadata
    semantic = metadata.semantic
    values = np.asarray(curve.values)
    if interval_mask is not None:
        if values.shape != interval_mask.shape:
            raise ReportPassportError(
                f"Размер кривой {metadata.original_mnemonic} не совпадает с активным индексом"
            )
        values = values[interval_mask]
    return ReportChannelSnapshot(
        curve_id=metadata.curve_id,
        original_mnemonic=metadata.original_mnemonic,
        canonical_mnemonic=metadata.canonical_mnemonic,
        canonical_kind=semantic.canonical_kind if semantic is not None else None,
        quantity_class=semantic.quantity_class.value if semantic is not None else None,
        source_uom=semantic.source_uom if semantic is not None else metadata.unit,
        canonical_uom=semantic.canonical_uom if semantic is not None else None,
        display_uom=metadata.unit,
        sensor_id=semantic.sensor_id if semantic is not None else None,
        semantic_source=semantic.source if semantic is not None else None,
        family=semantic.family if semantic is not None else None,
        category=semantic.category if semantic is not None else None,
        confidence=semantic.confidence if semantic is not None else None,
        matched_by=semantic.matched_by if semantic is not None else None,
        aliases=semantic.aliases if semantic is not None else (),
        evidence=semantic.evidence if semantic is not None else (),
        source_dataset_id=metadata.source_dataset_id,
        provenance=metadata.provenance,
        version=curve.version,
        state=curve.state.value,
        values_sha256=_array_digest(values),
    )


def _coverage_snapshot(item: ChannelCoverage) -> ReportCoverageSnapshot:
    payload = item.payload()
    return ReportCoverageSnapshot(
        channel_key=item.channel_key,
        mnemonic=item.mnemonic,
        availability=item.availability.value,
        primary_state=item.primary_state.value,
        total_count=item.total_count,
        observed_count=item.observed_count,
        zero_count=item.zero_count,
        missing_count=item.missing_count,
        unavailable_count=item.unavailable_count,
        coverage_percent=float(payload["coverage_percent"]),
        missing_percent=float(payload["missing_percent"]),
        zero_percent=float(payload["zero_percent"]),
        zero_percent_of_observed=float(payload["zero_percent_of_observed"]),
    )

def _formula_snapshots(
    session: ProjectSession,
    curves: Sequence[CurveData],
) -> tuple[ReportFormulaSnapshot, ...]:
    grouped: dict[tuple[str, str, str, str], list[str]] = {}
    for curve in curves:
        parsed = _parse_formula_provenance(curve.metadata.provenance)
        if parsed is None:
            continue
        kind, formula_id, version = parsed
        grouped.setdefault((kind, formula_id, version, curve.metadata.provenance), []).append(
            curve.metadata.curve_id
        )

    registry = _formula_registry()
    snapshots: list[ReportFormulaSnapshot] = []
    for (kind, formula_id, version, provenance), curve_ids in sorted(grouped.items()):
        expression_sha256: str | None = None
        source: str | None = None
        if kind == "calculation":
            try:
                passport = registry.passport(formula_id)
            except KeyError:
                pass
            else:
                expression_sha256 = sha256(passport.expression.encode("utf-8")).hexdigest()
                source = passport.source
                version = passport.version
        elif kind == "custom-formula":
            definition = session.project.custom_formulas.get(formula_id)
            if definition is not None:
                expression_sha256 = sha256(definition.expression.encode("utf-8")).hexdigest()
                source = "project-custom-formula"
                version = str(definition.version)
        snapshots.append(
            ReportFormulaSnapshot(
                kind,
                formula_id,
                version,
                provenance,
                tuple(sorted(curve_ids)),
                expression_sha256,
                source,
            )
        )
    return tuple(snapshots)


@lru_cache(maxsize=1)
def _formula_registry():
    return build_all_sourced_formula_registry()


def _parse_formula_provenance(provenance: str) -> tuple[str, str, str] | None:
    parts = provenance.split(":")
    if len(parts) < 3 or parts[0] not in {"calculation", "custom-formula"}:
        return None
    formula_id = parts[1].strip()
    version = parts[2].strip()
    if not formula_id or not version:
        return None
    return parts[0], formula_id, version


def _dataset_digest(
    dataset: Dataset,
    curves: Sequence[CurveData],
    interval: ReportIntervalSnapshot,
    interval_mask: np.ndarray[Any, Any],
) -> str:
    metadata = {
        "dataset_id": dataset.dataset_id,
        "name": dataset.name,
        "kind": dataset.kind.value,
        "depth_domain": dataset.depth_domain.value,
        "active_index": {
            "index_id": dataset.active_index.index_id,
            "mnemonic": dataset.active_index.mnemonic,
            "type": dataset.active_index.index_type.value,
            "role": dataset.active_index.role.value,
            "unit": dataset.active_index.unit,
            "values_sha256": interval.index_values_sha256,
        },
        "interval": _json_ready(asdict(interval)),
        "channels": [
            _json_ready(asdict(_channel_snapshot(curve, interval_mask))) for curve in curves
        ],
    }
    return sha256(_canonical_json(metadata).encode("utf-8")).hexdigest()


def _interval_mask(
    values: np.ndarray[Any, Any],
    interval: ReportIntervalSnapshot,
) -> np.ndarray[Any, Any]:
    array = np.asarray(values)
    if array.ndim != 1:
        raise ReportPassportError("Активный индекс Report Passport должен быть одномерным")
    if np.issubdtype(array.dtype, np.datetime64):
        try:
            start = np.datetime64(str(interval.start), "ns")
            end = np.datetime64(str(interval.end), "ns")
        except ValueError as exc:
            raise ReportPassportError("Границы datetime-интервала имеют неверный формат") from exc
        if start == end:
            raise ReportPassportError("Интервал Report Passport должен иметь разные границы")
        lower, upper = (start, end) if start <= end else (end, start)
        normalized = array.astype("datetime64[ns]")
        return (~np.isnat(normalized)) & (normalized >= lower) & (normalized <= upper)
    try:
        numeric = np.asarray(array, dtype=np.float64)
        start = float(interval.start)
        end = float(interval.end)
    except (TypeError, ValueError) as exc:
        raise ReportPassportError("Границы числового интервала имеют неверный формат") from exc
    if not np.isfinite(start) or not np.isfinite(end):
        raise ReportPassportError("Границы интервала должны быть конечными")
    if start == end:
        raise ReportPassportError("Интервал Report Passport должен иметь разные границы")
    lower, upper = (start, end) if start <= end else (end, start)
    return np.isfinite(numeric) & (numeric >= lower) & (numeric <= upper)


def _report_data_size_bytes(
    dataset: Dataset,
    curves: Sequence[CurveData],
    interval_mask: np.ndarray[Any, Any],
) -> int:
    size = _normalized_array_size_bytes(np.asarray(dataset.active_index.values)[interval_mask])
    for curve in curves:
        values = np.asarray(curve.values)
        if values.shape != interval_mask.shape:
            raise ReportPassportError(
                f"Размер кривой {curve.metadata.original_mnemonic} не совпадает с активным индексом"
            )
        size += _normalized_array_size_bytes(values[interval_mask])
    return size


def _normalized_array_size_bytes(values: np.ndarray[Any, Any]) -> int:
    array = np.asarray(values)
    if np.issubdtype(array.dtype, np.datetime64) or np.issubdtype(array.dtype, np.number):
        return int(array.size * 8)
    return sum(8 + len(str(item).encode("utf-8")) for item in array.reshape(-1))

def _array_digest(values: np.ndarray[Any, Any]) -> str:
    array = np.asarray(values)
    digest = sha256()
    digest.update(str(array.shape).encode("ascii"))
    if np.issubdtype(array.dtype, np.datetime64):
        normalized = array.astype("datetime64[ns]").astype("<i8", copy=False)
        digest.update(b"datetime64[ns]\0")
        digest.update(normalized.tobytes(order="C"))
        return digest.hexdigest()
    if np.issubdtype(array.dtype, np.number):
        normalized = np.asarray(array, dtype="<f8").copy()
        normalized[np.isnan(normalized)] = np.nan
        normalized[normalized == 0.0] = 0.0
        digest.update(b"float64\0")
        digest.update(normalized.tobytes(order="C"))
        return digest.hexdigest()
    digest.update(b"text\0")
    for item in array.reshape(-1):
        payload = str(item).encode("utf-8")
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def _passport_digest(passport: ReportPassport) -> str:
    return sha256(passport.canonical_json(include_digest=False).encode("utf-8")).hexdigest()


def _canonical_json(payload: Any) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _json_ready(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Path):
        return value.name
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_ready(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float):
        if not np.isfinite(value):
            raise ReportPassportError("Report Passport не поддерживает NaN/Infinity в метаданных")
        return value
    return value


def _scalar_value(value: float | str) -> float | str:
    if isinstance(value, str):
        return value
    numeric = float(value)
    if not np.isfinite(numeric):
        raise ReportPassportError("Граница Report Passport должна быть конечной")
    return numeric


def _language_value(value: Any) -> str:
    raw = getattr(value, "value", value)
    language = str(raw).strip().lower()
    if language not in {"ru", "kk", "en"}:
        raise ReportPassportError("Язык Report Passport должен быть ru, kk или en")
    return language


def _validate_sha256(value: str, field_name: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{field_name} имеет неверный формат SHA-256")

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from geoworkbench.domain.models import (
    CalculationState,
    CanvasObject,
    CurveData,
    CurveMetadata,
    CustomFormulaDefinition,
    CuttingsComponent,
    CuttingsSample,
    Dataset,
    DatasetIndex,
    DatasetKind,
    DepthDomain,
    IndexRole,
    IndexType,
    TimeDepthAggregationPolicy,
    TimeDepthMappingProfile,
    LithologyInterval,
    InterpretationInterval,
    WellInterpretation,
    MasterlogColumnTemplate,
    MasterlogCurveStyle,
    MasterlogHeaderElement,
    MasterlogTemplate,
    Project,
    ProjectLithotype,
    ProjectStratigraphyUnit,
    StratigraphyInterval,
    Well,
    ExportProfile,
)
from geoworkbench.tablet.layout_codec import TabletLayoutFormatError, layout_from_dict
from geoworkbench.tablet.models import TabletLayout
from geoworkbench.catalogs.sensors import normalize_sensor_key
from geoworkbench.storage.project_migrations import (
    ProjectMigrationError,
    migrate_project_payload,
)
from geoworkbench.data.lossless_las import LosslessLasDocument
from geoworkbench.data.las_import_report import (
    LasImportIssue,
    LasImportReport,
    LasIssueSeverity,
    LasSourceSnapshot,
    validate_import_report,
)
from geoworkbench.services.depth_axis import DepthAxisReport, DepthDirection
from geoworkbench.services.las_parameter_resolver import infer_canonical_mnemonic
from geoworkbench.services.semantic_channels import (
    SemanticChannelBinding,
    default_semantic_channel_dictionary,
)
from geoworkbench.services.uom_dictionary import QuantityClass
from geoworkbench.services.text_normalization import clean_display_text, clean_mnemonic
from geoworkbench.printing.image_assets import ImageAsset, ImageAssetError, load_image_assets
from geoworkbench.storage.source_artifacts import (
    SourceArtifactError,
    load_source_documents,
    validate_artifact_manifest,
)


PROJECT_FORMAT_VERSION = 16


@dataclass(slots=True)
class ProjectDocument:
    project: Project
    tablet_layouts: dict[str, TabletLayout] = field(default_factory=dict)
    tablet_presets: dict[str, TabletLayout] = field(default_factory=dict)
    source_documents: dict[str, LosslessLasDocument] = field(default_factory=dict)
    import_reports: dict[str, LasImportReport] = field(default_factory=dict)
    image_assets: dict[str, ImageAsset] = field(default_factory=dict)


class ProjectFormatError(RuntimeError):
    """Raised when a project JSON file cannot be safely reconstructed."""


def _required(data: dict[str, Any], key: str, expected: type) -> Any:
    value = data.get(key)
    if not isinstance(value, expected):
        raise ProjectFormatError(f"Поле '{key}' отсутствует или имеет неверный тип")
    return value


def _required_int(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ProjectFormatError(f"Поле '{key}' отсутствует или не является целым числом")
    return value


def _semantic_binding_from_dict(data: dict[str, Any]) -> SemanticChannelBinding:
    raw_aliases = data.get("aliases", [])
    raw_evidence = data.get("evidence", [])
    if not isinstance(raw_aliases, list) or not all(
        isinstance(item, str) for item in raw_aliases
    ):
        raise ProjectFormatError("Semantic aliases must be a list of strings")
    if not isinstance(raw_evidence, list) or not all(
        isinstance(item, str) for item in raw_evidence
    ):
        raise ProjectFormatError("Semantic evidence must be a list of strings")
    try:
        return SemanticChannelBinding(
            canonical_kind=str(_required(data, "canonical_kind", str)),
            canonical_mnemonic=clean_mnemonic(_required(data, "canonical_mnemonic", str)),
            quantity_class=QuantityClass(str(_required(data, "quantity_class", str))),
            canonical_uom=clean_display_text(data.get("canonical_uom")) or None,
            source_uom=clean_display_text(data.get("source_uom")) or None,
            aliases=tuple(raw_aliases),
            sensor_id=(str(data["sensor_id"]) if data.get("sensor_id") is not None else None),
            source=(str(data["source"]) if data.get("source") is not None else None),
            family=str(data.get("family", "other")),
            category=str(data.get("category", "unknown")),
            source_mnemonic=clean_display_text(_required(data, "source_mnemonic", str)),
            confidence=float(data.get("confidence", 0.0)),
            matched_by=str(data.get("matched_by", "unresolved")),
            evidence=tuple(raw_evidence),
        )
    except (TypeError, ValueError) as exc:
        raise ProjectFormatError("Invalid semantic channel binding") from exc


def _curve_from_dict(data: dict[str, Any]) -> CurveData:
    metadata_data = _required(data, "metadata", dict)
    original_mnemonic = clean_mnemonic(_required(metadata_data, "original_mnemonic", str))
    stored_canonical = (
        clean_mnemonic(metadata_data.get("canonical_mnemonic"))
        if metadata_data.get("canonical_mnemonic")
        else None
    )
    unit = clean_display_text(metadata_data.get("unit")) or None
    description = clean_display_text(metadata_data.get("description")) or None
    inferred_canonical = infer_canonical_mnemonic(
        original_mnemonic,
        description=description or "",
        unit=unit or "",
    )
    # Old project versions often stored original.upper() as the canonical value. Upgrade
    # only that placeholder. A canonical name explicitly different from the original is a
    # user/catalog decision and must remain authoritative.
    canonical_mnemonic = stored_canonical
    if not stored_canonical or normalize_sensor_key(stored_canonical) == normalize_sensor_key(
        original_mnemonic
    ):
        canonical_mnemonic = inferred_canonical or stored_canonical
    raw_semantic = metadata_data.get("semantic")
    if raw_semantic is not None and not isinstance(raw_semantic, dict):
        raise ProjectFormatError("Curve semantic binding must be an object")
    semantic = (
        _semantic_binding_from_dict(raw_semantic)
        if isinstance(raw_semantic, dict)
        else default_semantic_channel_dictionary().resolve(
            original_mnemonic,
            description=description or "",
            unit=unit or "",
            canonical_mnemonic=canonical_mnemonic,
        )
    )
    metadata = CurveMetadata(
        curve_id=str(_required(metadata_data, "curve_id", str)),
        original_mnemonic=original_mnemonic,
        canonical_mnemonic=semantic.canonical_mnemonic,
        unit=unit,
        description=description,
        source_dataset_id=str(_required(metadata_data, "source_dataset_id", str)),
        provenance=str(metadata_data.get("provenance", "source")),
        semantic=semantic,
    )
    values = np.asarray(_required(data, "values", list), dtype=np.float64)
    try:
        state = CalculationState(str(data.get("state", CalculationState.CURRENT.value)))
    except ValueError as exc:
        raise ProjectFormatError(f"Неизвестное состояние кривой: {data.get('state')}") from exc
    return CurveData(
        metadata=metadata,
        values=values,
        version=int(data.get("version", 1)),
        state=state,
    )


def _index_from_dict(data: dict[str, Any]) -> DatasetIndex:
    try:
        index_type = IndexType(str(_required(data, "index_type", str)))
        role = IndexRole(str(_required(data, "role", str)))
    except ValueError as exc:
        raise ProjectFormatError("Неизвестный тип или роль индекса") from exc
    raw_values = _required(data, "values", list)
    values = (
        np.asarray(raw_values, dtype=np.int64).astype("datetime64[ns]")
        if index_type is IndexType.DATETIME
        else np.asarray(raw_values, dtype=np.float64)
    )
    evidence = data.get("evidence", [])
    if not isinstance(evidence, list) or not all(isinstance(item, str) for item in evidence):
        raise ProjectFormatError("Evidence индекса должен быть списком строк")
    try:
        return DatasetIndex(
            index_id=str(_required(data, "index_id", str)),
            mnemonic=clean_mnemonic(_required(data, "mnemonic", str)),
            index_type=index_type,
            role=role,
            unit=clean_display_text(data.get("unit")) or None,
            values=values,
            confidence=float(data.get("confidence", 1.0)),
            evidence=tuple(evidence),
            datetime_format=data.get("datetime_format"),
            timezone=data.get("timezone"),
        )
    except (TypeError, ValueError) as exc:
        raise ProjectFormatError("Некорректные данные индекса") from exc


def _import_report_from_dict(data: dict[str, Any]) -> LasImportReport:
    source_data = _required(data, "source", dict)
    depth_data = _required(data, "depth_axis", dict)
    raw_sections = _required(source_data, "section_names", list)
    if not all(isinstance(item, str) for item in raw_sections):
        raise ProjectFormatError("section_names отчёта должен быть списком строк")
    try:
        source = LasSourceSnapshot(
            path=Path(_required(source_data, "path", str)),
            size_bytes=_required_int(source_data, "size_bytes"),
            sha256=str(_required(source_data, "sha256", str)),
            encoding=str(_required(source_data, "encoding", str)),
            newline_style=str(_required(source_data, "newline_style", str)),
            section_names=tuple(raw_sections),
            las_version=source_data.get("las_version"),
            wrap=source_data.get("wrap"),
            null_value=_optional_float_field(source_data, "null_value"),
        )
        depth_axis = DepthAxisReport(
            direction=DepthDirection(str(_required(depth_data, "direction", str))),
            start=_optional_float_field(depth_data, "start"),
            stop=_optional_float_field(depth_data, "stop"),
            nominal_step=_optional_float_field(depth_data, "nominal_step"),
            is_uniform=bool(_required(depth_data, "is_uniform", bool)),
            duplicate_count=_required_int(depth_data, "duplicate_count"),
            missing_count=_required_int(depth_data, "missing_count"),
            gap_count=_required_int(depth_data, "gap_count"),
        )
    except (TypeError, ValueError) as exc:
        raise ProjectFormatError("Некорректный source/depth provenance") from exc
    raw_issues = _required(data, "issues", list)
    issues: list[LasImportIssue] = []
    try:
        for item in raw_issues:
            if not isinstance(item, dict):
                raise TypeError("issue должен быть объектом")
            issues.append(
                LasImportIssue(
                    code=str(_required(item, "code", str)),
                    severity=LasIssueSeverity(str(_required(item, "severity", str))),
                    message=str(_required(item, "message", str)),
                )
            )
    except (TypeError, ValueError) as exc:
        raise ProjectFormatError("Некорректный список import issues") from exc
    report = LasImportReport(source, depth_axis, tuple(issues))
    try:
        validate_import_report(report)
    except ValueError as exc:
        raise ProjectFormatError(str(exc)) from exc
    return report


def _optional_float_field(data: dict[str, Any], key: str) -> float | None:
    value = data.get(key)
    if isinstance(value, bool):
        raise ProjectFormatError(f"Поле '{key}' не может быть логическим")
    return float(value) if value is not None else None


def _dataset_from_dict(data: dict[str, Any]) -> Dataset:
    try:
        kind = DatasetKind(str(_required(data, "kind", str)))
        depth_domain = DepthDomain(str(_required(data, "depth_domain", str)))
    except ValueError as exc:
        raise ProjectFormatError("Неизвестный тип набора данных или шкалы глубины") from exc

    raw_indexes = data.get("indexes", {})
    if not isinstance(raw_indexes, dict):
        raise ProjectFormatError("Поле indexes должно быть объектом")
    indexes = {
        str(index_id): _index_from_dict(item)
        for index_id, item in raw_indexes.items()
        if isinstance(item, dict)
    }
    if len(indexes) != len(raw_indexes):
        raise ProjectFormatError("Запись индекса должна быть объектом")
    try:
        dataset = Dataset(
            dataset_id=str(_required(data, "dataset_id", str)),
            name=clean_display_text(_required(data, "name", str)),
            kind=kind,
            depth_domain=depth_domain,
            depth=np.asarray(_required(data, "depth", list), dtype=np.float64),
            source_path=Path(data["source_path"]) if data.get("source_path") else None,
            version_headers={
                clean_mnemonic(k): clean_display_text(v)
                for k, v in dict(data.get("version_headers", {})).items()
            },
            headers={
                clean_mnemonic(k): clean_display_text(v)
                for k, v in dict(data.get("headers", {})).items()
            },
            parameters={
                clean_mnemonic(k): clean_display_text(v)
                for k, v in dict(data.get("parameters", {})).items()
            },
            indexes=indexes,
            active_index_id=data.get("active_index_id"),
        )
    except (TypeError, ValueError) as exc:
        raise ProjectFormatError("Файл содержит некорректные данные dataset") from exc
    curve_map = _required(data, "curves", dict)
    dataset.curves = {
        str(curve_id): _curve_from_dict(curve) for curve_id, curve in curve_map.items()
    }
    for curve in dataset.curves.values():
        if curve.values.shape != dataset.depth.shape:
            raise ProjectFormatError(
                f"Кривая {curve.metadata.original_mnemonic} имеет длину {len(curve.values)}, "
                f"а шкала глубины — {len(dataset.depth)}"
            )
    return dataset


def _well_from_dict(data: dict[str, Any]) -> Well:
    well = Well(
        well_id=str(_required(data, "well_id", str)),
        name=str(_required(data, "name", str)),
    )
    datasets = _required(data, "datasets", dict)
    well.datasets = {
        str(dataset_id): _dataset_from_dict(item) for dataset_id, item in datasets.items()
    }
    well.lithology = [LithologyInterval(**item) for item in data.get("lithology", [])]
    well.cuttings = [
        CuttingsSample(
            sample_id=item["sample_id"],
            top_depth=float(item["top_depth"]),
            bottom_depth=float(item["bottom_depth"]),
            components=[CuttingsComponent(**component) for component in item.get("components", [])],
            lba_group=(int(item["lba_group"]) if item.get("lba_group") is not None else None),
            lba_type_id=item.get("lba_type_id"),
            lba_intensity=item.get("lba_intensity"),
            lba_color=item.get("lba_color"),
            lba_distribution=item.get("lba_distribution"),
            lba_cut=item.get("lba_cut"),
            lba_cut_speed=item.get("lba_cut_speed"),
            lba_cut_color=item.get("lba_cut_color"),
            lba_residue_type=item.get("lba_residue_type"),
            lba_residue_color=item.get("lba_residue_color"),
            lba_odour=item.get("lba_odour"),
            lba_stain=item.get("lba_stain"),
            lba_description=item.get("lba_description"),
            calcite_percent=(
                float(item["calcite_percent"]) if item.get("calcite_percent") is not None else None
            ),
            dolomite_percent=(
                float(item["dolomite_percent"])
                if item.get("dolomite_percent") is not None
                else None
            ),
            description=item.get("description"),
            analysis_interpretation=item.get("analysis_interpretation"),
        )
        for item in data.get("cuttings", [])
    ]
    well.stratigraphy = [StratigraphyInterval(**item) for item in data.get("stratigraphy", [])]
    raw_interpretations = data.get("interpretations", {})
    if not isinstance(raw_interpretations, dict):
        raise ProjectFormatError("Поле interpretations скважины должно быть объектом")
    for interpretation_id, item in raw_interpretations.items():
        if not isinstance(interpretation_id, str) or not isinstance(item, dict):
            raise ProjectFormatError("Запись интерпретации имеет неверный формат")
        raw_intervals = item.get("intervals", [])
        if not isinstance(raw_intervals, list) or not all(
            isinstance(interval, dict) for interval in raw_intervals
        ):
            raise ProjectFormatError("Интервалы интерпретации должны быть списком объектов")
        try:
            interpretation = WellInterpretation(
                interpretation_id=str(_required(item, "interpretation_id", str)),
                name=str(_required(item, "name", str)),
                description=item.get("description"),
                intervals=[InterpretationInterval(**interval) for interval in raw_intervals],
            )
        except (TypeError, ValueError) as exc:
            raise ProjectFormatError(f"Некорректная интерпретация '{interpretation_id}'") from exc
        if interpretation.interpretation_id != interpretation_id:
            raise ProjectFormatError(
                f"ID интерпретации '{interpretation_id}' не совпадает с содержимым"
            )
        well.interpretations[interpretation_id] = interpretation
    well.canvas_objects = [CanvasObject(**item) for item in data.get("canvas_objects", [])]
    return well


def project_from_dict(data: dict[str, Any]) -> Project:
    project = Project(
        project_id=str(_required(data, "project_id", str)),
        name=str(_required(data, "name", str)),
    )
    wells = _required(data, "wells", dict)
    project.wells = {str(well_id): _well_from_dict(item) for well_id, item in wells.items()}
    raw_lithotypes = data.get("lithotypes", {})
    if not isinstance(raw_lithotypes, dict):
        raise ProjectFormatError("Поле 'lithotypes' должно быть объектом")
    for lithotype_id, item in raw_lithotypes.items():
        if not isinstance(lithotype_id, str) or not isinstance(item, dict):
            raise ProjectFormatError("Запись справочника литотипов имеет неверный формат")
        try:
            lithotype_record = ProjectLithotype(**item)
        except TypeError as exc:
            raise ProjectFormatError(f"Некорректная запись литотипа '{lithotype_id}'") from exc
        if lithotype_record.lithotype_id != lithotype_id:
            raise ProjectFormatError(
                f"ID записи литотипа '{lithotype_id}' не совпадает с содержимым"
            )
        project.lithotypes[lithotype_id] = lithotype_record
    raw_stratigraphy_units = data.get("stratigraphy_units", {})
    if not isinstance(raw_stratigraphy_units, dict):
        raise ProjectFormatError("Поле 'stratigraphy_units' должно быть объектом")
    for unit_id, item in raw_stratigraphy_units.items():
        if not isinstance(unit_id, str) or not isinstance(item, dict):
            raise ProjectFormatError("Запись стратиграфического справочника имеет неверный формат")
        try:
            stratigraphy_record = ProjectStratigraphyUnit(**item)
        except TypeError as exc:
            raise ProjectFormatError(
                f"Некорректная стратиграфическая запись '{unit_id}'"
            ) from exc
        if stratigraphy_record.unit_id != unit_id:
            raise ProjectFormatError(
                f"ID стратиграфической записи '{unit_id}' не совпадает с содержимым"
            )
        project.stratigraphy_units[unit_id] = stratigraphy_record
    raw_templates = data.get("description_templates", {})
    if not isinstance(raw_templates, dict) or not all(
        isinstance(name, str) and isinstance(text, str) for name, text in raw_templates.items()
    ):
        raise ProjectFormatError("Поле 'description_templates' должно быть строковым объектом")
    project.description_templates = dict(raw_templates)
    raw_masterlog_templates = data.get("masterlog_templates", {})
    if not isinstance(raw_masterlog_templates, dict):
        raise ProjectFormatError("Поле 'masterlog_templates' должно быть объектом")
    for template_id, item in raw_masterlog_templates.items():
        if not isinstance(template_id, str) or not isinstance(item, dict):
            raise ProjectFormatError("Запись шаблона мастерлога имеет неверный формат")
        try:
            header_elements = [
                MasterlogHeaderElement(**element) for element in item.get("header_elements", [])
            ]
            columns = []
            for column in item.get("columns", []):
                column_data = dict(column)
                raw_curve_styles = column_data.get("curve_styles", {})
                if not isinstance(raw_curve_styles, dict):
                    raise TypeError("Стили кривых Masterlog должны быть объектом")
                column_data["curve_styles"] = {
                    str(mnemonic): MasterlogCurveStyle(**style)
                    for mnemonic, style in raw_curve_styles.items()
                    if isinstance(style, dict)
                }
                if len(column_data["curve_styles"]) != len(raw_curve_styles):
                    raise TypeError("Запись стиля кривой Masterlog имеет неверный формат")
                columns.append(MasterlogColumnTemplate(**column_data))
            template = MasterlogTemplate(
                template_id=str(_required(item, "template_id", str)),
                name=str(_required(item, "name", str)),
                page_format=str(item.get("page_format", "roll")),
                depth_scale=int(item.get("depth_scale", 500)),
                header_height_mm=float(item.get("header_height_mm", 45.0)),
                header_elements=header_elements,
                columns=columns,
                properties=dict(item.get("properties", {})),
                version=int(item.get("version", 1)),
            )
        except (TypeError, ValueError) as exc:
            raise ProjectFormatError(f"Некорректный шаблон мастерлога '{template_id}'") from exc
        if template.template_id != template_id:
            raise ProjectFormatError(
                f"ID шаблона мастерлога '{template_id}' не совпадает с содержимым"
            )
        project.masterlog_templates[template_id] = template
    raw_formulas = data.get("custom_formulas", {})
    if not isinstance(raw_formulas, dict):
        raise ProjectFormatError("Поле 'custom_formulas' должно быть объектом")
    for formula_id, item in raw_formulas.items():
        if not isinstance(formula_id, str) or not isinstance(item, dict):
            raise ProjectFormatError("Запись пользовательской формулы имеет неверный формат")
        try:
            formula = CustomFormulaDefinition(**item)
        except TypeError as exc:
            raise ProjectFormatError(f"Некорректная формула '{formula_id}'") from exc
        if formula.formula_id != formula_id:
            raise ProjectFormatError(f"ID формулы '{formula_id}' не совпадает с содержимым")
        project.custom_formulas[formula_id] = formula
    raw_export_profiles = data.get("export_profiles", {})
    if not isinstance(raw_export_profiles, dict):
        raise ProjectFormatError("Поле 'export_profiles' должно быть объектом")
    for profile_id, item in raw_export_profiles.items():
        if not isinstance(profile_id, str) or not isinstance(item, dict):
            raise ProjectFormatError("Запись профиля экспорта имеет неверный формат")
        raw_mnemonics = item.get("curve_mnemonics")
        if not isinstance(raw_mnemonics, list) or not all(
            isinstance(value, str) for value in raw_mnemonics
        ):
            raise ProjectFormatError("Кривые профиля экспорта должны быть списком строк")
        try:
            profile = ExportProfile(
                profile_id=str(_required(item, "profile_id", str)),
                name=str(_required(item, "name", str)),
                curve_mnemonics=tuple(raw_mnemonics),
            )
        except ValueError as exc:
            raise ProjectFormatError(f"Некорректный профиль экспорта '{profile_id}'") from exc
        if profile.profile_id != profile_id:
            raise ProjectFormatError(
                f"ID профиля экспорта '{profile_id}' не совпадает с содержимым"
            )
        project.export_profiles[profile_id] = profile
    raw_mapping_profiles = data.get("time_depth_mapping_profiles", {})
    if not isinstance(raw_mapping_profiles, dict):
        raise ProjectFormatError("Поле 'time_depth_mapping_profiles' должно быть объектом")
    for profile_id, item in raw_mapping_profiles.items():
        if not isinstance(profile_id, str) or not isinstance(item, dict):
            raise ProjectFormatError("Запись TIME↔DEPTH профиля имеет неверный формат")
        try:
            mapping_profile = TimeDepthMappingProfile(
                profile_id=str(_required(item, "profile_id", str)),
                name=str(_required(item, "name", str)),
                dataset_id=str(_required(item, "dataset_id", str)),
                time_index_id=str(_required(item, "time_index_id", str)),
                depth_index_id=str(_required(item, "depth_index_id", str)),
                aggregation_policy=TimeDepthAggregationPolicy(
                    str(_required(item, "aggregation_policy", str))
                ),
                version=int(item.get("version", 1)),
            )
        except (TypeError, ValueError) as exc:
            raise ProjectFormatError(f"Некорректный TIME↔DEPTH профиль '{profile_id}'") from exc
        if mapping_profile.profile_id != profile_id:
            raise ProjectFormatError(
                f"ID TIME↔DEPTH профиля '{profile_id}' не совпадает с содержимым"
            )
        project.time_depth_mapping_profiles[profile_id] = mapping_profile
    datasets = {
        dataset.dataset_id: dataset
        for well in project.wells.values()
        for dataset in well.datasets.values()
    }
    for mapping_profile in project.time_depth_mapping_profiles.values():
        dataset = datasets.get(mapping_profile.dataset_id)
        if dataset is None:
            raise ProjectFormatError(
                f"TIME↔DEPTH профиль '{mapping_profile.profile_id}' ссылается на неизвестный набор"
            )
        for index_id, role in (
            (mapping_profile.time_index_id, IndexRole.TIME),
            (mapping_profile.depth_index_id, IndexRole.DEPTH),
        ):
            index = dataset.indexes.get(index_id)
            if index is None or index.role is not role:
                raise ProjectFormatError(
                    f"TIME↔DEPTH профиль '{mapping_profile.profile_id}' "
                    f"ссылается на индекс без роли {role.value}"
                )
    return project


def project_document_from_dict(data: dict[str, Any]) -> ProjectDocument:
    """Migrate and reconstruct a project document using the current schema."""
    try:
        data = migrate_project_payload(data, PROJECT_FORMAT_VERSION)
    except ProjectMigrationError as exc:
        raise ProjectFormatError(str(exc)) from exc

    project = project_from_dict(_required(data, "project", dict))
    raw_layouts = _required(data, "tablet_layouts", dict)
    layouts: dict[str, TabletLayout] = {}
    for dataset_id, raw_layout in raw_layouts.items():
        if not isinstance(dataset_id, str) or not dataset_id:
            raise ProjectFormatError("Идентификатор набора для компоновки должен быть строкой")
        try:
            layouts[dataset_id] = layout_from_dict(raw_layout)
        except TabletLayoutFormatError as exc:
            raise ProjectFormatError(
                f"Некорректная компоновка планшета для набора '{dataset_id}'"
            ) from exc

    known_dataset_ids = {
        dataset_id for well in project.wells.values() for dataset_id in well.datasets
    }
    unknown_dataset_ids = set(layouts) - known_dataset_ids
    if unknown_dataset_ids:
        unknown = ", ".join(sorted(unknown_dataset_ids))
        raise ProjectFormatError(f"Компоновка ссылается на неизвестный набор: {unknown}")
    raw_presets = _required(data, "tablet_presets", dict)
    presets: dict[str, TabletLayout] = {}
    for name, raw_layout in raw_presets.items():
        if not isinstance(name, str) or not name.strip():
            raise ProjectFormatError("Имя шаблона планшета должно быть непустой строкой")
        try:
            presets[name] = layout_from_dict(raw_layout)
        except TabletLayoutFormatError as exc:
            raise ProjectFormatError(f"Некорректный шаблон планшета '{name}'") from exc
    try:
        artifact_manifest = validate_artifact_manifest(data.get("source_artifacts", {}))
    except SourceArtifactError as exc:
        raise ProjectFormatError(str(exc)) from exc
    unknown_artifact_ids = set(artifact_manifest) - known_dataset_ids
    if unknown_artifact_ids:
        unknown = ", ".join(sorted(unknown_artifact_ids))
        raise ProjectFormatError(f"Source artifact ссылается на неизвестный набор: {unknown}")
    raw_reports = data.get("import_reports", {})
    if not isinstance(raw_reports, dict):
        raise ProjectFormatError("Поле import_reports должно быть объектом")
    reports = {
        str(dataset_id): _import_report_from_dict(item)
        for dataset_id, item in raw_reports.items()
        if isinstance(item, dict)
    }
    if len(reports) != len(raw_reports):
        raise ProjectFormatError("Запись import report должна быть объектом")
    unknown_report_ids = set(reports) - known_dataset_ids
    if unknown_report_ids:
        unknown = ", ".join(sorted(unknown_report_ids))
        raise ProjectFormatError(f"Import report ссылается на неизвестный набор: {unknown}")
    return ProjectDocument(project, layouts, presets, import_reports=reports)


def load_project_document(path: str | Path, *, max_size_mb: int = 512) -> ProjectDocument:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)
    if source.stat().st_size > max_size_mb * 1024 * 1024:
        raise ProjectFormatError(f"Файл проекта превышает лимит {max_size_mb} МБ")
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProjectFormatError(f"Не удалось прочитать проект: {source}") from exc
    if not isinstance(raw, dict):
        raise ProjectFormatError("Корень проекта должен быть JSON-объектом")
    try:
        document = project_document_from_dict(raw)
        try:
            document.source_documents = load_source_documents(
                source, dict(raw.get("source_artifacts", {}))
            )
            _validate_report_artifact_consistency(document)
        except SourceArtifactError as exc:
            raise ProjectFormatError(str(exc)) from exc
        try:
            document.image_assets = load_image_assets(source, raw.get("image_assets", {}))
        except ImageAssetError as exc:
            raise ProjectFormatError(str(exc)) from exc
        return document
    except ProjectFormatError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise ProjectFormatError("Файл содержит некорректные данные проекта") from exc


def load_project(path: str | Path, *, max_size_mb: int = 512) -> Project:
    return load_project_document(path, max_size_mb=max_size_mb).project


def _validate_report_artifact_consistency(document: ProjectDocument) -> None:
    for dataset_id in set(document.source_documents) & set(document.import_reports):
        source = document.source_documents[dataset_id]
        report_source = document.import_reports[dataset_id].source
        if source.size_bytes != report_source.size_bytes or source.sha256 != report_source.sha256:
            raise ProjectFormatError(
                f"Import report не соответствует source artifact dataset {dataset_id}"
            )

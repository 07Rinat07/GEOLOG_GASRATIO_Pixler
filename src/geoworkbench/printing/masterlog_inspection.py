from __future__ import annotations

from dataclasses import dataclass
from math import log10

import numpy as np
from PySide6.QtCore import QPointF, QRectF

from geoworkbench.domain.models import MasterlogColumnTemplate, MasterlogTemplate
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.lithotype_catalog_controller import LithotypeCatalogController
from geoworkbench.printing.masterlog_renderer import (
    curve_x_range,
    masterlog_curve_bindings,
    masterlog_depth_range,
    masterlog_size_mm,
)
from geoworkbench.services.localization import AppLanguage


@dataclass(frozen=True, slots=True)
class MasterlogInspection:
    column_id: str
    column_title: str
    depth: float
    mnemonic: str | None = None
    value: float | None = None
    unit: str | None = None
    description: str | None = None
    interval: tuple[float, float] | None = None

    def display_text(self, language: AppLanguage) -> str:
        depth_label = {
            AppLanguage.RU: "Глубина",
            AppLanguage.KK: "Тереңдік",
            AppLanguage.EN: "Depth",
        }[language]
        interval_label = {
            AppLanguage.RU: "Интервал",
            AppLanguage.KK: "Аралық",
            AppLanguage.EN: "Interval",
        }[language]
        lines = [self.column_title]
        if self.mnemonic is not None and self.value is not None:
            suffix = f" {self.unit}" if self.unit else ""
            lines.append(f"{self.mnemonic}: {self.value:g}{suffix}")
        lines.append(f"{depth_label}: {self.depth:g} м")
        if self.interval is not None:
            lines.append(f"{interval_label}: {self.interval[0]:g}–{self.interval[1]:g} м")
        if self.description:
            lines.append(self.description)
        return "\n".join(lines)


def inspect_masterlog_point(
    point: QPointF,
    target: QRectF,
    template: MasterlogTemplate,
    session: ProjectSession,
    *,
    depth_range: tuple[float, float] | None = None,
    language: AppLanguage = AppLanguage.RU,
) -> MasterlogInspection | None:
    effective_range = depth_range or masterlog_depth_range(session)
    dataset = session.current_dataset
    if effective_range is None or dataset is None:
        return None
    size = masterlog_size_mm(template, session, depth_range=effective_range)
    scale = min(target.width() / size.width(), target.height() / size.height())
    if scale <= 0:
        return None
    origin_x = target.x() + (target.width() - size.width() * scale) / 2.0
    origin_y = target.y() + (target.height() - size.height() * scale) / 2.0
    x_mm = (point.x() - origin_x) / scale
    y_mm = (point.y() - origin_y) / scale
    plot_top = template.header_height_mm + 12.0
    if y_mm < plot_top or y_mm > size.height():
        return None
    column = _column_at(template, x_mm)
    if column is None:
        return None
    top, bottom = effective_range
    depth = top + (y_mm - plot_top) / (size.height() - plot_top) * (bottom - top)
    if column.column_type in {"lithology", "text", "description"}:
        return _inspect_lithology(column, depth, session, language)
    if column.column_type == "cuttings":
        return _inspect_cuttings(column, depth, session, language)
    if column.column_type in {"calcimetry", "lba"}:
        return _inspect_sample_analysis(column, depth, session, language)
    if column.column_type == "depth":
        return MasterlogInspection(column.column_id, column.title, depth)
    return _inspect_curves(column, x_mm, depth, template, session)


def _column_at(template: MasterlogTemplate, x_mm: float) -> MasterlogColumnTemplate | None:
    left = 0.0
    for column in template.columns:
        if left <= x_mm <= left + column.width_mm:
            return column
        left += column.width_mm
    return None


def _inspect_lithology(
    column: MasterlogColumnTemplate,
    depth: float,
    session: ProjectSession,
    language: AppLanguage,
) -> MasterlogInspection:
    well = session.current_well
    interval = next(
        (
            item
            for item in (well.lithology if well is not None else ())
            if item.top_depth <= depth <= item.bottom_depth
        ),
        None,
    )
    if interval is None:
        return MasterlogInspection(column.column_id, column.title, depth)
    project_definition = session.project.lithotypes.get(interval.lithotype_id)
    definition = project_definition or next(
        (
            item
            for item in LithotypeCatalogController(session).available()
            if item.lithotype_id == interval.lithotype_id
        ),
        None,
    )
    if definition is None:
        name = interval.lithotype_id
    else:
        if hasattr(definition, "localized_name"):
            name = definition.localized_name(language.value)
        elif language is AppLanguage.EN:
            name = definition.name_en
        elif language is AppLanguage.KK:
            name = definition.name_kk or definition.name_ru
        else:
            name = definition.name_ru
    description = " — ".join(value for value in (name, interval.description or "") if value)
    return MasterlogInspection(
        column.column_id,
        column.title,
        depth,
        description=description,
        interval=(interval.top_depth, interval.bottom_depth),
    )


def _inspect_cuttings(
    column: MasterlogColumnTemplate,
    depth: float,
    session: ProjectSession,
    language: AppLanguage,
) -> MasterlogInspection:
    well = session.current_well
    sample = next(
        (
            item
            for item in (well.cuttings if well is not None else ())
            if item.top_depth <= depth <= item.bottom_depth
        ),
        None,
    )
    if sample is None:
        return MasterlogInspection(column.column_id, column.title, depth)
    catalog = {item.lithotype_id: item for item in LithotypeCatalogController(session).available()}
    parts = [
        f"{catalog[item.lithotype_id].localized_name(language.value) if item.lithotype_id in catalog else item.lithotype_id}: {item.percentage:g}%"
        for item in sample.components
    ]
    if sample.description:
        parts.append(sample.description)
    return MasterlogInspection(
        column.column_id,
        column.title,
        depth,
        description="; ".join(parts),
        interval=(sample.top_depth, sample.bottom_depth),
    )


def _inspect_sample_analysis(
    column: MasterlogColumnTemplate,
    depth: float,
    session: ProjectSession,
    language: AppLanguage,
) -> MasterlogInspection:
    well = session.current_well
    sample = next(
        (
            item
            for item in (well.cuttings if well is not None else ())
            if item.top_depth <= depth <= item.bottom_depth
        ),
        None,
    )
    if sample is None:
        return MasterlogInspection(column.column_id, column.title, depth)
    labels = {
        AppLanguage.RU: ("Кальцит", "Доломит", "Интенсивность"),
        AppLanguage.KK: ("Кальцит", "Доломит", "Қарқындылық"),
        AppLanguage.EN: ("Calcite", "Dolomite", "Intensity"),
    }[language]
    if column.column_type == "calcimetry":
        parts = []
        if sample.calcite_percent is not None:
            parts.append(f"{labels[0]} CaCO₃: {sample.calcite_percent:g}%")
        if sample.dolomite_percent is not None:
            parts.append(f"{labels[1]} CaMg(CO₃)₂: {sample.dolomite_percent:g}%")
        if sample.insoluble_residue_percent is not None:
            residue_label = {
                AppLanguage.RU: "Нерастворимый остаток",
                AppLanguage.KK: "Ерімейтін қалдық",
                AppLanguage.EN: "Insoluble residue",
            }[language]
            parts.append(f"{residue_label}: {sample.insoluble_residue_percent:g}%")
    else:
        parts = [
            value
            for value in (
                f"Group: {sample.lba_group}" if sample.lba_group is not None else None,
                sample.lba_type_id,
                f"{labels[2]}: {sample.lba_intensity}"
                if sample.lba_intensity is not None
                else None,
                sample.lba_color,
                sample.lba_distribution,
                sample.lba_cut,
                sample.lba_cut_speed,
                sample.lba_cut_color,
                sample.lba_residue_type,
                sample.lba_residue_color,
                sample.lba_odour,
                sample.lba_stain,
                sample.lba_description,
            )
            if value
        ]
    return MasterlogInspection(
        column.column_id,
        column.title,
        depth,
        description="; ".join(parts),
        interval=(sample.top_depth, sample.bottom_depth),
    )


def _inspect_curves(
    column: MasterlogColumnTemplate,
    x_mm: float,
    depth: float,
    template: MasterlogTemplate,
    session: ProjectSession,
) -> MasterlogInspection | None:
    dataset = session.current_dataset
    assert dataset is not None
    depths = np.asarray(dataset.active_index.values, dtype=np.float64)
    bindings = masterlog_curve_bindings(template, dataset)
    x_range = curve_x_range(column, dataset, bindings)
    if x_range is None or depths.size == 0:
        return MasterlogInspection(column.column_id, column.title, depth)
    column_index = next(index for index, item in enumerate(template.columns) if item is column)
    column_left = sum(item.width_mm for item in template.columns[:column_index])
    click_fraction = min(
        1.0, max(0.0, (x_mm - column_left - 0.5) / max(0.1, column.width_mm - 1.0))
    )
    candidates: list[tuple[float, str, float, str | None, str | None, float]] = []
    for mnemonic in column.curve_mnemonics:
        curve_id = bindings.get(mnemonic)
        curve = dataset.curves.get(curve_id) if curve_id else dataset.curve_by_mnemonic(mnemonic)
        if curve is None:
            continue
        values = np.asarray(curve.values, dtype=np.float64)
        if values.shape != depths.shape:
            continue
        valid = np.isfinite(depths) & np.isfinite(values)
        if column.x_scale == "logarithmic":
            valid &= values > 0
        indexes = np.flatnonzero(valid)
        if not indexes.size:
            continue
        index = int(indexes[np.argmin(np.abs(depths[indexes] - depth))])
        value = float(values[index])
        minimum, maximum = x_range
        if column.x_scale == "logarithmic":
            value_position = log10(value)
            minimum, maximum = log10(minimum), log10(maximum)
        else:
            value_position = value
        fraction = (value_position - minimum) / (maximum - minimum)
        candidates.append(
            (
                abs(fraction - click_fraction),
                mnemonic,
                value,
                curve.metadata.unit,
                curve.metadata.description,
                float(depths[index]),
            )
        )
    if not candidates:
        return MasterlogInspection(column.column_id, column.title, depth)
    _, mnemonic, value, unit, description, sample_depth = min(candidates)
    return MasterlogInspection(
        column.column_id,
        column.title,
        sample_depth,
        mnemonic,
        value,
        unit,
        description,
    )

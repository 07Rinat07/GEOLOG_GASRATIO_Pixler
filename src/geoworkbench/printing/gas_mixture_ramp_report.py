from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import escape
import os
from pathlib import Path
import tempfile

import numpy as np
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QLineF, QMarginsF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QImage,
    QPageLayout,
    QPageSize,
    QPainter,
    QPdfWriter,
    QPen,
    QTextDocument,
)

from geoworkbench.domain.models import IndexRole
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.gas_ratio_interpretation import classify_gas_ratio
from geoworkbench.services.las_parameter_resolver import (
    ParameterResolutionError,
    resolve_gas_ratio_inputs,
)
from geoworkbench.services.localization import AppLanguage
from geoworkbench.printing.unicode_support import preflight_texts, print_font


class GasMixtureRampReportError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class GasMixtureComponent:
    mnemonic: str
    baseline_value: float
    representative_value: float
    composition_percent: float
    peak_value: float


@dataclass(frozen=True, slots=True)
class GasMixtureRampReport:
    project_name: str
    well_name: str
    dataset_name: str
    generated_at: str
    time_label: str
    time_values: tuple[float, ...]
    series: tuple[tuple[str, tuple[float, ...]], ...]
    components: tuple[GasMixtureComponent, ...]
    wetness: float | None
    balance: float | None
    character: float | None
    pixler_ratios: tuple[tuple[str, float], ...]
    interpretation_code: str
    confidence: str
    warnings: tuple[str, ...]


_COLORS = {
    "C1": "#1d4ed8",
    "C2": "#16a34a",
    "C3": "#0891b2",
    "C4Σ": "#ea580c",
    "C5Σ": "#9333ea",
}


def build_gas_mixture_ramp_report(
    session: ProjectSession,
) -> GasMixtureRampReport:
    dataset = session.current_dataset
    well = session.current_well
    if dataset is None or well is None:
        raise GasMixtureRampReportError("Сначала выберите скважину и набор данных")

    try:
        gases = resolve_gas_ratio_inputs(dataset)
    except (ParameterResolutionError, ValueError) as exc:
        raise GasMixtureRampReportError(
            "Для разгонки газовой смеси нужны согласованные C1, C2, C3, C4 и C5"
        ) from exc

    c1 = np.asarray(gases["C1"], dtype=np.float64)
    c2 = np.asarray(gases["C2"], dtype=np.float64)
    c3 = np.asarray(gases["C3"], dtype=np.float64)
    c4 = _summed_component(gases, "C4", "IC4", "NC4", c1)
    c5 = _summed_component(gases, "C5", "IC5", "NC5", c1)
    arrays = (c1, c2, c3, c4, c5)
    if any(values.shape != c1.shape for values in arrays):
        raise GasMixtureRampReportError("Кривые C1–C5 имеют разное число отсчётов")

    time_values, time_label, time_warning = _time_axis(dataset, c1.size)
    valid = np.isfinite(time_values)
    for values in arrays:
        valid &= np.isfinite(values) & (values >= 0.0)
    if np.count_nonzero(valid) < 3:
        raise GasMixtureRampReportError(
            "Для разгонки требуется не менее трёх согласованных отсчётов C1–C5"
        )

    baselines = np.asarray(
        [float(np.nanpercentile(values[valid], 20.0)) for values in arrays],
        dtype=np.float64,
    )
    corrected = tuple(
        np.maximum(values - baseline, 0.0)
        for values, baseline in zip(arrays, baselines, strict=True)
    )
    total = sum(corrected)
    valid_total = valid & np.isfinite(total) & (total > 0.0)
    if not np.any(valid_total):
        interpretation_code = "background_or_no_hydrocarbons"
        representative = np.zeros(5, dtype=np.float64)
        confidence = "low"
    else:
        peak = float(np.nanmax(total[valid_total]))
        peak_window = valid_total & (total >= peak * 0.5)
        if np.count_nonzero(peak_window) < 2:
            peak_index = int(np.nanargmax(np.where(valid_total, total, np.nan)))
            start = max(0, peak_index - 1)
            stop = min(total.size, peak_index + 2)
            peak_window = np.zeros(total.shape, dtype=bool)
            peak_window[start:stop] = valid[start:stop]
        representative = np.asarray(
            [float(np.nanmedian(values[peak_window])) for values in corrected],
            dtype=np.float64,
        )
        interpretation_code, confidence = _classify_mixture(representative)

    representative_total = float(np.sum(representative))
    composition = (
        100.0 * representative / representative_total
        if representative_total > 0.0
        else np.zeros(5, dtype=np.float64)
    )
    names = ("C1", "C2", "C3", "C4Σ", "C5Σ")
    components = tuple(
        GasMixtureComponent(
            name,
            float(baseline),
            float(value),
            float(percent),
            float(np.nanmax(values[valid])),
        )
        for name, baseline, value, percent, values in zip(
            names, baselines, representative, composition, corrected, strict=True
        )
    )
    heavier = float(np.sum(representative[1:]))
    wetness = 100.0 * heavier / representative_total if representative_total > 0.0 else None
    balance_denominator = float(np.sum(representative[2:]))
    balance = (
        float((representative[0] + representative[1]) / balance_denominator)
        if balance_denominator > 0.0
        else None
    )
    character = (
        float((representative[3] + representative[4]) / representative[2])
        if representative[2] > 0.0
        else None
    )
    ratios = tuple(
        (f"C1/{name}", float(representative[0] / denominator))
        for name, denominator in zip(names[1:], representative[1:], strict=True)
        if denominator > 0.0
    )
    warnings = [
        (
            "Результат является скрининговой интерпретацией отклика C1–C5. "
            "Он не заменяет калиброванный лабораторный анализ состава пробы."
        ),
        (
            "Категория «вода» по одному отклику углеводородных газов не назначается; "
            "низкий сигнал обозначается как фон/недостаточно данных."
        ),
        (
            "Для количественных молярных долей нужны калибровка газоанализатора, "
            "контроль нуля/стандарта и оценка неопределённости."
        ),
        (
            "Фоновый уровень каждого компонента оценён по нижнему квантилю временного "
            "отклика и вычтен только для расчёта состава; на диаграмме показан исходный отклик."
        ),
    ]
    if time_warning:
        warnings.append(time_warning)

    sampled = _sample_indices(c1.size, limit=900)
    return GasMixtureRampReport(
        session.project.name,
        well.name,
        dataset.name,
        datetime.now().astimezone().isoformat(timespec="seconds"),
        time_label,
        tuple(float(value) for value in time_values[sampled]),
        tuple(
            (
                name,
                tuple(float(value) for value in values[sampled]),
            )
            for name, values in zip(names, arrays, strict=True)
        ),
        components,
        wetness,
        balance,
        character,
        ratios,
        interpretation_code,
        confidence,
        tuple(warnings),
    )


def gas_mixture_ramp_html(
    report: GasMixtureRampReport,
    language: AppLanguage = AppLanguage.RU,
    *,
    include_chart: bool = True,
) -> str:
    labels = _labels(language)
    component_rows = "".join(
        "<tr>"
        f"<td>{escape(item.mnemonic)}</td>"
        f"<td>{item.baseline_value:.6g}</td>"
        f"<td>{item.representative_value:.6g}</td>"
        f"<td>{item.composition_percent:.2f}%</td>"
        f"<td>{item.peak_value:.6g}</td>"
        "</tr>"
        for item in report.components
    )
    ratio_rows = "".join(
        f"<tr><td>{escape(name)}</td><td>{value:.4g}</td></tr>"
        for name, value in report.pixler_ratios
    )
    warnings = "".join(f"<li>{escape(item)}</li>" for item in report.warnings)
    chart = (
        f"<h2>{escape(labels['chart'])}</h2>"
        f'<img alt="{escape(labels["chart"])}" width="900" height="390" '
        f'src="{_chart_data_uri(report, language)}" />'
        if include_chart
        else ""
    )
    wetness = "—" if report.wetness is None else f"{report.wetness:.2f}%"
    balance = "—" if report.balance is None else f"{report.balance:.4g}"
    character = "—" if report.character is None else f"{report.character:.4g}"
    base_font_size = "9pt" if include_chart else "10pt"
    cell_padding = "3px 5px" if include_chart else "4px 6px"
    return f"""
    <html><head><meta charset="utf-8"><style>
    body {{ color:#172033; font-size:{base_font_size}; }}
    h1 {{ font-size:18pt; margin:0 0 8px 0; }}
    h2 {{ font-size:13pt; margin:10px 0 5px 0; }}
    table {{ border-collapse:collapse; width:100%; margin:6px 0 10px 0; }}
    th, td {{ border:1px solid #94a3b8; padding:{cell_padding}; }}
    th {{ background:#e2e8f0; }}
    .result {{ border:2px solid #315a7d; background:#eef6fc; padding:10px; }}
    .muted {{ color:#475569; }}
    </style></head><body>
    <h1>{escape(labels["title"])}</h1>
    <p class="muted">{escape(report.project_name)} · {escape(report.well_name)} ·
    {escape(report.dataset_name)} · {escape(report.generated_at)}</p>
    {chart}
    <div class="result"><b>{escape(labels["result"])}:</b>
    {escape(labels[report.interpretation_code])}<br>
    <b>{escape(labels["confidence"])}:</b> {escape(labels[report.confidence])}<br>
    <b>Wh:</b> {wetness} · <b>Bh:</b> {balance} · <b>Ch:</b> {character}</div>
    <h2>{escape(labels["composition"])}</h2>
    <table><tr><th>Компонент</th><th>{escape(labels["baseline"])}</th>
    <th>{escape(labels["representative"])}</th>
    <th>{escape(labels["share"])}</th><th>{escape(labels["peak"])}</th></tr>
    {component_rows}</table>
    <h2>Pixler</h2>
    <table><tr><th>{escape(labels["ratio"])}</th><th>{escape(labels["value"])}</th></tr>
    {ratio_rows or '<tr><td colspan="2">—</td></tr>'}</table>
    <h2>{escape(labels["limitations"])}</h2><ul>{warnings}</ul>
    <p class="muted">Haworth, Sellens &amp; Whittaker (1985), AAPG Bulletin 69(8);
    Pixler (1969), JPT 21; ISO 6974-1:2012.</p>
    </body></html>
    """


def export_gas_mixture_ramp_pdf(
    report: GasMixtureRampReport,
    target: str | Path,
    *,
    language: AppLanguage = AppLanguage.RU,
    include_chart: bool = True,
    overwrite: bool = False,
) -> Path:
    destination = Path(target)
    if destination.suffix.casefold() != ".pdf":
        destination = destination.with_suffix(".pdf")
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.stem}-",
        suffix=".pdf",
        dir=destination.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        writer = QPdfWriter(str(temporary))
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageOrientation(
            QPageLayout.Orientation.Landscape if include_chart else QPageLayout.Orientation.Portrait
        )
        writer.setPageMargins(
            QMarginsF(12.0, 12.0, 12.0, 12.0),
            QPageLayout.Unit.Millimeter,
        )
        writer.setResolution(300)
        writer.setTitle("Gas mixture ramp report")
        writer.setCreator("GEOLOG GASRATIO@Pixler")
        html = gas_mixture_ramp_html(
            report,
            language,
            include_chart=include_chart,
        )
        unicode_report = preflight_texts([html])
        if not unicode_report.ok:
            raise GasMixtureRampReportError(unicode_report.error_message())
        document = QTextDocument()
        document.setDefaultFont(print_font(9.0 if include_chart else 10.0, text=html))
        document.setHtml(html)
        document.print_(writer)
        del writer
        if temporary.stat().st_size <= 0:
            raise GasMixtureRampReportError("Не удалось сформировать PDF-отчёт")
        os.replace(temporary, destination)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        if isinstance(exc, (FileExistsError, GasMixtureRampReportError)):
            raise
        raise GasMixtureRampReportError(f"Не удалось экспортировать PDF: {destination}") from exc
    return destination


def _time_axis(dataset, size: int) -> tuple[np.ndarray, str, str | None]:
    time_index = next(
        (item for item in dataset.indexes.values() if item.role is IndexRole.TIME),
        None,
    )
    if time_index is None:
        return (
            np.arange(size, dtype=np.float64),
            "№ отсчёта",
            "В наборе нет временной оси; график построен по порядковому номеру отсчёта.",
        )
    raw = np.asarray(time_index.values)
    if np.issubdtype(raw.dtype, np.datetime64):
        nanoseconds = raw.astype("datetime64[ns]").astype(np.int64)
        finite = nanoseconds != np.iinfo(np.int64).min
        origin = int(nanoseconds[finite][0]) if np.any(finite) else 0
        values = (nanoseconds - origin).astype(np.float64) / 1_000_000_000.0
        return values, "Время от начала, с", None
    values = np.asarray(raw, dtype=np.float64)
    return values, f"{time_index.mnemonic}, {time_index.unit or ''}".rstrip(", "), None


def _classify_mixture(representative: np.ndarray) -> tuple[str, str]:
    total = float(np.sum(representative))
    if not np.isfinite(total) or total <= np.finfo(np.float64).eps:
        return "background_or_no_hydrocarbons", "low"
    wetness = 100.0 * float(np.sum(representative[1:])) / total
    balance_denominator = float(np.sum(representative[2:]))
    balance = (
        float((representative[0] + representative[1]) / balance_denominator)
        if balance_denominator > np.finfo(np.float64).eps
        else None
    )
    character = (
        float((representative[3] + representative[4]) / representative[2])
        if representative[2] > np.finfo(np.float64).eps
        else None
    )
    available_heavy = int(np.count_nonzero(representative[1:] > 0.0))
    confidence = "high" if available_heavy >= 3 else "medium" if available_heavy >= 1 else "low"
    assessment = classify_gas_ratio(
        wetness=wetness,
        balance=balance,
        character=character,
    )
    return assessment.code, confidence


def _summed_component(
    gases: dict[str, np.ndarray],
    total_name: str,
    iso_name: str,
    normal_name: str,
    template: np.ndarray,
) -> np.ndarray:
    if iso_name in gases or normal_name in gases:
        return gases.get(iso_name, np.zeros_like(template)) + gases.get(
            normal_name, np.zeros_like(template)
        )
    return gases.get(total_name, np.zeros_like(template))


def _sample_indices(size: int, *, limit: int) -> np.ndarray:
    if size <= limit:
        return np.arange(size, dtype=np.int64)
    return np.linspace(0, size - 1, limit, dtype=np.int64)


def _chart_data_uri(
    report: GasMixtureRampReport,
    language: AppLanguage,
) -> str:
    image = QImage(1500, 650, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        title_font = print_font(16.0, text=_labels(language)["chart"])
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QColor("#172033"))
        painter.drawText(
            QRectF(70, 12, 1360, 38),
            Qt.AlignmentFlag.AlignCenter,
            _labels(language)["chart"],
        )
        painter.setFont(print_font(9.0, text=_labels(language)["chart_scale"]))
        painter.drawText(
            QRectF(90, 48, 440, 20),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            _labels(language)["chart_scale"],
        )
        plot = QRectF(90, 70, 1320, 480)
        painter.setPen(QPen(QColor("#334155"), 2))
        painter.drawRect(plot)
        x = np.asarray(report.time_values, dtype=np.float64)
        finite_x = x[np.isfinite(x)]
        if finite_x.size == 0:
            return ""
        x_min = float(np.min(finite_x))
        x_max = float(np.max(finite_x))
        if x_max <= x_min:
            x_max = x_min + 1.0
        all_values = np.concatenate(
            [np.asarray(values, dtype=np.float64) for _name, values in report.series]
        )
        finite_values = all_values[np.isfinite(all_values) & (all_values >= 0.0)]
        y_max = float(np.max(np.log10(1.0 + finite_values))) if finite_values.size else 1.0
        y_max = max(1.0, y_max)
        grid_pen = QPen(QColor("#cbd5e1"), 1)
        label_font = print_font(9.0, text=report.time_label)
        painter.setFont(label_font)
        for tick in range(6):
            fraction = tick / 5.0
            y = plot.bottom() - fraction * plot.height()
            painter.setPen(grid_pen)
            painter.drawLine(QLineF(plot.left(), y, plot.right(), y))
            raw_value = 10 ** (fraction * y_max) - 1.0
            painter.setPen(QColor("#334155"))
            painter.drawText(
                QRectF(5, y - 10, 78, 20),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{raw_value:.3g}",
            )
            x_position = plot.left() + fraction * plot.width()
            painter.setPen(grid_pen)
            painter.drawLine(QLineF(x_position, plot.top(), x_position, plot.bottom()))
            time_value = x_min + fraction * (x_max - x_min)
            painter.setPen(QColor("#334155"))
            painter.drawText(
                QRectF(x_position - 55.0, plot.bottom() + 4.0, 110.0, 20.0),
                Qt.AlignmentFlag.AlignCenter,
                f"{time_value:.4g}",
            )
        for name, raw_series in report.series:
            values = np.asarray(raw_series, dtype=np.float64)
            usable = np.isfinite(x) & np.isfinite(values) & (values >= 0.0)
            indices = np.flatnonzero(usable)
            if indices.size < 2:
                continue
            painter.setPen(QPen(QColor(_COLORS[name]), 3, Qt.PenStyle.SolidLine))
            previous = None
            for index in indices:
                px = plot.left() + (x[index] - x_min) / (x_max - x_min) * plot.width()
                py = plot.bottom() - np.log10(1.0 + values[index]) / y_max * plot.height()
                current = (float(px), float(py))
                if previous is not None:
                    painter.drawLine(QLineF(previous[0], previous[1], current[0], current[1]))
                previous = current
        legend_x = 110.0
        for name, _values in report.series:
            painter.setPen(QPen(QColor(_COLORS[name]), 5))
            painter.drawLine(QLineF(legend_x, 590.0, legend_x + 28.0, 590.0))
            painter.setPen(QColor("#172033"))
            painter.drawText(QRectF(legend_x + 34.0, 576.0, 80.0, 28.0), name)
            legend_x += 135.0
        painter.drawText(
            QRectF(620, 610, 300, 25),
            Qt.AlignmentFlag.AlignCenter,
            report.time_label,
        )
    finally:
        painter.end()
    payload = QByteArray()
    buffer = QBuffer(payload)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    # PySide 6.11 accepts the documented string format at runtime while its
    # bundled type stub still declares only a bytes-like format.
    image.save(buffer, "PNG")  # type: ignore[call-overload]
    return "data:image/png;base64," + bytes(payload.toBase64().data()).decode("ascii")


def _labels(language: AppLanguage) -> dict[str, str]:
    return {
        AppLanguage.RU: {
            "title": "Разгонка газовой смеси",
            "chart": "Временная диаграмма отклика C1–C5",
            "chart_scale": "Ось Y: логарифмическое представление log10(1 + отклик)",
            "result": "Предварительная интерпретация пробы",
            "confidence": "Уверенность",
            "composition": "Состав в области максимального отклика",
            "baseline": "Фон",
            "representative": "Представительное значение",
            "share": "Доля C1–C5",
            "peak": "Максимум",
            "ratio": "Отношение",
            "value": "Значение",
            "limitations": "Контроль качества и ограничения",
            "probable_dry_gas": "вероятный сухой газ",
            "probable_gas_or_condensate": "вероятный газ/газоконденсат",
            "probable_liquid_hydrocarbons": "вероятные жидкие УВ (нефть/конденсат)",
            "heavy_or_residual_hydrocarbons": "тяжёлые/остаточные жидкие УВ или загрязнённая проба",
            "background_or_no_hydrocarbons": "фоновый сигнал или недостаточно УВ-компонентов",
            "very_light_dry_gas": "очень лёгкий сухой газ; возможно непродуктивный",
            "light_dry_gas": "возможный лёгкий сухой газ",
            "productive_gas_increasing_wetness": (
                "газ с увеличением содержания тяжёлых УВ"
            ),
            "gas_increasing_wetness": "газ с увеличением содержания тяжёлых УВ",
            "wet_gas_or_gas_condensate": "влажный газ или газоконденсат",
            "light_oil_high_gor": "лёгкая нефть с высоким газовым фактором",
            "gas_condensate_or_high_api_oil": (
                "газоконденсат или лёгкая нефть с высоким API/GOR"
            ),
            "productive_oil_decreasing_gravity": (
                "нефть с увеличением плотности"
            ),
            "poor_low_gravity_oil": (
                "бедная тяжёлая нефть с низким газосодержанием"
            ),
            "heavy_or_residual_oil": "тяжёлая или остаточная нефть",
            "low": "низкая",
            "medium": "средняя",
            "high": "высокая",
        },
        AppLanguage.KK: {
            "title": "Газ қоспасын айдау",
            "chart": "C1–C5 жауабының уақыт диаграммасы",
            "chart_scale": "Y осі: log10(1 + жауап) логарифмдік көрінісі",
            "result": "Сынаманың алдын ала интерпретациясы",
            "confidence": "Сенімділік",
            "composition": "Максималды жауап аймағындағы құрам",
            "baseline": "Фон",
            "representative": "Өкілдік мән",
            "share": "C1–C5 үлесі",
            "peak": "Максимум",
            "ratio": "Қатынас",
            "value": "Мән",
            "limitations": "Сапаны бақылау және шектеулер",
            "probable_dry_gas": "ықтимал құрғақ газ",
            "probable_gas_or_condensate": "ықтимал газ/газ конденсаты",
            "probable_liquid_hydrocarbons": "ықтимал сұйық көмірсутектер",
            "heavy_or_residual_hydrocarbons": "ауыр/қалдық сұйық көмірсутектер немесе ластанған сынама",
            "background_or_no_hydrocarbons": "фондық сигнал немесе көмірсутек компоненттері жеткіліксіз",
            "very_light_dry_gas": "өте жеңіл құрғақ газ; өнімсіз болуы мүмкін",
            "light_dry_gas": "ықтимал жеңіл құрғақ газ",
            "productive_gas_increasing_wetness": (
                "ауыр көмірсутектер мөлшері артатын газ"
            ),
            "gas_increasing_wetness": "ауыр көмірсутектер мөлшері артатын газ",
            "wet_gas_or_gas_condensate": "ылғалды газ немесе газ конденсаты",
            "light_oil_high_gor": "газ факторы жоғары жеңіл мұнай",
            "gas_condensate_or_high_api_oil": (
                "газ конденсаты немесе API/GOR жоғары жеңіл мұнай"
            ),
            "productive_oil_decreasing_gravity": (
                "тығыздығы артатын мұнай"
            ),
            "poor_low_gravity_oil": "газ мөлшері аз ауыр мұнай",
            "heavy_or_residual_oil": "ауыр немесе қалдық мұнай",
            "low": "төмен",
            "medium": "орташа",
            "high": "жоғары",
        },
        AppLanguage.EN: {
            "title": "Gas mixture ramp analysis",
            "chart": "C1–C5 detector response versus time",
            "chart_scale": "Y axis: logarithmic display log10(1 + response)",
            "result": "Preliminary sample interpretation",
            "confidence": "Confidence",
            "composition": "Composition around maximum response",
            "baseline": "Baseline",
            "representative": "Representative value",
            "share": "C1–C5 share",
            "peak": "Peak",
            "ratio": "Ratio",
            "value": "Value",
            "limitations": "Quality control and limitations",
            "probable_dry_gas": "probable dry gas",
            "probable_gas_or_condensate": "probable gas/gas condensate",
            "probable_liquid_hydrocarbons": "probable liquid hydrocarbons (oil/condensate)",
            "heavy_or_residual_hydrocarbons": "heavy/residual liquid hydrocarbons or contaminated sample",
            "background_or_no_hydrocarbons": "background response or insufficient hydrocarbon components",
            "very_light_dry_gas": (
                "very light dry gas; possibly non-productive"
            ),
            "light_dry_gas": "possible light dry gas",
            "productive_gas_increasing_wetness": (
                "gas with increasing heavy-hydrocarbon content"
            ),
            "gas_increasing_wetness": (
                "gas with increasing heavy-hydrocarbon content"
            ),
            "wet_gas_or_gas_condensate": "wet gas or gas condensate",
            "light_oil_high_gor": "light oil with high GOR",
            "gas_condensate_or_high_api_oil": (
                "gas condensate or high-API/high-GOR light oil"
            ),
            "productive_oil_decreasing_gravity": (
                "oil with increasing density"
            ),
            "poor_low_gravity_oil": "poor low-gravity oil with low gas content",
            "heavy_or_residual_oil": "heavy or residual oil",
            "low": "low",
            "medium": "medium",
            "high": "high",
        },
    }[language]

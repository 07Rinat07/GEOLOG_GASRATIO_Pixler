from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

from geoworkbench.domain.models import (
    MasterlogColumnTemplate,
    MasterlogCurveStyle,
    MasterlogHeaderElement,
    MasterlogTemplate,
)
from geoworkbench.forms.models import (
    FormAxisKind,
    FormColumn,
    FormDocument,
    FormTemplateOrigin,
    FormTrack,
    ParameterBinding,
)
from geoworkbench.importers.delphi_stream import (
    DelphiBinary,
    DelphiBinaryReader,
    DelphiComponent,
    DelphiComponentStream,
    DelphiStreamError,
    get_property,
    parse_delphi_component_stream,
)
from geoworkbench.tablet.models import CurveLineStyle, CurveStyle, TrackKind, XScale

if TYPE_CHECKING:
    from geoworkbench.printing.image_assets import ImageAsset



class SkfImportError(ValueError):
    """Raised when an SKF file cannot be converted into application models."""


@dataclass(frozen=True, slots=True)
class SkfImportReport:
    source_name: str
    source_size_bytes: int
    source_sha256: str
    root_class: str
    component_count: int
    column_count: int
    header_element_count: int
    image_asset_count: int
    signature_offset: int
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SkfImportResult:
    form: FormDocument
    header_template: MasterlogTemplate
    image_assets: dict[str, ImageAsset]
    report: SkfImportReport
    component_stream: DelphiComponentStream


@dataclass(slots=True)
class _Geometry:
    left: float
    top: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.left + self.width

    @property
    def bottom(self) -> float:
        return self.top + self.height


@dataclass(slots=True)
class _ImportContext:
    source_name: str
    root: DelphiComponent
    dpi: float = 96.0
    coordinate_to_mm: float | None = None
    warnings: list[str] = field(default_factory=list)
    image_assets: dict[str, ImageAsset] = field(default_factory=dict)

    @property
    def unit_to_mm(self) -> float:
        return self.coordinate_to_mm or (25.4 / self.dpi)


def import_skf_file(source: str | Path) -> SkfImportResult:
    path = Path(source)
    if not path.is_file() or path.is_symlink():
        raise SkfImportError("Источник SKF должен быть обычным файлом")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise SkfImportError(f"Не удалось получить сведения о SKF: {path}") from exc
    if size > DelphiBinaryReader.MAX_STREAM_BYTES:
        raise SkfImportError("SKF превышает безопасный предел 64 МБ")
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise SkfImportError(f"Не удалось прочитать SKF: {path}") from exc
    return import_skf_payload(payload, source_name=path.name)


def import_skf_payload(payload: bytes, *, source_name: str = "imported.skf") -> SkfImportResult:
    try:
        stream = parse_delphi_component_stream(payload)
    except DelphiStreamError as exc:
        raise SkfImportError(str(exc)) from exc
    context = _ImportContext(source_name, stream.root)
    form = _build_form(context)
    template = _build_masterlog_template(context, form)
    form.print_header_template_id = template.template_id
    report = SkfImportReport(
        source_name=source_name,
        source_size_bytes=len(payload),
        source_sha256=sha256(payload).hexdigest(),
        root_class=stream.root.class_name,
        component_count=len(stream.root.walk()),
        column_count=len(form.columns),
        header_element_count=len(template.header_elements),
        image_asset_count=len(context.image_assets),
        signature_offset=stream.signature_offset,
        warnings=tuple(context.warnings),
    )
    template.properties["skf_import_report"] = {
        "source_name": report.source_name,
        "source_size_bytes": report.source_size_bytes,
        "source_sha256": report.source_sha256,
        "root_class": report.root_class,
        "component_count": report.component_count,
        "column_count": report.column_count,
        "header_element_count": report.header_element_count,
        "image_asset_count": report.image_asset_count,
        "signature_offset": report.signature_offset,
        "warnings": list(report.warnings),
    }
    return SkfImportResult(form, template, dict(context.image_assets), report, stream)


def _build_form(context: _ImportContext) -> FormDocument:
    axis = _detect_axis(context.root)
    groups = _candidate_column_groups(context.root)
    candidates = groups[0] if groups else _fallback_columns(context.root)
    columns: list[FormColumn] = []
    for index, component in enumerate(candidates):
        geometry = _geometry(component)
        if geometry is None:
            continue
        title = _display_text(component) or _clean_component_name(component.name) or f"Column {index + 1}"
        group_title = _display_text(_parent_of(context.root, component)) if component is not context.root else ""
        kind = _track_kind(component, title)
        bindings = _bindings(component, context)
        if kind in {TrackKind.CURVE, TrackKind.GAS, TrackKind.DEXP} and not bindings:
            binding = _binding_from_component(component, context)
            if binding is not None:
                bindings = [binding]
        show_labels = _bool_property(component, "ShowLabels", "ShowText", "ShowCaption", default=False)
        track = FormTrack.create(
            title=title,
            kind=kind,
            bindings=bindings,
            locked=False,
            grid_x=_bool_property(component, "GridX", "ShowVerticalGrid", default=True),
            grid_y=_bool_property(component, "GridY", "ShowHorizontalGrid", default=True),
            grid_alpha=_float_property(component, "GridAlpha", default=0.2, minimum=0.0, maximum=1.0),
            x_axis_label=_text_property(component, "AxisLabel", "XAxisLabel", "Unit"),
            title_orientation=_orientation(component),
            title_position=_vertical_position(component),
            show_interval_labels=show_labels,
        )
        width = max(80, min(2000, int(round(geometry.width))))
        columns.append(
            FormColumn.create(
                title=title,
                group_title=group_title or "",
                width=width,
                locked=False,
                tracks=[track],
                title_orientation=_orientation(component),
                title_position=_vertical_position(component),
            )
        )
    if not columns:
        context.warnings.append("Колонки SKF не распознаны явно; создана универсальная графическая колонка")
        columns = [
            FormColumn.create(
                "Imported SKF",
                width=320,
                tracks=[FormTrack.create("Imported SKF", TrackKind.CURVE)],
            )
        ]
    name = _display_text(context.root) or Path(context.source_name).stem
    description = (
        f"Imported from Delphi SKF component stream ({context.root.class_name}). "
        "The linked Masterlog template stores source traceability and the SKF import report."
    )
    return FormDocument(
        form_id=str(uuid4()),
        name=name[:160],
        axis_kind=axis,
        columns=columns,
        description=description,
        origin=FormTemplateOrigin.USER,
        read_only=False,
        style_id="imported-skf",
    )


def _build_masterlog_template(context: _ImportContext, form: FormDocument) -> MasterlogTemplate:
    root_geometry = _document_geometry(context.root)
    context.coordinate_to_mm = _coordinate_unit_to_mm(root_geometry.width)
    page_width_mm = max(210.0, root_geometry.width * context.unit_to_mm)
    header_nodes, header_bottom_units = _header_components(context.root, root_geometry)
    header_elements: list[MasterlogHeaderElement] = []
    for component, absolute_geometry in header_nodes:
        element = _header_element(
            component, context, root_geometry, absolute_geometry=absolute_geometry
        )
        if element is not None:
            header_elements.append(element)
    if not header_elements:
        header_elements.append(
            MasterlogHeaderElement(
                str(uuid4()),
                "text",
                5.0,
                3.0,
                max(50.0, page_width_mm - 10.0),
                8.0,
                {"text": form.name, "font_size_mm": 4.5, "align": "center"},
            )
        )
        context.warnings.append("Элементы шапки SKF не распознаны; создан заголовок-заполнитель")
        header_bottom_units = 50.0
    total_px = sum(max(column.width, 1) for column in form.columns)
    printable_width_mm = max(120.0, page_width_mm - 10.0)
    columns: list[MasterlogColumnTemplate] = []
    for form_column in form.columns:
        track = form_column.tracks[0]
        mnemonics = [binding.source_mnemonic or binding.canonical_parameter_id for binding in track.bindings]
        curve_styles = {
            mnemonic: MasterlogCurveStyle(
                color=binding.style.color,
                width=binding.style.width,
                line_style=binding.style.line_style.value,
                x_min=binding.x_min,
                x_max=binding.x_max,
            )
            for mnemonic, binding in zip(mnemonics, track.bindings, strict=False)
        }
        x_min, x_max = _combined_range(track.bindings)
        columns.append(
            MasterlogColumnTemplate(
                column_id=form_column.column_id,
                title=form_column.title,
                column_type=track.kind.value,
                width_mm=max(8.0, printable_width_mm * form_column.width / total_px),
                curve_mnemonics=mnemonics,
                properties={
                    "group_title": form_column.group_title,
                    "title_orientation": form_column.title_orientation,
                    "title_position": form_column.title_position,
                    "source": "skf",
                },
                x_scale=(track.bindings[0].x_scale.value if track.bindings else "linear"),
                x_min=x_min,
                x_max=x_max,
                curve_styles=curve_styles,
                grid_x=track.grid_x,
                grid_y=track.grid_y,
                grid_major_divisions=5,
                grid_minor_divisions=5,
                grid_alpha=track.grid_alpha,
            )
        )
    header_height_mm = max(20.0, min(500.0, header_bottom_units * context.unit_to_mm + 3.0))
    return MasterlogTemplate(
        template_id=str(uuid4()),
        name=f"{form.name} — SKF header"[:200],
        page_format="roll",
        depth_scale=500,
        header_height_mm=header_height_mm,
        header_elements=header_elements,
        columns=columns,
        properties={
            "source_format": "skf-delphi-component-stream",
            "source_file": context.source_name,
            "orientation": "landscape" if root_geometry.width >= root_geometry.height else "portrait",
            "custom_width_mm": page_width_mm,
            "custom_height_mm": max(297.0, root_geometry.height * context.unit_to_mm),
            "linked_form_id": form.form_id,
        },
    )


def _candidate_column_groups(root: DelphiComponent) -> list[list[DelphiComponent]]:
    groups: list[tuple[float, list[DelphiComponent]]] = []
    for parent in root.walk():
        candidates = [child for child in parent.children if _is_column_candidate(child)]
        if len(candidates) < 2:
            continue
        candidates.sort(
            key=lambda item: (
                geometry.left if (geometry := _geometry(item)) is not None else 0.0
            )
        )
        geometries = [_geometry(item) for item in candidates]
        valid = [item for item in geometries if item is not None]
        if len(valid) < 2:
            continue
        span = max(item.right for item in valid) - min(item.left for item in valid)
        median_height = sorted(item.height for item in valid)[len(valid) // 2]
        score = len(valid) * 1000 + span + median_height
        groups.append((score, candidates))
    return [items for _, items in sorted(groups, key=lambda pair: pair[0], reverse=True)]


def _fallback_columns(root: DelphiComponent) -> list[DelphiComponent]:
    candidates = [component for component in root.walk() if _is_column_candidate(component)]
    candidates.sort(
        key=lambda item: (
            geometry.left if (geometry := _geometry(item)) is not None else 0.0
        )
    )
    return candidates[:64]


def _is_column_candidate(component: DelphiComponent) -> bool:
    geometry = _geometry(component)
    if geometry is None or geometry.width < 18 or geometry.height < 80:
        return False
    token = _tokens(component)
    class_token = component.class_name.casefold()
    keyword = any(
        value in token
        for value in (
            "column",
            "track",
            "curve",
            "graph",
            "chart",
            "scale",
            "depth",
            "глуб",
            "литолог",
            "шлам",
            "газ",
            "стратиграф",
            "кальц",
            "lba",
            "лба",
        )
    )
    has_curve_child = any(_curve_mnemonic(child) for child in component.walk()[1:])
    panel_like = any(value in class_token for value in ("panel", "frame", "track", "chart"))
    return keyword or has_curve_child or (panel_like and len(component.children) >= 2)


def _document_geometry(root: DelphiComponent) -> _Geometry:
    explicit = _geometry(root)
    if explicit is not None:
        return explicit
    top_level = [geometry for child in root.children if (geometry := _geometry(child)) is not None]
    if not top_level:
        return _Geometry(0.0, 0.0, 1200.0, 900.0)
    left = min(item.left for item in top_level)
    top = min(item.top for item in top_level)
    right = max(item.right for item in top_level)
    bottom = max(item.bottom for item in top_level)
    return _Geometry(left, top, max(1.0, right - left), max(1.0, bottom - top))


def _coordinate_unit_to_mm(document_width: float) -> float:
    # Native GeoSketch print documents use page coordinates close to millimetres
    # (typically 210/297/420 wide). Synthetic/legacy component streams often use
    # screen pixels around 800-1600 wide. Preserve both representations.
    return 1.0 if 80.0 <= document_width <= 500.0 else 25.4 / 96.0


def _absolute_component_geometries(
    root: DelphiComponent,
) -> list[tuple[DelphiComponent, _Geometry]]:
    result: list[tuple[DelphiComponent, _Geometry]] = []

    def visit(node: DelphiComponent, parent_left: float, parent_top: float) -> None:
        geometry = _geometry(node)
        left = parent_left
        top = parent_top
        if geometry is not None:
            left += geometry.left
            top += geometry.top
            absolute = _Geometry(left, top, geometry.width, geometry.height)
            if node is not root:
                result.append((node, absolute))
        for child in node.children:
            visit(child, left, top)

    visit(root, 0.0, 0.0)
    return result


def _contains_print_series(component: DelphiComponent) -> bool:
    return any(
        "series" in node.class_name.casefold()
        for node in component.walk()
    )


def _header_components(
    root: DelphiComponent, root_geometry: _Geometry
) -> tuple[list[tuple[DelphiComponent, _Geometry]], float]:
    absolute = _absolute_component_geometries(root)
    geometry_by_identity = {id(component): geometry for component, geometry in absolute}

    body_roots = [
        component
        for component in root.children
        if (geometry := geometry_by_identity.get(id(component))) is not None
        and (
            _contains_print_series(component)
            or (
                component.class_name.casefold().endswith("printfield")
                and geometry.height >= max(80.0, root_geometry.height * 0.30)
            )
        )
    ]
    body_root_ids = {id(component) for component in body_roots}
    body_top = min(
        (geometry_by_identity[id(component)].top for component in body_roots),
        default=root_geometry.top + root_geometry.height * 0.35,
    )
    body_top = max(root_geometry.top + 20.0, body_top)

    elements: list[tuple[DelphiComponent, _Geometry]] = []
    bottom = root_geometry.top

    def visit(node: DelphiComponent, inside_body: bool = False) -> None:
        nonlocal bottom
        if node is root:
            for child in node.children:
                visit(child, False)
            return
        now_inside_body = inside_body or id(node) in body_root_ids
        if now_inside_body:
            return
        geometry = geometry_by_identity.get(id(node))
        if geometry is not None and geometry.top < body_top:
            if (
                geometry.width > 1.0
                and geometry.height > 1.0
                and (_display_text(node) or _binary_properties(node) or _is_shape(node))
            ):
                elements.append((node, geometry))
                bottom = max(bottom, min(geometry.bottom, body_top))
            for child in node.children:
                visit(child, False)

    visit(root)
    normalized_bottom = max(0.0, bottom - root_geometry.top)
    return elements[:1000], normalized_bottom


def _header_element(
    component: DelphiComponent,
    context: _ImportContext,
    root_geometry: _Geometry,
    *,
    absolute_geometry: _Geometry | None = None,
) -> MasterlogHeaderElement | None:
    geometry = absolute_geometry or _geometry(component)
    if geometry is None:
        return None
    x = max(0.0, (geometry.left - root_geometry.left) * context.unit_to_mm)
    y = max(0.0, (geometry.top - root_geometry.top) * context.unit_to_mm)
    width = max(1.0, geometry.width * context.unit_to_mm)
    height = max(1.0, geometry.height * context.unit_to_mm)
    image = _extract_image(component, context)
    if image is not None:
        return MasterlogHeaderElement(
            str(uuid4()),
            "image",
            x,
            y,
            width,
            height,
            {"asset_ref": image.asset_id, "mode": "fit", "source_component": component.name},
        )
    if _is_shape(component):
        return MasterlogHeaderElement(
            str(uuid4()),
            "line",
            x,
            y,
            width,
            height,
            {
                "color": _color(component),
                "line_width": max(0.2, _float_property(component, "Pen.Width", "LineWidth", default=1.0)),
                "source_component": component.name,
            },
        )
    text = _display_text(component)
    if not text:
        return None
    data_field = _text_property(component, "DataField", "FieldName", "Field", "Binding")
    element_type = "field" if data_field else "text"
    properties: dict[str, Any] = {
        "text": text,
        "color": _color(component, foreground=True),
        "font_size_mm": max(1.5, _font_size(component) * 0.3528),
        "align": _alignment(component),
        "orientation": _orientation(component),
        "vertical_position": _vertical_position(component),
        "source_component": component.name,
        "source_class": component.class_name,
    }
    if data_field:
        properties["field"] = _header_field_name(data_field)
    return MasterlogHeaderElement(str(uuid4()), element_type, x, y, width, height, properties)


def _bindings(component: DelphiComponent, context: _ImportContext) -> list[ParameterBinding]:
    bindings: list[ParameterBinding] = []
    seen: set[str] = set()
    for node in component.walk():
        binding = _binding_from_component(node, context)
        if binding is None:
            continue
        key = (binding.source_mnemonic or binding.canonical_parameter_id).casefold()
        if key in seen:
            continue
        seen.add(key)
        bindings.append(binding)
    return bindings[:64]


def _binding_from_component(
    component: DelphiComponent, context: _ImportContext
) -> ParameterBinding | None:
    mnemonic = _curve_mnemonic(component)
    if not mnemonic:
        return None
    display = _display_text(component) or _text_property(
        component, "Description", "ParameterName", "LongName"
    ) or mnemonic
    unit = _text_property(component, "Unit", "Units", "Measure", "UOM")
    source_was_logarithmic = _is_log_scale(component)
    # Imported forms follow the application-wide linear default.  The source
    # flag is used only to widen a former positive-only range to zero; users can
    # opt into logarithmic mode explicitly after import.
    scale = XScale.LINEAR
    minimum = _number_property(component, "XMin", "ScaleMin", "Min", "Minimum", "LeftValue")
    maximum = _number_property(component, "XMax", "ScaleMax", "Max", "Maximum", "RightValue")
    if (
        source_was_logarithmic
        and minimum is not None
        and maximum is not None
        and minimum > 0
        and maximum > 0
    ):
        minimum = 0.0
    x_min, x_max = _safe_range(scale, minimum, maximum)
    return ParameterBinding.create(
        canonical_parameter_id=_safe_identifier(mnemonic, prefix="parameter"),
        display_name=display[:120],
        source_mnemonic=mnemonic[:80],
        unit=unit[:40],
        style=CurveStyle(
            color=_color(component),
            width=max(0.5, min(10.0, _float_property(component, "LineWidth", "Pen.Width", default=1.5))),
            line_style=_line_style(component),
        ),
        x_scale=scale,
        x_min=x_min,
        x_max=x_max,
    )


def _curve_mnemonic(component: DelphiComponent) -> str:
    value = _text_property(
        component,
        "Mnemonic",
        "Mnem",
        "CurveMnemonic",
        "CurveName",
        "ParameterCode",
        "ParamCode",
        "Channel",
        "DataField",
        "FieldName",
        "Code",
    )
    value = value.strip()
    if not value:
        name = component.name.strip()
        if re.fullmatch(r"[A-Za-zА-Яа-я][A-Za-zА-Яа-я0-9_:\-/]{0,79}", name):
            token = component.class_name.casefold()
            if any(part in token for part in ("curve", "series", "graph", "channel")):
                value = name
    return re.sub(r"\s+", "_", value)[:80]


def _track_kind(component: DelphiComponent, title: str) -> TrackKind:
    token = f"{_tokens(component)} {title.casefold()}"
    mapping = (
        (TrackKind.DEPTH, ("depth", "глубин", "глубина", "md")),
        (TrackKind.STRATIGRAPHY, ("stratig", "стратиграф")),
        (TrackKind.LITHOLOGY, ("lith", "литолог")),
        (TrackKind.CUTTINGS, ("cutting", "шламограмм", "шлам")),
        (TrackKind.CALCIMETRY, ("calcimet", "кальциметр", "caco3")),
        (TrackKind.LBA, ("lba", "лба", "bitum")),
        (TrackKind.TEXT, ("description", "описание", "text", "memo")),
        (TrackKind.DEXP, ("dexp", "d-эксп", "dэксп")),
        (TrackKind.GAS, ("gas", "газ", "c1", "c2", "c3", "c4", "c5")),
        (TrackKind.INTERPRETATION, ("interpret", "интерпретац")),
    )
    for kind, keywords in mapping:
        if any(keyword in token for keyword in keywords):
            return kind
    return TrackKind.CURVE


def _detect_axis(root: DelphiComponent) -> FormAxisKind:
    token = " ".join(_tokens(component) for component in root.walk()).casefold()
    if any(value in token for value in ("time", "datetime", "время", "временн")) and not any(
        value in token for value in ("depth", "глубин", "глубина")
    ):
        return FormAxisKind.TIME
    return FormAxisKind.DEPTH


def _geometry(component: DelphiComponent) -> _Geometry | None:
    left = _number_property(component, "Left", "X", "PosX")
    top = _number_property(component, "Top", "Y", "PosY")
    width = _number_property(component, "Width", "ClientWidth", "W")
    height = _number_property(component, "Height", "ClientHeight", "H")
    if width is None or height is None:
        return None
    return _Geometry(float(left or 0.0), float(top or 0.0), float(width), float(height))


def _display_text(component: DelphiComponent | None) -> str:
    if component is None:
        return ""
    return _text_property(
        component,
        "Caption",
        "Title",
        "Text",
        "Label",
        "DisplayName",
        "Description",
    ).strip()


def _text_property(component: DelphiComponent, *names: str) -> str:
    value = get_property(component, *names, default="")
    if isinstance(value, str):
        return value.replace("\x00", "").strip()
    return ""


def _number_property(component: DelphiComponent, *names: str) -> float | None:
    value = get_property(component, *names)
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", "."))
        except ValueError:
            return None
    return None


def _bool_property(
    component: DelphiComponent, *names: str, default: bool
) -> bool:
    value = get_property(component, *names, default=default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.casefold() in {"true", "yes", "1", "да"}
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _float_property(
    component: DelphiComponent,
    *names: str,
    default: float,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    value = _number_property(component, *names)
    result = default if value is None else float(value)
    if minimum is not None:
        result = max(minimum, result)
    if maximum is not None:
        result = min(maximum, result)
    return result


def _orientation(component: DelphiComponent) -> str:
    raw = str(get_property(component, "TextOrientation", "Orientation", "Rotate", "Angle", default=""))
    normalized = raw.casefold().replace("°", "")
    if normalized in {"90", "+90", "vertical", "topdown", "clockwise"}:
        return "vertical_top_to_bottom"
    if normalized in {"-90", "270", "bottomup", "counterclockwise"}:
        return "vertical_bottom_to_top"
    return "horizontal"


def _vertical_position(component: DelphiComponent) -> str:
    raw = str(get_property(component, "VerticalAlignment", "TextPosition", "VAlign", default=""))
    normalized = raw.casefold()
    if any(value in normalized for value in ("top", "верх", "roof")):
        return "top"
    if any(value in normalized for value in ("bottom", "низ", "base")):
        return "bottom"
    return "center"


def _alignment(component: DelphiComponent) -> str:
    raw = str(get_property(component, "Alignment", "TextAlign", "HAlign", default=""))
    normalized = raw.casefold()
    if "right" in normalized or "прав" in normalized:
        return "right"
    if "center" in normalized or "центр" in normalized:
        return "center"
    return "left"


def _font_size(component: DelphiComponent) -> float:
    value = _number_property(component, "Font.Height", "Font.Size", "FontSize")
    if value is None:
        return 10.0
    value = abs(value)
    if value > 30:
        value *= 0.75
    return max(5.0, min(72.0, value))


def _color(component: DelphiComponent, *, foreground: bool = False) -> str:
    names = ("Font.Color", "TextColor", "Color") if foreground else (
        "Pen.Color",
        "LineColor",
        "SeriesColor",
        "Color",
        "Font.Color",
    )
    raw = get_property(component, *names)
    return _delphi_color(raw)


def _delphi_color(raw: Any) -> str:
    named = {
        "clblack": "#000000",
        "clwhite": "#ffffff",
        "clred": "#ff0000",
        "clgreen": "#008000",
        "clblue": "#0000ff",
        "clyellow": "#ffff00",
        "cllime": "#00ff00",
        "clfuchsia": "#ff00ff",
        "claqua": "#00ffff",
        "clgray": "#808080",
        "clsilver": "#c0c0c0",
        "clmaroon": "#800000",
        "clnavy": "#000080",
        "clteal": "#008080",
        "clpurple": "#800080",
        "clolive": "#808000",
    }
    if isinstance(raw, str):
        if raw.casefold() in named:
            return named[raw.casefold()]
        if re.fullmatch(r"#[0-9a-fA-F]{6}", raw):
            return raw.casefold()
    if isinstance(raw, int) and not isinstance(raw, bool):
        value = raw & 0xFFFFFF
        red = value & 0xFF
        green = (value >> 8) & 0xFF
        blue = (value >> 16) & 0xFF
        return f"#{red:02x}{green:02x}{blue:02x}"
    return "#2563eb"


def _line_style(component: DelphiComponent) -> CurveLineStyle:
    raw = str(get_property(component, "Pen.Style", "LineStyle", "Style", default="")).casefold()
    if "dashdot" in raw or "dash_dot" in raw:
        return CurveLineStyle.DASH_DOT
    if "dash" in raw:
        return CurveLineStyle.DASH
    if "dot" in raw:
        return CurveLineStyle.DOT
    return CurveLineStyle.SOLID


def _is_log_scale(component: DelphiComponent) -> bool:
    raw = str(get_property(component, "Scale", "ScaleType", "AxisScale", default="")).casefold()
    return "log" in raw or _bool_property(component, "Logarithmic", "LogScale", default=False)


def _safe_range(
    scale: XScale, minimum: float | None, maximum: float | None
) -> tuple[float | None, float | None]:
    if minimum is None or maximum is None or not (minimum < maximum):
        return None, None
    if scale is XScale.LOGARITHMIC and minimum <= 0:
        return None, None
    return float(minimum), float(maximum)


def _combined_range(bindings: list[ParameterBinding]) -> tuple[float | None, float | None]:
    ranges = [(item.x_min, item.x_max) for item in bindings if item.x_min is not None and item.x_max is not None]
    if not ranges:
        return None, None
    return min(item[0] for item in ranges), max(item[1] for item in ranges)



def _is_shape(component: DelphiComponent) -> bool:
    token = f"{component.class_name} {component.name}".casefold()
    return any(value in token for value in ("shape", "line", "bevel", "separator", "border"))


def _binary_properties(component: DelphiComponent) -> list[DelphiBinary]:
    result: list[DelphiBinary] = []
    for value in component.properties.values():
        if isinstance(value, DelphiBinary):
            result.append(value)
        elif isinstance(value, list):
            result.extend(item for item in value if isinstance(item, DelphiBinary))
    return result


def _extract_image(component: DelphiComponent, context: _ImportContext) -> ImageAsset | None:
    try:
        from PySide6.QtCore import QBuffer, QIODevice
        from PySide6.QtGui import QImage
        from geoworkbench.printing.image_assets import ImageAsset, PNG_MEDIA_TYPE
    except ImportError:
        return None
    for binary in _binary_properties(component):
        payload = _find_raster_payload(binary.payload)
        if payload is None:
            continue
        image = QImage.fromData(payload)
        if image.isNull():
            continue
        buffer = QBuffer()
        if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
            continue
        try:
            if not image.save(buffer, cast(Any, "PNG")):
                continue
            png = bytes(buffer.data().data())
        finally:
            buffer.close()
        digest = sha256(png).hexdigest()
        asset = ImageAsset(
            f"sha256:{digest}",
            f"{_clean_component_name(component.name) or 'skf-image'}.png",
            PNG_MEDIA_TYPE,
            png,
        )
        context.image_assets.setdefault(asset.asset_id, asset)
        return asset
    return None


def _find_raster_payload(payload: bytes) -> bytes | None:
    signatures = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"BM")
    positions = [(payload.find(signature), signature) for signature in signatures]
    positions = [(position, signature) for position, signature in positions if position >= 0]
    if not positions:
        return None
    position, _ = min(positions, key=lambda item: item[0])
    return payload[position:]


def _header_field_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", ".", value.casefold()).strip(".")
    return f"header.{normalized or 'field'}"


def _safe_identifier(value: str, *, prefix: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    if not normalized:
        normalized = sha256(value.encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"{prefix}-{normalized}"[:120]


def _clean_component_name(value: str) -> str:
    return re.sub(r"[_\-]+", " ", value).strip()


def _tokens(component: DelphiComponent) -> str:
    pieces = [component.class_name, component.name, _display_text(component)]
    for key in ("Kind", "Type", "Role", "DataField", "Mnemonic", "Parameter"):
        value = get_property(component, key)
        if isinstance(value, str):
            pieces.append(value)
    return " ".join(pieces).casefold()


def _parent_of(root: DelphiComponent, target: DelphiComponent) -> DelphiComponent | None:
    for node in root.walk():
        if target in node.children:
            return node
    return None

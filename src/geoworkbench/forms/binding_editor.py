from __future__ import annotations

from dataclasses import dataclass, replace
from typing import cast

from geoworkbench.forms.editor import FormStructureEditor
from geoworkbench.forms.models import ParameterBinding
from geoworkbench.tablet.models import CurveLineStyle, CurveStyle, XScale

_UNSET = object()


@dataclass(slots=True)
class TrackBindingEditor:
    """Qt-independent editor for ParameterBinding objects of one form track."""

    structure: FormStructureEditor
    track_id: str

    @property
    def track(self):
        return self.structure.track(self.track_id)[1]

    @property
    def bindings(self) -> tuple[ParameterBinding, ...]:
        return tuple(self.track.bindings)

    def binding(self, binding_id: str) -> ParameterBinding:
        for binding in self.track.bindings:
            if binding.binding_id == binding_id:
                return binding
        raise KeyError(binding_id)

    def add(
        self,
        canonical_parameter_id: str,
        display_name: str,
        *,
        source_mnemonic: str | None = None,
        unit: str = "",
        color: str = "#2563eb",
        width: float = 1.5,
        line_style: CurveLineStyle = CurveLineStyle.SOLID,
        x_scale: XScale = XScale.LINEAR,
        x_min: float | None = None,
        x_max: float | None = None,
        index: int | None = None,
    ) -> ParameterBinding:
        binding = ParameterBinding.create(
            canonical_parameter_id,
            display_name,
            source_mnemonic=source_mnemonic,
            unit=unit,
            style=CurveStyle(color=color, width=width, line_style=line_style),
            x_scale=x_scale,
            x_min=x_min,
            x_max=x_max,
        )
        self.track.add_binding(binding, index)
        self.structure.form.validate()
        self.structure.dirty = True
        return binding

    def remove(self, binding_id: str) -> ParameterBinding:
        if self.track.locked:
            raise PermissionError("Дорожка заблокирована")
        removed = self.track.remove_binding(binding_id)
        self.structure.form.validate()
        self.structure.dirty = True
        return removed

    def move(self, binding_id: str, target_index: int) -> None:
        if self.track.locked:
            raise PermissionError("Дорожка заблокирована")
        bindings = self.track.bindings
        old_index = next(
            (index for index, item in enumerate(bindings) if item.binding_id == binding_id),
            None,
        )
        if old_index is None:
            raise KeyError(binding_id)
        item = bindings.pop(old_index)
        bindings.insert(max(0, min(target_index, len(bindings))), item)
        self.structure.form.validate()
        self.structure.dirty = True

    def update(
        self,
        binding_id: str,
        *,
        canonical_parameter_id: str | None = None,
        display_name: str | None = None,
        source_mnemonic: str | None | object = _UNSET,
        unit: str | None = None,
        visible: bool | None = None,
        color: str | None = None,
        width: float | None = None,
        line_style: CurveLineStyle | None = None,
        x_scale: XScale | None = None,
        x_min: float | None | object = _UNSET,
        x_max: float | None | object = _UNSET,
    ) -> ParameterBinding:
        current = self.binding(binding_id)
        style = CurveStyle(
            color=color if color is not None else current.style.color,
            width=width if width is not None else current.style.width,
            line_style=line_style if line_style is not None else current.style.line_style,
        )
        resolved_source = (
            current.source_mnemonic
            if source_mnemonic is _UNSET
            else cast(str | None, source_mnemonic)
        )
        resolved_x_min = current.x_min if x_min is _UNSET else cast(float | None, x_min)
        resolved_x_max = current.x_max if x_max is _UNSET else cast(float | None, x_max)
        updated = replace(
            current,
            canonical_parameter_id=(
                canonical_parameter_id
                if canonical_parameter_id is not None
                else current.canonical_parameter_id
            ),
            display_name=display_name if display_name is not None else current.display_name,
            source_mnemonic=resolved_source,
            unit=unit if unit is not None else current.unit,
            visible=visible if visible is not None else current.visible,
            style=style,
            x_scale=x_scale if x_scale is not None else current.x_scale,
            x_min=resolved_x_min,
            x_max=resolved_x_max,
        )
        for index, item in enumerate(self.track.bindings):
            if item.binding_id == binding_id:
                self.track.bindings[index] = updated
                break
        self.structure.form.validate()
        self.structure.dirty = True
        return updated

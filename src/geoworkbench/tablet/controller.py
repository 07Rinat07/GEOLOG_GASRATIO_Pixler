from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from geoworkbench.domain.models import Dataset, new_id
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.channel_groups import (
    DEXP_MNEMONIC_ORDER,
    GAS_MNEMONIC_ORDER,
    available_mnemonics,
)
from geoworkbench.services.curve_catalog import (
    CurveFamily,
    analyze_dataset_curves,
    recommended_curve_mnemonics,
)
from geoworkbench.tablet.models import (
    CurveStyle,
    TabletLayout,
    TrackDefinition,
    TrackKind,
    XScale,
)


@dataclass(slots=True)
class TabletController:
    """Application commands for tablet layouts, independent of Qt widgets."""

    session: ProjectSession

    def build_default_layout(self) -> TabletLayout:
        dataset = self._require_dataset()
        return self.build_layout_for_curves(recommended_curve_mnemonics(dataset))

    def build_layout_for_curves(self, curve_mnemonics: list[str]) -> TabletLayout:
        dataset = self._require_dataset()
        selected = list(dict.fromkeys(curve_mnemonics))
        self._validate_mnemonics(dataset, selected)
        entries = {item.mnemonic: item for item in analyze_dataset_curves(dataset)}
        tracks = self._context_tracks()

        # A single X axis must only contain physically comparable parameters.
        # Category-only grouping (for example all drilling curves together) is
        # misleading because ROP, RPM, WOB and pressure use different units and
        # scales. Family + unit therefore defines a display-compatible track.
        grouped: dict[tuple[CurveFamily, str], list[str]] = {}
        group_order: list[tuple[CurveFamily, str]] = []
        for mnemonic in selected:
            entry = entries.get(mnemonic)
            family = entry.family if entry is not None else CurveFamily.OTHER
            unit_key = (entry.unit if entry is not None else "").strip().casefold()
            if family in {CurveFamily.GAS, CurveFamily.DEXP}:
                # Gas components and DEXP/NCT are intentionally compared together;
                # the logarithmic gas track handles their broad magnitude spread.
                unit_key = ""
            elif family is CurveFamily.OTHER:
                unit_key = mnemonic.casefold()
            key = (family, unit_key)
            if key not in grouped:
                grouped[key] = []
                group_order.append(key)
            grouped[key].append(mnemonic)

        gas_order = available_mnemonics(dataset, GAS_MNEMONIC_ORDER)
        dexp_order = available_mnemonics(dataset, DEXP_MNEMONIC_ORDER)
        for family, unit_key in group_order:
            mnemonics = grouped[(family, unit_key)]
            if family is CurveFamily.GAS:
                mnemonics = [name for name in gas_order if name in mnemonics] + [
                    name for name in mnemonics if name not in gas_order
                ]
            elif family is CurveFamily.DEXP:
                mnemonics = [name for name in dexp_order if name in mnemonics] + [
                    name for name in mnemonics if name not in dexp_order
                ]

            title, kind, width, scale = self._family_track_spec(family, mnemonics)
            tracks.append(
                TrackDefinition(
                    new_id(),
                    title,
                    kind,
                    curve_mnemonics=mnemonics,
                    width=width,
                    x_scale=scale,
                )
            )

        layout = TabletLayout(tracks)
        self.session.set_current_tablet_layout(layout)
        self.session.dirty = True
        return layout

    @staticmethod
    def _family_track_spec(
        family: CurveFamily,
        mnemonics: list[str],
    ) -> tuple[str, TrackKind, int, XScale]:
        specs: dict[CurveFamily, tuple[str, TrackKind, int, XScale]] = {
            CurveFamily.GAS: ("GAS", TrackKind.GAS, 380, XScale.LOGARITHMIC),
            CurveFamily.ROP: ("ROP", TrackKind.CURVE, 300, XScale.LINEAR),
            CurveFamily.ROTARY_SPEED: ("RPM", TrackKind.CURVE, 280, XScale.LINEAR),
            CurveFamily.WOB: ("WOB", TrackKind.CURVE, 280, XScale.LINEAR),
            CurveFamily.TORQUE: ("TQ", TrackKind.CURVE, 280, XScale.LINEAR),
            CurveFamily.PRESSURE: ("SPP", TrackKind.CURVE, 300, XScale.LINEAR),
            CurveFamily.HOOKLOAD: ("HKLD", TrackKind.CURVE, 300, XScale.LINEAR),
            CurveFamily.FLOW: ("FLOW", TrackKind.CURVE, 300, XScale.LINEAR),
            CurveFamily.DRILLING_DEPTH: ("DRILLING DEPTH", TrackKind.CURVE, 300, XScale.LINEAR),
            CurveFamily.MUD_DENSITY: ("MW / ECD", TrackKind.CURVE, 300, XScale.LINEAR),
            CurveFamily.TEMPERATURE: ("TEMP", TrackKind.CURVE, 300, XScale.LINEAR),
            CurveFamily.PIT_VOLUME: ("PIT VOL", TrackKind.CURVE, 300, XScale.LINEAR),
            CurveFamily.CONDUCTIVITY: ("CONDUCTIVITY", TrackKind.CURVE, 300, XScale.LINEAR),
            CurveFamily.CHLORIDES: ("CHLORIDES", TrackKind.CURVE, 300, XScale.LINEAR),
            CurveFamily.GAMMA_RAY: ("GR", TrackKind.CURVE, 300, XScale.LINEAR),
            CurveFamily.SP: ("SP", TrackKind.CURVE, 280, XScale.LINEAR),
            CurveFamily.CALIPER: ("CALI", TrackKind.CURVE, 280, XScale.LINEAR),
            CurveFamily.BULK_DENSITY: ("RHOB", TrackKind.CURVE, 280, XScale.LINEAR),
            CurveFamily.NEUTRON: ("NPHI", TrackKind.CURVE, 280, XScale.LINEAR),
            CurveFamily.SONIC: ("DT", TrackKind.CURVE, 300, XScale.LINEAR),
            CurveFamily.RESISTIVITY: ("RES", TrackKind.CURVE, 340, XScale.LOGARITHMIC),
            CurveFamily.PEF: ("PEF", TrackKind.CURVE, 280, XScale.LINEAR),
            CurveFamily.DEXP: ("DEXP / NCT", TrackKind.DEXP, 320, XScale.LINEAR),
            CurveFamily.OTHER: (" / ".join(mnemonics), TrackKind.CURVE, 280, XScale.LINEAR),
        }
        return specs[family]

    def replace_track_curves(
        self,
        track_id: str,
        curve_mnemonics: list[str],
    ) -> TrackDefinition:
        dataset = self._require_dataset()
        mnemonics = list(dict.fromkeys(curve_mnemonics))
        if not mnemonics:
            raise ValueError("Выберите хотя бы одну кривую")
        self._validate_mnemonics(dataset, mnemonics)
        track = self._require_layout().track_by_id(track_id)
        if track.kind not in {TrackKind.CURVE, TrackKind.GAS, TrackKind.DEXP}:
            raise ValueError("Состав кривых можно менять только у графического трека")
        track.curve_mnemonics = mnemonics
        track.curve_styles = {
            mnemonic: style
            for mnemonic, style in track.curve_styles.items()
            if mnemonic in mnemonics
        }
        track.title = " / ".join(mnemonics)
        self.session.dirty = True
        return track

    def _context_tracks(self) -> list[TrackDefinition]:
        tracks = [TrackDefinition(new_id(), "Глубина", TrackKind.DEPTH, width=120)]
        well = self.session.current_well
        if well is None:
            return tracks
        if well.interpretations:
            tracks.append(
                TrackDefinition(new_id(), "Интерпретация", TrackKind.INTERPRETATION, width=280)
            )
        if well.stratigraphy:
            tracks.append(
                TrackDefinition(new_id(), "Стратиграфия", TrackKind.STRATIGRAPHY, width=220)
            )
        if well.lithology:
            tracks.append(TrackDefinition(new_id(), "Литология", TrackKind.LITHOLOGY, width=180))
            tracks.append(TrackDefinition(new_id(), "Описание пород", TrackKind.TEXT, width=320))
        if well.cuttings:
            if any(item.components for item in well.cuttings):
                tracks.append(
                    TrackDefinition(new_id(), "Шламограмма", TrackKind.CUTTINGS, width=240)
                )
            if any(
                item.calcite_percent is not None or item.dolomite_percent is not None
                for item in well.cuttings
            ):
                tracks.append(
                    TrackDefinition(new_id(), "Кальциметрия", TrackKind.CALCIMETRY, width=220)
                )
            if any(
                any(
                    value is not None and value != ""
                    for value in (
                        item.lba_type_id,
                        item.lba_group,
                        item.lba_intensity,
                        item.lba_color,
                        item.lba_distribution,
                        item.lba_cut,
                        item.lba_cut_speed,
                        item.lba_cut_color,
                        item.lba_residue_type,
                        item.lba_residue_color,
                        item.lba_odour,
                        item.lba_stain,
                        item.lba_description,
                    )
                )
                for item in well.cuttings
            ):
                tracks.append(TrackDefinition(new_id(), "ЛБА", TrackKind.LBA, width=260))
        return tracks

    def add_track(
        self,
        kind: TrackKind,
        curve_mnemonics: list[str] | None = None,
    ) -> TrackDefinition:
        dataset = self._require_dataset()
        mnemonics = list(curve_mnemonics or [])
        title = kind.value
        width = 250
        x_scale = XScale.LINEAR
        if kind is TrackKind.DEPTH:
            title = "Глубина"
            width = 120
            mnemonics = []
        elif kind is TrackKind.GAS:
            title = "Газ"
            mnemonics = available_mnemonics(dataset, GAS_MNEMONIC_ORDER)
            width = 360
            x_scale = XScale.LOGARITHMIC
        elif kind is TrackKind.DEXP:
            title = "DEXP / NCT"
            mnemonics = available_mnemonics(dataset, DEXP_MNEMONIC_ORDER)
            if not mnemonics:
                raise ValueError("В наборе нет рассчитанных кривых DEXP/NCT")
            width = 320
        elif kind is TrackKind.LITHOLOGY:
            title = "Литология"
            width = 180
            mnemonics = []
        elif kind is TrackKind.CUTTINGS:
            title = "Шламограмма"
            width = 240
            mnemonics = []
        elif kind is TrackKind.CALCIMETRY:
            title = "Кальциметрия"
            width = 220
            mnemonics = []
        elif kind is TrackKind.LBA:
            title = "ЛБА"
            width = 260
            mnemonics = []
        elif kind is TrackKind.STRATIGRAPHY:
            title = "Стратиграфия"
            width = 220
            mnemonics = []
        elif kind is TrackKind.INTERPRETATION:
            title = "Интерпретация"
            width = 280
            mnemonics = []
        elif kind is TrackKind.TEXT:
            title = "Описание пород"
            width = 320
            mnemonics = []
        elif not mnemonics:
            raise ValueError("Выберите хотя бы одну кривую")
        else:
            self._validate_mnemonics(dataset, mnemonics)
            title = " / ".join(mnemonics)

        track = TrackDefinition(
            new_id(),
            title,
            kind,
            curve_mnemonics=mnemonics,
            width=width,
            x_scale=x_scale,
        )
        self._require_layout().add_track(track)
        self.session.dirty = True
        return track

    def set_track_width(self, track_id: str, width: int) -> None:
        self._require_layout().set_track_width(track_id, width)
        self.session.dirty = True

    def set_track_x_scale(self, track_id: str, scale: XScale) -> None:
        self._require_layout().set_track_x_scale(track_id, scale)
        self.session.dirty = True

    def set_track_x_range(
        self,
        track_id: str,
        minimum: float | None,
        maximum: float | None,
    ) -> None:
        self._require_layout().set_track_x_range(track_id, minimum, maximum)
        self.session.dirty = True

    def set_visible_depth(self, top: float, bottom: float) -> bool:
        changed = self._require_layout().set_visible_depth(top, bottom)
        if changed:
            self.session.dirty = True
        return changed

    def reset_visible_depth(self) -> bool:
        changed = self._require_layout().set_visible_depth(None, None)
        if changed:
            self.session.dirty = True
        return changed

    def set_cursor_depth(self, depth: float) -> bool:
        changed = self._require_layout().set_cursor_depth(depth)
        if changed:
            self.session.dirty = True
        return changed

    def update_track_view_settings(
        self,
        track_id: str,
        *,
        width: int,
        x_scale: XScale,
        x_min: float | None,
        x_max: float | None,
    ) -> None:
        self._require_layout().update_track_view_settings(
            track_id,
            width=width,
            x_scale=x_scale,
            x_min=x_min,
            x_max=x_max,
        )
        self.session.dirty = True

    def set_curve_style(self, track_id: str, mnemonic: str, style: CurveStyle) -> None:
        self._require_layout().track_by_id(track_id).set_curve_style(mnemonic, style)
        self.session.dirty = True

    def set_track_grid(self, track_id: str, show_x: bool, show_y: bool, alpha: float) -> None:
        self._require_layout().track_by_id(track_id).set_grid(show_x, show_y, alpha)
        self.session.dirty = True

    def set_track_x_axis_label(self, track_id: str, label: str) -> None:
        self._require_layout().track_by_id(track_id).set_x_axis_label(label)
        self.session.dirty = True

    def save_preset(self, name: str) -> None:
        normalized = name.strip()
        if not normalized:
            raise ValueError("Имя шаблона не может быть пустым")
        if len(normalized) > 100:
            raise ValueError("Имя шаблона не должно превышать 100 символов")
        self.session.tablet_presets[normalized] = deepcopy(self._require_layout())
        self.session.dirty = True

    def apply_preset(self, name: str) -> TabletLayout:
        try:
            preset = self.session.tablet_presets[name]
        except KeyError as exc:
            raise KeyError(f"Шаблон планшета не найден: {name}") from exc
        layout = deepcopy(preset)
        self.session.set_current_tablet_layout(layout)
        self.session.dirty = True
        return layout

    def delete_preset(self, name: str) -> None:
        if name not in self.session.tablet_presets:
            raise KeyError(f"Шаблон планшета не найден: {name}")
        del self.session.tablet_presets[name]
        self.session.dirty = True

    def move_track(self, track_id: str, offset: int) -> bool:
        layout = self._require_layout()
        track = layout.track_by_id(track_id)
        current_index = layout.tracks.index(track)
        target_index = max(0, min(current_index + offset, len(layout.tracks) - 1))
        if target_index == current_index:
            return False
        layout.move_track(track_id, target_index)
        self.session.dirty = True
        return True

    def hide_track(self, track_id: str) -> None:
        self._require_layout().set_track_visible(track_id, False)
        self.session.dirty = True

    def show_all_tracks(self) -> int:
        layout = self._require_layout()
        hidden = [track for track in layout.tracks if not track.visible]
        for track in hidden:
            layout.set_track_visible(track.track_id, True)
        if hidden:
            self.session.dirty = True
        return len(hidden)

    def remove_track(self, track_id: str) -> TrackDefinition:
        track = self._require_layout().remove_track(track_id)
        self.session.dirty = True
        return track

    def _require_dataset(self) -> Dataset:
        dataset = self.session.current_dataset
        if dataset is None:
            raise RuntimeError("Сначала выберите набор данных")
        return dataset

    def _require_layout(self) -> TabletLayout:
        layout = self.session.current_tablet_layout
        if layout is None:
            raise RuntimeError("Сначала создайте компоновку планшета")
        return layout

    @staticmethod
    def _validate_mnemonics(dataset: Dataset, mnemonics: list[str]) -> None:
        missing = [name for name in mnemonics if dataset.curve_by_mnemonic(name) is None]
        if missing:
            raise ValueError(f"Кривые отсутствуют в наборе: {', '.join(missing)}")

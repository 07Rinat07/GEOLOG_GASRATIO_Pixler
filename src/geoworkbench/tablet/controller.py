from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.domain.models import Dataset, new_id
from geoworkbench.project.session import ProjectSession
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind, XScale


GAS_MNEMONIC_ORDER = (
    "TG",
    "TOTALGAS",
    "TG_CALC",
    "C1",
    "C2",
    "C3",
    "IC4",
    "NC4",
    "C4",
    "IC5",
    "NC5",
    "C5",
)
DEXP_MNEMONIC_ORDER = ("DEXP", "DEXPC", "NCT", "DEXPC_NCT")


@dataclass(slots=True)
class TabletController:
    """Application commands for tablet layouts, independent of Qt widgets."""

    session: ProjectSession

    def build_default_layout(self) -> TabletLayout:
        dataset = self._require_dataset()
        curve_names = [curve.metadata.original_mnemonic for curve in dataset.curves.values()]
        gas_names = [
            name for name in GAS_MNEMONIC_ORDER if dataset.curve_by_mnemonic(name) is not None
        ]
        remaining = [name for name in curve_names if name not in gas_names]

        tracks = [TrackDefinition(new_id(), "Глубина", TrackKind.DEPTH, width=120)]
        if gas_names:
            tracks.append(
                TrackDefinition(
                    new_id(),
                    "Газ",
                    TrackKind.GAS,
                    curve_mnemonics=gas_names[:8],
                    width=360,
                )
            )
        dexp_names = [
            name for name in DEXP_MNEMONIC_ORDER if dataset.curve_by_mnemonic(name) is not None
        ]
        if dexp_names:
            tracks.append(
                TrackDefinition(
                    new_id(),
                    "DEXP / NCT",
                    TrackKind.DEXP,
                    curve_mnemonics=dexp_names,
                    width=320,
                )
            )
            remaining = [name for name in remaining if name not in dexp_names]
        tracks.extend(
            TrackDefinition(
                new_id(),
                mnemonic,
                TrackKind.CURVE,
                curve_mnemonics=[mnemonic],
                width=250,
            )
            for mnemonic in remaining[:3]
        )
        layout = TabletLayout(tracks)
        self.session.set_current_tablet_layout(layout)
        self.session.dirty = True
        return layout

    def add_track(
        self,
        kind: TrackKind,
        curve_mnemonics: list[str] | None = None,
    ) -> TrackDefinition:
        dataset = self._require_dataset()
        mnemonics = list(curve_mnemonics or [])
        title = kind.value
        width = 250
        if kind is TrackKind.DEPTH:
            title = "Глубина"
            width = 120
            mnemonics = []
        elif kind is TrackKind.GAS:
            title = "Газ"
            mnemonics = [
                name for name in GAS_MNEMONIC_ORDER if dataset.curve_by_mnemonic(name) is not None
            ]
            width = 360
        elif kind is TrackKind.DEXP:
            title = "DEXP / NCT"
            mnemonics = [
                name for name in DEXP_MNEMONIC_ORDER if dataset.curve_by_mnemonic(name) is not None
            ]
            if not mnemonics:
                raise ValueError("В наборе нет рассчитанных кривых DEXP/NCT")
            width = 320
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

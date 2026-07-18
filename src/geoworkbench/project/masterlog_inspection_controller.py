from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.domain.models import CanvasObject, MasterlogTemplate, new_id
from geoworkbench.printing.masterlog_inspection import MasterlogInspection
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage


@dataclass(slots=True)
class MasterlogInspectionController:
    session: ProjectSession

    def available(self, template_id: str) -> tuple[CanvasObject, ...]:
        well = self.session.current_well
        if well is None:
            return ()
        return tuple(
            sorted(
                (
                    item
                    for item in well.canvas_objects
                    if item.object_type == "masterlog_inspection"
                    and item.properties.get("template_id") == template_id
                ),
                key=lambda item: (
                    item.top_depth if item.top_depth is not None else item.y,
                    item.object_id,
                ),
            )
        )

    def remove(self, template_id: str, object_id: str) -> CanvasObject:
        well = self.session.current_well
        if well is None:
            raise RuntimeError("Сначала выберите скважину")
        item = next(
            (value for value in self.available(template_id) if value.object_id == object_id),
            None,
        )
        if item is None:
            raise KeyError(f"Печатная выноска не найдена: {object_id}")
        well.canvas_objects.remove(item)
        self.session.dirty = True
        return item

    def pin(
        self,
        template: MasterlogTemplate,
        inspection: MasterlogInspection,
        language: AppLanguage,
    ) -> CanvasObject:
        well = self.session.current_well
        if well is None:
            raise RuntimeError("Сначала выберите скважину")
        interval = inspection.interval
        item = CanvasObject(
            object_id=new_id(),
            object_type="masterlog_inspection",
            anchor_type="interval" if interval is not None else "depth",
            x=0.0,
            y=inspection.depth,
            width=0.0,
            height=0.0,
            top_depth=interval[0] if interval is not None else inspection.depth,
            bottom_depth=interval[1] if interval is not None else None,
            parameter_mnemonic=inspection.mnemonic,
            track_id=inspection.column_id,
            properties={
                "template_id": template.template_id,
                "text": inspection.display_text(language),
                "language": language.value,
            },
        )
        well.canvas_objects.append(item)
        self.session.dirty = True
        return item

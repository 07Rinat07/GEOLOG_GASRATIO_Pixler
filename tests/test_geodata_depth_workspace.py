from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QComboBox, QRadioButton, QToolButton

from geoworkbench.domain.models import (
    CuttingsComponent,
    CuttingsSample,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.forms import FormApplyEngine, factory_templates, form_from_dict, form_to_dict
from geoworkbench.forms.templates import CURATED_FACTORY_TEMPLATE_IDS, curated_factory_templates
from geoworkbench.project.cuttings_controller import CuttingsController
from geoworkbench.project.lithotype_catalog_controller import CatalogLithotype
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.tablet.layout_codec import layout_from_dict, layout_to_dict
from geoworkbench.tablet.models import TabletLayout, TrackDefinition, TrackKind
from geoworkbench.tablet.tablet_view import TabletView
from geoworkbench.ui.unified_cuttings_sample_dialog import UnifiedCuttingsSampleDialog


def _catalog() -> tuple[CatalogLithotype, ...]:
    return (
        CatalogLithotype(
            "sandstone",
            "SS",
            "Песчаник",
            "Sandstone",
            "sedimentary",
            "#e7cf8b",
            "dots",
            True,
            "Құмтас",
        ),
        CatalogLithotype(
            "clay",
            "CL",
            "Глина",
            "Clay",
            "sedimentary",
            "#94a3b8",
            "horizontal",
            True,
            "Саз",
        ),
    )


def _controller() -> CuttingsController:
    session = ProjectSession()
    session.add_dataset(
        Dataset("data", "Log", DatasetKind.GTI, DepthDomain.MD, np.array([0.0, 1000.0])),
        "Well",
    )
    return CuttingsController(session)


def test_curated_form_manager_library_contains_only_working_reference_forms() -> None:
    assert CURATED_FACTORY_TEMPLATE_IDS == (
        "factory-geodata-depth-workspace",
        "factory-masterlog-geological-geochemical",
        "factory-engineering-control-time",
    )
    assert tuple(curated_factory_templates()) == CURATED_FACTORY_TEMPLATE_IDS


def test_geodata_depth_form_matches_reference_sections_and_column_order() -> None:
    form = factory_templates("ru")["factory-geodata-depth-workspace"]

    assert [column.title for column in form.columns] == [
        "Глубина",
        "Возраст",
        "Литология",
        "Шламограмма",
        "Описание пород и шлама",
        "Кальциметрия",
        "ЛБА",
        "Технология",
        "Буровой раствор",
        "Абсолютный газ",
        "Относительный газ",
    ]
    assert [column.group_title for column in form.columns] == [
        "Геология",
        "Геология",
        "Геология",
        "Геология",
        "Геология",
        "Геология",
        "Геология",
        "Технология",
        "Технология",
        "Газовые данные",
        "Газовые данные",
    ]
    kinds = [column.tracks[0].kind for column in form.columns]
    assert kinds[:7] == [
        TrackKind.DEPTH,
        TrackKind.STRATIGRAPHY,
        TrackKind.LITHOLOGY,
        TrackKind.CUTTINGS,
        TrackKind.TEXT,
        TrackKind.CALCIMETRY,
        TrackKind.LBA,
    ]


def test_form_and_tablet_layout_roundtrip_preserve_group_titles() -> None:
    form = factory_templates()["factory-geodata-depth-workspace"]
    restored_form = form_from_dict(form_to_dict(form))
    assert [column.group_title for column in restored_form.columns] == [
        column.group_title for column in form.columns
    ]

    dataset = Dataset("data", "LAS", DatasetKind.GTI, DepthDomain.MD, np.array([0.0, 1.0]))
    layout = FormApplyEngine().build_layout(restored_form, dataset).layout
    restored_layout = layout_from_dict(layout_to_dict(layout))
    assert [track.group_title for track in restored_layout.tracks] == [
        track.group_title for track in layout.tracks
    ]


def test_tablet_renders_merged_section_headers_and_keeps_depth_in_form_order(qapp) -> None:
    dataset = Dataset(
        "data",
        "LAS",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.linspace(100.0, 200.0, 101),
    )
    layout = TabletLayout(
        [
            TrackDefinition("depth", "Depth", TrackKind.DEPTH, group_title="Geology"),
            TrackDefinition("lithology", "Lithology", TrackKind.LITHOLOGY, group_title="Geology"),
            TrackDefinition("technology", "Technology", TrackKind.CURVE, group_title="Technology"),
            TrackDefinition("gas", "Gas", TrackKind.GAS, group_title="Gas data"),
        ]
    )
    view = TabletView()
    view.set_layout_model(layout)
    view.set_dataset(dataset)
    view.resize(900, 600)
    view.show()
    qapp.processEvents()

    assert view.rendered_track_ids == ("depth", "lithology", "technology", "gas")
    assert view.pinned_track_ids == ()
    assert view.group_header_titles == ("Geology", "Technology", "Gas data")
    view.close()


def test_full_sample_reedit_updates_same_object_without_duplicate() -> None:
    controller = _controller()
    sample = controller.create_full_sample(
        100.0,
        105.0,
        {"sandstone": 70.0, "clay": 30.0},
        lba_type_id="ЛБ",
        lba_intensity=2,
        calcite_percent=20.0,
        dolomite_percent=10.0,
        description="<b>Initial</b>",
    )

    updated = controller.update_full_sample(
        sample.sample_id,
        top_depth=101.0,
        bottom_depth=106.0,
        components={"clay": 100.0},
        lba_type_id="МБ",
        lba_intensity=4,
        lba_group=4,
        calcite_percent=35.0,
        dolomite_percent=15.0,
        description="<p>Updated</p>",
        analysis_interpretation="Oil show",
    )

    assert updated is sample
    assert len(controller.available()) == 1
    assert (sample.top_depth, sample.bottom_depth) == (101.0, 106.0)
    assert sample.components[0].lithotype_id == "clay"
    assert sample.lba_type_id == "МБ"
    assert sample.lba_intensity == 4
    assert sample.calcite_percent == 35.0
    assert sample.description == "<p>Updated</p>"
    assert sample.analysis_interpretation == "Oil show"


def test_unified_sample_dialog_prefills_all_shared_fields(qapp) -> None:
    controller = _controller()
    sample = controller.create_full_sample(
        100.0,
        105.0,
        {"sandstone": 70.0, "clay": 30.0},
        lba_type_id="ЛБ",
        lba_intensity=3,
        lba_group=3,
        lba_color="БЖ",
        calcite_percent=25.0,
        dolomite_percent=15.0,
        description="<p><b>Rich text</b></p>",
        analysis_interpretation="Conclusion",
    )
    dialog = UnifiedCuttingsSampleDialog(
        sample.top_depth,
        sample.bottom_depth,
        _catalog(),
        language=AppLanguage.RU,
        sample=sample,
    )

    assert dialog.components() == {"sandstone": 70.0, "clay": 30.0}
    values = dialog.values()
    assert values["lba_type_id"] == "ЛБ"
    assert values["lba_intensity"] == 3
    assert values["calcite_percent"] == 25.0
    assert values["dolomite_percent"] == 15.0
    assert "Rich text" in (values["description"] or "")
    assert values["analysis_interpretation"] == "Conclusion"
    dialog.close()


def test_cuttings_description_is_visible_and_wrapped_in_text_track(qapp) -> None:
    dataset = Dataset(
        "description-data",
        "LAS",
        DatasetKind.GTI,
        DepthDomain.MD,
        np.linspace(100.0, 160.0, 61),
    )
    view = TabletView()
    view.set_layout_model(
        TabletLayout(
            [
                TrackDefinition(
                    "description",
                    "Описание пород",
                    TrackKind.TEXT,
                    width=220,
                )
            ]
        )
    )
    view.set_cuttings(
        [
            CuttingsSample(
                "sample-description",
                105.0,
                115.0,
                [CuttingsComponent("clay", 100.0)],
                description=(
                    "<p><b>Глина 100%</b>, серая, алевритистая, плотная и слабокарбонатная.</p>"
                ),
            )
        ]
    )
    view.resize(420, 620)
    view.show()
    view.set_dataset(dataset)
    qapp.processEvents()

    assert view.rendered_lithology_descriptions("description") == (
        "Глина 100%, серая, алевритистая, плотная и слабокарбонатная.",
    )
    assert view.visible_lithology_text_ids("description") == ("sample-description",)
    item = view._rendered["description"].lithology_description_items["sample-description"]
    assert item.textItem.textWidth() == 190.0
    assert item.boundingRect().height() > 25.0
    view.close()


def test_geodata_workspace_uses_absolute_and_relative_gas_composition_columns() -> None:
    form = factory_templates("ru")["factory-geodata-depth-workspace"]
    absolute = next(
        column for column in form.columns if column.column_id == "column-geodata-absolute-gas"
    )
    relative = next(
        column for column in form.columns if column.column_id == "column-geodata-relative-gas"
    )

    absolute_ids = [binding.canonical_parameter_id for binding in absolute.tracks[0].bindings]
    relative_ids = [binding.canonical_parameter_id for binding in relative.tracks[0].bindings]

    assert absolute_ids == ["TG_CALC", "C1", "C2"]
    assert relative_ids == ["C1_REL", "C2_REL", "C3_REL", "C4_REL", "C5_REL"]
    assert all(
        binding.x_min == 0 and binding.x_max == 100 for binding in relative.tracks[0].bindings
    )


def test_unified_sample_dialog_shows_residue_and_colored_lba_controls(qapp) -> None:
    dialog = UnifiedCuttingsSampleDialog(
        100.0,
        105.0,
        _catalog(),
        language=AppLanguage.RU,
    )
    dialog.calcite_input.setValue(35.0)
    dialog.dolomite_input.setValue(10.0)
    qapp.processEvents()

    assert dialog.residue_label.text() == "55 %"
    assert dialog.findChild(QRadioButton, "lba-type-ЛБ") is not None
    assert dialog.findChild(QRadioButton, "lba-intensity-5") is not None
    assert dialog.findChild(QComboBox, "cuttings-rock-1") is not None
    dialog.close()


def test_rich_cuttings_editor_exposes_highlight_scripts_and_alignment(qapp) -> None:
    dialog = UnifiedCuttingsSampleDialog(
        100.0,
        105.0,
        _catalog(),
        language=AppLanguage.RU,
    )

    assert dialog.rich_description.findChild(QToolButton, "rich-text-superscript") is not None
    assert dialog.rich_description.findChild(QToolButton, "rich-text-subscript") is not None
    assert dialog.rich_description.findChild(QToolButton, "rich-text-align-center") is not None
    assert dialog.rich_description.findChild(QToolButton, "rich-text-align-right") is not None
    dialog.close()


def test_geodata_ru_technology_bindings_use_localized_human_names() -> None:
    form = factory_templates("ru")["factory-geodata-depth-workspace"]
    technology = next(
        column for column in form.columns if column.column_id == "column-geodata-technology-primary"
    )
    mud = next(
        column for column in form.columns if column.column_id == "column-geodata-technology-secondary"
    )

    assert [binding.display_name for binding in technology.tracks[0].bindings] == [
        "Нагрузка на долото",
        "Давление на манифольде",
        "Крутящий момент",
        "Скорость проходки",
    ]
    assert [binding.display_name for binding in mud.tracks[0].bindings] == [
        "Плотность раствора на входе",
        "Вес на крюке",
        "Обороты ротора",
        "Расход на входе",
    ]

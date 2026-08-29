import re

from geoworkbench.forms.a4_factory_templates import (
    A4_FACTORY_TEMPLATE_IDS,
    a4_factory_templates,
)
from geoworkbench.forms.catalog import HIDDEN_FACTORY_TEMPLATE_IDS, visible_factory_forms
from geoworkbench.forms.models import FormTemplateOrigin
from geoworkbench.forms.templates import factory_templates
from geoworkbench.forms.templates import localized_factory_label
from geoworkbench.printing.form_width_advisor import FormWidthLevel, audit_form_width
from geoworkbench.services.localization import AppLanguage
from geoworkbench.tablet.models import TrackKind

PORTRAIT_IDS = {
    "factory-masterlog-a4-portrait",
    "factory-technology-a4-portrait",
    "factory-daily-a4-portrait",
    "factory-complex-gas-a4-portrait",
}
LANDSCAPE_IDS = set(A4_FACTORY_TEMPLATE_IDS) - PORTRAIT_IDS


def test_visible_factory_catalog_contains_only_new_a4_pairs() -> None:
    forms = a4_factory_templates("ru")

    assert tuple(forms) == A4_FACTORY_TEMPLATE_IDS
    assert set(forms) == PORTRAIT_IDS | LANDSCAPE_IDS
    assert set(forms).isdisjoint(HIDDEN_FACTORY_TEMPLATE_IDS)
    assert tuple(form.form_id for form in visible_factory_forms(None, "ru")) == (
        A4_FACTORY_TEMPLATE_IDS
    )


def test_every_a4_factory_fits_its_named_orientation_without_hidden_scaling() -> None:
    for form_id, form in a4_factory_templates("ru").items():
        audit = audit_form_width(column.width for column in form.columns if column.visible)
        assert form.read_only is True
        assert form.origin is FormTemplateOrigin.FACTORY
        if form_id in PORTRAIT_IDS:
            assert form.preferred_page_orientation.value == "portrait"
            assert audit.level is FormWidthLevel.FITS_PORTRAIT
            assert audit.total_width_px <= audit.portrait_capacity_px
            assert form.print_header_template_id == form.print_header_template_ids["portrait"]
        else:
            assert form.preferred_page_orientation.value == "landscape"
            assert audit.level in {
                FormWidthLevel.FITS_PORTRAIT,
                FormWidthLevel.FITS_LANDSCAPE,
            }
            assert audit.total_width_px <= audit.landscape_capacity_px
            assert form.print_header_template_id == form.print_header_template_ids["landscape"]


def test_masterlog_a4_forms_use_rock_description_title_for_interpretation() -> None:
    expected_titles = {
        "ru": "Описание пород",
        "kk": "Тау жыныстарының сипаттамасы",
        "en": "Rock description",
    }

    for language, expected_title in expected_titles.items():
        forms = a4_factory_templates(language)
        for orientation in ("portrait", "landscape"):
            form = forms[f"factory-masterlog-a4-{orientation}"]
            interpretation = [
                column
                for column in form.columns
                if any(track.kind is TrackKind.INTERPRETATION for track in column.tracks)
            ]

            assert len(interpretation) == 1
            assert interpretation[0].title == expected_title
            assert interpretation[0].column_id == (
                f"column-a4-{orientation}-interpretation"
            )


def test_masterlog_portrait_columns_are_compact_and_fit_added_interpretation() -> None:
    form = a4_factory_templates("ru")["factory-masterlog-a4-portrait"]
    widths = {column.column_id: column.width for column in form.columns}
    audit = audit_form_width(column.width for column in form.columns if column.visible)

    assert widths == {
        "column-depth-axis": 64,
        "column-a4-portrait-stratigraphy": 48,
        "column-a4-portrait-lithology": 48,
        "column-a4-portrait-cuttings": 48,
        "column-a4-portrait-calcimetry": 48,
        "column-a4-portrait-lba": 48,
        "column-a4-portrait-drilling": 144,
        "column-a4-portrait-gas": 144,
        "column-a4-portrait-interpretation": 106,
    }
    assert audit.total_width_px == 714
    assert audit.total_width_px <= audit.portrait_capacity_px
    assert audit.level is FormWidthLevel.FITS_PORTRAIT


def test_complex_gas_factory_contains_all_requested_gas_groups() -> None:
    form = a4_factory_templates("ru")["factory-complex-gas-a4-landscape"]
    titles = [column.title for column in form.columns if column.visible]
    canonical_ids = {
        binding.canonical_parameter_id
        for column in form.columns
        for track in column.tracks
        for binding in track.bindings
    }

    assert titles == [
        "Глубина",
        "ROP / скорость проходки",
        "Компоненты C1–C5",
        "Суммарный газ",
        "C1–C5, нормализованные",
        "C1–C5, относительный состав",
        "Газовые индексы",
        "Отношения Pixler",
    ]
    assert {
        "ROP",
        "TG_CALC",
        "C1",
        "C2",
        "C3",
        "IC4",
        "NC4",
        "IC5",
        "NC5",
        "TG_NORM",
        "C1_NORM_REF",
    } <= canonical_ids

    depth_track = form.columns[0].tracks[0]
    assert depth_track.title_orientation == "horizontal"
    absolute = next(
        column for column in form.columns if column.column_id == "column-complex-absolute"
    )
    absolute_bindings = absolute.tracks[0].bindings
    assert [binding.display_name for binding in absolute_bindings] == [
        "C1 Метан",
        "C2 Этан",
        "C3 Пропан",
        "iC4 Изобутан",
        "nC4 Н-бутан",
        "iC5 Изопентан",
        "nC5 Н-пентан",
    ]
    assert all(binding.header_text_color == "#0f172a" for binding in absolute_bindings)
    assert {
        "WETNESS",
        "BALANCE",
        "CHARACTER",
        "PIXLER_C1_C2",
        "PIXLER_C1_C5",
    } <= canonical_ids


def test_legacy_forms_remain_resolvable_but_are_hidden() -> None:
    all_templates = factory_templates("ru")
    assert HIDDEN_FACTORY_TEMPLATE_IDS <= set(all_templates)
    assert "factory-gas-ratio-pixler-depth" in all_templates
    assert "factory-masterlog-geological-geochemical" in all_templates


def test_a4_parameter_names_and_axis_labels_follow_selected_language() -> None:
    expected = {
        "ru": {
            "TQ": "Крутящий момент",
            "HKLD": "Вес на крюке",
            "FLOW_IN": "Расход на входе",
            "PIT_VOL": "Общий объём ёмкостей",
            "HOLE_DEPTH": "Глубина скважины",
            "TEMP_IN": "Температура раствора на входе",
            "TOTAL_GAS": "Суммарный газ",
        },
        "kk": {
            "TQ": "Айналу моменті",
            "HKLD": "Ілмектегі салмақ",
            "FLOW_IN": "Кірістегі шығын",
            "PIT_VOL": "Ыдыстардың жалпы көлемі",
            "HOLE_DEPTH": "Ұңғыма тереңдігі",
            "TEMP_IN": "Кірістегі ерітінді температурасы",
            "TOTAL_GAS": "Жалпы газ",
        },
        "en": {
            "TQ": "Torque",
            "HKLD": "Hook load",
            "FLOW_IN": "Flow in",
            "PIT_VOL": "Total pit volume",
            "HOLE_DEPTH": "Hole depth",
            "TEMP_IN": "Mud temperature in",
            "TOTAL_GAS": "Total gas",
        },
    }

    for language, expected_names in expected.items():
        forms = a4_factory_templates(language)
        actual_names = {
            binding.canonical_parameter_id: binding.display_name
            for form in forms.values()
            for column in form.columns
            for track in column.tracks
            for binding in track.bindings
            if binding.canonical_parameter_id in expected_names
        }
        assert actual_names == expected_names

        complex_form = forms["factory-complex-gas-a4-landscape"]
        labels = {
            column.column_id: column.tracks[0].x_axis_label
            for column in complex_form.columns
            if column.visible and column.tracks
        }
        assert labels["column-complex-relative"] == {
            "ru": "% от суммы",
            "kk": "жалпыдан %",
            "en": "% of total",
        }[language]
        assert labels["column-complex-pixler"] == {
            "ru": "отношение (лог.)",
            "kk": "қатынас (лог.)",
            "en": "ratio (log)",
        }[language]


def test_all_english_factory_forms_do_not_contain_cyrillic_visible_text() -> None:
    visible_text: list[str] = []
    for form in factory_templates("en").values():
        visible_text.extend((form.name, form.description))
        for column in form.columns:
            visible_text.extend((column.title, column.group_title or ""))
            for track in column.tracks:
                visible_text.extend((track.title, track.x_axis_label))
                visible_text.extend(binding.display_name for binding in track.bindings)

    assert not [text for text in visible_text if re.search(r"[А-Яа-яЁё]", text)]


def test_every_visible_a4_caption_retranslates_from_saved_russian_text() -> None:
    russian_forms = a4_factory_templates("ru")

    for language in (AppLanguage.KK, AppLanguage.EN):
        localized_forms = a4_factory_templates(language.value)
        for form_id, russian_form in russian_forms.items():
            localized_form = localized_forms[form_id]
            assert len(russian_form.columns) == len(localized_form.columns)

            for russian_column, localized_column in zip(
                russian_form.columns,
                localized_form.columns,
                strict=True,
            ):
                assert localized_factory_label(russian_column.title, language) == (
                    localized_column.title
                )
                assert localized_factory_label(russian_column.group_title, language) == (
                    localized_column.group_title
                )
                assert len(russian_column.tracks) == len(localized_column.tracks)

                for russian_track, localized_track in zip(
                    russian_column.tracks,
                    localized_column.tracks,
                    strict=True,
                ):
                    assert localized_factory_label(russian_track.title, language) == (
                        localized_track.title
                    )
                    assert len(russian_track.bindings) == len(localized_track.bindings)
                    for russian_binding, localized_binding in zip(
                        russian_track.bindings,
                        localized_track.bindings,
                        strict=True,
                    ):
                        assert localized_factory_label(
                            russian_binding.display_name,
                            language,
                        ) == localized_binding.display_name

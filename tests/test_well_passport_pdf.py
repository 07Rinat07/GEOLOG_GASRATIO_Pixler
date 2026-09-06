import numpy as np
import fitz
import pytest

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.domain.well_passport import WellPassport
from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.printing.masterlog_renderer import export_masterlog_pdf
from geoworkbench.printing.unicode_support import configure_application_unicode_fonts
from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.project.session import ProjectSession
from geoworkbench.project.well_passport_controller import WellPassportController
from geoworkbench.services.localization import AppLanguage


@pytest.mark.parametrize("orientation", ["portrait", "landscape"])
@pytest.mark.parametrize("language", list(AppLanguage))
def test_passport_pdf_uses_shared_values_and_selected_language(
    qapp, tmp_path, orientation, language
):
    assert configure_application_unicode_fonts(qapp).required_sample_supported
    session = ProjectSession()
    session.add_dataset(
        Dataset("data", "LAS", DatasetKind.GTI, DepthDomain.MD, np.array([1000.0, 1001.0])),
        "TEST-101",
    )
    templates = MasterlogTemplateController(session)
    template = templates.create_header_template(
        orientation,
        preset_catalog_id="factory-header:masterlog_header_a4_" + orientation,
        preferred_orientation=orientation,
    )
    template.properties["orientation"] = orientation
    countries = {"ru": "Казахстан", "kk": "Қазақстан", "en": "Kazakhstan"}
    casing = {"ru": "Кондуктор", "kk": "Кондуктор", "en": "Surface casing"}
    WellPassportController(session).save(
        WellPassport(
            values={
                "header.well_number": "TEST-101",
                "header.actual_depth": 1612.75,
                "header.casing_0_diameter": 177.8,
                "header.casing_0_depth": 777.25,
                "header.casing_1_diameter": 139.7,
                "header.casing_1_depth": 1500.5,
            },
            texts_i18n={
                "header.country": countries,
                "header.casing_0_name": casing,
                "header.casing_1_name": {
                    "ru": "Эксплуатационная кол.",
                    "kk": "Пайдалану бағанасы",
                    "en": "Production casing",
                },
            },
            logo_refs={"customer": ""},
        )
    )
    target = tmp_path / f"passport_{orientation}_{language.value}.pdf"
    export_masterlog_pdf(
        template, session, target, settings=MasterlogOutputSettings(1000.0, 1001.0, language)
    )
    with fitz.open(target) as pdf:
        assert len(pdf) == 1
        page = pdf[0]
        assert (page.rect.width > page.rect.height) == (orientation == "landscape")
        text = "".join(page.get_text().split())
        for expected in (
            "TEST-101",
            "1612.75",
            "177.8",
            "777.25",
            countries[language.value],
            casing[language.value],
        ):
            assert "".join(expected.split()) in text
        for legacy_value in ("5029", "3856", "2388", "Load logo", "Загрузить логотип"):
            assert "".join(legacy_value.split()) not in text
        assert "1500.5" in text

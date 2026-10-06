from copy import deepcopy

import fitz
import numpy as np
import pytest

from geoworkbench.domain.models import Dataset, DatasetKind, DepthDomain
from geoworkbench.domain.well_passport import WellPassport
from geoworkbench.printing.header_fields import (
    DOCUMENT_CONTROL_HEADER_FIELDS,
    PASSPORT_HEADER_FIELDS,
    SUPPORTED_HEADER_FIELDS,
    header_field_defaults,
    header_field_label,
    resolve_header_field,
)
from geoworkbench.printing.masterlog_output import MasterlogOutputSettings
from geoworkbench.printing.masterlog_renderer import _header_text, export_masterlog_pdf
from geoworkbench.project.controller import ProjectController
from geoworkbench.project.masterlog_template_controller import MasterlogTemplateController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.masterlog_header_dialog import HeaderDataDialog, HeaderElementDialog


@pytest.mark.parametrize('language', list(AppLanguage))
@pytest.mark.parametrize('date', ['', '2026-09-30'])
@pytest.mark.parametrize('passport', [False, True])
def test_document_control_survives_project_reopen_and_pdf(qapp, tmp_path, language, date, passport):
    session = ProjectSession()
    dataset = Dataset('log', 'Logging', DatasetKind.GTI, DepthDomain.MD, np.array([100., 101.]))
    dataset.headers = {'DATE': 'LAS acquisition date', 'REPORT_DATE': 'Vendor date', 'REVISION': 'Vendor revision'}
    session.add_dataset(dataset, 'Well')
    if passport:
        session.current_well.passport = WellPassport(values={'header.start_date': '2025-01-01'})
    controller = MasterlogTemplateController(session)
    template = controller.create('Controlled form')
    template.header_height_mm = 85
    template.properties['body_height_mm'] = 60
    template.page_format = 'A4'
    values = {
        'header.document_number': 'DOC-042', 'header.revision': '03',
        'header.status': 'Approved', 'header.report_date': date,
        'header.prepared_by': 'Engineer A', 'header.checked_by': 'Engineer B',
        'header.approved_by': 'Engineer C', 'header.confidentiality': 'Internal use',
    }
    controller.update_header_fields(template.template_id, values)
    for index, field in enumerate(values):
        controller.add_header_element(template.template_id, element_type='field',
                                      x_mm=5, y_mm=5 + index * 9, width_mm=180, height_mm=8,
                                      properties={'field': field})
    other = controller.copy(template.template_id, 'Other revision')
    controller.update_header_fields(other.template_id, {'header.document_number': 'OTHER', 'header.revision': '04'})
    package = tmp_path / 'controlled.geologpkg'
    ProjectController(session=session).save_project(package)
    restored = ProjectController().open_project(package)
    restored_template = restored.project.masterlog_templates[template.template_id]
    before = deepcopy(restored_template)
    original_depth = restored.current_dataset.depth.copy()
    for field, value in values.items():
        assert resolve_header_field(restored, field, restored_template, language) == value
        element = next(e for e in restored_template.header_elements if e.properties.get('field') == field)
        assert _header_text(element, restored, restored_template, language) == value
    assert resolve_header_field(restored, 'header.report_date', restored.project.masterlog_templates[other.template_id], language) == ''
    target = tmp_path / 'controlled.pdf'
    export_masterlog_pdf(restored_template, restored, target, settings=MasterlogOutputSettings(100, 101, language))
    with fitz.open(target) as document:
        text = ''.join(page.get_text() for page in document)
    for value in values.values():
        if value:
            assert value in text
    for forbidden in ('Vendor date', 'Vendor revision', 'LAS acquisition date', '2025-01-01', '{header.report_date}', 'OTHER'):
        assert forbidden not in text
    assert restored_template == before
    np.testing.assert_array_equal(restored.current_dataset.depth, original_depth)


@pytest.mark.parametrize('language', list(AppLanguage))
def test_document_control_is_editable_with_adopted_passport(qapp, language):
    session = ProjectSession()
    dataset = Dataset('log', 'Log', DatasetKind.GTI, DepthDomain.MD, np.array([1., 2.]))
    session.add_dataset(dataset, 'Well')
    session.current_well.passport = WellPassport()
    controller = MasterlogTemplateController(session)
    template = controller.create('Form')
    dialog = HeaderDataDialog(controller, template.template_id, language=language)
    element_dialog = HeaderElementDialog(language=language)
    try:
        for field in DOCUMENT_CONTROL_HEADER_FIELDS:
            assert field in SUPPORTED_HEADER_FIELDS
            assert field not in PASSPORT_HEADER_FIELDS
            assert field not in header_field_defaults()
            assert header_field_label(field, language) != field
            assert dialog.inputs[field].placeholderText() == ''
            assert element_dialog.field_input.findData(field) >= 0
        dialog.inputs['header.report_date'].setText('2026-09-30')
        controller.update_header_fields(template.template_id, dialog.values())
        assert resolve_header_field(session, 'header.report_date', template) == '2026-09-30'
        dialog._clear()
        controller.update_header_fields(template.template_id, dialog.values())
        assert resolve_header_field(session, 'header.report_date', template) == ''
        assert resolve_header_field(session, 'header.report_date') == ''
    finally:
        dialog.close()
        element_dialog.close()

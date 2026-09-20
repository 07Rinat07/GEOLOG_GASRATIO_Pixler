from pathlib import Path

from PySide6.QtWidgets import QDialogButtonBox

from geoworkbench.domain.models import MasterlogTemplate
from geoworkbench.printing.print_job import PrintOutputFormat
from geoworkbench.project.annotation_controller import DepthAnnotationController
from geoworkbench.project.masterlog_inspection_controller import MasterlogInspectionController
from geoworkbench.project.session import ProjectSession
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.header_preview_widget import HeaderPreviewDialog
from geoworkbench.ui.masterlog_callouts_dialog import MasterlogCalloutsDialog
from geoworkbench.ui.print_job_status_dialog import PrintJobStatusDialog
from geoworkbench.ui.skf_import_options_dialog import SkfImportOptionsDialog
from geoworkbench.ui.symbol_insertion_dialog import SymbolInsertionDialog


def _assert_inside_work_area(dialog, qapp) -> None:
    dialog.show()
    qapp.processEvents()

    screen = dialog.screen()
    assert screen is not None
    assert screen.availableGeometry().contains(dialog.geometry())


def test_symbol_insertion_dialog_fits_current_work_area(qapp) -> None:
    dialog = SymbolInsertionDialog(
        DepthAnnotationController(ProjectSession()),
        language=AppLanguage.RU,
    )

    _assert_inside_work_area(dialog, qapp)
    buttons = dialog.findChild(QDialogButtonBox)
    assert buttons is not None
    assert buttons.isVisible()
    assert buttons.geometry().bottom() <= dialog.contentsRect().bottom()
    dialog.close()


def test_print_job_status_actions_remain_visible(qapp, tmp_path: Path) -> None:
    dialog = PrintJobStatusDialog(
        language=AppLanguage.RU,
        output_format=PrintOutputFormat.PDF,
        target=tmp_path / "report.pdf",
    )

    _assert_inside_work_area(dialog, qapp)
    assert dialog.close_button.isVisible()
    assert dialog.folder_button.isVisible()
    assert dialog.open_button.isVisible()
    dialog.mark_failed("test")
    dialog.close()


def test_header_preview_dialog_clamps_desktop_preferred_size(qapp) -> None:
    session = ProjectSession()
    template = MasterlogTemplate("header-preview", "Preview")
    dialog = HeaderPreviewDialog(
        template,
        session,
        language=AppLanguage.RU,
    )

    _assert_inside_work_area(dialog, qapp)
    buttons = dialog.findChild(QDialogButtonBox)
    assert buttons is not None
    assert buttons.isVisible()
    dialog.close()


def test_skf_import_options_fit_current_work_area(qapp) -> None:
    dialog = SkfImportOptionsDialog(language=AppLanguage.RU)

    _assert_inside_work_area(dialog, qapp)
    buttons = dialog.findChild(QDialogButtonBox)
    assert buttons is not None
    assert buttons.isVisible()
    dialog.close()


def test_masterlog_callouts_fit_current_work_area(qapp) -> None:
    session = ProjectSession()
    dialog = MasterlogCalloutsDialog(
        MasterlogInspectionController(session),
        "template",
        language=AppLanguage.RU,
    )

    _assert_inside_work_area(dialog, qapp)
    buttons = dialog.findChild(QDialogButtonBox)
    assert buttons is not None
    assert buttons.isVisible()
    dialog.close()

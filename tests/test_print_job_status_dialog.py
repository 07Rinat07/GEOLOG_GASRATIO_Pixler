from pathlib import Path

from geoworkbench.printing.print_job import PrintOutputFormat
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.print_job_status_dialog import PrintJobStatusDialog


def test_file_status_only_enables_open_after_result_exists(qapp, tmp_path) -> None:
    target = tmp_path / "report.pdf"
    opened: list[Path] = []
    shown_folders: list[Path] = []
    dialog = PrintJobStatusDialog(
        language=AppLanguage.RU,
        output_format=PrintOutputFormat.PDF,
        target=target,
        open_path_callback=lambda path: not opened.append(path),
        open_folder_callback=lambda path: not shown_folders.append(path),
    )

    assert dialog.working
    assert not dialog.ready
    assert not dialog.open_button.isEnabled()
    assert not dialog.close_button.isEnabled()
    assert "ещё создаётся" in dialog.detail_label.text()

    target.write_bytes(b"%PDF-1.7\n")
    dialog.mark_ready(page_count=3, paths=(target,))

    assert not dialog.working
    assert dialog.ready
    assert dialog.primary_path == target
    assert dialog.open_button.isEnabled()
    assert dialog.folder_button.isEnabled()
    assert dialog.close_button.isEnabled()
    assert "Документ готов" in dialog.status_label.text()
    assert "3 стр." in dialog.detail_label.text()
    dialog.open_button.click()
    dialog.folder_button.click()
    assert opened == [target]
    assert shown_folders == [tmp_path]
    dialog.close()


def test_printer_status_reports_handoff_without_file_open_actions(qapp) -> None:
    dialog = PrintJobStatusDialog(
        language=AppLanguage.RU,
        output_format=PrintOutputFormat.PRINTER,
    )

    dialog.show_sending()
    assert "принтеру" in dialog.status_label.text()
    dialog.mark_ready(page_count=12)

    assert dialog.ready
    assert "передано принтеру" in dialog.status_label.text()
    assert "12 стр." in dialog.detail_label.text()
    assert not dialog.open_button.isEnabled()
    assert not dialog.folder_button.isEnabled()
    dialog.close()


def test_failed_status_never_marks_document_ready(qapp, tmp_path) -> None:
    dialog = PrintJobStatusDialog(
        language=AppLanguage.RU,
        output_format=PrintOutputFormat.PDF,
        target=tmp_path / "failed.pdf",
    )

    dialog.mark_failed("Недостаточно места")

    assert not dialog.working
    assert not dialog.ready
    assert "не готов" in dialog.status_label.text()
    assert "Недостаточно места" in dialog.detail_label.text()
    assert dialog.close_button.isEnabled()
    assert not dialog.open_button.isEnabled()
    dialog.close()


def test_missing_export_file_is_not_reported_as_ready(qapp, tmp_path) -> None:
    missing = tmp_path / "missing.pdf"
    dialog = PrintJobStatusDialog(
        language=AppLanguage.RU,
        output_format=PrintOutputFormat.PDF,
        target=missing,
    )

    dialog.mark_ready(page_count=1, paths=(missing,))

    assert not dialog.ready
    assert "не готов" in dialog.status_label.text()
    assert "не найден" in dialog.detail_label.text()
    assert not dialog.open_button.isEnabled()
    dialog.close()

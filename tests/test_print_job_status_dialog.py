from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from geoworkbench.printing.print_job import PrintOutputFormat
from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui import print_job_status_dialog as status_dialog_module
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
    assert shown_folders == [target]
    dialog.close()


def test_printer_status_enables_companion_pdf_actions(qapp, tmp_path) -> None:
    target = tmp_path / "printed-copy.pdf"
    target.write_bytes(b"%PDF-1.7\n")
    opened: list[Path] = []
    shown: list[Path] = []
    dialog = PrintJobStatusDialog(
        language=AppLanguage.RU,
        output_format=PrintOutputFormat.PRINTER,
        open_path_callback=lambda path: not opened.append(path),
        open_folder_callback=lambda path: not shown.append(path),
    )

    dialog.show_sending()
    assert "принтеру" in dialog.status_label.text()
    dialog.mark_ready(page_count=12, paths=(target,))

    assert dialog.ready
    assert dialog.primary_path == target
    assert "передано принтеру" in dialog.status_label.text()
    assert "12 стр." in dialog.detail_label.text()
    assert dialog.open_button.isEnabled()
    assert dialog.folder_button.isEnabled()
    dialog.open_button.click()
    dialog.folder_button.click()
    assert opened == [target]
    assert shown == [target]
    dialog.close()


def test_printer_status_without_companion_file_keeps_file_actions_disabled(qapp) -> None:
    dialog = PrintJobStatusDialog(
        language=AppLanguage.RU,
        output_format=PrintOutputFormat.PRINTER,
    )
    dialog.mark_ready(page_count=1)
    assert dialog.ready
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
    assert dialog.folder_button.isEnabled()
    dialog.close()


def test_failed_file_status_can_open_destination_folder(qapp, tmp_path) -> None:
    target = tmp_path / "failed.pdf"
    shown: list[Path] = []
    dialog = PrintJobStatusDialog(
        language=AppLanguage.RU,
        output_format=PrintOutputFormat.PDF,
        target=target,
        open_folder_callback=lambda path: not shown.append(path),
    )
    dialog.mark_failed("Ошибка рендера")
    dialog.folder_button.click()
    assert shown == [tmp_path]
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
    assert dialog.folder_button.isEnabled()
    dialog.close()



def test_windows_open_document_uses_native_shell(qapp, tmp_path, monkeypatch) -> None:
    target = tmp_path / "report.pdf"
    target.write_bytes(b"%PDF-1.7\n")
    opened: list[str] = []
    monkeypatch.setattr(status_dialog_module.sys, "platform", "win32")
    monkeypatch.setattr(
        status_dialog_module.os,
        "startfile",
        lambda value: opened.append(value),
        raising=False,
    )

    assert PrintJobStatusDialog._open_document_path(target) is True
    assert opened == [str(target.resolve())]


def test_windows_show_in_folder_selects_completed_file(qapp, tmp_path, monkeypatch) -> None:
    target = tmp_path / "report.pdf"
    target.write_bytes(b"%PDF-1.7\n")
    launches: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(status_dialog_module.sys, "platform", "win32")
    monkeypatch.setattr(
        status_dialog_module,
        "_start_detached",
        lambda program, arguments: not launches.append((program, arguments)),
    )

    assert PrintJobStatusDialog._reveal_path(target) is True
    assert launches == [("explorer.exe", ["/select,", str(target.resolve())])]


def test_failed_system_open_is_visible_to_user(qapp, tmp_path, monkeypatch) -> None:
    target = tmp_path / "report.pdf"
    target.write_bytes(b"%PDF-1.7\n")
    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, _title, message: warnings.append(message),
    )
    dialog = PrintJobStatusDialog(
        language=AppLanguage.RU,
        output_format=PrintOutputFormat.PDF,
        target=target,
        open_path_callback=lambda _path: False,
    )
    dialog.mark_ready(page_count=1, paths=(target,))
    dialog.open_button.click()
    assert warnings
    assert str(target) in warnings[0]
    dialog.close()


def test_windows_show_in_folder_opens_existing_directory(
    qapp, tmp_path, monkeypatch
) -> None:
    launches: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(status_dialog_module.sys, "platform", "win32")
    monkeypatch.setattr(
        status_dialog_module,
        "_start_detached",
        lambda program, arguments: not launches.append((program, arguments)),
    )

    assert PrintJobStatusDialog._reveal_path(tmp_path) is True
    assert launches == [("explorer.exe", [str(tmp_path.resolve())])]

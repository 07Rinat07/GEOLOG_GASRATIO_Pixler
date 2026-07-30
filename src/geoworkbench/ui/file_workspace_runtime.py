from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QInputDialog,
    QMessageBox,
    QTableWidgetItem,
    QTreeWidgetItem,
)

from geoworkbench.files.archive_service import ArchiveError, ArchiveFormat
from geoworkbench.files.datum import calculate_datum_elevations
from geoworkbench.files.document_service import DocumentError, DocumentKind
from geoworkbench.files.engineering import EngineeringExpressionError, format_engineering_value
from geoworkbench.files.logo_service import LogoDesignError
from geoworkbench.files.pdf_tools import PdfTools, PdfToolsError
from geoworkbench.ui.file_workspace_release import FileWorkspaceWidget as _ReleaseWorkspace


_RUNTIME: dict[str, dict[str, str]] = {
    "ru": {
        "open_document_title": "Открыть документ",
        "document_filter": "Документы (*.pdf *.jpg *.jpeg *.png *.tif *.tiff *.bmp)",
        "save_title": "Сохранение",
        "save_as_title": "Сохранить документ как",
        "saved": "Сохранено: {path}",
        "note_title": "Примечание PDF",
        "note_prompt": "Примечание:",
        "redact_title": "Безопасное удаление PDF",
        "redact_question": "Удалить текст, графику и затронутые пиксели внутри выделенной области? До сохранения действие можно отменить.",
        "annotations_title": "Удаление аннотаций",
        "annotations_deleted": "Удалено аннотаций: {count}",
        "image_size_title": "Размер изображения",
        "image_width": "Ширина, px:",
        "image_height": "Высота, px:",
        "image_only": "Операция доступна только для изображения",
        "image_crop_title": "Обрезка изображения",
        "image_correction_title": "Коррекция изображения",
        "brightness": "Яркость",
        "contrast": "Контраст",
        "saturation": "Насыщенность",
        "sharpness": "Резкость",
        "grayscale": "Оттенки серого",
        "autocontrast": "Автоконтраст",
        "merge_title": "Объединить PDF",
        "merge_target": "Результирующий PDF",
        "merge_done": "Объединённый PDF: {path}",
        "split_title": "Разделить PDF",
        "split_folder": "Папка для страниц",
        "split_done": "Создано страниц: {count}\n{path}",
        "export_source": "PDF для экспорта",
        "export_target": "Сохранить DOCX",
        "export_text_done": "Редактируемый DOCX: {path}",
        "export_pages_source": "PDF для переноса страниц",
        "export_pages_target": "Сохранить Word с видом страниц",
        "export_pages_done": "DOCX с сохранённым видом страниц: {path}\nСтраницы вставлены как изображения; внешний вид сохранён, текст не редактируется.",
        "logo_save_title": "Сохранить логотип",
        "logo_filter": "Изображения (*.png *.jpg *.bmp *.tif)",
        "archive_add_files": "Добавить файлы в архив",
        "archive_add_folder": "Добавить папку в архив",
        "archive_create_title": "Создать архив",
        "archive_format_missing": "Не выбран формат архива",
        "archive_done": "Создано: {path}",
        "archive_open_title": "Открыть архив",
        "archive_filter": "Архивы (*.zip *.7z *.tar *.tar.gz *.tgz *.tar.bz2 *.tar.xz *.rar)",
        "archive_contents_title": "Состав архива",
        "archive_extract_title": "Распаковать архив",
        "archive_destination": "Папка распаковки",
        "archive_extracted": "Извлечено объектов: {count}",
        "archive_folder": "папка",
        "archive_file": "файл",
        "calculator_title": "Калькулятор",
        "converter_title": "Конвертер",
        "datum_title": "Высотные отметки",
        "pdf_title": "PDF",
        "image_title": "Изображение",
        "archive_title": "Архив",
        "details": "Подробности: {error}",
    },
    "kk": {
        "open_document_title": "Құжатты ашу",
        "document_filter": "Құжаттар (*.pdf *.jpg *.jpeg *.png *.tif *.tiff *.bmp)",
        "save_title": "Сақтау",
        "save_as_title": "Құжатты басқаша сақтау",
        "saved": "Сақталды: {path}",
        "note_title": "PDF ескертпесі",
        "note_prompt": "Ескертпе:",
        "redact_title": "PDF мазмұнын қауіпсіз жою",
        "redact_question": "Белгіленген аймақтағы мәтінді, графиканы және кескін пиксельдерін жою керек пе? Сақтауға дейін әрекетті болдырмауға болады.",
        "annotations_title": "Аннотацияларды жою",
        "annotations_deleted": "Жойылған аннотациялар: {count}",
        "image_size_title": "Кескін өлшемі",
        "image_width": "Ені, px:",
        "image_height": "Биіктігі, px:",
        "image_only": "Бұл әрекет тек кескін үшін қолжетімді",
        "image_crop_title": "Кескінді қию",
        "image_correction_title": "Кескінді түзету",
        "brightness": "Жарықтық",
        "contrast": "Контраст",
        "saturation": "Қанықтық",
        "sharpness": "Айқындық",
        "grayscale": "Сұр реңктер",
        "autocontrast": "Автоконтраст",
        "merge_title": "PDF файлдарын біріктіру",
        "merge_target": "Нәтижелік PDF",
        "merge_done": "Біріктірілген PDF: {path}",
        "split_title": "PDF файлын бөлу",
        "split_folder": "Беттерге арналған бума",
        "split_done": "Жасалған беттер: {count}\n{path}",
        "export_source": "Экспортталатын PDF",
        "export_target": "DOCX сақтау",
        "export_text_done": "Өңделетін DOCX: {path}",
        "export_pages_source": "Беттері тасымалданатын PDF",
        "export_pages_target": "Бет көрінісі бар Word файлын сақтау",
        "export_pages_done": "Бет көрінісі сақталған DOCX: {path}\nБеттер кескін ретінде енгізілді; сыртқы көрініс сақталады, мәтін өңделмейді.",
        "logo_save_title": "Логотипті сақтау",
        "logo_filter": "Кескіндер (*.png *.jpg *.bmp *.tif)",
        "archive_add_files": "Мұрағатқа файлдар қосу",
        "archive_add_folder": "Мұрағатқа бума қосу",
        "archive_create_title": "Мұрағат жасау",
        "archive_format_missing": "Мұрағат форматы таңдалмаған",
        "archive_done": "Жасалды: {path}",
        "archive_open_title": "Мұрағатты ашу",
        "archive_filter": "Мұрағаттар (*.zip *.7z *.tar *.tar.gz *.tgz *.tar.bz2 *.tar.xz *.rar)",
        "archive_contents_title": "Мұрағат құрамы",
        "archive_extract_title": "Мұрағатты тарқату",
        "archive_destination": "Тарқату бумасы",
        "archive_extracted": "Шығарылған нысандар: {count}",
        "archive_folder": "бума",
        "archive_file": "файл",
        "calculator_title": "Калькулятор",
        "converter_title": "Түрлендіргіш",
        "datum_title": "Биіктік белгілері",
        "pdf_title": "PDF",
        "image_title": "Кескін",
        "archive_title": "Мұрағат",
        "details": "Толық мәлімет: {error}",
    },
    "en": {
        "open_document_title": "Open document",
        "document_filter": "Documents (*.pdf *.jpg *.jpeg *.png *.tif *.tiff *.bmp)",
        "save_title": "Save",
        "save_as_title": "Save document as",
        "saved": "Saved: {path}",
        "note_title": "PDF note",
        "note_prompt": "Note:",
        "redact_title": "Secure PDF removal",
        "redact_question": "Remove text, vector graphics and affected image pixels inside the selected area? The action can be undone before saving.",
        "annotations_title": "Delete annotations",
        "annotations_deleted": "Annotations deleted: {count}",
        "image_size_title": "Image size",
        "image_width": "Width, px:",
        "image_height": "Height, px:",
        "image_only": "This operation is available only for images",
        "image_crop_title": "Crop image",
        "image_correction_title": "Image correction",
        "brightness": "Brightness",
        "contrast": "Contrast",
        "saturation": "Saturation",
        "sharpness": "Sharpness",
        "grayscale": "Grayscale",
        "autocontrast": "Auto contrast",
        "merge_title": "Merge PDF files",
        "merge_target": "Resulting PDF",
        "merge_done": "Merged PDF: {path}",
        "split_title": "Split PDF",
        "split_folder": "Folder for pages",
        "split_done": "Pages created: {count}\n{path}",
        "export_source": "PDF to export",
        "export_target": "Save DOCX",
        "export_text_done": "Editable DOCX: {path}",
        "export_pages_source": "PDF whose pages will be transferred",
        "export_pages_target": "Save Word document preserving page appearance",
        "export_pages_done": "DOCX preserving page appearance: {path}\nPages were inserted as images; appearance is preserved and page text is not editable.",
        "logo_save_title": "Save logo",
        "logo_filter": "Images (*.png *.jpg *.bmp *.tif)",
        "archive_add_files": "Add files to archive",
        "archive_add_folder": "Add folder to archive",
        "archive_create_title": "Create archive",
        "archive_format_missing": "No archive format selected",
        "archive_done": "Created: {path}",
        "archive_open_title": "Open archive",
        "archive_filter": "Archives (*.zip *.7z *.tar *.tar.gz *.tgz *.tar.bz2 *.tar.xz *.rar)",
        "archive_contents_title": "Archive contents",
        "archive_extract_title": "Extract archive",
        "archive_destination": "Extraction folder",
        "archive_extracted": "Objects extracted: {count}",
        "archive_folder": "folder",
        "archive_file": "file",
        "calculator_title": "Calculator",
        "converter_title": "Converter",
        "datum_title": "Elevation references",
        "pdf_title": "PDF",
        "image_title": "Image",
        "archive_title": "Archive",
        "details": "Details: {error}",
    },
}

_TITLE_KEYS: dict[str, str] = {
    "Открытие документа": "open_document_title",
    "Сохранение": "save_title",
    "Примечание PDF": "note_title",
    "Скрытие области PDF": "redact_title",
    "Удаление аннотаций": "annotations_title",
    "Размер изображения": "image_size_title",
    "Обрезка изображения": "image_crop_title",
    "Коррекция изображения": "image_correction_title",
    "Объединение PDF": "merge_title",
    "Разделение PDF": "split_title",
    "Экспорт PDF в DOCX": "export_target",
    "Экспорт страниц PDF в Word": "export_pages_target",
    "Сохранение логотипа": "logo_save_title",
    "Создание архива": "archive_create_title",
    "Состав архива": "archive_contents_title",
    "Распаковка архива": "archive_extract_title",
    "Калькулятор": "calculator_title",
    "Конвертер": "converter_title",
    "Вертикальные отметки": "datum_title",
    "Выделение PDF": "pdf_title",
}

_ERROR_TEXT: dict[str, dict[str, str]] = {
    "kk": {
        "Документ не открыт": "Құжат ашылмаған",
        "PDF защищён паролем": "PDF құпиясөзбен қорғалған",
        "Поддерживаются PDF, JPEG, PNG, TIFF и BMP": "PDF, JPEG, PNG, TIFF және BMP қолдау көрсетіледі",
        "Сначала выделите область мышью": "Алдымен аймақты тышқанмен белгілеңіз",
        "Введите текст": "Мәтінді енгізіңіз",
        "Введите текст примечания": "Ескертпе мәтінін енгізіңіз",
        "Выделенная область слишком мала": "Белгіленген аймақ тым кішкентай",
        "Не удалось определить траекторию ластика": "Өшіргіш траекториясын анықтау мүмкін болмады",
        "Траектория ластика слишком длинная": "Өшіргіш траекториясы тым ұзын",
        "Выделите область обрезки": "Қию аймағын белгілеңіз",
        "Изображение слишком большое": "Кескін тым үлкен",
    },
    "en": {
        "Документ не открыт": "No document is open",
        "PDF защищён паролем": "The PDF is password protected",
        "Поддерживаются PDF, JPEG, PNG, TIFF и BMP": "PDF, JPEG, PNG, TIFF and BMP are supported",
        "Сначала выделите область мышью": "Select an area with the mouse first",
        "Введите текст": "Enter text",
        "Введите текст примечания": "Enter note text",
        "Выделенная область слишком мала": "The selected area is too small",
        "Не удалось определить траекторию ластика": "The eraser path could not be determined",
        "Траектория ластика слишком длинная": "The eraser path is too long",
        "Выделите область обрезки": "Select a crop area",
        "Изображение слишком большое": "The image is too large",
    },
}

_ERROR_PREFIXES: dict[str, dict[str, str]] = {
    "kk": {
        "Файл не найден:": "Файл табылмады:",
        "Не удалось открыть файл:": "Файлды ашу мүмкін болмады:",
        "PDF не сохранён:": "PDF сақталмады:",
        "Изображение не сохранено:": "Кескін сақталмады:",
        "Не удалось применить ластик:": "Өшіргішті қолдану мүмкін болмады:",
        "Неподдерживаемый PDF-шрифт:": "Қолдау көрсетілмейтін PDF қарпі:",
        "Не удалось встроить PDF-шрифт:": "PDF қарпін ендіру мүмкін болмады:",
        "Не удалось вставить текст:": "Мәтінді енгізу мүмкін болмады:",
    },
    "en": {
        "Файл не найден:": "File not found:",
        "Не удалось открыть файл:": "Could not open file:",
        "PDF не сохранён:": "PDF was not saved:",
        "Изображение не сохранено:": "Image was not saved:",
        "Не удалось применить ластик:": "Could not apply the eraser:",
        "Неподдерживаемый PDF-шрифт:": "Unsupported PDF font:",
        "Не удалось встроить PDF-шрифт:": "Could not embed the PDF font:",
        "Не удалось вставить текст:": "Could not insert text:",
    },
}


def runtime_catalogs_have_same_keys() -> bool:
    keys = [set(catalog) for catalog in _RUNTIME.values()]
    return all(item == keys[0] for item in keys[1:])


class FileWorkspaceWidget(_ReleaseWorkspace):
    """Files workspace with localized dialogs, confirmations, results and common errors."""

    def _rt(self, key: str, **values: object) -> str:
        language = self.language if self.language in _RUNTIME else "ru"
        return _RUNTIME[language][key].format(**values)

    def _localized_error(self, error: Exception | str) -> str:
        message = str(error)
        if self.language == "ru":
            return message
        exact = _ERROR_TEXT[self.language].get(message)
        if exact is not None:
            return exact
        for source, target in _ERROR_PREFIXES[self.language].items():
            if message.startswith(source):
                return target + message[len(source) :]
        return self._rt("details", error=message)

    def _show_error(self, title: str, error: Exception | str) -> None:
        key = _TITLE_KEYS.get(title)
        localized_title = self._rt(key) if key is not None else title
        QMessageBox.warning(self, localized_title, self._localized_error(error))

    def _open_document(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            self._rt("open_document_title"),
            "",
            self._rt("document_filter"),
        )
        if not filename:
            return
        try:
            self.document_service.open(Path(filename))
            self._refresh_document()
        except DocumentError as error:
            self._show_error(self._rt("open_document_title"), error)

    def _save_document(self) -> None:
        try:
            path = self.document_service.save()
            self.document_status.setText(self._rt("saved", path=path))
        except DocumentError as error:
            self._show_error(self._rt("save_title"), error)

    def _save_document_as(self) -> None:
        if not self.document_service.is_open:
            self._show_error(self._rt("save_title"), DocumentError("Документ не открыт"))
            return
        is_pdf = self.document_service.kind is DocumentKind.PDF
        file_filter = "PDF (*.pdf)" if is_pdf else self._rt("logo_filter")
        filename, _ = QFileDialog.getSaveFileName(
            self,
            self._rt("save_as_title"),
            "",
            file_filter,
        )
        if not filename:
            return
        try:
            path = self.document_service.save_as(Path(filename))
            self.document_status.setText(self._rt("saved", path=path))
        except DocumentError as error:
            self._show_error(self._rt("save_title"), error)

    def _note_pdf(self) -> None:
        text, accepted = QInputDialog.getMultiLineText(
            self,
            self._rt("note_title"),
            self._rt("note_prompt"),
        )
        if not accepted:
            return
        try:
            left, top, _right, _bottom = self._selected_document_rect()
            self.document_service.add_pdf_note((left, top), text)
            self._refresh_document()
        except DocumentError as error:
            self._show_error(self._rt("note_title"), error)

    def _redact_pdf(self) -> None:
        answer = QMessageBox.question(
            self,
            self._rt("redact_title"),
            self._rt("redact_question"),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.document_service.redact_pdf_area(self._selected_document_rect())
            self._refresh_document()
        except DocumentError as error:
            self._show_error(self._rt("redact_title"), error)

    def _delete_pdf_annotations(self) -> None:
        try:
            count = self.document_service.delete_pdf_annotations(self._selected_document_rect())
            self._refresh_document()
            self.document_status.setText(self._rt("annotations_deleted", count=count))
        except DocumentError as error:
            self._show_error(self._rt("annotations_title"), error)

    def _resize_image(self) -> None:
        size = self.document_service.image_size
        if size is None:
            self._show_error(self._rt("image_size_title"), self._rt("image_only"))
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(self._rt("image_size_title"))
        form = QFormLayout(dialog)
        width = self._integer_spin(1, 100_000, size[0])
        height = self._integer_spin(1, 100_000, size[1])
        form.addRow(self._rt("image_width"), width)
        form.addRow(self._rt("image_height"), height)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.document_service.resize_image(width.value(), height.value())
            self._refresh_document()
        except DocumentError as error:
            self._show_error(self._rt("image_size_title"), error)

    def _crop_image(self) -> None:
        try:
            left, top, right, bottom = self._selected_document_rect()
            self.document_service.crop_image(
                (round(left), round(top), round(right), round(bottom))
            )
            self._refresh_document()
        except DocumentError as error:
            self._show_error(self._rt("image_crop_title"), error)

    def _correct_image(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(self._rt("image_correction_title"))
        form = QFormLayout(dialog)
        controls: list[QDoubleSpinBox] = []
        for key in ("brightness", "contrast", "saturation", "sharpness"):
            spin = QDoubleSpinBox()
            spin.setRange(0.0, 4.0)
            spin.setSingleStep(0.1)
            spin.setValue(1.0)
            controls.append(spin)
            form.addRow(self._rt(key), spin)
        grayscale = QCheckBox(self._rt("grayscale"))
        autocontrast = QCheckBox(self._rt("autocontrast"))
        form.addRow(grayscale)
        form.addRow(autocontrast)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.document_service.correct_image(
                brightness=controls[0].value(),
                contrast=controls[1].value(),
                color=controls[2].value(),
                sharpness=controls[3].value(),
                grayscale=grayscale.isChecked(),
                autocontrast=autocontrast.isChecked(),
            )
            self._refresh_document()
        except DocumentError as error:
            self._show_error(self._rt("image_correction_title"), error)

    def _merge_pdfs(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self, self._rt("merge_title"), "", "PDF (*.pdf)"
        )
        if not files:
            return
        target, _ = QFileDialog.getSaveFileName(
            self, self._rt("merge_target"), "merged.pdf", "PDF (*.pdf)"
        )
        if not target:
            return
        try:
            result = PdfTools.merge([Path(item) for item in files], Path(target))
            self.pdf_tools_log.append(self._rt("merge_done", path=result))
        except PdfToolsError as error:
            self._show_error(self._rt("merge_title"), error)

    def _split_pdf(self) -> None:
        source, _ = QFileDialog.getOpenFileName(
            self, self._rt("split_title"), "", "PDF (*.pdf)"
        )
        if not source:
            return
        destination = QFileDialog.getExistingDirectory(self, self._rt("split_folder"))
        if not destination:
            return
        try:
            results = PdfTools.split(Path(source), Path(destination))
            self.pdf_tools_log.append(
                self._rt("split_done", count=len(results), path=destination)
            )
        except PdfToolsError as error:
            self._show_error(self._rt("split_title"), error)

    def _export_pdf_docx(self) -> None:
        source, _ = QFileDialog.getOpenFileName(
            self, self._rt("export_source"), "", "PDF (*.pdf)"
        )
        if not source:
            return
        target, _ = QFileDialog.getSaveFileName(
            self, self._rt("export_target"), "document.docx", "DOCX (*.docx)"
        )
        if not target:
            return
        try:
            result = PdfTools.export_text_docx(Path(source), Path(target))
            self.pdf_tools_log.append(self._rt("export_text_done", path=result))
        except PdfToolsError as error:
            self._show_error(self._rt("export_target"), error)

    def _export_pdf_pages_docx(self) -> None:
        source, _ = QFileDialog.getOpenFileName(
            self, self._rt("export_pages_source"), "", "PDF (*.pdf)"
        )
        if not source:
            return
        target, _ = QFileDialog.getSaveFileName(
            self,
            self._rt("export_pages_target"),
            "document_pages.docx",
            "DOCX (*.docx)",
        )
        if not target:
            return
        try:
            result = PdfTools.export_pages_docx(Path(source), Path(target))
            self.pdf_tools_log.append(self._rt("export_pages_done", path=result))
        except PdfToolsError as error:
            self._show_error(self._rt("export_pages_target"), error)

    def _save_logo(self) -> None:
        target, _ = QFileDialog.getSaveFileName(
            self,
            self._rt("logo_save_title"),
            "logo.png",
            self._rt("logo_filter"),
        )
        if not target:
            return
        try:
            result = self.logo_service.save(self._logo_design(), Path(target))
            self.logo_preview.setToolTip(str(result))
        except LogoDesignError as error:
            self._show_error(self._rt("logo_save_title"), error)

    def _archive_add_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, self._rt("archive_add_files"))
        for filename in files:
            self._add_archive_source(Path(filename))

    def _archive_add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, self._rt("archive_add_folder"))
        if folder:
            self._add_archive_source(Path(folder))

    def _archive_create(self) -> None:
        archive_format = self.archive_format_combo.currentData()
        if not isinstance(archive_format, ArchiveFormat):
            self._show_error(
                self._rt("archive_create_title"),
                self._rt("archive_format_missing"),
            )
            return
        suffix = f".{archive_format.value}"
        target, _ = QFileDialog.getSaveFileName(
            self,
            self._rt("archive_create_title"),
            f"archive{suffix}",
        )
        if not target:
            return
        try:
            result = self.archive_service.create(
                Path(target), tuple(self._archive_sources), archive_format
            )
            QMessageBox.information(
                self,
                self._rt("archive_title"),
                self._rt("archive_done", path=result),
            )
        except ArchiveError as error:
            self._show_error(self._rt("archive_create_title"), error)

    def _archive_inspect(self) -> None:
        source, _ = QFileDialog.getOpenFileName(
            self,
            self._rt("archive_open_title"),
            "",
            self._rt("archive_filter"),
        )
        if not source:
            return
        try:
            entries = self.archive_service.list_entries(Path(source))
            self.archive_entries.clear()
            for entry in entries:
                QTreeWidgetItem(
                    self.archive_entries,
                    [
                        entry.name,
                        str(entry.size),
                        self._rt("archive_folder" if entry.is_directory else "archive_file"),
                    ],
                )
        except ArchiveError as error:
            self._show_error(self._rt("archive_contents_title"), error)

    def _archive_extract(self) -> None:
        source, _ = QFileDialog.getOpenFileName(
            self,
            self._rt("archive_extract_title"),
            "",
            self._rt("archive_filter"),
        )
        if not source:
            return
        destination = QFileDialog.getExistingDirectory(
            self, self._rt("archive_destination")
        )
        if not destination:
            return
        try:
            results = self.archive_service.extract(Path(source), Path(destination))
            QMessageBox.information(
                self,
                self._rt("archive_title"),
                self._rt("archive_extracted", count=len(results)),
            )
        except ArchiveError as error:
            self._show_error(self._rt("archive_extract_title"), error)

    def _calculate_expression(self) -> None:
        try:
            result = self.calculator.evaluate(self.expression_input.text())
            self.expression_result.setText(format_engineering_value(result))
        except EngineeringExpressionError as error:
            self._show_error(self._rt("calculator_title"), error)

    def _convert_units(self) -> None:
        category = self.converter_category.currentData()
        source = self.converter_source.currentData()
        target = self.converter_target.currentData()
        if not all(isinstance(item, str) for item in (category, source, target)):
            return
        try:
            result = self.converter.convert(
                self.converter_value.text(), category, source, target
            )
            self.converter_result.setText(format_engineering_value(result))
        except (EngineeringExpressionError, KeyError, ValueError) as error:
            self._show_error(self._rt("converter_title"), error)

    def _calculate_datum(self) -> None:
        values = [control.value() for control in self.datum_inputs]
        try:
            result = calculate_datum_elevations(
                datum_elevation_m=values[0],
                gl_offset_m=values[1],
                wellhead_above_gl_m=values[2],
                df_above_gl_m=values[3],
                rt_above_df_m=values[4],
                kb_above_rt_m=values[5],
            )
        except ValueError as error:
            self._show_error(self._rt("datum_title"), error)
            return
        for row, (name, value) in enumerate(result.as_rows()):
            self.datum_table.setItem(row, 0, QTableWidgetItem(name))
            self.datum_table.setItem(
                row, 1, QTableWidgetItem(format_engineering_value(value))
            )

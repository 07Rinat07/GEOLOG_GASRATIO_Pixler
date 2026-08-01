from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from geoworkbench.printing.hydrocarbon_interpretation_report_identity import (
    InterpretationReportIdentity,
)
from geoworkbench.services.localization import AppLanguage


class InterpretationReportDetailsDialog(QDialog):
    """Edit presentation-only report details without renaming loaded data."""

    def __init__(
        self,
        defaults: InterpretationReportIdentity,
        parent: QWidget | None = None,
        *,
        language: AppLanguage = AppLanguage.RU,
        initial: InterpretationReportIdentity | None = None,
    ) -> None:
        super().__init__(parent)
        self.language = language
        self.defaults = defaults.cleaned()
        self.setModal(True)
        self.resize(760, 720)
        self.setMinimumSize(640, 560)
        self.setWindowTitle(
            self._text(
                "Реквизиты и титульный лист отчёта",
                "Есеп деректемелері және титулдық бет",
                "Report details and cover page",
            )
        )

        root = QVBoxLayout(self)
        description = QLabel(
            self._text(
                "Эти поля используются только в PDF и при печати. Названия "
                "проекта, скважины и загруженных файлов в программе не изменяются.",
                "Бұл өрістер тек PDF пен басып шығаруда қолданылады. Бағдарламадағы "
                "жоба, ұңғыма және жүктелген файл атаулары өзгермейді.",
                "These fields are used only in PDF output and printing. Project, "
                "well, and loaded-file names inside the application are not changed.",
            )
        )
        description.setWordWrap(True)
        root.addWidget(description)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(4, 4, 8, 4)
        body_layout.setSpacing(10)

        document_group = QGroupBox(
            self._text("Документ", "Құжат", "Document")
        )
        document_form = QFormLayout(document_group)
        self.report_title = self._line("reportTitle")
        self.report_subtitle = self._line("reportSubtitle")
        self.document_number = self._line("documentNumber")
        self.revision = self._line("revision")
        self.document_status = self._line("documentStatus")
        self.report_date = self._line("reportDate")
        document_form.addRow(
            self._text("Название отчёта:", "Есеп атауы:", "Report title:"),
            self.report_title,
        )
        document_form.addRow(
            self._text("Подзаголовок:", "Қосымша тақырып:", "Subtitle:"),
            self.report_subtitle,
        )
        document_form.addRow(
            self._text("Номер документа:", "Құжат нөмірі:", "Document number:"),
            self.document_number,
        )
        document_form.addRow(
            self._text("Ревизия:", "Ревизия:", "Revision:"),
            self.revision,
        )
        document_form.addRow(
            self._text("Статус:", "Күйі:", "Status:"),
            self.document_status,
        )
        document_form.addRow(
            self._text("Дата отчёта:", "Есеп күні:", "Report date:"),
            self.report_date,
        )
        body_layout.addWidget(document_group)

        well_group = QGroupBox(
            self._text("Проект и скважина", "Жоба және ұңғыма", "Project and well")
        )
        well_form = QFormLayout(well_group)
        self.project_name = self._line("projectName")
        self.well_name = self._line("wellName")
        self.field_name = self._line("fieldName")
        self.location = self._line("location")
        self.operator_name = self._line("operatorName")
        self.contractor_name = self._line("contractorName")
        self.rig_name = self._line("rigName")
        self.dataset_name = self._line("datasetName")
        self.interval = self._line("interval")
        well_form.addRow(
            self._text("Проект:", "Жоба:", "Project:"),
            self.project_name,
        )
        well_form.addRow(
            self._text("Скважина:", "Ұңғыма:", "Well:"),
            self.well_name,
        )
        well_form.addRow(
            self._text("Месторождение / площадь:", "Кен орны / алаң:", "Field / area:"),
            self.field_name,
        )
        well_form.addRow(
            self._text("Местоположение:", "Орналасуы:", "Location:"),
            self.location,
        )
        well_form.addRow(
            self._text("Оператор / заказчик:", "Оператор / тапсырыс беруші:", "Operator / client:"),
            self.operator_name,
        )
        well_form.addRow(
            self._text("Сервисная компания:", "Сервистік компания:", "Service company:"),
            self.contractor_name,
        )
        well_form.addRow(
            self._text("Буровая / установка:", "Бұрғылау қондырғысы:", "Rig / unit:"),
            self.rig_name,
        )
        well_form.addRow(
            self._text("Название набора в отчёте:", "Есептегі деректер атауы:", "Dataset label:"),
            self.dataset_name,
        )
        well_form.addRow(
            self._text("Интервал отчёта:", "Есеп аралығы:", "Report interval:"),
            self.interval,
        )
        body_layout.addWidget(well_group)

        approval_group = QGroupBox(
            self._text("Ответственные лица", "Жауапты тұлғалар", "Document responsibility")
        )
        approval_form = QFormLayout(approval_group)
        self.prepared_by = self._line("preparedBy")
        self.checked_by = self._line("checkedBy")
        self.approved_by = self._line("approvedBy")
        approval_form.addRow(
            self._text("Подготовил:", "Дайындаған:", "Prepared by:"),
            self.prepared_by,
        )
        approval_form.addRow(
            self._text("Проверил:", "Тексерген:", "Checked by:"),
            self.checked_by,
        )
        approval_form.addRow(
            self._text("Утвердил:", "Бекіткен:", "Approved by:"),
            self.approved_by,
        )
        body_layout.addWidget(approval_group)

        notes_group = QGroupBox(
            self._text("Примечания", "Ескертпелер", "Notes")
        )
        notes_layout = QFormLayout(notes_group)
        self.confidentiality = self._line("confidentiality")
        self.remarks = QPlainTextEdit()
        self.remarks.setObjectName("reportRemarks")
        self.remarks.setMaximumHeight(92)
        notes_layout.addRow(
            self._text("Гриф / доступ:", "Қолжетімділік белгісі:", "Classification:"),
            self.confidentiality,
        )
        notes_layout.addRow(
            self._text("Примечание на титульном листе:", "Титулдық бет ескертпесі:", "Cover note:"),
            self.remarks,
        )
        body_layout.addWidget(notes_group)
        body_layout.addStretch(1)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        reset_button = QPushButton(
            self._text(
                "Подставить данные из программы",
                "Бағдарлама деректерін қою",
                "Restore application values",
            )
        )
        reset_button.clicked.connect(lambda: self._apply(self.defaults))
        root.addWidget(reset_button)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._apply((initial or defaults).cleaned())

    def selected_identity(self) -> InterpretationReportIdentity:
        return InterpretationReportIdentity(
            report_title=self.report_title.text(),
            report_subtitle=self.report_subtitle.text(),
            project_name=self.project_name.text(),
            well_name=self.well_name.text(),
            field_name=self.field_name.text(),
            location=self.location.text(),
            operator_name=self.operator_name.text(),
            contractor_name=self.contractor_name.text(),
            rig_name=self.rig_name.text(),
            dataset_name=self.dataset_name.text(),
            interval=self.interval.text(),
            document_number=self.document_number.text(),
            revision=self.revision.text(),
            document_status=self.document_status.text(),
            report_date=self.report_date.text(),
            prepared_by=self.prepared_by.text(),
            checked_by=self.checked_by.text(),
            approved_by=self.approved_by.text(),
            confidentiality=self.confidentiality.text(),
            remarks=self.remarks.toPlainText(),
        ).cleaned()

    def _apply(self, identity: InterpretationReportIdentity) -> None:
        self.report_title.setText(identity.report_title)
        self.report_subtitle.setText(identity.report_subtitle)
        self.project_name.setText(identity.project_name)
        self.well_name.setText(identity.well_name)
        self.field_name.setText(identity.field_name)
        self.location.setText(identity.location)
        self.operator_name.setText(identity.operator_name)
        self.contractor_name.setText(identity.contractor_name)
        self.rig_name.setText(identity.rig_name)
        self.dataset_name.setText(identity.dataset_name)
        self.interval.setText(identity.interval)
        self.document_number.setText(identity.document_number)
        self.revision.setText(identity.revision)
        self.document_status.setText(identity.document_status)
        self.report_date.setText(identity.report_date)
        self.prepared_by.setText(identity.prepared_by)
        self.checked_by.setText(identity.checked_by)
        self.approved_by.setText(identity.approved_by)
        self.confidentiality.setText(identity.confidentiality)
        self.remarks.setPlainText(identity.remarks)

    @staticmethod
    def _line(object_name: str) -> QLineEdit:
        field = QLineEdit()
        field.setObjectName(object_name)
        field.setClearButtonEnabled(True)
        return field

    def _text(self, ru: str, kk: str, en: str) -> str:
        if self.language is AppLanguage.KK:
            return kk
        if self.language is AppLanguage.EN:
            return en
        return ru


__all__ = ["InterpretationReportDetailsDialog"]

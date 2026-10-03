from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.services.localization import AppLanguage


@dataclass(frozen=True, slots=True)
class HydrocarbonReportPrintLabels:
    pdf_passport_dataset_required: str
    pdf_invalid_interval: str
    pdf_create_failed: str
    pdf_export_failed: str
    print_range_outside: str
    print_start_failed: str
    print_next_page_failed: str
    print_prepare_page_failed: str
    print_report_no_pages: str
    print_page_range_missing: str
    range_no_depth_axis: str
    range_format_required: str
    range_parse_failed: str
    range_order_invalid: str
    range_outside_data: str


_RU = HydrocarbonReportPrintLabels(
    pdf_passport_dataset_required="Для Report Passport интерпретации требуется выбранный набор данных",
    pdf_invalid_interval="Некорректный интервал отчёта",
    pdf_create_failed="Не удалось сформировать PDF-отчёт",
    pdf_export_failed="Не удалось экспортировать PDF",
    print_range_outside="Диапазон печати выходит за пределы отчёта",
    print_start_failed="Не удалось запустить системную печать",
    print_next_page_failed="Не удалось создать следующую печатную страницу",
    print_prepare_page_failed="Не удалось подготовить страницу {page} для печати",
    print_report_no_pages="Печатный отчёт не содержит страниц",
    print_page_range_missing="Не выбран диапазон страниц",
    range_no_depth_axis="В наборе данных нет конечной оси глубины",
    range_format_required="Интервал должен иметь вид «1980–2016.20 m»",
    range_parse_failed="Не удалось прочитать границы интервала",
    range_order_invalid="Верхняя граница интервала должна быть меньше нижней",
    range_outside_data="Выбранный интервал выходит за диапазон данных {top:.2f}–{bottom:.2f}",
)

_KK = HydrocarbonReportPrintLabels(
    pdf_passport_dataset_required="Интерпретация Report Passport үшін деректер жинағын таңдау қажет",
    pdf_invalid_interval="Есеп аралығы қате",
    pdf_create_failed="PDF есебін құру мүмкін болмады",
    pdf_export_failed="PDF экспорттау мүмкін болмады",
    print_range_outside="Басып шығару диапазоны есеп шегінен тыс",
    print_start_failed="Жүйелік басып шығаруды іске қосу мүмкін болмады",
    print_next_page_failed="Келесі баспа бетін құру мүмкін болмады",
    print_prepare_page_failed="{page}-бетті басып шығаруға дайындау мүмкін болмады",
    print_report_no_pages="Баспа есебінде беттер жоқ",
    print_page_range_missing="Беттер диапазоны таңдалмаған",
    range_no_depth_axis="Деректер жинағында жарамды тереңдік осі жоқ",
    range_format_required="Аралық «1980–2016.20 m» түрінде берілуі керек",
    range_parse_failed="Аралық шекараларын оқу мүмкін болмады",
    range_order_invalid="Аралықтың жоғарғы шекарасы төменгі шекарасынан кіші болуы керек",
    range_outside_data="Таңдалған аралық деректер диапазонынан тыс: {top:.2f}–{bottom:.2f}",
)

_EN = HydrocarbonReportPrintLabels(
    pdf_passport_dataset_required="A selected dataset is required for the interpretation Report Passport",
    pdf_invalid_interval="Invalid report interval",
    pdf_create_failed="Failed to create the PDF report",
    pdf_export_failed="Failed to export the PDF",
    print_range_outside="The print range is outside the report",
    print_start_failed="Failed to start system printing",
    print_next_page_failed="Failed to create the next printed page",
    print_prepare_page_failed="Failed to prepare page {page} for printing",
    print_report_no_pages="The printable report contains no pages",
    print_page_range_missing="No page range was selected",
    range_no_depth_axis="The dataset has no finite depth axis",
    range_format_required="The interval must use the form “1980–2016.20 m”",
    range_parse_failed="Could not parse the interval bounds",
    range_order_invalid="The interval top must be less than the bottom",
    range_outside_data="The selected interval is outside the data range {top:.2f}–{bottom:.2f}",
)


def hydrocarbon_report_print_labels(
    language: AppLanguage,
) -> HydrocarbonReportPrintLabels:
    return {
        AppLanguage.RU: _RU,
        AppLanguage.KK: _KK,
        AppLanguage.EN: _EN,
    }[language]


__all__ = [
    "HydrocarbonReportPrintLabels",
    "hydrocarbon_report_print_labels",
]

from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.services.localization import AppLanguage


@dataclass(frozen=True, slots=True)
class HydrocarbonReportLabels:
    title_standard: str
    title_opus: str
    sheet_interpretation: str
    sheet_methods: str
    sheet_opus: str
    sheet_depth: str
    project: str
    well: str
    dataset: str
    generated: str
    primary_gas_curve: str
    robust_z_threshold: str
    prospective_count: str
    confirmed_count: str
    note_zero_missing: str
    group_interval: str
    group_raw_gas: str
    group_normalized_gas: str
    group_anomaly: str
    group_control: str
    headers: tuple[str, ...]
    status_prospective: str
    status_confirmed: str
    requires_geologist: str
    no_intervals: str
    check_threshold: str
    strength_low: str
    strength_medium: str
    strength_high: str
    method: str
    status: str
    used_data: str
    calculation_rule: str
    source_evidence: str
    available: str
    no_data: str
    methods_heading: str
    prospective_heading: str
    interval: str
    strength: str
    preliminary_interpretation: str
    absolute_gas: str
    basis: str
    details_heading: str
    manual_heading: str
    interpretation: str
    type_label: str
    label: str
    comment: str
    no_manual: str
    opus_heading: str
    profile: str
    mode: str
    interval_source: str
    working_unit: str
    total_gas_lod: str
    input_label: str
    curve: str
    source_unit: str
    indicator: str
    exact_formula: str
    class_label: str
    class_support: str
    valid_rows: str
    local_background: str
    peak_total_gas: str
    delta_tg: str
    max_robust_z: str
    max_contrast: str
    median: str
    vote: str
    vote_interpretation: str
    vote_support: str
    available_rows: str
    votes_qc: str
    formula_provenance: str
    workbook_sha: str
    lod_not_set: str
    detector_not_run: str
    min_word: str
    mean_word: str
    max_word: str
    profile_word: str
    insufficient_data: str
    lba_absent: str
    correlation: str
    manual_interval_basis: str
    progress_prepare: str
    progress_intervals: str
    progress_save: str
    progress_ready: str
    progress_depth: str
    document: str
    revision: str
    document_status: str
    report_date: str
    field_area: str
    location: str
    operator_customer: str
    service_company: str
    rig: str
    report_interval: str
    prepared_by: str
    checked_by: str
    approved_by: str
    cover_note: str


_RU = HydrocarbonReportLabels(
    title_standard="Сводная интерпретация газового каротажа и УВ-интервалов",
    title_opus="Дополнительный отчёт ОПУС C1-C5 по всей скважине",
    sheet_interpretation="Интерпретация УВ",
    sheet_methods="Методика",
    sheet_opus="ОПУС Газомер",
    sheet_depth="Данные по глубине",
    project="Проект",
    well="Скважина",
    dataset="Набор данных",
    generated="Сформирован",
    primary_gas_curve="Основная газовая кривая",
    robust_z_threshold="Порог robust z",
    prospective_count="Перспективных УВ-интервалов",
    confirmed_count="Подтверждено геологом",
    note_zero_missing=(
        "Примечание: 0 — реальное нулевое измерение. Пустая ячейка означает, что "
        "подходящая кривая или корректные отсчёты отсутствуют. Для каждого интервала "
        "приведены минимум, среднее и максимум."
    ),
    group_interval="Интервал и интерпретация",
    group_raw_gas="Исходный общий газ",
    group_normalized_gas="Нормализованный газ",
    group_anomaly="Аномалия",
    group_control="Абсолютный газ и геологический контроль",
    headers=(
        "№","Кровля","Подошва","Мощность","Ед.","Статус УВ-пласта",
        "Предварительная интерпретация","Сила аномалии","Исходный общий газ / единица",
        "Мин исходного газа","Среднее исходного газа","Макс исходного газа",
        "Нормализованный газ / единица","Мин нормализованного газа",
        "Среднее нормализованного газа","Макс нормализованного газа","Max robust z",
        "Абсолютный газ по компонентам: мин / среднее / макс","Haworth / Pixler",
        "DEXP: мин / среднее / макс","ЛБА и сопоставление",
        "Решение геолога / комментарий","Основание",
    ),
    status_prospective="Перспективный УВ-интервал",
    status_confirmed="Подтвержден геологом",
    requires_geologist="Требуется подтверждение геологом",
    no_intervals="Перспективные УВ-интервалы не найдены",
    check_threshold="Проверьте порог robust z и доступность газовых данных",
    strength_low="низкая", strength_medium="средняя", strength_high="высокая",
    method="Метод", status="Статус", used_data="Использованные данные",
    calculation_rule="Расчёт и правило интерпретации",
    source_evidence="Источник и степень подтверждения",
    available="доступен", no_data="нет данных",
    methods_heading="Методы и доступность",
    prospective_heading="Перспективные интервалы УВ-проявлений",
    interval="Интервал", strength="Сила аномалии",
    preliminary_interpretation="Предварительная интерпретация",
    absolute_gas="Абсолютный газ: мин / среднее / макс", basis="Основание",
    details_heading="Интерпретация по интервалам",
    manual_heading="Интервалы, подтверждённые геологом",
    interpretation="Интерпретация", type_label="Тип", label="Подпись", comment="Комментарий",
    no_manual="Подтверждённые геологом интервалы пока не заполнены.",
    opus_heading="ОПУС Газомер — пять показателей и голоса",
    profile="Профиль", mode="Режим", interval_source="Источник интервалов",
    working_unit="Рабочая единица", total_gas_lod="LOD TotalGas",
    input_label="Вход", curve="Кривая", source_unit="Исходная единица",
    indicator="Показатель", exact_formula="Точная формула профиля",
    class_label="Класс", class_support="Поддержка класса, %",
    valid_rows="Валидные / все строки", local_background="Локальный фон",
    peak_total_gas="Пик TotalGas", delta_tg="ΔTG", max_robust_z="Max robust z",
    max_contrast="Max контраст", median="Медиана", vote="Голос",
    vote_interpretation="Интерпретация голоса", vote_support="Поддержка голоса, %",
    available_rows="Доступные / все строки", votes_qc="Голоса 1–7 / QC",
    formula_provenance="Происхождение формул", workbook_sha="SHA-256 книги",
    lod_not_set="не задан; detector не запускается без скрытого значения",
    detector_not_run="локальный detector не запускался",
    min_word="мин", mean_word="среднее", max_word="макс", profile_word="профиль",
    insufficient_data="недостаточно данных",
    lba_absent="ЛБА отсутствует", correlation="сопоставление",
    manual_interval_basis="Интервал внесён и подтверждён геологом.",
    progress_prepare="Подготовка структуры Excel",
    progress_intervals="Интервалы и статистика готовы",
    progress_save="Сохранение Excel-файла", progress_ready="Excel-отчёт готов",
    progress_depth="Запись данных по глубине: {current} из {total}",
    document="Документ", revision="Ревизия", document_status="Статус",
    report_date="Дата отчёта", field_area="Месторождение / площадь",
    location="Местоположение", operator_customer="Оператор / заказчик",
    service_company="Сервисная компания", rig="Буровая / установка",
    report_interval="Интервал отчёта", prepared_by="Подготовил",
    checked_by="Проверил", approved_by="Утвердил",
    cover_note="Графики, методы, перспективные интервалы и ограничения методики приведены на следующих страницах.",
)

_KK = HydrocarbonReportLabels(
    title_standard="Газ каротажы мен КС аралықтарының жиынтық интерпретациясы",
    title_opus="Ұңғыма бойынша C1-C5 ОПУС қосымша есебі",
    sheet_interpretation="КС интерпретациясы",
    sheet_methods="Әдістеме",
    sheet_opus="ОПУС Газомер",
    sheet_depth="Тереңдік деректері",
    project="Жоба", well="Ұңғыма", dataset="Деректер жинағы", generated="Құрылған",
    primary_gas_curve="Негізгі газ қисығы", robust_z_threshold="robust z шегі",
    prospective_count="Перспективалы КС аралықтары", confirmed_count="Геолог растаған",
    note_zero_missing=(
        "Ескерту: 0 — нақты нөлдік өлшем. Бос ұяшық сәйкес қисық немесе жарамды "
        "өлшем жоқ екенін білдіреді. Әр аралық үшін минимум, орташа және максимум берілген."
    ),
    group_interval="Аралық және интерпретация", group_raw_gas="Бастапқы жалпы газ",
    group_normalized_gas="Нормаланған газ", group_anomaly="Аномалия",
    group_control="Абсолюттік газ және геологиялық бақылау",
    headers=(
        "№","Жабыны","Табаны","Қалыңдық","Бірл.","КС қабатының күйі",
        "Алдын ала интерпретация","Аномалия күші","Бастапқы жалпы газ / бірлік",
        "Бастапқы газ мин","Бастапқы газ орташа","Бастапқы газ макс",
        "Нормаланған газ / бірлік","Нормаланған газ мин","Нормаланған газ орташа",
        "Нормаланған газ макс","Max robust z",
        "Компоненттер бойынша абсолюттік газ: мин / орташа / макс","Haworth / Pixler",
        "DEXP: мин / орташа / макс","ЛБА және салыстыру",
        "Геолог шешімі / түсініктеме","Негіздеме",
    ),
    status_prospective="Перспективалы КС аралығы", status_confirmed="Геолог растаған",
    requires_geologist="Геолог растауы қажет", no_intervals="Перспективалы КС аралықтары табылмады",
    check_threshold="robust z шегін және газ деректерінің қолжетімділігін тексеріңіз",
    strength_low="төмен", strength_medium="орташа", strength_high="жоғары",
    method="Әдіс", status="Күй", used_data="Қолданылған деректер",
    calculation_rule="Есеп және интерпретация ережесі",
    source_evidence="Дереккөз және растау деңгейі", available="қолжетімді", no_data="дерек жоқ",
    methods_heading="Әдістер және қолжетімділік", prospective_heading="КС көріністерінің перспективалы аралықтары",
    interval="Аралық", strength="Аномалия күші", preliminary_interpretation="Алдын ала интерпретация",
    absolute_gas="Абсолюттік газ: мин / орташа / макс", basis="Негіздеме",
    details_heading="Аралықтар бойынша интерпретация", manual_heading="Геолог растаған аралықтар",
    interpretation="Интерпретация", type_label="Түрі", label="Белгі", comment="Түсініктеме",
    no_manual="Геолог растаған аралықтар әзірге толтырылмаған.",
    opus_heading="ОПУС Газомер — бес көрсеткіш және дауыстар",
    profile="Профиль", mode="Режим", interval_source="Аралықтар көзі", working_unit="Жұмыс бірлігі",
    total_gas_lod="LOD TotalGas", input_label="Кіріс", curve="Қисық", source_unit="Бастапқы бірлік",
    indicator="Көрсеткіш", exact_formula="Профильдің нақты формуласы", class_label="Класс",
    class_support="Класс қолдауы, %", valid_rows="Жарамды / барлық жолдар",
    local_background="Жергілікті фон", peak_total_gas="TotalGas шыңы", delta_tg="ΔTG",
    max_robust_z="Max robust z", max_contrast="Max контраст", median="Медиана",
    vote="Дауыс", vote_interpretation="Дауыс интерпретациясы", vote_support="Дауыс қолдауы, %",
    available_rows="Қолжетімді / барлық жолдар", votes_qc="1–7 дауыстар / QC",
    formula_provenance="Формулалардың шығу тегі", workbook_sha="Кітап SHA-256",
    lod_not_set="берілмеген; detector жасырын мәнсіз іске қосылмайды",
    detector_not_run="жергілікті detector іске қосылмады",
    min_word="мин", mean_word="орташа", max_word="макс", profile_word="профиль",
    insufficient_data="дерек жеткіліксіз", lba_absent="ЛБА жоқ", correlation="салыстыру",
    manual_interval_basis="Аралық енгізіліп, геологпен расталған.",
    progress_prepare="Excel құрылымын дайындау", progress_intervals="Аралықтар мен статистика дайын",
    progress_save="Excel файлын сақтау", progress_ready="Excel есебі дайын",
    progress_depth="Тереңдік деректерін жазу: {current} / {total}",
    document="Құжат", revision="Ревизия", document_status="Күй", report_date="Есеп күні",
    field_area="Кен орны / алаң", location="Орналасуы", operator_customer="Оператор / тапсырыс беруші",
    service_company="Сервистік компания", rig="Бұрғылау қондырғысы", report_interval="Есеп аралығы",
    prepared_by="Дайындаған", checked_by="Тексерген", approved_by="Бекіткен",
    cover_note="Графиктер, әдістер, перспективалы аралықтар және әдістеме шектеулері келесі беттерде берілген.",
)

_EN = HydrocarbonReportLabels(
    title_standard="Integrated mud-gas and hydrocarbon-interval interpretation",
    title_opus="Additional whole-well OPUS C1-C5 report",
    sheet_interpretation="HC interpretation", sheet_methods="Methods",
    sheet_opus="OPUS Gasomer", sheet_depth="Depth data",
    project="Project", well="Well", dataset="Dataset", generated="Generated",
    primary_gas_curve="Primary gas curve", robust_z_threshold="Robust-z threshold",
    prospective_count="Prospective HC intervals", confirmed_count="Geologist-confirmed",
    note_zero_missing=(
        "Note: 0 is an observed zero. A blank cell means that a suitable curve or valid "
        "samples are unavailable. Minimum, mean and maximum are reported for each interval."
    ),
    group_interval="Interval and interpretation", group_raw_gas="Raw total gas",
    group_normalized_gas="Normalized gas", group_anomaly="Anomaly",
    group_control="Absolute gas and geological control",
    headers=(
        "No.","Top","Bottom","Thickness","Unit","HC interval status","Preliminary interpretation",
        "Anomaly strength","Raw total gas / unit","Raw gas min","Raw gas mean","Raw gas max",
        "Normalized gas / unit","Normalized gas min","Normalized gas mean","Normalized gas max",
        "Max robust z","Absolute component gas: min / mean / max","Haworth / Pixler",
        "DEXP: min / mean / max","LBA and correlation","Geologist decision / comment","Basis",
    ),
    status_prospective="Prospective HC interval", status_confirmed="Geologist-confirmed",
    requires_geologist="Geologist confirmation required", no_intervals="No prospective HC intervals found",
    check_threshold="Check the robust-z threshold and gas-data availability",
    strength_low="low", strength_medium="medium", strength_high="high",
    method="Method", status="Status", used_data="Data used",
    calculation_rule="Calculation and interpretation rule", source_evidence="Source and evidence level",
    available="available", no_data="no data", methods_heading="Methods and availability",
    prospective_heading="Prospective hydrocarbon-show intervals", interval="Interval",
    strength="Anomaly strength", preliminary_interpretation="Preliminary interpretation",
    absolute_gas="Absolute gas: min / mean / max", basis="Basis",
    details_heading="Interval interpretation", manual_heading="Geologist-confirmed intervals",
    interpretation="Interpretation", type_label="Type", label="Label", comment="Comment",
    no_manual="No geologist-confirmed intervals have been entered yet.",
    opus_heading="OPUS Gasomer — five indicators and votes", profile="Profile", mode="Mode",
    interval_source="Interval source", working_unit="Working unit", total_gas_lod="TotalGas LOD",
    input_label="Input", curve="Curve", source_unit="Source unit", indicator="Indicator",
    exact_formula="Exact profile formula", class_label="Class", class_support="Class support, %",
    valid_rows="Valid / total rows", local_background="Local background", peak_total_gas="Peak TotalGas",
    delta_tg="ΔTG", max_robust_z="Max robust z", max_contrast="Max contrast", median="Median",
    vote="Vote", vote_interpretation="Vote interpretation", vote_support="Vote support, %",
    available_rows="Available / total rows", votes_qc="Votes 1–7 / QC",
    formula_provenance="Formula provenance", workbook_sha="Workbook SHA-256",
    lod_not_set="not set; detector does not run with a hidden fallback value",
    detector_not_run="local detector was not run",
    min_word="min", mean_word="mean", max_word="max", profile_word="profile",
    insufficient_data="insufficient data", lba_absent="LBA unavailable", correlation="correlation",
    manual_interval_basis="Interval entered and confirmed by geologist.",
    progress_prepare="Preparing Excel structure", progress_intervals="Intervals and statistics ready",
    progress_save="Saving Excel file", progress_ready="Excel report ready",
    progress_depth="Writing depth data: {current} of {total}",
    document="Document", revision="Revision", document_status="Status", report_date="Report date",
    field_area="Field / area", location="Location", operator_customer="Operator / customer",
    service_company="Service company", rig="Rig", report_interval="Report interval",
    prepared_by="Prepared by", checked_by="Checked by", approved_by="Approved by",
    cover_note="Charts, methods, prospective intervals and method limitations are provided on the following pages.",
)


def hydrocarbon_report_labels(language: AppLanguage) -> HydrocarbonReportLabels:
    return {
        AppLanguage.RU: _RU,
        AppLanguage.KK: _KK,
        AppLanguage.EN: _EN,
    }[language]


__all__ = ["HydrocarbonReportLabels", "hydrocarbon_report_labels"]

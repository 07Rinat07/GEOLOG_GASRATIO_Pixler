"""Localized factual receipt after an explicit gas-ratio calculation."""
from geoworkbench.domain.models import Dataset
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.pixler_coverage import pixler_coverage


def gas_ratio_result_text(dataset: Dataset, language: AppLanguage) -> str:
    coverage = pixler_coverage(dataset)
    title, profiles, span, gaps, unavailable, empty, save = {
        AppLanguage.RU: (
            "Расчёт завершён для набора", "Полные профили Пикслера",
            "Первый–последний полный профиль по порядку строк",
            "Строк без полного профиля: {count}. Диапазон может содержать пропуски.",
            "Отсутствуют актуальные отношения", "Полных профилей для Пикслера нет.",
            "Результат находится в текущем проекте. Для обновлённого PDF сформируйте отчёт заново.",
        ),
        AppLanguage.KK: (
            "Деректер үшін есеп аяқталды", "Толық Pixler профильдері",
            "Жолдар ретімен бірінші–соңғы толық профиль",
            "Толық профилі жоқ жолдар: {count}. Аралықта бос орындар болуы мүмкін.",
            "Өзекті қатынастар жоқ", "Pixler үшін толық профильдер жоқ.",
            "Нәтиже ағымдағы жобада. Жаңартылған PDF үшін есепті қайта жасаңыз.",
        ),
        AppLanguage.EN: (
            "Calculation completed for dataset", "Complete Pixler profiles",
            "First–last complete profile in row order",
            "Rows without a complete profile: {count}. The span may contain gaps.",
            "Current ratios unavailable", "No complete Pixler profiles are available.",
            "Results are in the current project. Generate the report again for an updated PDF.",
        ),
    }[language]
    lines = [f"{title}: {dataset.name}",
             f"{profiles}: {coverage.complete_rows}/{coverage.total_rows}"]
    if coverage.complete_rows:
        index = dataset.active_index
        lines.append(f"{span} ({index.mnemonic}): "
                     f"{coverage.first_index}–{coverage.last_index} {index.unit or ''}")
    else:
        lines.append(empty)
    if coverage.complete_rows < coverage.total_rows:
        lines.append(gaps.format(count=coverage.total_rows - coverage.complete_rows))
    if coverage.unavailable_ratios:
        lines.append(f"{unavailable}: {', '.join(coverage.unavailable_ratios)}")
    lines.append(save)
    return "\n".join(lines)

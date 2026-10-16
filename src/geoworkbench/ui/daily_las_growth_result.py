"""Explicit location and actual index range after a persisted daily update."""
from pathlib import Path

from geoworkbench.domain.models import Dataset
from geoworkbench.services.localization import AppLanguage
from geoworkbench.services.gas_update_coverage import gas_update_coverage


def daily_las_growth_result_text(
    dataset: Dataset, project_path: Path, language: AppLanguage,
    *, cells_filled: int = 0,
) -> str:
    index = dataset.active_index
    values = index.values
    start = str(values[0]) if len(values) else "—"
    stop = str(values[-1]) if len(values) else "—"
    labels = {
        AppLanguage.RU: (
            "Обновлён набор", "Фактический диапазон", "Проект с результатом",
            "Исходные LAS не перезаписаны. Отдельный наращённый LAS ещё не создан. "
            "Чтобы получить его, выберите «Экспорт LAS» для этого набора и сохраните под новым именем.",
        ),
        AppLanguage.KK: (
            "Жаңартылған деректер", "Нақты аралық", "Нәтижесі бар жоба",
            "Бастапқы LAS өзгертілмеді. Жеке ұзартылған LAS әлі жасалмаған. "
            "Оны алу үшін осы деректерге «LAS экспорттау» таңдап, жаңа атаумен сақтаңыз.",
        ),
        AppLanguage.EN: (
            "Updated dataset", "Actual range", "Project containing the result",
            "Source LAS files were not overwritten. A separate extended LAS has not been created. "
            "Use Export LAS for this dataset and save it under a new name.",
        ),
    }[language]
    fill_label = {AppLanguage.RU: "Заполнено пустых ячеек",
                  AppLanguage.KK: "Толтырылған бос ұяшықтар",
                  AppLanguage.EN: "Empty cells filled"}[language]
    fill_summary = f"{fill_label}: {cells_filled}\n" if cells_filled else ""
    gas_summary = _gas_summary(dataset, language)
    return (f"{labels[0]}: {dataset.name}\n"
            f"{labels[1]}: {start}–{stop} {index.unit or ''}\n"
            f"{fill_summary}{labels[2]}:\n{project_path}\n\n{gas_summary}\n\n{labels[3]}")


def _gas_summary(dataset: Dataset, language: AppLanguage) -> str:
    coverage = gas_update_coverage(dataset)
    title, missing, ambiguous, last, stale = {
        AppLanguage.RU: (
            "Газовые данные во всём обновлённом наборе (заполнено строк)",
            "нет данных", "неоднозначные мнемоники", "последнее значение по индексу",
            "Расчётные кривые устарели. Повторите расчёт Gas Ratio / Haworth / Pixler",
        ),
        AppLanguage.KK: (
            "Жаңартылған толық деректердегі газдар (толтырылған жолдар)",
            "деректер жоқ", "мнемоникалар бірмәнді емес", "индекс бойынша соңғы мән",
            "Есептік қисықтар ескірген. Gas Ratio / Haworth / Pixler есебін қайталаңыз",
        ),
        AppLanguage.EN: (
            "Gas data in the entire updated dataset (populated rows)",
            "no data", "ambiguous mnemonics", "last value at index",
            "Calculated curves are stale. Run Gas Ratio / Haworth / Pixler again",
        ),
    }[language]
    lines = [title + ":"]
    index = dataset.active_index
    for item in coverage.components:
        if item.ambiguous:
            detail = ambiguous
        elif not item.source or not item.count:
            detail = missing
        else:
            detail = (f"{item.source}: {item.count}/{coverage.rows}; "
                      f"{last} {index.mnemonic}: {item.last_index} {index.unit or ''}")
        lines.append(f"{item.component}: {detail}")
    if coverage.stale_ratios:
        lines.append(stale + ".")
    return "\n".join(lines)

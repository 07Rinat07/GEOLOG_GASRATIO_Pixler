"""Explicit location and actual index range after a persisted daily update."""
from pathlib import Path

from geoworkbench.domain.models import Dataset
from geoworkbench.services.localization import AppLanguage


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
    return (f"{labels[0]}: {dataset.name}\n"
            f"{labels[1]}: {start}–{stop} {index.unit or ''}\n"
            f"{fill_summary}{labels[2]}:\n{project_path}\n\n{labels[3]}")

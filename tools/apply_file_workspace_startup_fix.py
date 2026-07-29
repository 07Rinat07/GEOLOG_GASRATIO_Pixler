from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one anchor in {path}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


def insert_after_once(path: Path, anchor: str, addition: str) -> None:
    text = path.read_text(encoding="utf-8")
    if addition.strip() in text:
        return
    count = text.count(anchor)
    if count != 1:
        raise RuntimeError(f"Expected one anchor in {path}, found {count}")
    path.write_text(text.replace(anchor, anchor + addition, 1), encoding="utf-8", newline="\n")


def main() -> None:
    main_window = ROOT / "src/geoworkbench/ui/main_window.py"
    replace_once(
        main_window,
        "from geoworkbench.ui.file_workspace_widget import FileWorkspaceWidget\n",
        '''try:\n    from geoworkbench.ui.file_workspace_widget import FileWorkspaceWidget\nexcept ModuleNotFoundError as file_workspace_import_error:\n    class FileWorkspaceWidget(QWidget):\n        \"\"\"Visible fallback when optional document dependencies are missing locally.\"\"\"\n\n        def __init__(self, parent: QWidget | None = None, *, language: str = \"ru\") -> None:\n            super().__init__(parent)\n            layout = QVBoxLayout(self)\n            title = QLabel(\"Модуль «Файлы» требует обновления зависимостей\")\n            title.setWordWrap(True)\n            command = QLabel(\n                \"После обновления проекта выполните в активном .venv:\\n\"\n                \"python -m pip install -e \\\".[dev]\\\"\\n\\n\"\n                f\"Недостающий модуль: {file_workspace_import_error.name or file_workspace_import_error}\"\n            )\n            command.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)\n            command.setWordWrap(True)\n            layout.addWidget(title)\n            layout.addWidget(command)\n            layout.addStretch(1)\n\n        @staticmethod\n        def tab_title(language: str) -> str:\n            return {\"ru\": \"Файлы\", \"kk\": \"Файлдар\", \"en\": \"Files\"}.get(\n                language, \"Файлы\"\n            )\n''',
    )

    readme = ROOT / "README.md"
    install_anchor = 'Если установлена другая версия Python 3.11+, замените `-3.11` на её номер. Активация окружения\n'
    install_note = '''\n> **Важно после обновления через Git.** Команда `git pull` обновляет исходный код, но не устанавливает\n> новые Python-зависимости. После каждого обновления, изменяющего `pyproject.toml`, выполните в активном\n> виртуальном окружении `python -m pip install -e \".[dev]\"`. Для вкладки «Файлы» требуются PyMuPDF\n> (импортируется как `fitz`) и Pillow. Если они отсутствуют, приложение теперь запускается, а вкладка\n> показывает команду восстановления окружения вместо аварийного завершения.\n\n'''
    insert_after_once(readme, install_anchor, install_note)

    feature_anchor = '- **Отчёты и печать.** Предварительный просмотр, A4/A3/рулонные носители, физическая печать и\n  экспорт в PDF, PNG, JPEG, TIFF, BMP, WebP, SVG, CSV, XLSX, DOCX и HTML.\n'
    feature_addition = '''- **Рабочее пространство «Файлы».** Отдельная видимая вкладка для PDF и изображений,\n  объединения и разделения PDF, экспорта текста в DOCX, логотипов, архивов, инженерного\n  калькулятора, конвертера единиц и расчёта отметок datum/GL/wellhead/DF/RT/KB-RKB.\n'''
    insert_after_once(readme, feature_anchor, feature_addition)

    file_docs = ROOT / "docs/FILE_WORKSPACE.md"
    startup_section = '''\n## Запуск после обновления / Жаңартудан кейін іске қосу / Startup after update\n\n`git pull` не обновляет содержимое существующего виртуального окружения. После получения версии с\nвкладкой «Файлы» выполните из корня проекта в активном `.venv`:\n\n```powershell\npython -m pip install -e \".[dev]\"\npython -c \"import fitz, PIL; print('Files workspace dependencies: OK')\"\npython -m geoworkbench.app.main\n```\n\nPyMuPDF устанавливается пакетом `PyMuPDF`, но импортируется в Python как `fitz`. Если зависимость\nотсутствует, основное приложение не должно завершаться аварийно: вкладка «Файлы» остаётся видимой\nи показывает команду обновления окружения. После установки зависимостей перезапустите приложение.\n\nҚолданыстағы `.venv` каталогын `git pull` жаңартпайды. Жобаны алғаннан кейін жоғарыдағы орнату\nкомандасын орындаңыз. `fitz` табылмаса, бағдарлама енді жабылмайды: «Файлдар» қойындысында ортаны\nжаңарту нұсқауы көрсетіледі.\n\nAn existing `.venv` is not updated by `git pull`. Run the installation command above after pulling\nchanges. When `fitz` is missing, the application now remains operational and the Files tab displays\na recovery instruction instead of terminating during startup.\n'''
    text = file_docs.read_text(encoding="utf-8")
    if "## Запуск после обновления" not in text:
        file_docs.write_text(text + startup_section, encoding="utf-8", newline="\n")

    localized = {
        ROOT / "docs/ru/README.md": '''\n\n## Вкладка «Файлы» и обновление зависимостей\n\nВкладка **«Файлы»** находится в основном рабочем окне и открывается также через **Файл → Файлы**\nили `Ctrl+Alt+F`. После `git pull` обновите активное окружение командой\n`python -m pip install -e \".[dev]\"`. PyMuPDF импортируется как `fitz`; без него приложение\nзапустится в безопасном режиме и покажет инструкцию прямо во вкладке.\n''',
        ROOT / "docs/kk/README.md": '''\n\n## «Файлдар» қойындысы және тәуелділіктерді жаңарту\n\n**«Файлдар»** қойындысы негізгі жұмыс терезесінде орналасқан және **Файл → Файлдар** немесе\n`Ctrl+Alt+F` арқылы ашылады. `git pull` командасынан кейін белсенді ортада\n`python -m pip install -e \".[dev]\"` орындаңыз. PyMuPDF Python ішінде `fitz` атауымен импортталады;\nол болмаған жағдайда бағдарлама жабылмай, қойындыда қалпына келтіру нұсқауын көрсетеді.\n''',
        ROOT / "docs/en/README.md": '''\n\n## Files tab and dependency updates\n\nThe **Files** tab is visible in the main workspace and can also be opened through **File → Files**\nor `Ctrl+Alt+F`. After `git pull`, update the active environment with\n`python -m pip install -e \".[dev]\"`. PyMuPDF is imported as `fitz`; when it is missing, the\napplication now starts in a safe fallback mode and displays recovery instructions in the tab.\n''',
    }
    for path, addition in localized.items():
        text = path.read_text(encoding="utf-8")
        heading = addition.strip().splitlines()[0]
        if heading not in text:
            path.write_text(text.rstrip() + addition + "\n", encoding="utf-8", newline="\n")

    changelog = ROOT / "docs/CHANGELOG.md"
    change = '- Исправлен запуск при устаревшем `.venv`: отсутствие PyMuPDF/`fitz` больше не блокирует всё приложение; вкладка «Файлы» остаётся видимой и показывает команду обновления зависимостей. README и инструкции RU/KK/EN синхронизированы.\n\n'
    insert_after_once(changelog, "## Unreleased\n\n", change)


if __name__ == "__main__":
    main()

# Запуск вкладки «Файлы» после обновления

## Русский

После `git pull` исходный код обновляется, но существующее виртуальное окружение `.venv` не получает новые пакеты автоматически. Для PDF и изображений вкладке «Файлы» нужны PyMuPDF и Pillow.

В PowerShell из корня проекта выполните:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -c "import fitz, PIL; print('Files workspace dependencies: OK')"
python -m geoworkbench.app.main
```

PyMuPDF устанавливается под именем `PyMuPDF`, но импортируется в коде как `fitz`. Ошибка `ModuleNotFoundError: No module named 'fitz'` означает, что активное окружение не обновлено или используется другой Python.

Проверьте используемый интерпретатор:

```powershell
python -c "import sys; print(sys.executable)"
python -m pip show PyMuPDF Pillow
```

После исправления приложение должно показывать вкладку **«Файлы»** в основном рабочем окне. Она также открывается через **Файл → Файлы** и `Ctrl+Alt+F`.

При отсутствии зависимости приложение больше не должно аварийно завершаться: вместо редактора во вкладке отображается команда восстановления окружения.

## Қазақша

`git pull` тек бастапқы кодты жаңартады, бірақ қолданыстағы `.venv` ішіне жаңа пакеттерді орнатпайды. Жоғарыдағы PowerShell командаларын орындаңыз. PyMuPDF Python ішінде `fitz` атауымен импортталады. Тәуелділік жоқ болса, бағдарлама енді жабылмайды және «Файлдар» қойындысында қалпына келтіру нұсқауын көрсетеді.

## English

`git pull` updates source files but does not install new packages into an existing `.venv`. Run the PowerShell commands above after pulling changes. PyMuPDF is imported as `fitz`. When the dependency is missing, the application now starts with a visible Files-tab recovery message instead of terminating during import.

# 0.7.33 шығарылым ескертпелері — интерактивті Import Review

Күні: 2026 жылғы 23 шілде. Күйі: тест жинағы.

## Жаңа мүмкіндіктер

- ортақ `ImportReviewDialog` CSV/TXT, Excel, LAS және GeoScape/Paradox үшін қосылды;
- белсенді индексті таңдап, оның мнемоникасын, рөлін, түрін және UOM мәнін түзетуге болады;
- қосымша сандық NULL белгісі тек қабылданған көшірмеде `NaN` мәніне ауыстырылады;
- әр арнаны қосу/алып тастау және canonical mnemonic/kind, quantity class, UOM мәндерін қолмен өзгерту мүмкіндігі бар;
- Semantic Channel Dictionary автоматты сәйкестендіруін әр арна үшін қайтаруға болады;
- preview NULL, duplicate, gap, order, unresolved, UOM conflict, all-null және duplicate kind жағдайларын көрсетеді;
- бұғаттайтын қателер растауды өшіреді, ескертулер көрініп тұрады;
- қабылданған қолмен шешімдер semantic binding evidence және dataset параметрлерінде сақталады.

## Архитектура және қауіпсіздік

- `ImportReviewController` initial plan, read-only preview және тексерілген commit үшін жауап береді;
- preview/commit терең көшірмемен жұмыс істеп, loader-owned dataset мәнін өзгертпейді;
- `DatasetImportJobExecutor` review кезеңін project-session port алдында шақырады;
- CSV/Excel/Paradox немесе жеке LAS импорты тоқтатылса, dataset/well жасалмайды және `dirty` өзгермейді;
- LAS batch әр файл үшін жеке review ашады;
- UOM өзгерісі мәндерді жасырын түрлендірмейді, тек метадеректерді түзетеді;
- project format v16 болып қалады.

## Тексеру

- 731 қолжетімді headless/regression/source-integrity тест өтті;
- 4 платформалық сценарий өткізіліп жіберілді;
- 3 LAS round-trip тестіне `lasio`, 1 Qt сценарийіне `PySide6` қажет;
- `compileall` қатесіз аяқталды;
- толық Ruff, mypy, Qt/LAS pytest және Windows GUI/HiDPI/PDF/physical-print smoke тексеруі толық ортада қайталануы керек.

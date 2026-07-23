# Жоба күйі

Кесім: 2026 жылғы 23 шілде. Пакет нұсқасы 0.7.33, тест жинағы.

## Шығарылым шешімі

Соңғы толық baseline — 0.7.28: Ruff өтті, mypy 262 бастапқы файлда 0 қате көрсетті, толық
pytest нәтижесі 1217 passed және 10 skipped. 0.7.33 үшін `compileall` және қолжетімді
headless/regression/source-integrity жинағы орындалды: 731 passed, 4 skipped. Үш LAS
round-trip тестіне `lasio`, бір Qt сценарийіне `PySide6` қажет; толық жинаққа PySide6,
pyqtgraph және lasio керек. Ruff пен mypy бұл контейнерде жоқ. Толық gate және міндетті
Windows/HiDPI/PDF/физикалық принтер матрицасы өтпейінше жинақ тест күйінде қалады.

## Расталған жұмыс негізі

- қауіпсіз LAS 1.2/2.0, CSV/TXT, Excel және GeoScape/Paradox workflow;
- multi-dataset және multi-index project format v16;
- Semantic Channel Dictionary және анық UOM quantity class;
- әр curve үшін сақталатын semantic binding;
- CSV, Excel, LAS және Paradox үшін ортақ интерактивті Import Review;
- индексті таңдау/тексеру, қолмен semantic/UOM override және қосымша NULL sentinel;
- NULL, duplicate, gap, order, unresolved, UOM conflict, all-null және duplicate kind QC;
- deep-copy controller және project-session port арқылы атомарлық растау;
- көп жолақты планшет, forms, Masterlog, PDF, Print Center, annotations және project assets;
- синхронды RU/KK/EN пайдаланушы құжаттары.

## Ағымдағы кесімді тексеру

| Тексеру | Нәтиже |
|---|---|
| Import Review controller | initial plan, preview және commit бастапқы dataset-ті өзгертпейді |
| Import jobs | CSV, Excel, LAS және Paradox review-ді жобаға тіркеуден бұрын шақырады |
| Бас тарту | dataset/well жасалмайды, `dirty` өзгермейді |
| QC | бұғаттайтын қателер commit-ті өшіреді, ескертулер көрінеді |
| Локализация | RU/KK/EN каталогтарында бірдей 1733 кілт бар |
| Қолжетімді regression | 731 passed, 4 skipped |
| Project format | v16 болып қалады |

## Ең жоғары тәуекелді техникалық қарыз

- `tablet/tablet_view.py` және `ui/main_window.py` әлі де ірі orchestration кластары;
- 0.7.33 толық Ruff/mypy/Qt/LAS gate толық ортада қайталануы керек;
- интерактивті диалог Windows-та үлкен кесте және HiDPI режимінде қолмен тексерілуі керек;
- экран/баспаға ортақ golden fixture жоқ;
- Import Review ішіндегі UOM өзгерісі мәндерді түрлендірмейді, тек метадеректерді түзетеді.

## Келесі бақылау нүктесі

Келесі тік кесім — Report Passport: source fingerprint, semantic bindings, formula versions,
UOM, form revision, тіл және render settings. Одан кейін golden fixtures. Stable шығарылым үшін
Windows GUI/HiDPI/PDF/physical-print smoke-test міндетті болып қалады.

Толығырақ: [Import Review](IMPORT_REVIEW.md),
[Semantic Channel Dictionary](SEMANTIC_CHANNEL_DICTIONARY.md) және
[жоспар](PROJECT_PLAN.md).

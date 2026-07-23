# Жоба күйі

Кесім: 2026 жылғы 23 шілде. Package version: 0.7.34, тест жинағы.

## Шығарылым шешімі

Соңғы толық расталған baseline — 0.7.28: Ruff таза, 262 source file ішінде mypy 0 error,
толық pytest нәтижесі 1217 passed және 10 skipped. 0.7.34 үшін `compileall` және қолжетімді
headless/regression/source-integrity suite аяқталды: 742 passed, 4 skipped. `lasio`/`PySide6`
жоқ болғандықтан тағы 4 LAS/Qt scenario әдейі deselected; толық collection 95 Qt/LAS import
error көрсетеді. Бұл контейнерде Ruff және mypy жоқ. Толық gate пен Windows/HiDPI/PDF/
physical-print matrix орындалғанша жинақ test build болып қалады.

## Расталған негіз

- қауіпсіз LAS 1.2/2.0, CSV/TXT, Excel және GeoScape/Paradox workflows;
- multi-dataset/multi-index project format v16;
- Semantic Channel Dictionary, UOM quantity classes және сақталатын semantic bindings;
- manual overrides, QC және atomic commit бар Import Review;
- SHA-256 тексеруі бар детерминирленген Report Passport schema v1;
- multi-track tablet, forms, Masterlog, Print Center, interpretation reports және annotations;
- синхронды RU/KK/EN құжаттамасы.

## Ағымдағы кезең нәтижесі

| Тексеру | Нәтиже |
|---|---|
| Детерминизм | өзгермеген data/form/language/render settings бірдей digest береді |
| Аралық | тек нақты report interval ішіндегі selected channel values хэштеледі |
| Semantic/UOM | sensor/source, kind, quantity, UOM, confidence, aliases және evidence толық сақталады |
| Sources | import snapshot, embedded LAS, external file немесе normalized report data SHA-256 алады |
| Formulas | ID, version, provenance және бар болса expression SHA-256 сақталады |
| Forms | Masterlog version қолданады, forms/layouts content-addressed revision қолданады |
| Export | Print Center, direct PNG/SVG/PDF, Masterlog және interpretation PDF sidecar жасайды |
| JSON validation | өзгертілген signed content қабылданбайды |
| Қолжетімді regression | 742 passed, 4 skipped, 4 dependency-specific scenario deselected |
| Project format | v16 болып қалады |

## Негізгі қалған тәуекел

- толық Ruff/mypy/Qt/LAS gate-ті толық ортада қайталау;
- Windows/HiDPI/PDF/physical-print smoke matrix орындау;
- output және sidecar жеке atomic, бірақ бір filesystem transaction емес;
- physical print digest есептейді, output path жоқ болғандықтан sidecar жасамайды;
- ортақ screen/print golden fixtures жоқ;
- output-file fingerprint ортақ `ReportDefinition` кейін қосылады.

## Келесі бақылау нүктесі

Screen/print grid, legend, lithotype және annotation үшін golden fixtures қосу. Stable мәртебесі
үшін Windows GUI/HiDPI/PDF/physical-print smoke matrix міндетті.

Толығырақ: [Report Passport](REPORT_PASSPORT.md), [Import Review](IMPORT_REVIEW.md),
[Semantic Channel Dictionary](SEMANTIC_CHANNEL_DICTIONARY.md) және [жоспар](PROJECT_PLAN.md).

# Жоба күйі

Кесім: 2026 жылғы 23 шілде. Пакет нұсқасы: 0.7.35, тесттік жинақ.

## Шығарылым шешімі

Соңғы толық расталған baseline 0.7.28: Ruff таза, mypy — 262 source file ішінде 0 қате,
толық pytest — 1217 өтті және 10 skipped. 0.7.35 үшін `compileall` және қолжетімді
headless/regression/source-integrity регрессиясы орындалды: 734 тест өтті, 4 платформалық
сценарий skipped. Үш LAS-roundtrip сценарийі `lasio` болмағандықтан қолжетімді жүгіруден
алынды; Qt/pyqtgraph тәуелді файлдар `PySide6` және `pyqtgraph`-сыз жиналмайды. Ruff және
mypy контейнерде жоқ. Жинақ толық gate және Windows/HiDPI/PDF/physical-print
матрицасына дейін test build болып қалады.

## Расталған негіз

- LAS, CSV/TXT, Excel және GeoScape/Paradox қауіпсіз import;
- Semantic Channel Dictionary және Import Review бар project format v16;
- детерминирленген Report Passport schema v1;
- grid, legend, lithotypes және annotations үшін JSON/SVG golden fixtures;
- grid, legend, pattern identity және annotation layout үшін ортақ screen/print geometry;
- синхронды RU/KK/EN құжаттамасы.

## 0.7.35 нәтижелері

| Тексеру | Нәтиже |
|---|---|
| Golden schema | `geoworkbench.render-golden/v1`, canonical JSON және SHA-256 |
| Grid | screen px және print mm үшін бірдей normalized fractions |
| Legend | ортақ рет, deduplication, unknown fallback және RU/KK/EN |
| Lithotypes | factory bitmap SHA-256 және 96 DPI physical tile size |
| Annotations | ортақ box/leader/rotation/clipping contract |
| Visual | screen және print SVG байт бойынша қайталанады |
| Нысаналы golden-contract тесттері | 19 passed |
| Қолжетімді регрессия | 734 passed, 4 skipped, 3 LAS scenarios deselected; Qt modules unavailable |
| Project format | v16 |

## Қалған тәуекел

- толық Ruff/mypy/Qt/LAS gate-ті қайталау;
- Windows/HiDPI/PDF/physical-print smoke-test орындау;
- structural/SVG goldens platform raster tolerance тексеруін алмастырмайды;
- `ReportDefinition`, interval selection және output fingerprint-ті біріктіру.

## Келесі бақылау нүктесі

Preview, PDF және кестелік экспорт үшін ортақ `ReportDefinition` және бір interval selection.

[Golden rendering](GOLDEN_RENDERING.md), [Report Passport](REPORT_PASSPORT.md) және
[жалпы жоспарды](../PROJECT_PLAN.md) қараңыз.

# 0.7.35 шығарылым ескертпелері — Golden Rendering Fixtures

Күні: 2026 жылғы 23 шілде. Күйі: тесттік жинақ.

## Жаңа

- grid, legend, lithotype patterns және annotations үшін төрт детерминирленген JSON golden
  fixture қосылды;
- экран планшеті мен баспа Masterlog үшін құрамдас SVG эталондары қосылды;
- әр JSON `geoworkbench.render-golden/v1` және canonical payload SHA-256 қолданады;
- `tools/update_render_goldens.py` committed fixtures файлдарын байт бойынша қайта жасайды.

## Ортақ геометрия

- major/minor grid geometry Qt-тан тәуелсіз `tablet/grid_geometry.py` модуліне шығарылды;
- экран мен баспа бір normalized fractions келісімін қолданады;
- screen және Masterlog legend ортақ `build_lithology_legend_from_ids()` қолданады;
- legacy lithotype pattern aliases нақты factory bitmap және content SHA-256 мәніне headless
  каталог арқылы шешіледі;
- annotation box және leader endpoint ортақ `annotation_layout.py` арқылы px немесе mm-де
  есептеледі;
- баспа annotation leader endpoint есептеуі rotation мәнін ескереді.

## Тексерулер

- 734 қолжетімді headless/regression/source-integrity тесті өтті;
- 4 платформалық сценарий өткізіліп жіберілді;
- 3 LAS-roundtrip сценарийі `lasio` болмағандықтан алынды; Qt/pyqtgraph модульдері `PySide6` және `pyqtgraph`-сыз қолжетімсіз;
- 19 нысаналы golden-contract тесті өтті;
- `compileall` қатесіз аяқталды;
- толық Ruff/mypy/Qt/LAS gate және Windows/HiDPI/PDF/physical-print smoke-test толық ортада
  қайталануы тиіс.

Жоба форматы v16 болып қалады.

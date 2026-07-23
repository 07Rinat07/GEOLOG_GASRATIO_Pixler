# Рендердің детерминирленген golden fixtures эталондары

## Мақсаты

Golden fixtures нақты Qt/Windows құрылғысын қолмен тексеруге дейін экран планшеті мен
баспа Masterlog үшін ортақ келісімді бекітеді. Олар геометрияның, legend ретінің,
lithotype pattern және annotation орналасуының жарияланбаған өзгерістерін анықтайды.

Эталонда жасалған уақыт, абсолют жол, кездейсоқ ID немесе қолданба нұсқасы жоқ. Бірдей
кіріс келісімі әрқашан байт бойынша бірдей JSON және SVG береді.

## Құрамы

Эталондар `tests/golden_rendering` ішінде орналасқан:

- `grid_screen_print_v1.json` — major/minor divisions, normalized fractions, экрандағы px
  және баспадағы mm координаттары;
- `legend_multilingual_v1.json` — рет, deduplication, unknown fallback және RU/KK/EN атаулар;
- `lithotype_patterns_v1.json` — compact/legacy aliases, factory asset SHA-256, bitmap tile
  өлшемі және 96 DPI кезіндегі физикалық өлшем;
- `annotations_screen_print_v1.json` — экран/баспа үшін box, anchor, leader endpoint,
  rotation және clipping;
- `screen_tablet_v1.svg` және `print_masterlog_v1.svg` — құрамдас визуал эталондар.

Әр JSON `geoworkbench.render-golden/v1` schema-сын пайдаланады және canonical payload
SHA-256 мәнін сақтайды.

## Ортақ іске асыру шекаралары

- `tablet/grid_geometry.py` — major/minor geometry үшін Qt-тан тәуелсіз дереккөз;
- экран grid renderer және Masterlog бір division contract қолданады;
- `build_lithology_legend_from_ids()` экран/баспа үшін code/name/color/pattern және unknown
  fallback-ты бірдей шешеді;
- `lithology_pattern_catalog.py` legacy alias-ты нақты factory bitmap-қа шешіп, content
  SHA-256 мәнін Qt-сыз тексереді;
- `annotation_layout.py` reference pixels мәндерін экран px немесе баспа mm-ге түрлендіріп,
  rotation қоса box пен leader endpoint-ті бірдей есептейді.

## Эталонды жаңарту

```powershell
.\.venv\Scripts\python.exe tools\update_render_goldens.py
```

Белсенді интерпретатормен де іске қосуға болады: `python tools/update_render_goldens.py`.

Golden өзгерісі тек күтілетін render өзгерісінің түсіндірмесімен бірге қабылданады.
`test_committed_render_goldens_match_deterministic_generator` барлық файлды байт бойынша
салыстырады.

## Тексерулер

Автоматты gate committed/regenerated сәйкестігін, JSON SHA-256, px/mm normalized grid,
bitmap physical tile size, legend реті мен локализациясын, annotation 96-DPI px→mm
масштабын және machine-specific path/timestamp жоқтығын тексереді.

Qt raster/PDF platform tolerance, HiDPI 100–200% және физикалық баспа stable алдында
міндетті Windows матрицасында қалады.

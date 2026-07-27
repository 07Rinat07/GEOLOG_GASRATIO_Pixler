# GeoSensor WITS Level 0 үйлесімділік каталогы

## Мақсаты

Кірістірілген `geosensor-wits-level0.json` каталогы GeoScape 2 архивіндегі машина оқитын
`GeoScape/WITS.csv` файлынан жасалған. Онда 1–25 жазбалар үшін 963 `record/item` жұбы, сипаттама,
short/long mnemonic, жарияланған тип және ұзындық бар.

Каталог GSWITS профилін толықтырады. Профиль тексерілген бірліктерді, aggregation, index type және
жіберу саясатын береді; каталог қалған стандартты өрістерді жалған `unknown record/item`
диагностикасынсыз тануға мүмкіндік береді.

## Стандартты тақырып

- `01` — Well Identifier;
- `02` — Sidetrack/Hole Section Number;
- `03` — Record Identifier;
- `04` — Sequence Identifier;
- `05` — Date;
- `06` — Time;
- `07` — Activity Code.

Бастапқы sequence нөмірі тек item `04` мәнінен оқылады.

## Қайталануы және шекарасы

Каталог `tools/build_geosensor_wits_catalog.py` командасымен қайта жасалады. Құрал ZIP path
қауіпсіздігін тексеріп, тек `GeoScape/WITS.csv` файлын оқиды және vendor binaries іске қоспайды.
Бастапқы EXE, BPL, MDB, FDB және PDF wheel мен бастапқы архивке кірмейді. Хештер мен талдау
[reference_manifest.json](../../vendor_reference/geosensor_geoscape2/inventory/reference_manifest.json)
және [ANALYSIS_GEOSCAPE2_WITS.md](../../vendor_reference/geosensor_geoscape2/analysis/ANALYSIS_GEOSCAPE2_WITS.md)
файлдарында сақталады.

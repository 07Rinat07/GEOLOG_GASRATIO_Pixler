# Ортақ ReportDefinition

`ReportDefinition` — бір есептің өзгермейтін сипаттамасы. Preview немесе export басталғанға
дейін ол dataset, нақты index, sections, curves, form, language және interval mode мәндерін
бекітеді.

## Аралық режимдері

- `full` — таңдалған осьтің толық диапазоны;
- `current` — Print Center ашылған сәтте бекітілген viewport;
- `custom` — пайдаланушы енгізген шекаралар;
- `selection` — тек сол оське тиесілі синхронды таңдау.

Resolver dataset/index сәйкестігін тексереді, аралықты нақты деректермен шектейді, бір inclusive
row set жасайды және `ResolvedReportDefinition` қайтарады. Preview, PDF/баспа және CSV/XLSX
аралықты бөлек қайта есептемейді.

## Қолданылатын жолдар

- Print Center: preview және соңғы job үшін бір resolved range;
- Masterlog: preview, PDF және system preview үшін бір depth range;
- таңдалған аралық экспорты: CSV/XLSX үшін бірдей curve IDs және rows;
- Report Passport: canonical definition payload және SHA-256 sidecar ішінде сақталады.

Планшет таңдалған `vertical_index_id` мәнін сақтайды; DEPTH-selection TIME-view-ға қолданылмайды.
Project format v16 болып қалады.

Толық инженерлік contract: [REPORT_DEFINITION.md](../REPORT_DEFINITION.md).

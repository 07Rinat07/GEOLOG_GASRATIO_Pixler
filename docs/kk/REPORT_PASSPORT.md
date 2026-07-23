# Report Passport

Күйі: 0.7.34 нұсқасынан іске асырылған; coverage 0.7.37-де schema v2 құрамына, ал баспа моделі 0.7.38-де schema v3 құрамына қосылды. Project format v16 болып қалады.

## Мақсаты

Report Passport — нақты PDF, PNG, SVG немесе Print Center нәтижесінің қандай деректер мен render
settings арқылы жасалғанын түсіндіретін детерминирленген JSON sidecar. Дерек, форма, тіл және
рендер параметрлері өзгермесе, қайта құрылған есептің `passport_sha256` мәні бірдей болады.

```text
report.pdf
report.pdf.passport.json
```

Физикалық баспада файл жолы жоқ, сондықтан бағдарлама паспорт digest мәнін есептеп көрсетеді,
бірақ sidecar файлын жасамайды.

## Қамтылған сценарийлер

- Print Center PDF және беттелген PNG/JPEG/TIFF/BMP/WebP/SVG;
- белсенді көріністі PNG, SVG және PDF форматына тікелей шығару;
- Masterlog PDF;
- сынамалар, кальциметрия және ЛБА бойынша interpretation PDF;
- физикалық баспа: тек digest.

Preview соңғы экспорт емес және паспорт жасамайды.

## Паспорт құрамында

- application және passport schema нұсқалары;
- project, well, dataset немесе well-level artifact идентификаторлары;
- нақты аралық, оған кірген sample саны және index values SHA-256;
- тек есеп аралығына кірген таңдалған channel мәндерінің fingerprints;
- original/canonical mnemonic, canonical kind, quantity class және source/display/canonical UOM;
- sensor ID, semantic source, family/category, confidence, matched-by, aliases және evidence;
- curve provenance, state және version;
- formula ID, version, expression SHA-256 және source;
- form/template ID, нақты version немесе content-addressed revision және definition SHA-256;
- RU/KK/EN тілі;
- renderer, format, DPI, page profile, orientation, margins, pagination және қосымша options;
- import кезінде сақталған source, embedded lossless LAS немесе қолжетімді external file fingerprint;
- нақты есеп деректерінің міндетті normalized fingerprint мәні бар.

## Source fingerprint басымдығы

1. Import-time `LasSourceSnapshot` — `stored-at-import`.
2. Embedded lossless LAS artifact — `embedded-project-artifact`.
3. Қолжетімді CSV/Excel/Paradox/LAS файлы — ескертумен `captured-at-report-time`.
4. Normalized report data — әрқашан қосылады.

Absolute path сақталмайды, тек файл атауы жазылады. Бастапқы файл жоқ болса да, project ішіндегі
normalized snapshot есепке кірген мәндерді тексеруге мүмкіндік береді.

## Детерминизм және тексеру

- JSON key sorting арқылы canonical түрде жазылады, metadata ішінде `NaN/Infinity` қабылданбайды;
- timestamp және absolute output path digest құрамына кірмейді;
- numeric arrays little-endian float64 форматына келтіріліп, NaN payload және signed zero нормалданады;
- digest `passport_sha256` өрісінен басқа барлық мазмұн бойынша есептеледі;
- `load_report_passport()` digest мәнін қайта есептеп, өзгертілген JSON-ды қабылдамайды;
- sidecar temporary file, `fsync` және atomic `os.replace` арқылы жазылады.

## Шектеулер

- output және sidecar жеке-жеке atomic жазылады, бірақ екеуі бір filesystem transaction емес;
- паспорт provenance дәлелі, ұйымның digital signature немесе сертификаты емес;
- output-file fingerprint ортақ `ReportDefinition` pipeline жасалғаннан кейін қосылады;
- stable мәртебесі үшін Windows/HiDPI/PDF/physical-print smoke matrix міндетті.

## ReportDefinition байланысы

0.7.36 нұсқасынан бастап sidecar canonical `ReportDefinition` payload және SHA-256 сақтайды.
Осылайша preview, PDF/баспа және кестелік экспорт бір dataset, index, interval, curves, form
және language қолданғанын тексеруге болады.

## Schema v2

0.7.37 нұсқасынан бастап passport әр сұралған арна үшін availability, observed, zeros, missing және unavailable coverage snapshot қол қояды.

## Schema v3 баспа моделі

0.7.38 нұсқасы A4/A3/custom/roll, orientation, Fit/100%, continuation overlap, margins және DPI мәндерін қол қояды. Physical layout өзгерсе, `passport_sha256` өзгереді.

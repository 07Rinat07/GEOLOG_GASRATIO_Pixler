# Report Passport

Күйі: 0.7.34 нұсқасынан бар. Coverage schema v2, print media schema v3, ал дайын output
artifacts fingerprints schema v4 құрамына 0.7.39 нұсқасында қосылды.

## Мақсаты

Report Passport — PDF, сурет, CSV/XLSX, DOCX/HTML немесе басқа есеп нәтижесінің provenance-ын
сипаттайтын deterministic JSON sidecar. Data, ReportDefinition, тіл, render settings және output
bytes өзгермесе, қайта генерацияланған `passport_sha256` бірдей болады.

```text
report.pdf
report.pdf.passport.json
```

Physical print файл жасамайды, сондықтан output artifact және файлдық sidecar жоқ preliminary
digest қана есептеледі.

## Қамтылған сценарийлер

- Print Center PDF және paged PNG/JPEG/TIFF/BMP/WebP/SVG;
- active visualization PNG/SVG/PDF;
- selected interval CSV/XLSX;
- Masterlog PDF;
- interpretation PDF;
- ортақ есеп келісімшарты арқылы DOCX және HTML;
- physical print: файлдық sidecar жоқ digest.

## Сақталатын provenance

- қолданба нұсқасы және passport schema;
- жоба, ұңғыма, dataset немесе well-level artifact;
- index, нақты аралық, sample count және index values SHA-256;
- таңдалған арналардың нақты мәндері fingerprints;
- semantic bindings, UOM, sensor/source, confidence, aliases және evidence;
- coverage: availability, observed, zeros, missing және unavailable;
- формулалар, нұсқалар және expression SHA-256;
- form/template/report-definition revision және SHA-256;
- RU/KK/EN тілі;
- renderer, format, DPI, media, orientation, margins, Fit/100% және continuations;
- source/import/lossless fingerprints;
- дайын artifacts basename, role/page, MIME, byte size және SHA-256.

## Source fingerprint басымдығы

1. `LasSourceSnapshot` — `stored-at-import`.
2. Кірістірілген lossless LAS artifact — `embedded-project-artifact`.
3. Қолжетімді сыртқы CSV/Excel/Paradox/LAS — `captured-at-report-time`.
4. Есептің нақты деректерінің normalized snapshot — әрқашан.

Absolute source/output paths passport құрамына кірмейді.

## Тексеру және файл транзакциясы

Passport output staging-ке толық жазылғаннан кейін ғана аяқталады. Әр файл үшін каталогсыз
қауіпсіз атау, `single-file` немесе `page` role, page number, MIME, size және нақты bytes SHA-256
сақталады.

`load_report_passport()` JSON digest, output бар-жоғын, size және SHA-256 мәнін тексереді.
Output пен sidecar recoverable transaction schema v1 арқылы орнатылады:

```text
staging → output fingerprint → signed passport → journaled backup/install
→ installed-file verification → committed → cleanup
```

`committed` күйіне дейінгі қате бұрынғы жұпты қайтарады. Одан кейінгі қате жаңа жұпты сақтап,
cleanup-ты аяқтайды. [Output транзакциясы](REPORT_OUTPUT_TRANSACTION.md).

## Детерминизм

- JSON кілттері сұрыпталып canonical түрде жазылады;
- timestamp, random ID және absolute output paths жоқ;
- `NaN`, Infinity және signed zero fingerprints ішінде нормаланады;
- digest `passport_sha256` өрісін қоспай есептеледі;
- fingerprints таңдалған аралық пен дайын output bytes-қа тәуелді.

## Сақтау және қайта тексеру

Passport есеп сәтті экспортталған кезде жасалады. Ол жобаны **Ctrl+S** арқылы сақтауды
алмастырмайды. Тексеру үшін output пен sidecar-ды бірге сақтап, sidecar-ды қолдау көрсетілетін
тексеру командасымен қайта ашыңыз. Absolute paths сақталмайтындықтан жұпты бірге көшіруге болады;
output атауы немесе bytes өзгерсе, fingerprint тексеруі өтпейді.

## Шектеулер

- бұл ұйымның электрондық қолтаңбасы немесе trusted timestamp емес;
- physical print output-file fingerprint жасамайды;
- recovery journal уақытша absolute paths қамтуы мүмкін, бірақ passport құрамына кірмейді;
- stable алдында Windows/NTFS/network-share/PDF/HiDPI/physical-print smoke-test міндетті.

# Report Passport

Күйі: 0.7.34 нұсқасынан бар. Coverage schema v2, print media schema v3 құрамына, ал дайын output
artifacts fingerprints schema v4 құрамына 0.7.39 нұсқасында қосылды. Project format v16 болып қалады.

## Мақсаты

Report Passport — PDF, image, CSV/XLSX немесе басқа report нәтижесінің provenance-ын сипаттайтын
deterministic JSON sidecar. Data, definition, language, render settings және output bytes өзгермесе,
`passport_sha256` бірдей болады.

```text
report.pdf
report.pdf.passport.json
```

Physical print файл жасамайды, сондықтан artifacts жоқ preliminary digest қана есептеледі.

## Қамтылған жолдар

- Print Center PDF және paged PNG/JPEG/TIFF/BMP/WebP/SVG;
- direct visualization PNG/SVG/PDF;
- selected interval CSV/XLSX;
- Masterlog PDF;
- interpretation PDF.

## Schema v4 output artifacts

Әр дайын файл үшін safe basename, `single-file` немесе `page` role, page number, MIME type, byte
size және нақты bytes SHA-256 сақталады. `load_report_passport()` JSON digest-пен бірге output
файлдың бар-жоғын, size және SHA-256 мәнін тексереді.

Output және sidecar recoverable transaction schema v1 арқылы орнатылады:

```text
staging → fingerprint → signed passport → journaled backup/install
→ installed-file verification → committed → cleanup
```

`committed` күйіне дейінгі қате бұрынғы жұпты қайтарады; committed кейінгі қате жаңа жұпты сақтап,
cleanup-ты аяқтайды. [Output транзакциясы](REPORT_OUTPUT_TRANSACTION.md).

## Шектеулер

Timestamp, random ID және absolute output paths passport ішінде жоқ. Бұл organizational digital
signature немесе trusted timestamp емес. Physical print output fingerprint жасамайды. Windows,
NTFS/network share, PDF, HiDPI және physical-print smoke-test міндетті.

## 0.7.40 ішіндегі DOCX және HTML

Passport schema v4 дайын DOCX/HTML файлының қауіпсіз атауын, MIME түрін, өлшемін және SHA-256
мәнін сақтайды. Экспорттан кейінгі кез келген өзгеріс sidecar жүктеу кезінде анықталады.

# Есеп файлдарының қалпына келетін транзакциясы

Күйі: 0.7.39 нұсқасында іске асырылды. Journal runtime schema: v1. Report Passport: schema v4.
Project format v16 болып қалады.

## Мақсаты

Есептің output-файлы және оның `*.passport.json` sidecar-ы енді бір қалпына келетін операция
ретінде бекітіледі. Бірнеше файлды бір мезетте атомарлы ауыстыру барлық filesystem-де мүмкін
емес, сондықтан journaled commit, толық rollback және процесс үзілгеннен кейін recovery қолданылады.

Қамтылған жолдар:

- Print Center PDF және paged PNG/JPEG/TIFF/BMP/WebP/SVG;
- active visualization үшін direct PNG/SVG/PDF;
- selected interval CSV/XLSX;
- Masterlog PDF;
- interpretation PDF.

## Commit реті

1. Target үшін қалған journal автоматты қалпына келтіріледі.
2. Renderer тек output жанындағы жасырын staging каталогына жазады.
3. Бос емес файлдар және қауіпсіз relative names тексеріледі.
4. Дайын байттар бойынша SHA-256, size және MIME type есептеледі.
5. Report Passport schema v4 `artifacts` тізімін алып, қайта қол қойылады.
6. Sidecar staging ішінде жазылады.
7. Destination және backup операциялары journal-ға жазылады.
8. Ескі файлдар backup-қа көшіріліп, жаңалары `os.replace` арқылы орнатылады.
9. Орнатылған output passport fingerprints бойынша қайта тексеріледі.
10. `committed` күйінен кейін backup, staging және journal өшіріледі.

## Recovery

`committed` күйіне дейін жаңа жартылай файлдар жойылып, бұрынғы output, sidecar және continuation
pages backup-тан қайтарылады. Commit жазылып, тек cleanup аяқталмаса, жаңа жұп сақталып, тек
қызметтік файлдар өшіріледі.

Сол target-ке келесі export recovery-ді автоматты іске қосады. Қолмен тексеру:

```powershell
.\.venv\Scripts\python.exe tools\recover_report_transactions.py "C:\Reports"
```

## Output fingerprint

Schema v4 әр дайын artifact үшін тек қауіпсіз basename, `single-file` немесе `page` role,
page number, MIME type, byte size және SHA-256 сақтайды. `load_report_passport()` JSON digest-пен
бірге барлық output artifact-ті тексереді, сондықтан кейін өзгертілген PDF/image/CSV/XLSX анықталады.

## Шектеулер

- absolute paths тек уақытша recovery journal ішінде болады, passport ішінде болмайды;
- recovery output каталогы мен өз staging workspace шегінен шықпайды;
- physical print файл жасамайды, сондықтан output fingerprint жоқ;
- бұл ұйымның digital signature немесе trusted timestamp механизмі емес;
- Windows және network filesystem smoke-test міндетті болып қалады.

# 0.7.34 шығарылым ескертпелері — Report Passport

Күні: 2026 жылғы 23 шілде. Күйі: тест жинағы.

## Жаңа

- canonical JSON және SHA-256 бар детерминирленген `ReportPassport` schema v1 қосылды;
- source fingerprints, нақты interval, selected channel values, толық semantic binding/UOM,
  formula versions, form revision, language және render settings сақталады;
- channel fingerprint тек нақты report interval ішіндегі sample мәндерін қамтиды;
- forms және tablet layouts content-addressed revision, Masterlog нақты version қолданады;
- absolute output path және generation timestamp паспортқа кірмейді;
- `load_report_passport()` өзгертілген signed JSON-ды анықтайды.

## Экспорт

- Print Center PDF және paged image үшін `<output>.passport.json` жасайды;
- active view direct PNG/SVG/PDF export дәл сондай sidecar жасайды;
- Masterlog PDF және interpretation PDF паспорт жасайды;
- physical print sidecar жасамай digest есептеп көрсетеді;
- бар sidecar overwrite confirmation кезінде есепке алынады.

## Sources және қауіпсіздік

- import-time LAS fingerprint, embedded lossless LAS немесе warning бар external-file fingerprint қолданылады;
- normalized report-data fingerprint әрқашан қосылады;
- sidecar temporary file, `fsync` және `os.replace` арқылы atomic жазылады;
- project format v16 болып қалады.

## Тексеру

- 742 қолжетімді headless/regression/source-integrity test өтті;
- 4 platform scenario skipped;
- dependency жоқ болғандықтан тағы 4 LAS/Qt scenario deselected;
- `compileall` қатесіз аяқталды;
- толық Ruff/mypy/Qt/LAS gate және Windows/HiDPI/PDF/physical-print smoke matrix әлі міндетті.

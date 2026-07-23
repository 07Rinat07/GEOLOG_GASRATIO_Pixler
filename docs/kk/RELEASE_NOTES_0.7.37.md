# 0.7.37 шығарылым ескертпелері — ортақ coverage моделі

- бір headless coverage анализаторы қосылды;
- нөл, missing sample және unavailable channel енді араластырылмайды;
- `ReportDefinition` және Report Passport schema v2 қолданады;
- CSV ішінде `0`, бос ұяшық және `#N/A`; XLSX coverage статистикасын да көрсетеді;
- JSON/Parquet және passport құрылымдалған coverage payload сақтайды;
- v1 definition payload runtime кезінде миграцияланады, project format v16 болып қалады.

Толығырақ: [Coverage моделі](COVERAGE_MODEL.md).

Проверки / checks: 57 focused passed, 1 optional skipped; 876 passed, 4 skipped, 3 LAS tests deselected.

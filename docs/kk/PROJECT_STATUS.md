# Жоба мәртебесі

Кесім: 2026 жылғы 23 шілде. Нұсқа: 0.7.40, тесттік жинақ.

## Орындалды

- ортақ `ReportDocumentModel` schema v1;
- бір `ResolvedReportDefinition` арқылы DOCX және автономды HTML;
- аралықты қайта есептемейтін нақты row indices;
- Coverage: нақты `0`, missing `—`, unavailable `#N/A`;
- макроссыз және сыртқы объектілерсіз deterministic OOXML;
- scripts және желілік ресурстарсыз inline CSS HTML;
- recoverable output transaction және Report Passport schema v4;
- дайын DOCX/HTML байттарының fingerprint-і;
- project format v16 болып қалады.

Тексеру: 73 passed focused tests; қолжетімді regression — 926 passed, 4 skipped, 3 LAS сценарийі deselected.
Толық Qt/LAS/Ruff/mypy gate және Windows Word/browser/PDF/HiDPI/physical-print smoke-test
міндетті болып қалады.

Келесі кезең: типтелген drilling/gas/show/sample/casing/formation-top оқиғалары.

[DOCX және HTML](DOCX_HTML_EXPORT.md) және [жалпы мәртебе](../PROJECT_STATUS.md).

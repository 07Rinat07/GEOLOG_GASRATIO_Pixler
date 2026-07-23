# Жоба мәртебесі

Кесім: 2026 жылғы 23 шілде. Нұсқа: 0.7.38, тесттік жинақ.

## Орындалды

- A4/A3/custom/roll үшін ортақ print-media schema v1;
- reference DPI 96 негізіндегі Fit және 100%;
- vertical pages және horizontal continuations бір deterministic plan құрайды;
- preview, PDF, paged files және physical printer бір job қолданады;
- system page range printer gate және final page count ішінде ескеріледі;
- gate media, bounds, margins, printable area, DPI және device state тексереді;
- Report Passport schema v3 деңгейіне көтерілді;
- project format v16 болып қалады.

Тексерулер: 56 focused және 27 print-specific tests өтті; қолжетімді регрессия —
910 passed, 4 skipped, 3 LAS tests deselected. Толық Qt/LAS/Ruff/mypy gate және real
Windows/HiDPI/PDF/physical-print smoke-test міндетті.

Келесі кезең: output + passport filesystem transaction және дайын файл fingerprint.

[Баспа моделі](PRINT_MEDIA_MODEL.md) және [жалпы мәртебе](../PROJECT_STATUS.md).

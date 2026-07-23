# Жоба мәртебесі

Кесім: 2026 жылғы 23 шілде. Нұсқа: 0.7.41, тесттік жинақ.

## Орындалды

- drilling/gas/show/sample/casing/formation-top үшін алты typed payload;
- depth/time anchors, canonical UTC timestamps, source, revision және calibration бар envelope;
- duplicate, out-of-order, gap, stale, calibration missing/expired QC;
- жалғыз mutation boundary ретінде `OperationalEventController`;
- project format v17 және қауіпсіз v16 → v17 migration;
- strict discriminator codec және typed payload round trip;
- EVENTS/DRILLING нақты `ResolvedReportDefinition` аралығын қолданады;
- `ui` пакетіндегі ескірген import-controller көшірмелері жойылды.

Кеңейтілген focused set: 108 passed. Қолжетімді headless regression: 936 passed, 4 skipped.
Толық Qt/LAS/Ruff/mypy gate және Windows/HiDPI/PDF/physical-print
smoke-test міндетті болып қалады.

Келесі срез: append-only growing dataset, checkpoint және deterministic replay.

[Operational events](OPERATIONAL_EVENTS.md) және [жалпы мәртебе](../PROJECT_STATUS.md).

# Ортақ ReportDefinition

`ReportDefinition` schema v2 — бір есептің өзгермейтін сипаттамасы. Preview немесе export
басталғанға дейін ол dataset, нақты index, sections, stable curve IDs, күтілетін мнемоникалар,
form, language және interval mode мәндерін бекітеді.

Resolver бір inclusive row set жасайды, мнемоникаларды шешеді, табылмаған сұрауларды unavailable
channel ретінде сақтайды және coverage есептейді. Preview, PDF/баспа және CSV/XLSX interval немесе
channel availability мәнін бөлек қайта есептемейді.

Resolved кестелік export белсенді сандық depth немесе relative-time index мәнін қолдайды.
CSV/XLSX нақты `resolved.interval.indices` жолдарын пайдаланады; бірінші баған, бірлік және
шекаралар белсенді index-тен алынады. TIME metadata үшін «Аралықтың басталуы» және «Аралықтың
аяқталуы» атаулары қолданылады. DATETIME шекаралары бұл adapter-де әзірге қолдау таппайды.

Schema v1 payload runtime schema v2 нұсқасына миграцияланады. Project format v19 `well.operational_events` және `well.acquisition_sessions` collection-дарын сақтайды; events v17-де енгізілді. `EVENTS` және `DRILLING`
үшін `resolve_operational_event_report()` дайын `ResolvedReportDefinition` шекараларын дәл
қолданады: depth → `depth_m`, relative time → `elapsed_time_s`, datetime → UTC `measured_at`.
Optional `event_kinds` comma-separated kind list береді. Interval қайта есептелмейді.

[Толық contract](../REPORT_DEFINITION.md) және [coverage моделі](COVERAGE_MODEL.md).

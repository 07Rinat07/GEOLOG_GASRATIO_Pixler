# Ортақ ReportDefinition

`ReportDefinition` schema v2 — бір есептің өзгермейтін сипаттамасы. Preview немесе export
басталғанға дейін ол dataset, нақты index, sections, stable curve IDs, күтілетін мнемоникалар,
form, language және interval mode мәндерін бекітеді.

Resolver бір inclusive row set жасайды, мнемоникаларды шешеді, табылмаған сұрауларды unavailable
channel ретінде сақтайды және coverage есептейді. Preview, PDF/баспа және CSV/XLSX interval немесе
channel availability мәнін бөлек қайта есептемейді.

Schema v1 payload runtime schema v2 нұсқасына миграцияланады. Project format v16 болып қалады.

[Толық contract](../REPORT_DEFINITION.md) және [coverage моделі](COVERAGE_MODEL.md).

# Документация

Документация разделена на три уровня: пользовательские инструкции, инженерные контракты и один
план проекта. История хранится в одном changelog, а generated test/build results — вне Git как
artifacts workflow `.github/workflows/release-gate.yml`.

## Начало работы

- Руководство: [Русский](ru/README.md) · [Қазақша](kk/README.md) · [English](en/README.md)
- Порядок разделов интерфейса и пользовательские процессы:
  [Русский](USER_GUIDE_RU.md) · [Қазақша](USER_GUIDE_KK.md) ·
  [English](USER_GUIDE_EN.md) · [индекс руководств](README.md)
- Карта функций: [Русский](ru/FEATURES.md) · [Қазақша](kk/FEATURES.md) ·
  [English](en/FEATURES.md)
- Безопасность: [политика](../SECURITY.md) · [Русский](ru/SECURITY.md) ·
  [Қазақша](kk/SECURITY.md) · [English](en/SECURITY.md)
- Диагностика: [Русский](ru/APPLICATION_DIAGNOSTICS.md) ·
  [Қазақша](kk/APPLICATION_DIAGNOSTICS.md) · [English](en/APPLICATION_DIAGNOSTICS.md)
- Запуск вкладки «Файлы» после обновления: [FILE_WORKSPACE_STARTUP.md](FILE_WORKSPACE_STARTUP.md)

## Управление проектом

- [PROJECT_PLAN.md](PROJECT_PLAN.md) — единственный актуальный план и открытые задачи.
- [ARCHITECTURE.md](ARCHITECTURE.md) — текущие границы и целевая декомпозиция.
- [REQUIREMENTS.md](REQUIREMENTS.md) — требования и критерии приёмки.
- [TESTING.md](TESTING.md) — обязательный автоматический и Windows gate.
- [PHYSICAL_PRINT_ACCEPTANCE.md](PHYSICAL_PRINT_ACCEPTANCE.md) — ручной REL-03/CUT-03 gate
  реального A4/A3 принтера и структурированное operator evidence.
- [ASSET_PROVENANCE.md](ASSET_PROVENANCE.md) — SEC-05 inventory, provenance/license coverage
  и строгий clearance gate встроенных lithology/symbol assets.
- [PERFORMANCE.md](PERFORMANCE.md) — воспроизводимые performance-baselines и regression guardrails.
- [CHANGELOG.md](CHANGELOG.md) — единая краткая история крупных изменений.
- [DOCUMENTATION_POLICY.md](DOCUMENTATION_POLICY.md) — правила порядка и актуальности.
- [OPUS_GASOMER_IMPLEMENTATION.md](OPUS_GASOMER_IMPLEMENTATION.md) — утверждённый
  инженерный контракт практического профиля ОПУС, решения и порядок продолжения.

## Основные пользовательские процессы

- Рабочий проект и ежедневное наращивание: [RU](ru/PROJECT_WORKFLOW.md) ·
  [KK](kk/PROJECT_WORKFLOW.md) · [EN](en/PROJECT_WORKFLOW.md)
- Сохранение импортированных и изменённых данных: [RU](ru/SESSION_SAVING.md) ·
  [KK](kk/SESSION_SAVING.md) · [EN](en/SESSION_SAVING.md)
- Import Review: [RU](ru/IMPORT_REVIEW.md) · [KK](kk/IMPORT_REVIEW.md) ·
  [EN](en/IMPORT_REVIEW.md)
- LAS Editor: [RU](ru/LAS_EDITOR.md) · [KK](kk/LAS_EDITOR.md) · [EN](en/LAS_EDITOR.md)
- Планшет: [RU](ru/UI_WORKSPACE.md) · [KK](kk/UI_WORKSPACE.md) · [EN](en/UI_WORKSPACE.md)
- Конструктор: [RU](ru/CONSTRUCTOR.md) · [KK](kk/CONSTRUCTOR.md) ·
  [EN](en/CONSTRUCTOR.md)
- Аннотации: [RU](ru/ANNOTATIONS.md) · [KK](kk/ANNOTATIONS.md) ·
  [EN](en/ANNOTATIONS.md)
- Paradox/GS2: [RU](ru/PARADOX_IMPORT.md) · [KK](kk/PARADOX_IMPORT.md) ·
  [EN](en/PARADOX_IMPORT.md)
- Отчёты: [RU](ru/REPORT_EXPORT.md) · [KK](kk/REPORT_EXPORT.md) ·
  [EN](en/REPORT_EXPORT.md)
- Интерпретация бурового газа и отчёт по всей скважине:
  [RU](ru/MUD_GAS_INTERPRETATION.md) · [KK](kk/MUD_GAS_INTERPRETATION.md) ·
  [EN](en/MUD_GAS_INTERPRETATION.md)
- Режимы нормализованного газа и сопоставление с ЛБА:
  [RU](ru/NORMALIZED_GAS_INTERPRETATION.md) ·
  [KK](kk/NORMALIZED_GAS_INTERPRETATION.md) ·
  [EN](en/NORMALIZED_GAS_INTERPRETATION.md)
- Печатные шапки и логотипы: [PRINT_HEADER_AND_LOGO_CATALOGS.md](PRINT_HEADER_AND_LOGO_CATALOGS.md)
- Файлы, PDF, изображения, архивы и расчёты: [RU](ru/FILES_WORKSPACE.md) ·
  [KK](kk/FILES_WORKSPACE.md) · [EN](en/FILES_WORKSPACE.md) ·
  [сводная памятка](FILES_WORKSPACE_GUIDE.md) · [инженерное описание](FILE_WORKSPACE.md)
- WITS0: [RU](ru/WITS0_CAPTURE.md) · [KK](kk/WITS0_CAPTURE.md) ·
  [EN](en/WITS0_CAPTURE.md)
- WITSML SOAP: [RU](ru/WITSML_1411_SOAP.md) · [KK](kk/WITSML_1411_SOAP.md) ·
  [EN](en/WITSML_1411_SOAP.md)

Дополнительные тематические ссылки доступны из `README.md` и `FEATURES.md` соответствующего
языка.

## Инженерные контракты

- Данные и импорт: [IMPORT_REVIEW.md](IMPORT_REVIEW.md),
  [SEMANTIC_CHANNEL_DICTIONARY.md](SEMANTIC_CHANNEL_DICTIONARY.md),
  [GS2_IMPORT.md](GS2_IMPORT.md), [LAS_IMPORT.md](LAS_IMPORT.md).
- Формы и планшет: [FORM_ENGINE.md](FORM_ENGINE.md),
  [TABLET_DEPTH_TIME_NAVIGATION.md](TABLET_DEPTH_TIME_NAVIGATION.md),
  [TABLET_RENDERING_BENCHMARKS.md](TABLET_RENDERING_BENCHMARKS.md).
- Отчёты: [REPORT_DEFINITION.md](REPORT_DEFINITION.md),
  [REPORT_OUTPUT_TRANSACTION.md](REPORT_OUTPUT_TRANSACTION.md),
  [REPORT_PASSPORT.md](REPORT_PASSPORT.md).
- Полевые данные: [WITS0_ACQUISITION.md](WITS0_ACQUISITION.md),
  [WITS0_RELIABILITY.md](WITS0_RELIABILITY.md),
  [WITSML_INVENTORY.md](WITSML_INVENTORY.md),
  [WITSML_DATA_IMPORT.md](WITSML_DATA_IMPORT.md),
  [ETP12_INTEROPERABILITY_GATE.md](ETP12_INTEROPERABILITY_GATE.md).

## Дополнительный инженерный каталог

- Импорт: [UNIVERSAL_IMPORT.md](UNIVERSAL_IMPORT.md), [CSV_IMPORT.md](CSV_IMPORT.md),
  [EXCEL_IMPORT.md](EXCEL_IMPORT.md).
- LAS и глубина/время: [LAS_EDITOR.md](LAS_EDITOR.md),
  [LAS_EDITOR_ARCHITECTURE.md](LAS_EDITOR_ARCHITECTURE.md),
  [TIME_DEPTH_LAS_ARCHITECTURE.md](TIME_DEPTH_LAS_ARCHITECTURE.md),
  [LAG_DEPTH_CORRECTION.md](LAG_DEPTH_CORRECTION.md).
- Расчёты и события: [DEXP_FORMULAS.md](DEXP_FORMULAS.md),
  [MUD_GAS_FORMULAS.md](MUD_GAS_FORMULAS.md),
  [OPUS_GASOMER_IMPLEMENTATION.md](OPUS_GASOMER_IMPLEMENTATION.md),
  [GAS_CONDITIONING_QC.md](GAS_CONDITIONING_QC.md),
  [NORMALIZED_GAS.md](NORMALIZED_GAS.md),
  [COMPLEX_GAS_FORM.md](COMPLEX_GAS_FORM.md),
  [OPERATIONAL_EVENTS.md](OPERATIONAL_EVENTS.md),
  [SENSOR_CATALOG.md](SENSOR_CATALOG.md).
- Формы и планшет: [CONSTRUCTOR_ARCHITECTURE.md](CONSTRUCTOR_ARCHITECTURE.md),
  [COMPOSITE_LOG.md](COMPOSITE_LOG.md),
  [INTERVAL_MOUSE_EDITING.md](INTERVAL_MOUSE_EDITING.md),
  [TABLET_GRID_STANDARD.md](TABLET_GRID_STANDARD.md).
- Отчёты и рендеринг: [REPORT_EXPORT.md](REPORT_EXPORT.md),
  [GOLDEN_RENDERING.md](GOLDEN_RENDERING.md),
  [PRINT_GAS_TIME_REGRESSION.md](PRINT_GAS_TIME_REGRESSION.md).
- ETP 1.2: [ETP12_ARCHITECTURE.md](ETP12_ARCHITECTURE.md),
  [ETP12_ACQUISITION.md](ETP12_ACQUISITION.md).
- WITS/WITSML: [WITS0_LIVE_VIEW.md](WITS0_LIVE_VIEW.md),
  [WITS0_WINDOWS_FIELD_GATE.md](WITS0_WINDOWS_FIELD_GATE.md),
  [WITSML_1411_SOAP.md](WITSML_1411_SOAP.md).
- Платформа: [BRANDING.md](BRANDING.md), [I18N.md](I18N.md).

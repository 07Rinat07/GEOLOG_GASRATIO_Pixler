# Documentation Index

## Active engineering documents

- [PROJECT_STATUS.md](PROJECT_STATUS.md) — current implementation state in Russian, Kazakh, and English.
- [ROADMAP.md](ROADMAP.md) — ordered development roadmap and next vertical slice.
- [ARCHITECTURE.md](ARCHITECTURE.md) — architectural boundaries and current project format.
- [REQUIREMENTS.md](REQUIREMENTS.md) — functional and non-functional requirements matrix.
- [TESTING.md](TESTING.md) — quality gates and regression matrix.
- [DOCUMENTATION_POLICY.md](DOCUMENTATION_POLICY.md) — documentation maintenance rules.
- [CHANGELOG.md](CHANGELOG.md) — concise history of completed increments.
- [SENSOR_CATALOG.md](SENSOR_CATALOG.md) — normalized Sensors/mnemonic reference and external JSON schema.
- LAS parameter resolver: [Русский](ru/LAS_PARAMETER_RESOLUTION.md) · [Қазақша](kk/LAS_PARAMETER_RESOLUTION.md) · [English](en/LAS_PARAMETER_RESOLUTION.md)
- [INTERVAL_MOUSE_EDITING.md](INTERVAL_MOUSE_EDITING.md) — direct interval drawing and boundary editing.
- [TABLET_DEPTH_TIME_NAVIGATION.md](TABLET_DEPTH_TIME_NAVIGATION.md) — synchronized depth/time scrolling, zoom, index selection, and persistence.

## User guides

- GeoData depth workspace: [Русский](ru/GEODATA_DEPTH_WORKSPACE.md) · [Қазақша](kk/GEODATA_DEPTH_WORKSPACE.md) · [English](en/GEODATA_DEPTH_WORKSPACE.md)
- [Русский](ru/README.md)
- [Қазақша](kk/README.md)
- [English](en/README.md)

All user-facing behavior changes must be reflected in all three guides and in the RU/KK/EN localization catalogs.

## Tablet Engine 2.0

- `ROADMAP.md` — updated product sequence and priorities.
- `PROJECT_PLAN.md` — researched plan through version 1.0.
- `TABLET_ENGINE_2.md` in `docs/ru`, `docs/kk`, and `docs/en` — user navigation controls.

- [Form Engine](FORM_ENGINE.md)
- Universal Print Center: [Русский](ru/UNIVERSAL_PRINT_CENTER.md) · [Қазақша](kk/UNIVERSAL_PRINT_CENTER.md) · [English](en/UNIVERSAL_PRINT_CENTER.md)

- Редактируемые подписи формы и стратиграфия: [RU](ru/FORM_CAPTIONS_AND_STRATIGRAPHY.md) · [KK](kk/FORM_CAPTIONS_AND_STRATIGRAPHY.md) · [EN](en/FORM_CAPTIONS_AND_STRATIGRAPHY.md)

## LAS Editor 2

- [Русский](ru/LAS_EDITOR_2.md)
- [Қазақша](kk/LAS_EDITOR_2.md)
- [English](en/LAS_EDITOR_2.md)

Безопасное сращивание LAS, возрастающая копия, вставка внешних кривых, карандаш,
Excel-подобная таблица и экспорт.

<!-- BEGIN FORM_CONSTRUCTOR_SLICE23 -->
## Universal Form Constructor 0.7.1

Plan: [Русский](ru/FORM_CONSTRUCTOR_PLAN.md) · [Қазақша](kk/FORM_CONSTRUCTOR_PLAN.md) · [English](en/FORM_CONSTRUCTOR_PLAN.md)  
User guide: [Русский](ru/CONSTRUCTOR.md) · [Қазақша](kk/CONSTRUCTOR.md) · [English](en/CONSTRUCTOR.md)  
Asset import report: [CONSTRUCTOR_ASSET_IMPORT_REPORT.md](CONSTRUCTOR_ASSET_IMPORT_REPORT.md)
Technical architecture: [CONSTRUCTOR_ARCHITECTURE.md](CONSTRUCTOR_ARCHITECTURE.md)  
Text/form/stratigraphy guide: [Русский](ru/FORM_CAPTIONS_AND_STRATIGRAPHY.md) · [Қазақша](kk/FORM_CAPTIONS_AND_STRATIGRAPHY.md) · [English](en/FORM_CAPTIONS_AND_STRATIGRAPHY.md)  
<!-- END FORM_CONSTRUCTOR_SLICE23 -->

## Lithotype rendering 0.7.2

- exact legacy BMP mapping: `src/geoworkbench/resources/lithotypes.ru.json`;
- compatibility and brush resolver: `src/geoworkbench/tablet/lithology_patterns.py`;
- native device-pixel tablet tiling: `src/geoworkbench/tablet/lithology_graphics.py`;
- user behaviour: `ru/CONSTRUCTOR.md`, `kk/CONSTRUCTOR.md`, `en/CONSTRUCTOR.md`.

# Roadmap — GEOLOG Gas Ratio & Pixler

## Current

### Tablet Engine 2.0 — Rendering Engine

Completed:

- shared depth/time camera and viewport;
- vertical and horizontal navigation;
- pinned depth track and minimap;
- peak-preserving LOD;
- LRU curve-geometry cache;
- unchanged-curve redraw suppression;
- static title/grid/axis descriptor cache;
- explicit dirty invalidation for data, style, viewport, static state and layout;
- partial single-track refresh without rebuilding adjacent tracks;
- independent cursor, selection, marker, annotation, preview, tooltip and rubber-band layers;
- per-layer visibility, Z-order and dirty revisions;
- overlay-only updates without curve-geometry rebuilds;
- cache and full/partial refresh metrics;
- 100k/1M/5M benchmark scenarios.

Remaining:

- performance diagnostics panel;
- accepted performance budgets on real Windows LAS files.

## Next

### Selection & Interaction Engine

- common hit-testing and selection;
- column drag-and-drop and resize handles;
- contextual editing and property panel;
- form-level Undo/Redo.

### Form Engine

- editable depth and time forms;
- arbitrary columns and curves;
- saved order, width, scale and style;
- custom parameters and mnemonic mapping;
- factory templates and user copies.

## Later, already agreed

- Normalized Gas;
- Gas Ratio;
- Pixler;
- hydrocarbon interpretation zones;
- printable graphical and textual interpretation reports.


- [x] Selection & Interaction Engine: базовая модель `HitResult`, `SelectionManager`, интеграция дорожек и интервалов, инфраструктура Undo/Redo.
- [x] Selection & Interaction Engine: hit-testing кривых и заголовков, resize handles, drag-and-drop порядка дорожек и Undo/Redo.
- [ ] Selection & Interaction Engine: панель свойств, множественное выделение и контекстные операции.

### Completed: Selection & Interaction — multiselect and context operations

- Ctrl/Shift multi-selection for tracks and curves.
- Curve properties shown in the inspector.
- Track context menu: move, hide, remove, undo, redo.

### Next

- Editable unified properties panel for track and curve styles.
- Batch operations for selected tracks/curves.
- Keyboard shortcuts and clipboard operations.

## Form Engine

- ✅ Модель и схема форм v1.
- ✅ Заводские шаблоны и пользовательское хранилище.
- ✅ Менеджер форм и первый безопасный механизм применения к планшету.
- ✅ Визуальный редактор структуры колонок и дорожек.
- ✅ Редактор ParameterBinding и оформления кривых внутри дорожки.
- 🔄 Следующий срез: живой предпросмотр на планшете и завершение рабочего сценария сохранения/применения.

- [x] Live Form Preview: draft state, auto-apply, manual apply, save and revert in one editor session.

### Tablet usability correction — completed

- per-curve auto/manual scales and styles;
- stacked readable curve headers;
- mouse-first curve selection;
- synchronized depth cursor values;
- 1/5/10/20/30/40/50 m and custom visible interval;
- RU/KK/EN strings for the affected workflow.

### Completed: specialized Gas Ratio & Pixler forms

- localized RU/KK/EN depth interpretation form;
- localized time monitoring form;
- normalized-gas QC form;
- detailed C1–C5 form;
- stable IDs and canonical bindings across languages.

### Next

- Normalized Gas Engine profiles, quality mask, derived curves, and provenance.

## Completed correction — working factory LAS forms

- [x] materialize the basic depth/time forms from the active LAS dataset;
- [x] group actual curves into readable category columns;
- [x] preserve source mnemonic, display name, unit, style, and reference range;
- [x] expose available/missing bindings in the form manager;
- [x] create an editable saved copy from a materialized factory form;
- [x] validate depth/time axis compatibility;
- [x] support mouse row selection and multi-select LAS-curve insertion in the track editor.


## Completed correction — runtime localization

- [x] apply Russian, Kazakh, and English immediately without restart;
- [x] retranslate the open shell and primary workbench widgets in place;
- [x] preserve project, dataset, tablet layout, zoom, and scroll state;
- [x] retain the selected language in `QSettings`;
- [x] cover the `ru → kk → en` workflow with a GUI regression test.

## Completed correction — exact vertical viewport

- [x] 1/5/10–100 presets and custom positive values;
- [x] immediate synchronized application to every tablet track;
- [x] automatic commit of typed values without Enter;
- [x] layout-model camera state as the single source of truth;
- [x] range preservation across resize, form rebuild, and runtime language changes;
- [x] active time-axis units in time forms;
- [x] full regression suite: 848 passed, 1 skipped.

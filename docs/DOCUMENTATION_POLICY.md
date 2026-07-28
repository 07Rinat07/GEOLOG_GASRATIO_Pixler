# Правила документации

## Канонические документы

- `docs/PROJECT_PLAN.md` — единственный план.
- `docs/CHANGELOG.md` — единственная история изменений.
- `docs/ARCHITECTURE.md` и `docs/REQUIREMENTS.md` — инженерные контракты.
- `docs/TESTING.md` — единственный общий quality/release gate; предметные field/interoperability
  checklists допустимы как его входы.
- `docs/{ru,kk,en}` — актуальные пользовательские, операторские и локализованные инженерные
  инструкции с одинаковым набором имён.

Запрещены отдельные `RELEASE_NOTES_*`, `BUILD_MANIFEST_*`, `HOTFIX_REPORT_*`,
`IMPLEMENTATION_REPORT_*`, `INCREMENT_*`, дополнительные `*_PLAN.md`, AI-аудиты и копии
статуса проекта. Generated test results, screenshots, preview и build manifests хранятся вне Git
(как CI artifacts после появления CI), а не в `docs`.

## Обновление

При изменении поведения одновременно обновляются:

1. код и regression test;
2. соответствующая инструкция RU/KK/EN;
3. `ARCHITECTURE.md` или `REQUIREMENTS.md`, если изменился контракт;
4. `PROJECT_PLAN.md`, только если открылась или закрылась задача;
5. краткая запись в `CHANGELOG.md`;
6. `SECURITY.md` и локализованные security guides при изменении импорта, сети, credentials,
   resource limits или retention.

Корневой и локализованные README используют одну команду запуска:
`python -m geoworkbench.app.main`.

## Защита данных

- Project, LAS, WITS/WITSML captures, exports, diagnostics и local paths являются
  пользовательскими данными и не попадают в Git.
- Разрешённый fixture должен находиться в `tests/fixtures` или контролируемом `resources/samples`,
  быть синтетическим/обезличенным и иметь понятное назначение.
- В документации не публикуются реальные имена скважин, клиентов, локальные пути и credentials.

## Проверка документации

Для документационных изменений выполняются:

```powershell
python tools/check_documentation.py
python -m pytest -q tests/test_documentation_sync_0762.py
```

Проверка контролирует одинаковые RU/KK/EN-файлы, рабочие ссылки, достижимость каждого документа
из канонического индекса, i18n keys, runtime marker, единственный план, отсутствие исторических
отчётов и каноническую команду запуска. Полный gate определён в [TESTING.md](TESTING.md).

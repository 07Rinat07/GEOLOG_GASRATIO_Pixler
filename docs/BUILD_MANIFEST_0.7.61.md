# Build manifest 0.7.61

Полный проект собран из версии 0.7.60 с непосредственным изменением исходного дерева.
Project format v20, form schema v6 и tablet layout v16 не изменялись.
Корневой `README.md` не изменён; техническая документация находится в `docs`.

## Реализация

- `src/geoworkbench/ui/symbol_insertion_dialog.py` — отдельное окно справочника, поиска и параметров размещения;
- `src/geoworkbench/project/symbol_insertion.py` — Qt-независимое преобразование выбора в контракт аннотации;
- `src/geoworkbench/form_constructor/asset_install.py` — выбор transparent/original варианта и установка PNG во внутреннее хранилище проекта;
- `src/geoworkbench/project/annotation_schema.py` — сохранение `symbol_id` и режима фона;
- `src/geoworkbench/project/annotation_controller.py` — валидация, создание, изменение и дублирование значка;
- `src/geoworkbench/ui/main_window.py` — команда панели F4, запуск окна и создание объекта;
- `src/geoworkbench/tablet/tablet_view.py` — команды контекстного меню и начальная позиция на графике;
- `src/geoworkbench/resources/i18n/{ru,kk,en}.json` — синхронная локализация интерфейса;
- `tests/test_graph_symbol_insertion.py` — catalog/model/round-trip/source/localization regression-тесты;
- `docs/{ru,kk,en}` — синхронные инструкции, статус, план и release notes.

## Проверка

- focused regression: **103 passed**;
- проверены все 19 transparent PNG и все 19 original BMP справочника;
- project JSON + image-assets round-trip: успешно;
- RU/KK/EN key parity: по 1881 ключу, расхождений нет;
- `python -m compileall -q src tests`: успешно;
- wheel `geolog_gasratio_pixler-0.7.61-py3-none-any.whl`: успешно собран и проверен `unzip -t`;
- wheel SHA-256: `64c8c6da89ef6b9c7ce189d6d5dad5f5561477024ac0e0ae757ed21c49996e82`;
- полный Qt/UI-прогон не выполнен: в контейнере отсутствуют PySide6, pyqtgraph и lasio;
- перед stable обязателен Windows/PySide6 smoke-test вставки обоих вариантов, drag/resize, Undo/Redo, reopen, PDF и печати при DPI 100%, 125% и 150%.

## SHA-256 ключевых файлов

```text
4a0aca9d53cd74ce4a1b394380fc0db103bbd2cec8c132e5bd880090d72daa5f  README.md
c111edab4e14458efd1336f2d1d79e62552f9f2a6812da85fd45da7b1063edbd  pyproject.toml
9e7375286148c9abff25e48572924d700dd3c9b1b8fffb8fa477e1a6ff00b457  src/geoworkbench/__init__.py
b0ae71cdc6c618d3f626c55b76ae074dbb6c6a7a7cff9526bbda6f17a768bb5c  src/geoworkbench/form_constructor/asset_install.py
fefd4e55a40d20198aa1308cfd7abff3d52628f32fb59dac0443b8d6b8e5b2fc  src/geoworkbench/project/annotation_schema.py
50937c8714ddb16c72eb504ba7db1336d9c7bf22b2ed24ad91a5fd6d50918960  src/geoworkbench/project/annotation_controller.py
229eeaf592f6c5a361f575a7a7c076c431faed4c5d853b49069f65d3b85f3902  src/geoworkbench/project/symbol_insertion.py
7de8b0103715f4ac044488ac2e8dbf1ec27701301a75a96e979711d2a3a26317  src/geoworkbench/ui/symbol_insertion_dialog.py
8f30561efcf12052e901f32ba3ddc39b2d3916d1e6ac77b3528ae47487cbe7d0  src/geoworkbench/ui/main_window.py
4e97cac5900ed9db784f74e9ec5c9a89ee8dd0849f2f7e997223a98dd16da9be  src/geoworkbench/tablet/tablet_view.py
43cc7dfe33c17b367c6834e37abb99d59629948543c832866bfb7414d42dc42e  src/geoworkbench/resources/i18n/ru.json
0c8c9ccdf04426d29449c9fea09118b0bd273b42f591d1623b89b043b76691dc  src/geoworkbench/resources/i18n/kk.json
7c65a4f6649efe493e0fffd52b18abf88322e149278f288a24ad27e9f623d7c8  src/geoworkbench/resources/i18n/en.json
b3d1d65c0a8b4119c8e3b0beaf605bd3f2348d15c2724041e84e85b3e6af8c60  tests/test_graph_symbol_insertion.py
036e07f84ed57a0dff08b61c6b7fb8acbe5d3af4dea48d223284f2fdeb5d457f  docs/ru/ANNOTATIONS.md
def26e74c01b1b8a92141327f23e6142f7fb4dd2585a68204d786874ccf7c9c9  docs/kk/ANNOTATIONS.md
8fecb0a8a252cd477cb8f3937e377c43237a2dfbc5bc1254d93c5e89dc55c255  docs/en/ANNOTATIONS.md
```

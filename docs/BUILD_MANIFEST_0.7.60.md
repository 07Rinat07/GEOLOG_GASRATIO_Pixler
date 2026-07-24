# Build manifest 0.7.60

Полный проект собран из версии 0.7.59 с непосредственным изменением исходного дерева.
Project format v20, form schema v6 и tablet layout v16 не изменялись.

## Реализация

- `src/geoworkbench/ui/interval_statistics_overlay.py` — дочерняя перемещаемая overlay-панель;
- `src/geoworkbench/ui/interval_overlay_geometry.py` — Qt-независимая политика геометрии;
- `src/geoworkbench/ui/main_window.py` — интеграция, очистка при form/dataset switch;
- `src/geoworkbench/ui/interval_statistics_panel.py` — адаптивная сетка кнопок 2×2;
- `tests/test_interval_overlay_geometry.py` — pure geometry regression;
- `tests/test_interval_statistics_overlay_contract.py` — source-contract regression;
- `tests/test_interval_statistics_overlay_widget.py` — Qt lifecycle/drag/close regression;
- `tests/test_root_readme_scope.py` — защита области ответственности корневого README.

## Проверка

- focused: 19 passed;
- доступная headless-регрессия: 1094 passed, 4 skipped, 3 deselected;
- `compileall`: успешно;
- wheel `0.7.60`: успешно собран;
- Qt widget-сценарии требуют Windows/PySide6.

## SHA-256 ключевых файлов

```text
4a0aca9d53cd74ce4a1b394380fc0db103bbd2cec8c132e5bd880090d72daa5f  README.md
000b989ca6178ee3c771950873e0fd52d69c611b913dbc2d5534287b0df51a6a  pyproject.toml
383f62b3ddd0551f378ca85d83826202feb748e47fdf6b6804302c4ee96807aa  src/geoworkbench/__init__.py
951fa5cff1e2e5006d672ba532ae61e97143fbb02eeefa3eeaf8371276b505c2  src/geoworkbench/ui/main_window.py
dc080a63145f13cc096ea691ab17c680468aeb2b379fb4a79260502617dfa631  src/geoworkbench/ui/interval_statistics_overlay.py
5055f1494017c4eed64fbc7b0ecf9d7c2faf570fad563477f6eb199f66a74287  src/geoworkbench/ui/interval_overlay_geometry.py
b10c52c1d986e609c25e441c860c26487a8c49fe35c8ea0fa062a8f748d0f1bf  src/geoworkbench/ui/interval_statistics_panel.py
2f3cd9837e0b2d287ba195b5514e375598d01b04a265da9e6cf39f9a0ccc8be5  tests/test_interval_overlay_geometry.py
87c5299a919cbe8d1d6177697c3910edf3ff081f54496ac5877a184396aaaba2  tests/test_interval_statistics_overlay_contract.py
d7d44534b5c54619b86a9494ead05753b99f3684b7d93fd37fb6827c4641c1c1  tests/test_interval_statistics_overlay_widget.py
93b1cf299b5ec8a2e4de93c2e07d81852856b80182ec9340e83588078e1d44eb  tests/test_root_readme_scope.py
```

# План отраслевых форматов, 3D и хранилища

Проверено 16 июля 2026 года по официальной документации проектов. Цель документа —
зафиксировать реалистичный порядок интеграции, а не объявить поддержку формата до появления
валидатора, тестовых наборов и loss/preflight-отчёта.

## Принятые решения

| Направление | Решение | Предлагаемый стек | Граница первой версии |
|---|---|---|---|
| DLIS/LIS | принять в ближайший отраслевой срез | `dlisio` как optional adapter | read-only DLIS v1/LIS79, inventory logical files/frames/channels, выбор frame/index, import report; исходник остаётся artifact |
| GIS | принять в ближайший отраслевой срез | GDAL/OGR как системная optional-зависимость | GeoPackage как основной vector exchange, Shapefile только совместимость, GeoTIFF/BigTIFF/COG, явный CRS и reprojection preflight |
| DOCX | принять после модели отчёта | `python-docx` как optional dependency | генерация из утверждённого `.docx`-шаблона; PDF остаётся канонической печатной формой |
| SEG-Y | второй приоритет | `segyio` как изолированный optional adapter | read-only headers/traces, geometry/QC, 2D section и выборка inline/xline; без загрузки полного куба в RAM и без скрытой перезаписи |
| HDF5/NetCDF | слой больших научных массивов | `xarray` + `h5py`/`h5netcdf`, позднее Dask | chunked/lazy dataset, координаты/атрибуты/единицы; не является произвольным «импортом любого HDF5» |
| GRDECL/EGRID | после модели 3D grid | `xtgeo` как optional adapter | сначала read-only corner-point grid и properties; экспорт только после unit/geometry/ACTNUM preflight |
| 3D | после SEG-Y/GIS/grid domain models | PyVista/VTK как optional UI-модуль | скважины, поверхности и ограниченные grid/seismic slices; level-of-detail и memory budget обязательны |
| SQL | принять для метаданных | сначала встроенный SQLite repository; SQLAlchemy 2 для будущего PostgreSQL | проекты, скважины, каталоги, provenance, задания и аудит; массивы остаются в chunked/object storage |
| RESCUE/Petrel | исследование, без обещания импорта | отдельный compatibility spike | только после публичного профиля формата, легальных fixtures и round-trip/loss matrix |
| Eclipse/CMG/tNavigator | экспорт после grid model | GRDECL/EGRID через адаптеры | отдельные экспортные профили и simulator-specific preflight; не считать один GRDECL универсально совместимым |

NoSQL в основной план не включён: текущие сущности, связи, версии и аудит естественно ложатся в
транзакционную SQL-модель. Object/chunk storage решает задачу больших массивов лучше, чем
хранение бинарных сейсмических трасс в документах NoSQL.

## Почему именно эти библиотеки

- [`dlisio`](https://dlisio.readthedocs.io/en/stable/) читает DLIS v1/RP66 и LIS79, но его
  документация прямо описывает неподдерживаемые варианты контейнеров. Поэтому первая версия
  обязана быть read-only и report-driven.
- [`segyio`](https://segyio.readthedocs.io/en/stable/segyio.html) предоставляет безопасный
  read-only режим, trace/header access и strict/non-strict geometry. Адаптер не должен открывать
  пользовательский файл в `r+` и не должен предполагать регулярную 3D-геометрию.
- [XTGeo](https://xtgeo.readthedocs.io/en/stable/datamodels.html) подтверждает import/export
  ASCII/binary GRDECL и EGRID, но у отдельных property-маршрутов есть ограничения. Это требует
  typed grid model и loss matrix до экспорта.
- [GDAL](https://gdal.org/en/stable/about.html) покрывает raster/vector formats; драйвер
  [GeoTIFF](https://gdal.org/en/stable/drivers/raster/gtiff.html) поддерживает BigTIFF. GDAL
  поставляется отдельно из-за native drivers и необходимости аудита лицензий конкретной сборки.
- [h5py](https://docs.h5py.org/en/stable/high/dataset.html) поддерживает chunked datasets,
  compression и выборочное чтение. [Xarray](https://docs.xarray.dev/en/stable/user-guide/dask.html)
  добавляет именованные измерения и lazy Dask arrays для данных больше памяти.
- [PyVista](https://docs.pyvista.org/user-guide/data_model.html) даёт VTK-модели geometry,
  topology и point/cell attributes, подходящие для скважин, поверхностей и corner-point grids.
- [`python-docx`](https://python-docx.readthedocs.io/en/latest/user/documents.html) умеет
  открывать и изменять шаблоны Word, включая стили, headers и footers.
- [SQLAlchemy 2](https://docs.sqlalchemy.org/en/20/) поддерживает SQLite и PostgreSQL через
  dialect boundary. В desktop-режиме сначала достаточно SQLite; серверная БД — отдельный режим.

## Архитектурные ограничения

1. Domain не импортирует `dlisio`, `segyio`, GDAL, XTGeo, HDF5, VTK или SQLAlchemy.
2. Каждый формат имеет `probe → inventory → mapping → validation → import/export report`.
3. Native и тяжёлые зависимости устанавливаются optional-группами, а отсутствие backend даёт
   понятную диагностику, не падение при запуске приложения.
4. Файлы размером больше памяти читаются окнами/chunks; проект хранит artifact reference,
   fingerprint, mapping и производные previews, а не обязательную полную копию в JSON.
5. Любой экспорт в simulator/GIS/SEG-Y получает preflight единиц, CRS, endian/revision,
   geometry и потерь. Исходный файл не открывается для изменения.
6. Тестовая матрица требует открытых fixtures, malformed/truncated cases, memory budget и
   повторного чтения созданного файла независимым валидатором, если он доступен.

## Порядок реализации

1. Общие `ExternalDatasetArtifact`, inventory/report и optional-backend diagnostics.
2. DLIS/LIS read-only adapter и frame/channel mapping в существующий multi-index Dataset.
3. GIS foundation: CRS model, well locations/trajectories, GeoPackage + GeoTIFF import/export.
4. Типизированная Report Model и DOCX renderer из версионированных шаблонов.
5. SEG-Y read-only adapter, trace-header inventory, windowed 2D viewer и cache policy.
6. Xarray/HDF5/NetCDF multidimensional store с chunk policy и memory benchmarks.
7. Grid domain model, GRDECL/EGRID import, затем PyVista 3D viewer.
8. Simulator export profiles; RESCUE/Petrel compatibility spike только после fixtures/spec audit.


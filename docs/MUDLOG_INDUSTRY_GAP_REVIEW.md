# Отраслевой gap-анализ Mud Logging / Surface Logging

Проверено 18 июля 2026 года по официальным материалам SLB, GEOLOG, Datalog,
Energistics и MainLog. Цель — определить функции продукта; названия коммерческих сервисов
не используются как обещание эквивалентности или совместимости.

## Источники

- [SLB Surface Logging](https://www.slb.com/products-and-services/innovating-in-oil-and-gas/well-construction/measurements/surface-logging)
- [SLB CLEAR wellbore risk reduction](https://www.slb.com/products-and-services/innovating-in-oil-and-gas/well-construction/measurements/surface-logging/clear-wellbore-risk-reduction-service)
- [SLB Defining Mud Logging](https://www.slb.com/resource-library/oilfield-review/defining-series/defining-mud-logging)
- [Datalog Mud Logging / WellWizard](https://www.datalogme.com/index.php/services/mud-logging/mud-logging-services)
- [GEOLOG GeoPressure case study](https://www.geolog.com/files/pdf/geopressure_case.pdf)
- [GEOLOG geoMPD](https://www.geolog.com/files/pdf/geolog_geoMPD_MS.pdf)
- [Energistics WITSML developers and users](https://energistics.org/witsml-developers-users)
- [Energistics WITSML MudLogReport](https://docs.energistics.org/WITSML/WITSML_TOPICS/WITSML-500-332-0-R-sv2000.html)
- [Energistics WITSML Log](https://docs.energistics.org/WITSML/WITSML_TOPICS/WITSML-000-048-0-C-sv2000.html)
- [MainLog features](https://mainlog.com/features/)

## Что уже покрыто

- multi-well project, LAS/CSV/Excel, несколько DEPTH/TIME индексов;
- редактирование кривых, provenance, Undo/Redo и project migrations;
- C1–C5/TG, gas ratios, Pixler, DEXP/DXС profiles и NCT;
- TIME↔DEPTH mapping и интервальная агрегация;
- литология, описания, Masterlog templates, symbols, PDF и Print Preview;
- настраиваемые linear/log tracks и базовая многотрековая визуализация.

## Критические пробелы

### P0 — фундамент достоверных данных

1. **Канонический словарь каналов и UOM.** Один параметр приходит под разными
   мнемониками и единицами. Нужны semantic channel kinds, dimension, conversion passport,
   sensor/source identity и запрет неявного смешивания.
2. **Acquisition/QC model.** Требуются sample timestamp, received timestamp, quality flags,
   stale/out-of-order/duplicate detection, gap report, calibration state и sensor health.
3. **Lag/depth correction.** Gas и cuttings относятся не к глубине регистрации на поверхности,
   а к рассчитанной lagged depth. Нужны pump strokes/annular volume/flow-based lag profiles,
   ручные контрольные точки и versioned correction provenance.
4. **Типизированные события и тревоги.** Connection/trip/background gas, kick/loss, drilling
   break, pumps on/off, bit/casing/formation top, sample/coring/show должны быть объектами,
   а не свободным текстом на картинке. Alarm rule обязан хранить threshold, hysteresis,
   debounce, acknowledgement, автора и аудит.
5. **Growing dataset.** Текущая модель ориентирована на законченный файл. Нужен append-only
   ingest с bounded buffer, backpressure, snapshot/checkpoint и воспроизводимым закрытием рейса.

### P1 — отраслевой MudLogReport

1. **WITSML 2.1 / ETP 1.2 профиль.** Energistics указывает WITSML 2.1 как актуальную версию
   для новой разработки. Первый этап должен быть offline XML/JSON inventory и mapping без
   секретов; сетевой ETP-клиент — после threat model, credential store и replay fixtures.
2. **MudLogReport domain.** Нужны интервальные cuttings/interpreted geology/show evaluation,
   chromatograph, gas peak, drilling parameters, Dxc/ECD/mud-density/ROP statistics,
   service company/personnel и ссылки на reports/logs.
3. **Gas peak и show evaluation.** Background/connection/trip gas, peak composition,
   fluorescence/cut, oil stain/odor, show quality, contact interpretation и collision-free
   annotations на Masterlog.
4. **Pore pressure / fracture gradient workflow.** Предбуровая модель, наблюдаемые Dxc/ECD,
   gas/background trends, mud weight, LOT/FIT, temperature/conductivity, cavings и uncertainty.
   Это decision-support с паспортом методики, не автоматический инженерный вердикт.
5. **Hydraulics и well-control trends.** Flow-in/out, pit volume, strokes, SPP, ECD, connection
   flowback baseline, deviations и совместный time/depth view.

### P2 — расширенная оценка пласта и операции

1. Масc-спектрометрия, расширенные hydrocarbons/inorganics и isotope channels.
2. Цифровые изображения шлама: scale, white/UV light, sample depth, chain of custody,
   неизменяемый оригинал и производные thumbnails/features.
3. Количественный cuttings flow/volume против теоретического выноса и hole-cleaning dashboard.
4. Multi-well real-time/historical offsets и correlation ties.
5. Event library с depth/time anchors и безопасными attachments вместо произвольных
   исполняемых документов.
6. Daily drilling/mudlog reports, смены персонала, approvals и revision history.

## Приоритет реализации

| Этап | Результат | Почему раньше остальных |
|---|---|---|
| 1 | Semantic Channel Dictionary + UOM/QC flags | без него WITS/WITSML и alarm rules недостоверны |
| 2 | Typed OperationalEvent/GasEvent/Show + audit | единая основа Masterlog, отчётов и тревог |
| 3 | Lag Correction Profile + preview/Undo | связывает surface gas/cuttings с пластом |
| 4 | Append/growing dataset и replay source | позволяет безопасно тестировать real-time без подключения к буровой |
| 5 | WITSML 2.1 offline inventory/MudLogReport mapping | стандартная модель обмена до сетевого транспорта |
| 6 | QC/alarm engine и trend dashboards | использует уже типизированные каналы и события |
| 7 | Secure ETP 1.2 client | только после credential/threat/reconnect/replay модели |
| 8 | Advanced cuttings/gas/pore-pressure modules | специализированные вычисления поверх надёжного ядра |

## Архитектурные ограничения

- Приложение не является сертифицированной well-control системой; alarm/pressure результаты
  сопровождаются источником, качеством и предупреждением о назначении.
- Сетевые учётные данные не входят в project JSON и логи.
- Raw acquisition остаётся append-only artifact; correction создаёт новую версию/mapping.
- Arrival time, measurement time и depth/time index не объединяются в одно поле.
- Любая автоматическая интерпретация показывает входы, методику, версию и uncertainty.
- WITSML/ETP реализуется изолированным адаптером; Domain не зависит от transport SDK.

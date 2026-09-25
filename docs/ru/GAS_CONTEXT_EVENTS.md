# Газовый контекст интерпретационных отчётов

## Назначение

`GasContextEvent` хранит подтверждённые или черновые интервалы газа известного происхождения
для Gas Ratio/Haworth, Pixler, OPUS и комбинированных газовых интерпретационных отчётов.
Модель не изменяет исходные LAS/GS2/WITS кривые и не подменяет измеренные C1–C5/TG.

## Повторяющиеся события

Один тип события может встречаться на скважине неограниченное число раз. Каждая запись имеет
собственный `event_id`, поэтому connection/build-up gas, СПО/trip, swab, gas-line test и другие
события сохраняются отдельными строками и не объединяются автоматически.

Поддерживаются: background, formation show, connection gas, trip gas, swab gas,
circulated gas, recycled gas, chromatograph test gas, gas-line test gas, lag-tracer gas,
calibration gas, elevated-unclassified и прочий технологический газ.

## Влияние на интерпретацию

`InterpretationImpact` имеет режимы:

- `exclude_geological` — исключить автоматическую геологическую классификацию;
- `technological_gas` — сохранить расчёты, но не назначать самостоятельный продуктивный пласт;
- `formation_gas` — учитывать как подтверждённый пластовый контекст;
- `review_required` — оставить решение на проверку геолога.

Gas-line/chromatograph/calibration/lag-tracer по умолчанию исключаются из геологической
классификации. Trip/swab/connection/circulated/recycled по умолчанию считаются технологическим
газом. Formation show по умолчанию имеет режим `formation_gas`.

## QC-значение

`reported_total_gas` и `reported_unit` — только ручной/внешний QC reference. Они не заменяют
измеренный Total Gas и не меняют исходные кривые.

## Хранение

События сохраняются на уровне скважины в `Well.gas_context_events`. Формат проекта v35
сохраняет их при Save/Reopen; проекты v34 и старше открываются с пустым списком событий.

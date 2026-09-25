# Gas context for interpretation reports

## Purpose

`GasContextEvent` stores confirmed or draft intervals of known gas origin for Gas Ratio/Haworth,
Pixler, OPUS and combined gas interpretation reports. The model never modifies source LAS/GS2/WITS
curves and never replaces measured C1–C5/TG values.

## Repeated events

The same event type may occur any number of times in a well. Every row has its own `event_id`,
so connection/build-up gas, trip gas, swab gas, gas-line tests and other events remain independent
records and are never merged automatically.

Supported event types include background, formation show, connection gas, trip gas, swab gas,
circulated gas, recycled gas, chromatograph test gas, gas-line test gas, lag-tracer gas,
calibration gas, elevated-unclassified and other technological gas.

## Interpretation impact

`InterpretationImpact` supports:

- `exclude_geological` — suppress automatic geological classification;
- `technological_gas` — preserve calculations without assigning a standalone productive interval;
- `formation_gas` — treat the context as confirmed formation gas;
- `review_required` — require geologist review.

Gas-line/chromatograph/calibration/lag-tracer events default to geological exclusion.
Trip/swab/connection/circulated/recycled events default to technological gas.
Formation show defaults to `formation_gas`.

## QC reference

`reported_total_gas` and `reported_unit` are operator/external QC references only. They do not
replace measured Total Gas and do not mutate source curves.

## Persistence

Events are stored at well level in `Well.gas_context_events`. Project format v35 preserves them
across Save/Reopen; v34 and older projects load with an empty event list.

# Версионированная lag/depth correction

Статус: реализовано в версии 0.7.44. Project format: v19. Lag correction schema: v1.

## Назначение

Коррекция связывает измерение на поверхности с расчётной глубиной поступления газа, шлама или
другого канала. Первичный acquisition dataset и append-only journal остаются неизменными. Каждая
коррекция материализуется как отдельный `DatasetKind.DERIVED` и хранит обе глубинные оси:

- source depth — исходная глубина регистрации;
- corrected depth — глубина после выбранного lag-профиля.

## Методы

- `constant_time`: постоянная задержка в секундах;
- `annular_volume_flow`: задержка `annular_volume_m3 / flow_rate_m3_per_s`;
- `pump_strokes`: задержка из объёма затрубья, подачи насоса и ходов в минуту;
- `control_points`: кусочно-линейная глубина по контрольным точкам `row → corrected depth`.

TIME-based методы требуют явный TIME и DEPTH index. Повторные временные значения разрешаются
только через выбранную `TimeDepthAggregationPolicy`. За диапазоном, где результат нельзя получить
без экстраполяции, corrected depth остаётся `NaN`.

## Версии и provenance

`LagCorrectionProfile` содержит непрерывные immutable revisions. Revision фиксирует метод,
параметры, индексы, curve IDs, aggregation policy, source row count, source SHA-256, output
SHA-256, acquisition sequence/audit digest, formula ID/version, UTC timestamp, автора и комментарий.
Новая revision создаёт новый output dataset; прежний результат не перезаписывается. Active revision
можно переключить с optimistic revision guard.

Source fingerprint подписывает использованный префикс строк, поэтому append-only рост исходника
разрешён, а изменение исторических значений или metadata обнаруживается. Codec при открытии
проекта пересобирает каждую derived projection и отклоняет divergence или tampering.

## Пользовательский сценарий

Откройте исходный dataset и выберите «Расчёты → Коррекция lag/depth...». В окне доступны:

1. профиль, назначение и набор кривых;
2. TIME/DEPTH indexes и метод расчёта;
3. новая revision с автором и комментарием;
4. preview source/corrected depth и lag;
5. активация прежней revision;
6. открытие derived dataset на source или corrected axis.

Выбранная ось становится active index derived dataset. `ReportDefinition` фиксирует этот index
явно, поэтому preview, экспорт и отчёт не переключают координату скрытно.

## Миграция

Project format v19 добавляет `well.lag_correction_profiles`. Миграция `v18 → v19` создаёт пустую
collection и не изменяет datasets, acquisition sessions, operational events или планшеты.

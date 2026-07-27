# GEOLOG GASRATIO@Pixler 0.7.75 — WITS0 Import Review и immutable AcquisitionDatasetSchema

## WITS0 Import Review

- Добавлен Qt-независимый `Wits0DiscoveryAccumulator`, который собирает все data fields `record/item`, типы, UOM, число корректных/NULL/error значений, диапазоны и ограниченные samples.
- Discovery snapshot immutable и детерминирован для live/replay. Его fingerprint описывает mapping surface, поэтому новые значения уже известных полей не делают подтверждённую схему устаревшей.
- Новый или изменённый `record/item`, inferred value kind/UOM либо впервые доступный header datetime меняет fingerprint и переводит schema в состояние stale.
- `Wits0ImportReviewController` отделяет draft, preview и atomic commit; raw bytes, parser output и проект в процессе проверки не изменяются.
- Диалог показывает все обнаруженные поля и блокирующие/предупреждающие QC findings.

## Semantic mapping, UOM и индекс

- Автоматическое предложение mapping использует существующий Semantic Channel Dictionary.
- Для каждого канала можно подтвердить или изменить canonical mnemonic, semantic kind, quantity class, source UOM и canonical UOM, а также исключить канал.
- Кандидаты active index формируются из WITS header date+time и подходящих numeric time/depth fields.
- Выбранное поле индекса не дублируется как кривая Dataset.
- Non-numeric channels, несовместимые quantity classes и требующийся численный UOM conversion блокируют commit.
- Неизвестные record/item сохраняются и доступны для ручного mapping вместо молчаливого удаления.

## Immutable schema и versioned custom profile

- Успешное подтверждение атомарно создаёт существующий immutable `AcquisitionDatasetSchema` с `AcquisitionIndexSchema`, `AcquisitionCurveSchema`, `CurveMetadata` и semantic provenance.
- Schema получает стабильный SHA-256 digest для аудита и последующей `AcquisitionSession`.
- Пользовательский mapping сохраняется отдельным JSON-файлом `<profile-id>.vN.json` через exclusive-create; встроенный `geoscape-gswits.json` не изменяется.
- Предыдущий профиль можно использовать как основу следующей ревизии; profile ID/version проверяются относительно base profile.
- Окно захвата получило команды **Проверка импорта…** и **Сбросить обнаружение**, количество каналов, состояние schema, digest и путь versioned profile.

## Ограничения и следующий этап

- Этап C не выполняет численное преобразование совместимых единиц; source и canonical UOM должны разрешаться в одну каноническую единицу.
- Подтверждение ещё не запускает `AcquisitionSession` и не добавляет строки в Dataset.
- Встроенный GeoScape mapping требует сверки с реальным обезличенным GSWITS raw-потоком.
- Следующий этап D: WITS frame → normalized measurement batch → append-only `AcquisitionSession` через `AcquisitionController`, checkpoints, bounded queue и backpressure.

## Совместимость

Project format остаётся `v20`, form schema — `v8`, tablet layout — `v18`; миграция проектов не требуется. Готовые и пользовательские формы, **Создать форму**, **Сохранить пользовательскую форму**, проверка совпадений и пробелов в имени, компактные колонки `50%`, `48` и `80`, **Ctrl+S** и повторное открытие сохранены без изменений.

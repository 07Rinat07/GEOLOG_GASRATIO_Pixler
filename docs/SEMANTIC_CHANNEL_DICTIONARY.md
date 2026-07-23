# Semantic Channel Dictionary

## Назначение

Словарь задаёт единый инженерный смысл каналов для LAS, CSV/TXT/Excel и
GeoScape/Paradox. Он не переименовывает исходные данные скрытно и не пытается угадать
неизвестную единицу. Результат сопоставления сохраняется вместе с кривой, чтобы проект
оставался воспроизводимым после обновления каталога.

## Источники правил

- `catalogs/sensors.py` и ресурсы Sensors — canonical mnemonic, vendor aliases, legacy
  `S/GID`, sensor ID, family, category и reference UOM;
- `services/uom_dictionary.py` — явные aliases единиц и их quantity class;
- `services/semantic_channels.py` — объединение признаков в стабильное определение и binding.

Каталог датчиков остаётся единственным источником vendor-алиасов. Семантический слой не
создаёт второй несогласованный список мнемоник.

## Снимок привязки кривой

`SemanticChannelBinding` содержит:

- `canonical_kind` и `canonical_mnemonic`;
- `quantity_class`;
- `canonical_uom` и исходный `source_uom`;
- aliases, `sensor_id`, source, family и category;
- точную исходную `source_mnemonic`;
- confidence, способ совпадения и evidence.

Binding является сериализуемым снимком решения, а не динамической ссылкой на текущую версию
каталога. Формат проекта v16 сохраняет его в метаданных кривой. При открытии legacy-проекта
binding восстанавливается, но уже сохранённая canonical mnemonic не перезаписывается.

## Политика единиц

`UomDictionary` нормализует только известные aliases. Каждая единица относится к quantity
class: length, time, pressure, volume fraction, flow rate, density, temperature и другим.
Неизвестная строка остаётся `unknown`; автоматическая конверсия и скрытое предположение
запрещены. Если мнемоника уверенно указывает на один физический тип, а source UOM — на другой,
confidence понижается и Import Review создаёт `channel-uom-conflict`.

## Интеграция

Semantic binding создаётся при импорте CSV/Excel, LAS и Paradox. Он сохраняется при:

- копировании и переносе кривых;
- merge datasets и external-LAS insert;
- развороте и ресэмплинге глубины;
- TIME↔DEPTH conversion и агрегации;
- JSON-экспорте dataset.

Curve Catalog сначала использует сохранённый binding и только затем legacy-эвристики.

## Import Review

`build_import_review(dataset)` создаёт детерминированную read-only модель:

- активный индекс, роль, тип, UOM и число строк;
- semantic binding каждого канала;
- число конечных и NULL-значений;
- unresolved channel, missing/unknown UOM, quantity conflict, all-null и duplicate canonical kind.

Функция не изменяет dataset. Интерактивное окно, ручные overrides и атомарное подтверждение
импорта являются следующим вертикальным срезом.

## Совместимость

- формат проекта: v16;
- layout: без изменений;
- исходные файлы: только чтение;
- неизвестные каналы: сохраняются без потери под `unknown.<mnemonic>`;
- изменение каталога не переписывает binding уже сохранённого проекта.

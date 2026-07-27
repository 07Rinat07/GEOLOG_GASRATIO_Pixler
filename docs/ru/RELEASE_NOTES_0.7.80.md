# GEOLOG GASRATIO@Pixler 0.7.80 — WITSML 1.4.1.1 SOAP только для чтения

## Клиент Store API только для чтения

Добавлен строгий SOAP 1.1-клиент устаревшего WITSML Store API для операций `WMLS_GetVersion`,
`WMLS_GetCap` и `WMLS_GetFromStore`. Операции изменения Store запрещены. Поддержана навигация
Well → Wellbore → Log → LogCurveInfo → LogData.

## Надёжность сети и аудит

Для каждого запроса настраиваются тайм-аут, ограниченные повторы с экспоненциальной задержкой,
лимит размера ответа и запрет DTD/entity. Аудит записывается в append-only JSONL с цепочкой SHA-256.
В аудит не попадают XML-запросы, пароли и заголовок Authorization.

## Credentials вне проекта

Профиль содержит только URL, имя пользователя, идентификатор credentials и открытые настройки.
В Windows пароль хранится в Windows Credential Manager. В Linux-среде разработки используется
непостоянное хранилище в памяти. Credentials не записываются в Dataset или файл проекта.

## Повторное использование Import Review

Полученный WITSML 1.4.1.1 LogData преобразуется в существующую immutable-модель ChannelSet. Затем
используются те же Semantic Channel Dictionary, UOM conversion, Import Review, Dataset digest и
атомарная регистрация проекта, что и для офлайн-импорта WITSML 2.x.

Параллельный Windows field reliability gate с реальным GSWITS остаётся открытым. Формат проекта —
v20, form schema — v8, tablet layout — v18.

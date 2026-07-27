# GEOLOG GASRATIO@Pixler 0.7.79 — импорт WITSML 2.x ChannelSet

Добавлено безопасное офлайн-чтение встроенных и относительных WITSML 2.x ChannelData arrays,
выбор ChannelSet, индекса и каналов, строгая UOM-нормализация, semantic Import Review и
детерминированный provenance Dataset. Полный immutable Dataset создаётся до изменения проекта, а
проверенный commit регистрируется один раз через атомарный project controller.

Строки с некорректным индексом остаются видимыми и могут быть явно исключены. Неподдерживаемые
типы массивов или UOM блокируют commit, а не интерпретируются предположительно. Сохранены XML/ZIP
лимиты, traversal protection, SHA-256 исходного XML/data и детерминированный digest Dataset.

Project format остаётся v20. Отдельный Windows reliability gate с реальным GSWITS всё ещё открыт и
выполняется параллельно; этот выпуск содержит checklist и существующие soak-инструменты.

# GEOLOG GASRATIO@Pixler 0.7.90

## Документация и запуск

Каноническая команда запуска — `python -m geoworkbench.app.main`. Она указана в корневом README,
русском, казахском и английском руководствах и в текущем тестовом gate. Устаревшие блоки старых
версий удалены из пользовательских README, а каталог документации теперь указывает на сборку
0.7.90.

## Тесты

Добавлен статический regression-тест module entry point, расширен documentation audit и обновлён
`docs/TESTING.md` с быстрым, полным и ручным Windows GUI-набором. Форматы project v21, form v9 и
tablet v19 не изменялись.

Штатный test runner теперь явно загружает `pytest_asyncio.plugin`, а отдельный headless runner выполняет все доступные тесты и не скрывает неизвестные collection-ошибки.

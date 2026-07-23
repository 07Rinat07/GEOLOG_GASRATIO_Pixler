# 0.7.43 — трёхсекундное приветственное окно

Тестовая сборка. Project format остаётся v18.

## Русский

- приветственное окно показывается не менее 3000 мс с момента фактического появления на экране;
- завершение инициализации больше не закрывает splash немедленно: оставшееся время выполняется через Qt-таймер без блокирующего `sleep`;
- если запуск занял более трёх секунд, дополнительная задержка не добавляется;
- после минимального времени сохраняется существующее плавное исчезновение длительностью 180 мс;
- добавлен Qt-независимый расчёт оставшейся задержки и headless-тесты граничных значений;
- project format, acquisition schema и сохранённые проекты не изменяются.

## Қазақша

- сәлемдесу терезесі экранда нақты пайда болған сәттен бастап кемінде 3000 мс көрсетіледі;
- инициализация аяқталғанда splash бірден жабылмайды: қалған уақыт блоктайтын `sleep` қолданбай Qt таймерімен орындалады;
- іске қосу үш секундтан ұзақ болса, қосымша кідіріс қосылмайды;
- ең аз көрсету уақытынан кейін бұрынғы 180 мс бірқалыпты өшу сақталады;
- қалған кідірісті есептейтін Qt-тәуелсіз функция және headless шекаралық тесттер қосылды;
- project format, acquisition schema және сақталған жобалар өзгермейді.

## English

- the welcome window remains visible for at least 3000 ms from its actual on-screen show event;
- startup completion no longer closes the splash immediately; the remaining time uses a Qt timer without blocking `sleep`;
- no extra delay is added when initialization already exceeds three seconds;
- the existing 180 ms fade-out runs after the minimum visibility period;
- added a Qt-independent remaining-delay helper with headless boundary tests;
- project format, acquisition schema, and saved projects are unchanged.

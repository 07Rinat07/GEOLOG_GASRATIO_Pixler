# План проекта

Актуально на 24 июля 2026 года. Исправляющий срез 0.7.49 сохраняет project format v20,
form schema v6 и tablet layout v16. После Windows-подтверждения следующий предметный этап —
read-only offline WITSML 2.1 inventory и mapping fixtures.

## P0 — hotfix 0.7.49: надёжная шкала и безопасные формы

- [x] устанавливать линейную шкалу по умолчанию для новых и автоматически созданных кривых;
- [x] включать scale/minimum/maximum в ключ рендера, чтобы ручной диапазон менял сам график;
- [x] применять корректный диапазон автоматически после debounce либо сразу по Enter;
- [x] сохранять оба поля диапазона при минимальной ширине графической колонки;
- [x] размещать unit и linear/logarithmic selector в отдельной адаптивной строке;
- [x] сохранять синхронизацию engineering ruler с major/minor divisions сетки;
- [x] рендерить новую форму до commit в project session;
- [x] восстанавливать последнюю рабочую форму, dirty marker и selection после ошибки;
- [x] откатывать live preview при отмене менеджера форм;
- [x] запрещать печать формы, которую не удалось безопасно применить;
- [x] покрыть render-before-commit, rollback и диапазон независимыми headless-тестами;
- [ ] выполнить Windows/PySide6/HiDPI smoke-test узких колонок, ручного диапазона и rollback.

Критерий 0.7.49: изменение minimum/maximum заметно перестраивает кривую; при сжатии колонки
оба предела остаются доступными; неудачное переключение или отмена preview не оставляет планшет
в частично изменённом состоянии.

## Следующие этапы

- [ ] read-only offline WITSML 2.1 inventory и mapping fixtures;
- [ ] alignment-controlled multi-dataset overlays в одной форме;
- [ ] directory watcher с preview-подтверждением ежедневного прироста;
- [ ] secured ETP 1.2 только после успешного fixture replay.

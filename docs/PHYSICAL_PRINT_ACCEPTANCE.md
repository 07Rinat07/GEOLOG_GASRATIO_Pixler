# Физическая приёмка печати REL-03 / CUT-03

Этот документ описывает только ручной Windows gate реального принтера. PDF, screenshot, virtual
printer и успешный GitHub Actions job не заменяют бумажный отпечаток. Пока сохранённый checklist
не содержит подтверждённый физический результат, `REL-03` и `CUT-03` остаются незавершёнными.

## Что печатается

`tools/windows_release_matrix.py` использует production `PrintJobExecutor` и последовательно
проверяет/печатает физические cases A4 portrait, A3 landscape, custom и roll. Для `CUT-03`
обязательны как минимум точные cases:

- `physical-a4-portrait-fit` — A4, portrait, Fit;
- `physical-a3-landscape-actual-size` — A3, landscape, 100%, включая continuation pages.

Acceptance sheet специально содержит длинный многоязычный текст `INTERPRETATION`, пользовательский
заголовок, границы интервала, цветные swatches и cuttings-style image. Это device/driver acceptance
fixture; оно не подменяет исходные данные проекта и не записывается в Dataset.

## Порядок оператора

1. Подключить реальный целевой принтер и убедиться, что его точное Windows-имя известно.
2. Запустить матрицу без финальных confirmation flags. Проверить, что physical gate не сообщает
   driver/layout error.
3. Забрать все листы A4/A3/custom/roll и визуально проверить каждый отпечаток.
4. Подтверждать критерий только если он выполнен на бумаге. Если хотя бы один критерий не выполнен,
   не использовать `--confirm-physical-output`; сохранить notes и дефект.
5. После успешной проверки повторить команду с полным набором confirmation flags и сохранить
   `windows-release-checklist.json`/`physical-printer-result.json` как release artifact вне Git.

Обязательные визуальные критерии:

- длинный rich-text `INTERPRETATION` полностью читаем и корректно переносится;
- cuttings-style photo/image присутствует и различима;
- пользовательский заголовок напечатан правильно;
- верхняя/нижняя границы интервала не потеряны и не обрезаны;
- цветовые элементы различимы на физическом носителе;
- реальные поля драйвера не обрезают обязательный контент;
- драйвер не показал предупреждение о бумаге, полях или принудительном масштабировании.

## Финальная команда

```powershell
python tools/windows_release_matrix.py `
  --scale-factor 1.0 `
  --platform windows `
  --output-dir build/ci-artifacts/windows-acceptance/physical `
  --printer "ТОЧНОЕ ИМЯ ПРИНТЕРА" `
  --operator "ФИО инженера" `
  --print-test `
  --confirm-rich-text `
  --confirm-cuttings-photo `
  --confirm-custom-heading `
  --confirm-interval-bounds `
  --confirm-color `
  --confirm-driver-margins `
  --confirm-no-driver-warning `
  --confirm-physical-output `
  --physical-notes "модель принтера, бумага/лоток, замечания" `
  --require-physical
```

`--confirm-physical-output` является финальным ручным утверждением и fail-closed требует все семь
структурированных признаков, `--printer`, `--operator` и фактический `--print-test`. Старый JSON с
одним `status: passed` больше не является достаточным evidence.

## Что считается блокирующим

Gate не закрывается при missing case, `gate_ok=false`, непропечатанной странице, неверной
ориентации A4/A3, недостаточном числе continuation pages, любом неполном visual evidence или
неуказанном операторе/принтере. В этих состояниях `overall_status` не может быть `passed`.

Физический checklist содержит generated evidence и не коммитится. В Git фиксируются только код
контракта, regression tests, этот операторский порядок и итоговый статус задачи после реальной
приёмки.

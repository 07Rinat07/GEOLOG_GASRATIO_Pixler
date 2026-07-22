# Windows release gate 0.7.27 — annotation deletion and form scope

## Mandatory annotation scenario

1. Open a project with a populated tablet and press F4.
2. Create one comment and one callout in form A.
3. Delete the comment from its right-click menu and confirm that it disappears immediately.
4. Undo, open the focused editor by double-clicking, use **Delete annotation**, then Undo again.
5. Delete through the full manager and through the Delete key.
6. Switch to form B for the same dataset: form-A objects must not be visible.
7. Return to form A: remaining objects must restore with the same text, position, size and style.
8. Add/remove/reorder a track inside form A: its annotations must remain visible.
9. Save the current tablet as a user form, reapply it and verify the same objects.
10. Compare screen, PDF and direct Masterlog output.

## Legacy migration

Open a project created before 0.7.27. Unscoped annotations must bind to the saved/current form once, remain editable and survive project save/reopen without appearing in another form.

## Release rule

Do not publish a stable package unless the scenario above passes on Windows 10/11 with PySide6 and pyqtgraph at 100%, 125% and 150% display scaling.

# Windows release gate 0.7.26 — typed Paradox batch plan

## Regression: `str` instead of `StrEnum`

1. Add D1174/D250 to the batch converter.
2. Select the configuration-required row and open manual DB configuration.
3. Choose depth and/or time, apply the plan to the batch operation, and retry.
4. The operation must not show `'str' object has no attribute 'value'`.
5. A successful row must provide a real LAS path and the generated file must reopen in the current LAS reader.
6. When the DB rows are spaced at 0.4 m, the LAS header must contain the actual 0.4 m step. A 0.2 m result is valid only after an explicit resampling command.

# Windows release gate 0.7.25 — batch configuration and black-tablet regression

## Batch DB → LAS

1. Add an ambiguous DB such as D250/D1174 and select depth and/or time export.
2. Start conversion. The result must be **Configuration required**, not a generic error.
3. Select the row and click **Configure selected DB…**.
4. Select the correct depth and time channels, then click **Apply to batch conversion**.
5. Accept the retry prompt. The LAS must be created in the shown output folder.
6. Open the generated LAS in the editor and verify row/column alignment.

## Tablet renderer

1. Open a populated tablet with no annotations. The graph body must remain visible and must not become black.
2. Toggle F4 several times. Curves and track backgrounds must remain visible.
3. Create a comment and a callout, drag them across tracks and resize them. Only the object areas may update.
4. Scroll and zoom depth/time; annotations must follow their anchors and remain below headers.
5. Delete all annotations. No invisible full-screen overlay may remain.
6. Compare screen, PDF preview and physical print.

This gate is mandatory on Windows 10/11 at 100%, 125% and 150% scaling.

# Windows release gate 0.7.24 — black-tablet regression

1. Open a project with populated PyQtGraph tracks; the graph body must contain curves and must not be a solid black rectangle.
2. Toggle F4 off/on five times; the graph body must remain visible.
3. Create a comment and a callout, move and resize them; only annotation regions may overlay the graphs.
4. Scroll and zoom depth/time; uncovered plot regions must remain visible.
5. Delete all annotations; the overlay native region must become empty and the plots must remain visible.
6. Repeat on Windows 10/11, light/dark theme, 100%, 125%, and 150% scaling.
7. Capture screenshots before F4, after F4, and with an annotation; reject the release if the plot body is predominantly black or empty.

# Проверка релиза 0.7.23

## Windows/HiDPI smoke-test ООП-маршрутизации

1. Открыть планшет и включить **F4**, не выбирая инструмент аннотации.
2. Щёлкнуть по кривой/газовой колонке: дорожка должна выделиться, а выбор кривой не должен блокироваться.
3. Дважды щёлкнуть по телу обычной кривой/газовой дорожки: должен открыться полный редактор колонки с добавлением/удалением параметров, настройкой кривых, единиц и масштаба.
4. Нажать правую кнопку по телу графика: должно открыться меню дорожки/параметров.
5. Выбрать **Комментарий**, **Выноска** или **Изображение** и щёлкнуть по нужной дорожке/глубине: объект должен создаться точно в точке щелчка.
6. Не снимая инструмент, щёлкнуть по существующей аннотации: должна выбираться существующая аннотация, а новая не создаётся.
7. Перемещать объект через несколько колонок и менять размер всеми угловыми/боковыми маркерами; планшет не должен мигать.
8. Во время drag выполнить Alt+Tab или вывести указатель за окно и отпустить кнопку: после возврата приложение не должно оставаться заблокированным.
9. Нажать Esc, затем снова выбрать/редактировать дорожку: редактор колонок должен работать без перезапуска.
10. Проверить двойной щелчок, F2, Enter, Delete и правое меню существующей аннотации.
11. Прокрутить/масштабировать глубину: аннотация должна следовать за привязкой и оставаться ниже шапок.
12. Сравнить экран, PDF и физическую печать.

## Пакетный DB → LAS

1. Добавить несколько `.db`, выбрать каталог результата и оставить маску `{source_name}_{mode}.las`.
2. Убедиться, что до запуска показан полный путь каждого будущего LAS.
3. Запустить конвертацию и проверить видимый прогресс/остановку.
4. После завершения выбрать успешную строку и нажать **Открыть LAS**.
5. Нажать **Открыть папку результата**, проверить фактическое наличие файлов.
6. Для ошибки проверить подробное сообщение и **Повторить ошибки**; для существующего результата — понятный статус пропуска.
7. Закрыть окно кнопкой **Закрыть** и системным крестиком.


## Windows smoke-test 0.7.21 — отсутствие мерцания

1. Включить F4 и создать комментарий и выноску.
2. Непрерывно перемещать каждый объект 10–15 секунд через несколько дорожек.
3. Изменить размер всеми угловыми и боковыми маркерами.
4. Убедиться, что кривые, шапки и фон планшета не исчезают и не вспыхивают.
5. Один раз щёлкнуть выбранный объект без перемещения: проект не должен получать новую Undo-команду.
6. После одного перемещения выполнить Undo: должен отмениться весь жест, а не отдельные пиксели.
7. Повторить при масштабе Windows 100%, 125%, 150% и на HiDPI-мониторе.
8. Проверить PDF и печать: экранные маркеры выбора не выводятся.

# Проверка версии 0.7.19

## Автоматическая проверка в текущей среде

```text
python -m compileall -q src tests                         PASS
focused non-GUI regression suite                         188 passed
RU/KK/EN key and placeholder parity                      PASS
JSON resources                                           PASS
BLData/D250 read and analysis                            PASS
source DB/PX/TV/FAM SHA-256 immutability                 PASS
```

## Обязательный Windows smoke-test аннотаций

1. Открыть глубинный планшет и нажать F4.
2. Создать комментарий и выноску кнопками панели.
3. Один раз щёлкнуть объект: должны появиться восемь маркеров.
4. Перетащить блок через две соседние колонки; точка выноски должна остаться на выбранной глубине/кривой.
5. Не меняя объект, прокрутить глубину колёсиком и вертикальной полосой: точка и блок должны перемещаться вместе с 119,0 м; при уходе 119,0 м из диапазона объект должен исчезнуть с экрана.
6. Выполнить увеличение/уменьшение масштаба и переход к другой глубине; смещение блока относительно точки привязки должно сохраниться.
7. Изменить ширину боковым маркером и одновременно ширину/высоту угловым.
8. Повторно открыть редактор двойным щелчком, F2/Enter и кнопкой «Редактировать выбранное».
9. Проверить правую кнопку, Delete и кнопку удаления.
10. Сохранить проект, закрыть и открыть его повторно; геометрия должна сохраниться.
11. Повторить на временном планшете.
12. Сравнить экран, PDF preview и физическую печать; служебная рамка/маркеры печататься не должны.
13. Убедиться, что аннотации отсутствуют в дереве проекта и доступны через менеджер «Все…».

## Обязательный Windows smoke-test DB → LAS

1. Открыть `BLData.db` через импорт GeoScape/Paradox.
2. Во время чтения проверить обновление этапа, процента, счётчика и времени; окно и главное приложение должны перемещаться и перерисовываться.
3. Нажать системный крестик или «Отмена» во время чтения; дождаться безопасного закрытия без изменения источника.
4. Открыть файл снова и дождаться предпросмотра; нижние кнопки должны быть видимы при разрешении около 1004×688.
5. Переключать глубину/время и вкладки без длительного зависания.
6. Нажать «Открыть в редакторе», затем повторить с «Сохранить LAS».
7. Проверить, что этап 6 доходит до 100%, LAS открывается текущим reader и колонки не смещены.
8. Повторить для `D250.db`; неоднозначные кандидаты глубины должны требовать подтверждения.

В контейнере нет PySide6, pyqtgraph и lasio, поэтому эти интерактивные пункты здесь не выполнялись.

## Windows smoke-test 0.7.20 — время и прямые аннотации

1. Открыть `BLData.db` и построить глубинный планшет.
2. Включить курсор и проверить, что `TIME` отображается как `ДД.ММ.ГГГГ ЧЧ:ММ:СС`, а не как `7648.2 S`.
3. Проверить то же значение в LAS-таблице, отдельном графике и предварительном просмотре Paradox.
4. Включить F4, выбрать «Комментарий» и щёлкнуть в середине конкретной дорожки: объект должен появиться сразу без предварительного диалога.
5. Перетащить объект через соседние дорожки, изменить размер каждым угловым и боковым маркером.
6. Перетащить объект к верхней границе: рамка, текст и линия не должны отображаться поверх шапки и подписей параметров.
7. Привязать выноску к кривой, прокрутить и масштабировать глубину: объект должен следовать за точкой данных и скрываться, когда точка выходит из видимого диапазона.
8. Открыть редактирование двойным щелчком, F2, Enter, кнопкой панели и контекстным меню.
9. Сохранить проект, закрыть и открыть: текст, геометрия, привязка и оформление должны сохраниться.
10. Сравнить экран, PDF и физическую печать: шапка не перекрыта, служебные маркеры выбора отсутствуют.

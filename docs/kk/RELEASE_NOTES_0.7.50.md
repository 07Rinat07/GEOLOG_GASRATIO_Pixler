# GEOLOG GASRATIO@Pixler 0.7.50 — пішіндерді қауіпсіз ауыстыру

Шкаланы өңдегеннен кейін жұмыс пішінін ауыстырғанда пайда болуы мүмкін маңызды PySide6
`Internal C++ object (CurveHeaderEditor) already deleted` қатесі түзетілді.

## Өзгерістер

- `CurveHeaderEditor.dispose()` виджет жойылмай тұрып кейінге қалдырылған range commit-ті тоқтатады;
- minimum/maximum, unit, scale және action controls disposal кезінде сигналдарды бұғаттайды;
- `TabletTrackWidget` `deleteLater` алдында editor-лар мен event filter-лерді тоқтатады;
- `TabletView` nested layout rebuild-ке жол бермейтін guard алды;
- MainWindow form transaction кезінде stale header events-ті елемейді;
- rollback ескі Qt объектілерін қолданбай, модельдің fresh deepcopy көшірмесінен қайта құрады;
- Form Manager бір сәтсіз apply үшін екі рет қалпына келтіруді орындамайды;
- preview-дан кейін Cancel бастапқы пішінді бөлек және бір рет қалпына келтіреді.

## Үйлесімділік

Package **0.7.50**; project format **v20**; form schema **v6**; tablet layout **v16**.
Migration қажет емес.

## Тексеру

Focused lifecycle/form/layout: **171 passed**. Қолжетімді headless regression:
**1044 passed, 4 skipped, 4 deselected**. `compileall` сәтті. Qt lifecycle үшін соңғы
Windows/PySide6 smoke-test қажет.

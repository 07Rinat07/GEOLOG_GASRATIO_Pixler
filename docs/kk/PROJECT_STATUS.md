# Жоба күйі

2026 жылғы 24 шілдедегі толық түзету жинағы: package **0.7.58**, project format **v20**, form schema **v6**, tablet layout **v16**.

## 0.7.58 нұсқасында аяқталды

- өзгеріс толық 0.7.56 жоба ағашына тікелей қайта енгізілді;
- аралық статистика әрқашан floating overlay және планшет енін азайтпайды;
- геометрия көп мониторлы координаталарды қоса белсенді мониторда шектеледі;
- overlay негізгі терезенің move/resize оқиғаларын орындайды;
- жабу, Тазарту, пішін және dataset ауыстыру ескі белгілеуді жояды;
- A4 бақылауы, сақталатын пішіндер, diagnostics және бұрынғы түзетулер сақталды;
- үш геометриялық және төрт integration contract тесті қосылды.

## Тексеру

Focused overlay жинағы: **27 passed**. Қолжетімді headless regression: **1048 passed, 4 skipped**. `src` және `tests` үшін `compileall` орындалды. Толық визуалды smoke-test Windows/PySide6/pyqtgraph ортасын қажет етеді.

## Келесі тік срез

Read-only offline WITSML 2.1 inventory және mapping fixtures.

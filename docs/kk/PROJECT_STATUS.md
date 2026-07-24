# Жоба күйі

2026 жылғы 24 шілде: package **0.7.55**, project format **v20**, form schema **v6**, tablet layout **v16**.

## 0.7.55 нұсқасында аяқталды

- барлық тереңдік графиктерінің басталуын туралау үшін ортақ тақырып жолағы сақталды;
- әр баған параметрлері жоғарғы шеттен аралықсыз орналастырылады;
- артық синхрондалған биіктік соңғы жолдан кейінгі stretch бөлігіне беріледі;
- параметрлері көп бағандар үшін айналдыру сақталды;
- конструктордағы `opened_from_projection` NameError жойылды;
- top-packed тақырыптарға Qt және статикалық regression-келісімшарттар қосылды.

## Тексеру

Focused header/form/constructor жиыны: **86 passed**. Қолжетімді headless regression: **1064 passed, 4 skipped, 4 deselected**. `compileall` сәтті. Windows/PySide6 визуалды smoke-test әртүрлі форма мен DPI үшін міндетті.

## Келесі тік кесінді

Read-only offline WITSML 2.1 inventory және mapping fixtures.

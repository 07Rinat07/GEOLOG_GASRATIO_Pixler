# Жоба күйі

2026 жылғы 24 шілде: package **0.7.59**, project format **v20**, form schema **v6**, tablet layout **v16**.

## 0.7.59 нұсқасында аяқталды

- diagnostics traceback бойынша `_localizer` өрісі жоқ `TabletTrackWidget` қатесі түзетілді;
- әр rendered track тақырып жасалғанға дейін `TabletView` белсенді localizer-ін алады;
- тікелей/plugin арқылы жасалған track қауіпсіз орысша fallback-localizer қолданады;
- алтыдан көп параметрі бар тығыз пішіндер localized scroll hint жасағанда енді құламайды;
- транзакциялық rollback соңғы жұмыс істейтін layout-ты сақтайды;
- source-contract және Qt regression тесттері қосылды.

## Тексеру

Контейнерде `compileall` және қолжетімді pure/source-contract тесттері орындалды. Windows/PySide6 smoke-test міндетті: RU/KK/EN тілдерінде бір бағанда 7–12 параметрі бар пішіндерді бірнеше рет ауыстыру.

## Келесі тік кесінді

Read-only offline WITSML 2.1 inventory және mapping fixtures.

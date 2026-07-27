# GEOLOG GASRATIO@Pixler 0.7.90

## Құжаттама және іске қосу

Негізгі іске қосу командасы — `python -m geoworkbench.app.main`. Ол түбірлік README, орысша,
қазақша және ағылшынша нұсқаулықтарда және ағымдағы test gate ішінде бірдей көрсетілген. Ескі
нұсқалардың бастапқы блоктары пайдаланушы README файлдарынан алынып тасталды, ал құжаттама
каталогы енді 0.7.90 жинағын көрсетеді.

## Тесттер

Module entry point үшін static regression-тест қосылды, documentation audit кеңейтілді және
`docs/TESTING.md` quick, full және Windows GUI тексерулерімен жаңартылды. Project v21, form v9 және
tablet v19 форматтары өзгерген жоқ.

Негізгі test runner енді `pytest_asyncio.plugin` модулін анық жүктейді, ал жеке headless runner барлық қолжетімді тесттерді орындайды және белгісіз collection қателерін жасырмайды.

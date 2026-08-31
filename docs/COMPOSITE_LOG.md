# Заводская форма Composite Log

В приложении доступны две редактируемые после применения формы: A4 книжная и
A4 альбомная. Они локализованы на русском, казахском и английском языках.

Базовая компоновка соответствует распространённой последовательности
открытого ствола: корреляция и состояние ствола (GR, SP, CALI, BS), три кривые
удельного сопротивления, плотностной–нейтронный комплекс, акустический каротаж,
литология, стратиграфия и описание пород.

Начальные масштабы служат безопасной заводской отправной точкой и остаются
редактируемыми:

- GR: 0–200 gAPI; SP: −100–100 mV; CALI и BS: 6–16 in;
- ILD, ILM, MSFL: логарифмический 0,2–2000 ohm·m;
- RHOB: 1,95–2,95 g/cm³; NPHI: −15–45 %; PEF: 0–10 b/e;
- DRHO: −0,25–0,25 g/cm³; DT: 40–140 µs/ft.

Параметры и масштабы выбраны по официальным материалам SLB и опубликованным
примерам USGS. Они не заменяют масштаб, заданный заголовком конкретного LAS:
после привязки данных геолог может изменить пределы каждой кривой в редакторе
формы или дорожки.

Источники:

- SLB, Basic Well Log Interpretation:
  https://www.slb.com/zh-cn/resource-library/oilfield-review/defining-series/defining-log-interpretation
- SLB Energy Glossary, Resistivity log:
  https://glossary.slb.com/en/terms/r/resistivity_log
- USGS North Kalikpik No. 1 LAS curve inventory:
  https://pubs.usgs.gov/of/1999/ofr-99-0015/Wells/NKalik1/LAS/NK1LAS.htm
- USGS example composite-log scales:
  https://pubs.usgs.gov/dds/0069-B/ch15_plate-4.pdf

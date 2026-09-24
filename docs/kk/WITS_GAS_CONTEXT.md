# WITS / ГТИ газ оқиғасының контексті

## Мақсаты

Жоғары Total Gas өздігінен көмірсутек қабатын дәлелдемейді. Интерпретатор геологиялық сигналды
операциялық және QC оқиғаларынан бөлуі тиіс. Газдың шығу контексті Haworth/Pixler бойынша fluid
screening-тан бөлек сақталады.

## Негізгі кластар

- **Фондық газ (BGG)** — тұрақты бұрғылау кезіндегі baseline.
- **Қабаттық газ көрінісі** — connection/trip/test/calibration оқиғалары алып тасталғаннан кейін
  stable drilling контекстінде robust background-тан сенімді жоғарылау.
- **Connection gas** — насос тоқтап, құбыр жалғанғаннан кейін шамамен бір lag өткен соң бетте
  байқалатын қысқа газ шыңы.
- **Trip gas** — СПО/циркуляция тоқтауы кезінде жиналып, циркуляция қайта басталғанда шығатын газ.
- **Circulated/recycled gas** — циркуляциямен немесе қалдық газдың қайта айналуымен байланысты газ.
- **Хроматограф test/calibration gas** — анализаторға берілетін белгілі test mixture; formation show емес.
- **ГТИ газ желісінің тесті** — sample line/extraction path тексеруге берілетін газ; геологиялық
  интерпретациядан шығарылады.
- **Lag tracer/carbide test** — lag тексеруге әдейі енгізілген трассер.
- **Elevated-unclassified** — газ жоғары, бірақ шығу себебі сенімді анықталмаған.

## Автоматика және оператор растауы

Гибридтік тәсіл қолданылады. Автоматика pump/SPM/flow, ROP, bit depth, block position,
on/off-bottom, drilling activity, connection/trip events және lag model деректерін пайдаланады.

Оператор event kind, axis (depth немесе elapsed time), start/end, optional value/unit, comment және
confirmed күйі бар қолмен интервал енгізе алады. Қолмен расталған QC/test интервалы automatic
formation-show шешімінен жоғары басымдықта болады.

## Lag және тереңдікке байлау

Surface detection және lag-corrected bit depth бөлек сақталады. Есеп surface time/depth,
lag estimate, corrected bit depth және lag source көрсетуі тиіс. Valid lag болмаса, бетте өлшенген
газ нақты қабатқа сенімді түрде байланбайды.

## Дереккөздер

SLB Energy Glossary; SLB Oilfield Review *Defining Mud Logging*; GEOLOG Surface Logging
specifications; AAPG Wiki *Mudlogging: gas extraction and monitoring*.

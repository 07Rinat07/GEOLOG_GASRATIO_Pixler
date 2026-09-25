# Интерпретациялық есептерге арналған газ контексті

## Мақсаты

`GasContextEvent` Gas Ratio/Haworth, Pixler, OPUS және біріктірілген газ интерпретациялық
есептері үшін шығу тегі белгілі газ аралықтарын сақтайды. Модель LAS/GS2/WITS бастапқы
қисықтарын өзгертпейді және өлшенген C1–C5/TG мәндерін алмастырмайды.

## Қайталанатын оқиғалар

Бір оқиға түрі ұңғымада шексіз рет қайталана алады. Әр жолдың жеке `event_id` идентификаторы
бар, сондықтан connection/build-up gas, СПО/trip, swab, gas-line test және басқа оқиғалар жеке
жазба болып қалады және автоматты түрде біріктірілмейді.

Қолдау көрсетілетін түрлер: background, formation show, connection gas, trip gas, swab gas,
circulated gas, recycled gas, chromatograph test gas, gas-line test gas, lag-tracer gas,
calibration gas, elevated-unclassified және басқа технологиялық газ.

## Интерпретацияға әсері

`InterpretationImpact` режимдері:

- `exclude_geological` — автоматты геологиялық жіктеуді алып тастау;
- `technological_gas` — есептерді сақтау, бірақ жеке өнімді қабат тағайындамау;
- `formation_gas` — расталған қабаттық газ ретінде есептеу;
- `review_required` — геолог тексеруін талап ету.

Gas-line/chromatograph/calibration/lag-tracer әдепкіде геологиялық интерпретациядан алынады.
Trip/swab/connection/circulated/recycled әдепкіде технологиялық газ болып саналады.
Formation show үшін әдепкі режим — `formation_gas`.

## QC мәні

`reported_total_gas` және `reported_unit` тек операторлық/сыртқы QC reference болып табылады.
Олар өлшенген Total Gas мәнін алмастырмайды және бастапқы қисықтарды өзгертпейді.

## Сақтау

Оқиғалар `Well.gas_context_events` ішінде ұңғыма деңгейінде сақталады. Project format v35
Save/Reopen кезінде оларды сақтайды; v34 және ескі жобалар бос оқиға тізімімен ашылады.
## Есептеу алдындағы өңдегіш

Интерпретация жұмыс кеңістігінде өңдегіш **есептеу алдында** жеке қадам ретінде ашылады.
Қайталанатын жолдар кестесі Add/Update/Duplicate/Delete әрекеттерін қолдайды. Әр жолда газ түрі,
жоғарғы/төменгі тереңдік, міндетті емес TG/QC reference және оның бірлігі, confirmed/draft күйі,
нақты `InterpretationImpact` және түсініктеме өңделеді.

Өңдеу транзакциялық: барлық әрекет `GasContextRegistry` жұмыс көшірмесінде орындалады.
**Сақтау** `Well.gas_context_events` тізімін атомарлы түрде ауыстырып, project session-ды
өзгертілген деп белгілейді; **Бас тарту** жобаны өзгертпейді. Бастапқы қисықтар өзгертілмейді.

Бұл инкремент оператор registry-сін жасайды және сақтайды. Confirmed оқиғаларын
Gas Ratio/Haworth/Pixler/OPUS candidate classification-ға қолдану және бірдей effective
context-ті preview/PDF/XLSX/DOCX ішінде көрсету келесі жеке инкрементте орындалады.

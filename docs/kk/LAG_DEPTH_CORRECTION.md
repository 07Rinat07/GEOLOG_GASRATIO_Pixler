# Нұсқаланатын lag/depth түзетуі

Күйі: 0.7.44 нұсқасында іске асырылды. Project format v19 ішінде енгізілді; ағымдағы project
format v20. Lag correction schema: v1.

## Мақсаты

Түзету жерүсті өлшемін газдың, шламның немесе басқа арнаның есептелген келу тереңдігімен
байланыстырады. Бастапқы acquisition dataset пен append-only journal өзгермейді. Әр түзету бөлек
`DatasetKind.DERIVED` ретінде жасалып, екі осьті сақтайды:

- **source depth** — бастапқы тіркеу тереңдігі;
- **corrected depth** — таңдалған lag профилінен кейінгі тереңдік.

## Есептеу әдістері

- `constant_time` — секундпен тұрақты кідіріс;
- `annular_volume_flow` — `annular_volume_m3 / flow_rate_m3_per_s` кідірісі;
- `pump_strokes` — затруб көлемі, сорғы беруі және минуттағы жүрістер бойынша есептеу;
- `control_points` — `row → corrected depth` бөліктік-сызықтық тәуелділігі.

TIME әдістері нақты TIME және DEPTH indexes талап етеді. Қайталанатын уақыт мәндері тек таңдалған
`TimeDepthAggregationPolicy` арқылы өңделеді. Сенімді интерполяция ауқымынан тыс corrected depth
`NaN` болып қалады; жасырын экстраполяция орындалмайды.

## Нұсқалар және provenance

`LagCorrectionProfile` реттелген immutable revisions сақтайды. Әр revision әдісті, параметрлерді,
индекстерді, curve IDs, aggregation policy, бастапқы жол санын, source/output SHA-256,
acquisition sequence/audit digest, formula ID/version, UTC уақытын, автор мен түсіндірмені
жазады. Жаңа revision жаңа output dataset жасайды және бұрынғы нәтижені қайта жазбайды.

Source fingerprint қолданылған тарихи жолдар префиксін қорғайды. Append-only дереккөзге жаңа
жолдар қосуға болады, бірақ тарихи мәндер, metadata немесе materialized output өзгерсе, жоба
жүктелгенде анықталады.

## Пайдаланушы сценарийі

1. Бастапқы dataset-ті таңдаңыз.
2. **Есептеулер → Lag/depth түзетуі...** командасын ашыңыз.
3. Профиль мен арналардың мақсатын таңдаңыз немесе жасаңыз.
4. TIME/DEPTH indexes және есептеу әдісін көрсетіңіз.
5. Әдіс параметрлерін, авторды және жаңа revision түсіндірмесін толтырыңыз.
6. Source depth, corrected depth және lag preview-ын тексеріңіз.
7. Revision жасап, қажет болса оны белсенді етіңіз.
8. Derived dataset-ті бастапқы немесе түзетілген осьпен ашыңыз.

`ReportDefinition` таңдалған index-ті нақты сақтайды, сондықтан preview, экспорт және есеп осьті
жасырын түрде ауыстырмайды.

## Сақтау, кері қайтару және қайта ашу

Профиль мен revisions жобаның бөлігі. Revision жасағаннан немесе ауыстырғаннан кейін **Ctrl+S**
басыңыз. Сақтамай жабу ағымдағы сеанс өзгерістерін жояды. Бақылау үшін жобаны қайта ашып,
белсенді revision, таңдалған ось, source/output fingerprints және derived dataset-ті тексеріңіз.
Ескі revision-ды белсенді ету жаңа revisions-ды жоймайды.

## Шектеулер және тексеру

- бастапқы acquisition dataset өзгермеуі тиіс;
- жасырын өлшем бірлігі немесе экстраполяция қолданылмайды;
- TIME/DEPTH, қайталанулар және диапазон ескертулері revision жасалғанға дейін түзетіледі;
- есеп пен экспорт нақты таңдалған осьті пайдалануы тиіс;
- жұмысқа енгізер алдында бірнеше бақылау тереңдігін қолмен есеппен салыстырыңыз.

## Миграция

Project format v19 `well.lag_correction_profiles` collection-ын қосады. `v18 → v19` migration
бос collection жасайды және datasets, acquisition sessions, operational events немесе планшеттерді
өзгертпейді.

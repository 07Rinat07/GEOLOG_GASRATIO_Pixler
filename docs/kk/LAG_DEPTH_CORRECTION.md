# Нұсқаланатын lag/depth түзетуі

Күйі: 0.7.44 нұсқасында іске асырылды. Project format v19 ішінде енгізілді; ағымдағы project format: v20. Lag correction schema: v1.

Түзету жерүсті өлшемін есептелген келу тереңдігімен байланыстырады және жазылған acquisition
dataset пен append-only journal-ды өзгертпейді. Әр immutable профиль ревизиясы бастапқы және
түзетілген тереңдік осьтері бар бөлек derived dataset жасайды.

Тұрақты уақыт, сақиналы көлем/шығын, сорғы беруі/жүрістері және қолмен берілетін row-to-depth
бақылау нүктелері қолдау табады. TIME әдістері нақты TIME және DEPTH index пен қайталанатын уақыт
мәндерінің aggregation policy таңдауын талап етеді. Интерполяция ауқымынан тыс нәтиже `NaN`
болып қалады; жасырын экстраполяция жоқ.

Ревизия параметрлерді, индекстерді, curve IDs, source row count/fingerprint, output digest,
acquisition sequence/audit provenance, formula ID/version, UTC уақытын, автор мен түсіндірмені
сақтайды. Жаңа ревизия жаңа output dataset жасайды. Source-қа жаңа жол қосуға болады, бірақ
тарихи префикс немесе материалданған output өзгерсе, жоба жүктелмейді.

«Есептеулер → Lag/depth түзетуі...» терезесі профиль жасауға, жаңа ревизия қосуға, preview көруге,
ескі ревизияны белсендіруге және derived dataset-ті бастапқы не түзетілген осьпен ашуға мүмкіндік
береді. `ReportDefinition` таңдалған index-ті нақты сақтайды.

Project format v19 `well.lag_correction_profiles` collection-ын қосады; `v18 → v19` migration бар
жоба деректерін өзгертпей бос collection жасайды.

# 0.7.39 шығарылым ескертпелері — есеп output транзакциясы

- output және Report Passport бір recoverable filesystem transaction арқылы бекітіледі;
- дайын файл Passport schema v4 ішінде SHA-256, byte size, MIME type және safe basename сақтайды;
- аяқталмаған commit rollback жасайды, committed операция тек cleanup-ты аяқтайды;
- overwrite кезінде артық continuation pages транзакция ішінде жойылады;
- Print Center, direct PNG/SVG/PDF, CSV/XLSX, Masterlog және interpretation PDF ортақ service қолданады;
- `tools/recover_report_transactions.py` қосылды;
- project format v16 болып қалады.

Тексеру: 37 focused tests; қолжетімді regression: 915 passed, 4 skipped, 3 LAS tests deselected.

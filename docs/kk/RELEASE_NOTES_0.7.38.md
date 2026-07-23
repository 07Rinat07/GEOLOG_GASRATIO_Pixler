# 0.7.38 шығарылым ескертпелері — ортақ баспа моделі

- A4/A3/custom/roll бір physical model қолданады;
- Fit және 100% continuation беттері қосылды;
- preview, PDF, файлдар және printer бір `PrintDocumentPlan` қолданады;
- system dialog таңдаған page range gate ішінде ескеріледі;
- printer gate device, media, size, margins, printable area және DPI тексереді;
- `tools/physical_print_gate.py` тек explicit `--print-test` кезінде басады;
- Report Passport schema v3 қолданады; project format v16 болып қалады.

Толығырақ: [Баспа пішімдері мен масштабы](PRINT_MEDIA_MODEL.md).

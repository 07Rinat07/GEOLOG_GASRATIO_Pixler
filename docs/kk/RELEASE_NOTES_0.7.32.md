# 0.7.32 шығарылым ескертпелері — Semantic Channel Dictionary

## Өзгерістер

- қолданыстағы Sensors catalog үстіне ортақ `SemanticChannelDictionary` және `UomDictionary`
  қосылды;
- әр импортталған curve canonical kind, quantity class, UOM, aliases, sensor/source, бастапқы
  mnemonic, confidence және evidence бар сериализацияланатын binding алады;
- CSV/Excel, LAS және Paradox бір resolver пайдаланады;
- белгісіз vendor channels және UOM анық күйде қалады және болжанбайды;
- UOM quantity conflict confidence мәнін төмендетіп, review қатесі ретінде көрсетіледі;
- binding copy, transfer, merge, reverse/resample және TIME↔DEPTH кезінде сақталады;
- index, NULL, unresolved, UOM және duplicate canonical kind үшін read-only headless Import
  Review model қосылды;
- project format v16-ға көтеріліп, v15 → v16 қауіпсіз migration қосылды.

## Үйлесімділік

Ескі жобалар дерек жоғалтпай ашылады. Binding жоқ legacy curve оқылғанда байытылады, бірақ
сақталған canonical mnemonic ауыстырылмайды. Бастапқы LAS/DB өзгертілмейді; layout пен
пайдаланушы сценарийлері өзгерген жоқ.

## Тексеру

707 қолжетімді тест өтті, 4 платформалық сценарий өткізіліп жіберілді; `compileall` және 0.7.32
wheel жинағы қатесіз аяқталды. Толық Qt/LAS pytest, Ruff, mypy және
Windows/HiDPI/PDF/physical-print gate орнатылған ортада қайталануы тиіс.

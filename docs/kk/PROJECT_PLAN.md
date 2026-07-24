# Жоба жоспары

2026 жылғы 24 шілдедегі күй. Package 0.7.48 project format v20-ны сақтап, tablet layout-ты
v16-ға көтереді. Windows тексерісінен кейін келесі срез — offline WITSML 2.1 inventory.

## 0.7.48 түзету hotfix аяқталды

- [x] шкала шеттерінде контрастты minimum/maximum өрістерін көрсету;
- [x] баған ені бойынша major/minor ticks бар толық инженерлік шкала салу;
- [x] нақты баған торында сақталған divisions мәндерін қолдану;
- [x] linear және logarithmic scale жазуларын бөлек интерполяциялау;
- [x] екі шекті `✓` не Enter алдында бірге дайындау;
- [x] display unit және scale type-ты тақырыпта тікелей өңдеу;
- [x] unit override кезінде сандық мәндерді қайта есептемеу;
- [x] unit/range/scale/colors параметрлерін layout және user form ішінде сақтау;
- [x] tablet layout v15 → v16 (`unit_override = null`) көшіру;
- [ ] кең және тар бағандарға Windows/PySide6/HiDPI smoke-test орындау.

## 0.7.47 түзету hotfix аяқталды

- [x] DB mixed index ретін тек қабылданған көшірмеде сұрыптау;
- [x] барлық индекс пен қисыққа бір тұрақты перестановка қолдану;
- [x] `index-sorted-copy` диагностикасын көрсету;
- [x] batch DB → LAS үшін DEPT/DEPTH/MD-ны басым таңдап, ambiguity safety сақтау;
- [x] сақталған профильді қолданып, LAS round-trip алдында сұрыптау;
- [x] ordinary curve тақырыбында manual min/max өңдеу;
- [x] auto/manual range және тақырып түстерін жұмыс пішінінде сақтау;
- [ ] D1174.db, BLData.db, batch conversion және тар тақырыптарды Windows-та тексеру.

## Кейінгі срездер

- [ ] read-only offline WITSML 2.1 inventory және mapping fixtures;
- [ ] бір пішіндегі alignment-controlled multi-dataset overlay;
- [ ] preview растауы бар каталог watcher;
- [ ] fixture replay өткеннен кейін ғана secured ETP 1.2.

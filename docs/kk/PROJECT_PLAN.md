# Жоба жоспары

2026 жылғы 24 шілдедегі күй.

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

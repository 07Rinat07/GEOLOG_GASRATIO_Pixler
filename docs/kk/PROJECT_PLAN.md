# Жоба жоспары

2026 жылғы 24 шілдедегі күй.

## 0.7.46 жедел hotfix аяқталды

- [x] tablet grid overlay ішінде `Qt.MouseButton.NoButton` қолдану;
- [x] grid/tablet presentation қатесі импортталған dataset-ке қолжетімділікті жаппау;
- [x] сәтті registration кейін safe table recovery workspace ашу;
- [x] Import Review warning-терін бұғаттамай сақтау;
- [x] әр файл қатесін read/parse/policy/review/register/present кезеңімен жинау;
- [x] severity, тұрақты code, action, context, exception type және traceback сақтау;
- [x] blocking report-ты автоматты жазу және UI ішінде Copy/Save беру;
- [x] duplicate LAS mnemonic-ті физикалық бағанмен сақтау және тек зақымдалған арнаны өткізу.

Қолмен қабылдау шарты: проблемалық LAS-ты Windows/PySide6 ішінде тексеріп, import, table recovery,
tablet first frame және diagnostic report қара workspace-сіз жұмыс істейтінін растау.

## Кейінгі срездер

- [ ] read-only offline WITSML 2.1 inventory және mapping fixtures;
- [ ] бір пішіндегі alignment-controlled multi-dataset overlay;
- [ ] preview растауы бар каталог watcher;
- [ ] fixture replay өткеннен кейін ғана secured ETP 1.2.

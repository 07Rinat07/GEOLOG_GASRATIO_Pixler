# Project Status / Статус проекта / Жоба күйі

## Русский

**Пакет приложения:** 0.6.0  
**Формат проекта:** v15  
**Состояние:** активная разработка; исправлен основной пользовательский сценарий загрузки LAS и построения планшета.

Готово в текущем инкременте:

- отдельная панель «Кривые LAS» с поиском и полной сводкой каналов;
- выбор рекомендуемого набора кривых;
- построение планшета из выбранных каналов с отдельными шкалами для несовместимых физических параметров;
- добавление новой дорожки и замена кривых выбранной дорожки;
- светлый контрастный рендер, единицы в легенде и устойчивый автоматический диапазон X;
- явное отображение каналов без числовых данных;
- пустой журнал скрыт по умолчанию;
- синхронная локализация RU/KK/EN;
- полный regression suite: 730 passed, 1 skipped;
- Ruff и MyPy: без ошибок.

Следующий срез: импорт внешнего справочника мнемоник/Sensors после получения полного референсного материала, затем прямое создание интервалов мышью на планшете.

## Қазақша

**Қолданба пакеті:** 0.6.0  
**Жоба форматы:** v15  
**Күйі:** белсенді әзірлеу; LAS жүктеу және планшет құрудың негізгі пайдаланушы сценарийі түзетілді.

Осы инкрементте орындалды:

- іздеу және арналардың толық жиынтығы бар «LAS қисықтары» панелі;
- ұсынылған қисықтар жиынын таңдау;
- таңдалған арналардан үйлеспейтін физикалық параметрлерге жеке шкалалар беретін планшет құру;
- жаңа жолақ қосу және таңдалған жолақ қисықтарын ауыстыру;
- ашық контрастты рендер, легендадағы өлшем бірліктері және тұрақты автоматты X ауқымы;
- сандық деректері жоқ арналарды анық көрсету;
- бос журнал әдепкіде жасырылған;
- RU/KK/EN локализациясы синхрондалған;
- толық regression suite: 730 passed, 1 skipped;
- Ruff және MyPy: қатесіз.

Келесі срез: толық референс материалы алынғаннан кейін сыртқы мнемоника/Sensors анықтамалығын импорттау, содан соң планшетте аралықтарды тінтуірмен тікелей жасау.

## English

**Application package:** 0.6.0  
**Project format:** v15  
**Status:** active development; the primary LAS-loading and tablet-building workflow has been corrected.

Completed in this increment:

- a dedicated LAS curves panel with search and complete channel summaries;
- recommended working-set selection;
- tablet construction from selected channels with independent scales for incompatible physical parameters;
- new-track creation and selected-track curve replacement;
- light high-contrast rendering, units in legends, and robust automatic X ranges;
- explicit display of channels without numeric data;
- the empty log dock is hidden by default;
- synchronized RU/KK/EN localization;
- full regression suite: 730 passed, 1 skipped;
- Ruff and MyPy: clean.

Next slice: external mnemonic/Sensors catalog import after the complete reference material is available, followed by direct mouse-driven interval creation on the tablet.

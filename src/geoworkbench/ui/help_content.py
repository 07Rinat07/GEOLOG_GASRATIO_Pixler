from __future__ import annotations

from dataclasses import dataclass

from geoworkbench.services.localization import AppLanguage


@dataclass(frozen=True, slots=True)
class HelpSection:
    key: str
    title: str
    html: str


_TITLES = {
    AppLanguage.RU: "Документация и инструкции",
    AppLanguage.KK: "Құжаттама және нұсқаулықтар",
    AppLanguage.EN: "Documentation and instructions",
}

_ACTION_TEXTS = {
    AppLanguage.RU: "Документация и инструкции...",
    AppLanguage.KK: "Құжаттама және нұсқаулықтар...",
    AppLanguage.EN: "Documentation and instructions...",
}


_OVERVIEW = {
    AppLanguage.RU: """
        <h1>Справочный центр GEOLOG GASRATIO@Pixler</h1>
        <p>Интерфейс разделён по назначению, чтобы рабочие вкладки не были
        перегружены служебными окнами.</p>
        <ul>
          <li><b>Рабочая область</b> — кривые, таблица LAS и планшет.</li>
          <li><b>Инструменты</b> — файлы, PDF, изображения и калькуляторы.</li>
          <li><b>Печать</b> — центр печати и все отчёты по интерпретации.</li>
          <li><b>Справка</b> — документация, пошаговые инструкции и диагностика.</li>
        </ul>
        <h2>Безопасный порядок работы</h2>
        <ol>
          <li>Откройте проект или импортируйте данные.</li>
          <li>Проверьте скважину, набор данных, единицы и активную шкалу.</li>
          <li>Выполните расчёты и визуальную проверку результатов.</li>
          <li>Сформируйте отчёт, проверьте предпросмотр и только затем экспортируйте.</li>
          <li>При ошибке сохраните диагностический пакет через раздел «Справка».</li>
        </ol>
    """,
    AppLanguage.KK: """
        <h1>GEOLOG GASRATIO@Pixler анықтамалық орталығы</h1>
        <p>Жұмыс қойындылары қызметтік терезелермен толып кетпеуі үшін интерфейс
        міндеті бойынша бөлінген.</p>
        <ul>
          <li><b>Жұмыс аймағы</b> — қисықтар, LAS кестесі және планшет.</li>
          <li><b>Құралдар</b> — файлдар, PDF, кескіндер және калькуляторлар.</li>
          <li><b>Басып шығару</b> — баспа орталығы және интерпретация есептері.</li>
          <li><b>Анықтама</b> — құжаттама, қадамдық нұсқаулықтар және диагностика.</li>
        </ul>
        <h2>Қауіпсіз жұмыс тәртібі</h2>
        <ol>
          <li>Жобаны ашыңыз немесе деректерді импорттаңыз.</li>
          <li>Ұңғыманы, деректер жиынын, бірліктерді және белсенді шкаланы тексеріңіз.</li>
          <li>Есептеулерді орындап, нәтижелерді көзбен тексеріңіз.</li>
          <li>Есепті құрып, алдын ала көріністі тексергеннен кейін ғана экспорттаңыз.</li>
          <li>Қате болса, «Анықтама» бөлімінен диагностикалық жинақты сақтаңыз.</li>
        </ol>
    """,
    AppLanguage.EN: """
        <h1>GEOLOG GASRATIO@Pixler help centre</h1>
        <p>The interface is organised by purpose so permanent work tabs are not
        crowded with utility windows.</p>
        <ul>
          <li><b>Workspace</b> — curves, the LAS table, and the tablet.</li>
          <li><b>Tools</b> — files, PDF, images, and calculators.</li>
          <li><b>Print</b> — Print Centre and all interpretation reports.</li>
          <li><b>Help</b> — documentation, step-by-step instructions, and diagnostics.</li>
        </ul>
        <h2>Safe workflow</h2>
        <ol>
          <li>Open a project or import data.</li>
          <li>Check the well, dataset, units, and active axis.</li>
          <li>Run calculations and visually review the results.</li>
          <li>Build the report, inspect the preview, and only then export it.</li>
          <li>If an error occurs, save a diagnostic bundle from Help.</li>
        </ol>
    """,
}


_PROJECT = {
    AppLanguage.RU: """
        <h1>Проект и ежедневное наращивание LAS</h1>
        <p><b>Главное правило:</b> рабочая форма, геологические описания,
        комментарии, символы и переводы хранятся в одном файле проекта
        <b>.geologpkg</b>. Ежедневный LAS добавляет новые глубины в выбранный
        набор данных и не заменяет уже заполненные слои.</p>
        <h2>Первый LAS и создание проекта</h2>
        <ol>
          <li>Импортируйте первый LAS и проверьте скважину, диапазон глубин,
              шаг, единицы и кривые.</li>
          <li>Сразу сохраните проект как <b>.geologpkg</b> в отдельной рабочей
              папке. Исходные LAS из синхронизируемой папки не редактируйте.</li>
          <li>Заполните форму: описание пород, ЛБА, шламограмму, кальциметрию,
              литологию, заметки и другие слои.</li>
          <li>Добавьте русскую, казахскую и английскую версии текста в этом же
              проекте и сохраните его сочетанием <b>Ctrl+S</b>.</li>
        </ol>
        <h2>Безопасное ежедневное наращивание</h2>
        <ol>
          <li>Дождитесь окончания синхронизации серверной папки и откройте тот же
              рабочий <b>.geologpkg</b>, а не вчерашнюю копию.</li>
          <li>Выберите <b>Файл → Ежедневно нарастить LAS...</b>, нужный набор
              данных и новый LAS из локальной синхронизируемой папки.</li>
          <li>Нажмите «Проверить прирост» и внимательно проверьте скважину,
              границу старых и новых глубин, шаг, единицы и список кривых.</li>
          <li>Если проверка успешна, выполните наращивание и сразу нажмите
              <b>Ctrl+S</b>. Старые интервалы и все языковые версии остаются в
              проекте.</li>
        </ol>
        <h2>Дубликат, конфликт и версии</h2>
        <ul>
          <li>Повторная загрузка того же LAS распознаётся как дубликат и не
              должна добавлять строки второй раз.</li>
          <li>При конфликте скважины, глубин, шага, единиц или ранее записанных
              значений наращивание отклоняется. Не обходите предупреждение
              обычным импортом — запросите правильный LAS.</li>
          <li>Локальные, перенесённые и расчётные кривые сохраняют старые
              значения, но их новый участок остаётся пустым. После наращивания
              повторно выполните нужные расчёты.</li>
          <li>Храните один активный проект и датированные резервные копии. Если
              сам <b>.geologpkg</b> синхронизируется, редактируйте его только на
              одном компьютере одновременно.</li>
        </ul>
        <h2>Печать и перенос</h2>
        <p>Для каждого PDF переключите язык приложения на <b>RU</b>, <b>KK</b>
        или <b>EN</b>, заново откройте Центр печати и проверьте предпросмотр.
        Для переноса на другой компьютер закройте проект после <b>Ctrl+S</b>,
        скопируйте один файл <b>.geologpkg</b> и откройте его на новом
        компьютере.</p>
    """,
    AppLanguage.KK: """
        <h1>Жоба және LAS деректерін күнделікті өсіру</h1>
        <p><b>Негізгі қағида:</b> жұмыс пішіні, геологиялық сипаттамалар,
        түсініктемелер, белгілер және аудармалар бір <b>.geologpkg</b> жоба
        файлында сақталады. Күнделікті LAS таңдалған деректер жиынына жаңа
        тереңдіктерді қосады және бұрын толтырылған қабаттарды алмастырмайды.</p>
        <h2>Бірінші LAS және жоба жасау</h2>
        <ol>
          <li>Бірінші LAS файлын импорттап, ұңғыманы, тереңдік ауқымын, қадамды,
              өлшем бірліктерін және қисықтарды тексеріңіз.</li>
          <li>Жобаны бірден бөлек жұмыс қалтасындағы <b>.geologpkg</b> файлына
              сақтаңыз. Синхрондалатын қалтадағы бастапқы LAS файлдарын өзгертпеңіз.</li>
          <li>Пішінді толтырыңыз: тау жыныстарының сипаттамасы, LBA, шламограмма,
              кальциметрия, литология, ескертпелер және басқа қабаттар.</li>
          <li>Осы жобада мәтіннің қазақ, орыс және ағылшын нұсқаларын қосып,
              <b>Ctrl+S</b> арқылы сақтаңыз.</li>
        </ol>
        <h2>Қауіпсіз күнделікті өсіру</h2>
        <ol>
          <li>Сервер қалтасының синхрондалуы аяқталғанын күтіп, кешегі көшірмені
              емес, сол жұмыс <b>.geologpkg</b> файлын ашыңыз.</li>
          <li><b>Файл → LAS деректерін күнделікті өсіру...</b> тармағын, қажетті
              деректер жиынын және жергілікті синхрондалатын қалтадағы жаңа LAS
              файлын таңдаңыз.</li>
          <li>«Өсімді тексеру» түймесін басып, ұңғыманы, ескі және жаңа
              тереңдіктердің шекарасын, қадамды, бірліктерді және қисықтарды тексеріңіз.</li>
          <li>Тексеру сәтті болса, өсіруді орындап, бірден <b>Ctrl+S</b> басыңыз.
              Ескі аралықтар мен барлық тілдік нұсқалар жобада қалады.</li>
        </ol>
        <h2>Қайталанатын файл, қайшылық және нұсқалар</h2>
        <ul>
          <li>Сол LAS файлын қайта жүктеу қайталанатын файл ретінде танылады
              және жолдарды екінші рет қоспайды.</li>
          <li>Ұңғыма, тереңдік, қадам, бірлік немесе бұрын жазылған мәндер бойынша
              қайшылық болса, өсіру қабылданбайды. Ескертуді кәдімгі импортпен
              айналып өтпеңіз — дұрыс LAS файлын сұраңыз.</li>
          <li>Жергілікті, тасымалданған және есептік қисықтардың ескі мәндері
              сақталады, бірақ жаңа бөлігі бос қалады. Өсіруден кейін қажетті
              есептеулерді қайта орындаңыз.</li>
          <li>Бір белсенді жоба мен күні көрсетілген резервтік көшірмелерді
              сақтаңыз. <b>.geologpkg</b> өзі синхрондалса, оны бір уақытта тек
              бір компьютерде өңдеңіз.</li>
        </ul>
        <h2>Басып шығару және тасымалдау</h2>
        <p>Әр PDF үшін қолданба тілін <b>RU</b>, <b>KK</b> немесе <b>EN</b> етіп
        ауыстырып, Баспа орталығын қайта ашыңыз және алдын ала көріністі
        тексеріңіз. Басқа компьютерге тасымалдау үшін <b>Ctrl+S</b> басқаннан
        кейін жобаны жауып, бір <b>.geologpkg</b> файлын көшіріп, оны жаңа
        компьютерде ашыңыз.</p>
    """,
    AppLanguage.EN: """
        <h1>Project and daily LAS append</h1>
        <p><b>Key rule:</b> the working form, geological descriptions, comments,
        symbols, and translations are stored together in one <b>.geologpkg</b>
        project. A daily LAS appends new depths to the selected dataset; it does
        not replace the layers you already completed.</p>
        <h2>First LAS and project creation</h2>
        <ol>
          <li>Import the first LAS and check the well, depth range, step, units,
              and curves.</li>
          <li>Immediately save the project as <b>.geologpkg</b> in a separate
              working folder. Do not edit source LAS files in the synced folder.</li>
          <li>Complete the form: rock description, LBA, cuttings log,
              calcimetry, lithology, notes, and other layers.</li>
          <li>Add Russian, Kazakh, and English text versions in this same project,
              then save it with <b>Ctrl+S</b>.</li>
        </ol>
        <h2>Safe daily append</h2>
        <ol>
          <li>Wait for the server folder to finish syncing and open the same
              working <b>.geologpkg</b>, not a copy from the previous day.</li>
          <li>Select <b>File → Append daily LAS data...</b>, the required dataset,
              and the new LAS from the local synced folder.</li>
          <li>Select “Analyze growth” and carefully check the well, old/new depth
              boundary, step, units, and curve list.</li>
          <li>If validation succeeds, append the data and immediately press
              <b>Ctrl+S</b>. Old intervals and all language versions remain in
              the project.</li>
        </ol>
        <h2>Duplicate, conflict, and version control</h2>
        <ul>
          <li>Loading the same LAS again is recognised as a duplicate and must
              not add its rows a second time.</li>
          <li>A well, depth, step, unit, or previously stored value conflict
              rejects the append. Do not bypass the warning with a regular
              import; request the correct LAS.</li>
          <li>Local, transferred, and calculated curves keep their old values,
              but their new interval remains empty. Rerun the required
              calculations after appending.</li>
          <li>Keep one active project and dated backups. If the <b>.geologpkg</b>
              itself is synced, edit it on only one computer at a time.</li>
        </ul>
        <h2>Printing and transfer</h2>
        <p>For each PDF, switch the application language to <b>RU</b>, <b>KK</b>,
        or <b>EN</b>, reopen Print Centre, and inspect the preview. To transfer
        the work to another computer, close the project after <b>Ctrl+S</b>,
        copy the single <b>.geologpkg</b> file, and open it on the other
        computer.</p>
    """,
}


_TOOLS = {
    AppLanguage.RU: """
        <h1>Файлы, PDF и калькуляторы</h1>
        <p>Окно открывается через <b>Инструменты → Файлы / PDF / Калькулятор</b>.</p>
        <h2>Файлы и документы</h2>
        <ol>
          <li>Откройте поддерживаемый файл и дождитесь завершения загрузки.</li>
          <li>Для PDF проверьте номер страницы и масштаб до редактирования.</li>
          <li>Сохраняйте результат под новым именем, пока исходный файл ещё нужен.</li>
          <li>Перед закрытием убедитесь, что изменения записаны на диск.</li>
        </ol>
        <h2>Калькуляторы</h2>
        <ol>
          <li>Выберите нужную инженерную вкладку.</li>
          <li>Проверьте единицы каждого входного поля.</li>
          <li>Не используйте результат при пустых, отрицательных или физически
              невозможных входных данных.</li>
          <li>Переносите результат в проект только после независимой проверки.</li>
        </ol>
        <p><b>Примечание:</b> отсутствие компонентов PyMuPDF или Pillow не должно
        блокировать основное приложение; окно покажет команду установки.</p>
    """,
    AppLanguage.KK: """
        <h1>Файлдар, PDF және калькуляторлар</h1>
        <p>Терезе <b>Құралдар → Файлдар / PDF / Калькулятор</b> арқылы ашылады.</p>
        <h2>Файлдар мен құжаттар</h2>
        <ol>
          <li>Қолдау көрсетілетін файлды ашып, жүктелудің аяқталуын күтіңіз.</li>
          <li>PDF өңдеу алдында бет нөмірі мен масштабты тексеріңіз.</li>
          <li>Түпнұсқа қажет болса, нәтижені жаңа атаумен сақтаңыз.</li>
          <li>Жабу алдында өзгерістердің дискіге жазылғанын тексеріңіз.</li>
        </ol>
        <h2>Калькуляторлар</h2>
        <ol>
          <li>Қажетті инженерлік қойындыны таңдаңыз.</li>
          <li>Әр кіріс өрісінің өлшем бірлігін тексеріңіз.</li>
          <li>Бос, теріс немесе физикалық мүмкін емес деректермен алынған нәтижені қолданбаңыз.</li>
          <li>Нәтижені жобаға тәуелсіз тексеруден кейін ғана енгізіңіз.</li>
        </ol>
        <p><b>Ескерту:</b> PyMuPDF немесе Pillow компоненттері болмаса да негізгі
        қолданба жұмысын жалғастырады; терезеде орнату пәрмені көрсетіледі.</p>
    """,
    AppLanguage.EN: """
        <h1>Files, PDF, and calculators</h1>
        <p>Open the window from <b>Tools → Files / PDF / Calculator</b>.</p>
        <h2>Files and documents</h2>
        <ol>
          <li>Open a supported file and wait until loading has finished.</li>
          <li>For PDF work, check the page number and zoom before editing.</li>
          <li>Save under a new name while the source file is still required.</li>
          <li>Before closing, confirm that changes were written to disk.</li>
        </ol>
        <h2>Calculators</h2>
        <ol>
          <li>Select the required engineering tab.</li>
          <li>Check the unit of every input field.</li>
          <li>Do not use results produced from blank, negative, or physically
              impossible inputs.</li>
          <li>Transfer a result to the project only after an independent check.</li>
        </ol>
        <p><b>Note:</b> missing PyMuPDF or Pillow components do not block the main
        application; the window displays the installation command.</p>
    """,
}


_PRINTING = {
    AppLanguage.RU: """
        <h1>Печать и экспорт отчётов</h1>
        <p>Центр печати и отчёты находятся в меню <b>Печать</b>.</p>
        <ol>
          <li>Выберите правильную скважину, набор данных и отображаемый интервал.</li>
          <li>Откройте предпросмотр и проверьте ориентацию, формат бумаги, поля,
              масштаб, заголовки и номера страниц.</li>
          <li>Для широких графиков используйте альбомную ориентацию A4 или A3.</li>
          <li>Проверьте, что графики не разрезаны между страницами, подписи читаемы,
              а правая шкала находится внутри печатной области.</li>
          <li>Сначала сохраните контрольный PDF. Физическую печать выполняйте только
              после просмотра этого PDF.</li>
          <li>Не считайте успешный экспорт доказательством корректной компоновки:
              итоговый файл необходимо открыть и осмотреть.</li>
        </ol>
        <h2>Отчёты по интерпретации</h2>
        <p>В подменю «Отчёты по интерпретации» доступны отчёт газового каротажа и
        отчёт кальциметрии/LBA. Они открываются отдельными окнами и не занимают
        постоянные вкладки рабочей области.</p>
    """,
    AppLanguage.KK: """
        <h1>Есептерді басып шығару және экспорттау</h1>
        <p>Баспа орталығы мен есептер <b>Басып шығару</b> мәзірінде орналасқан.</p>
        <ol>
          <li>Дұрыс ұңғыманы, деректер жиынын және көрсетілетін аралықты таңдаңыз.</li>
          <li>Алдын ала көріністе бағдарды, қағаз өлшемін, жиектерді, масштабты,
              тақырыптарды және бет нөмірлерін тексеріңіз.</li>
          <li>Кең графиктер үшін A4 немесе A3 көлденең бағдарын қолданыңыз.</li>
          <li>Графиктердің беттер арасында бөлінбегенін, жазулардың оқылатынын және
              оң жақ шкаланың баспа аумағында қалғанын тексеріңіз.</li>
          <li>Алдымен бақылау PDF сақтаңыз. Қағазға басуды PDF тексерілгеннен кейін орындаңыз.</li>
          <li>Сәтті экспорт дұрыс орналасуды дәлелдемейді: дайын файлды міндетті түрде ашыңыз.</li>
        </ol>
        <h2>Интерпретация есептері</h2>
        <p>«Интерпретация есептері» ішкі мәзірінде газ каротажы және
        кальциметрия/LBA есептері бар. Олар бөлек терезеде ашылады және тұрақты
        жұмыс қойындыларын алмайды.</p>
    """,
    AppLanguage.EN: """
        <h1>Printing and report export</h1>
        <p>Print Centre and reports are located in the <b>Print</b> menu.</p>
        <ol>
          <li>Select the correct well, dataset, and displayed interval.</li>
          <li>In preview, verify orientation, paper format, margins, scale,
              headers, and page numbers.</li>
          <li>Use A4 or A3 landscape orientation for wide charts.</li>
          <li>Confirm charts are not split across pages, labels are readable,
              and the right axis remains inside the printable area.</li>
          <li>Save a control PDF first. Print physically only after reviewing it.</li>
          <li>A successful export does not prove correct layout; always open and
              inspect the resulting file.</li>
        </ol>
        <h2>Interpretation reports</h2>
        <p>The Interpretation reports submenu contains the mud-gas report and the
        calcimetry/LBA report. They open in separate windows and do not occupy
        permanent workspace tabs.</p>
    """,
}


_INTERPRETATION = {
    AppLanguage.RU: """
        <h1>Интерпретация газового каротажа</h1>
        <p>Откройте <b>Печать → Отчёты по интерпретации → Интерпретация газового
        каротажа</b>.</p>
        <ol>
          <li><b>Выберите скважину и набор данных.</b> Проверьте C1–C5, ROP,
              RPM, WOB, BIT/BS и FLOW. Для SLIDE желательно иметь забойный RPM.</li>
          <li><b>Выберите источник нормализованного газа:</b> сервер, локальный
              расчёт или сопоставление обеих кривых.</li>
          <li><b>Настройте BIT и входные данные.</b> Заполните интервалы диаметров
              долота, проверьте единицы и отсутствие необъяснённых пропусков.</li>
          <li><b>Проверьте ROP_REF, BIT_REF, FLOW_REF и эффективность газовой
              системы.</b> Значения должны соответствовать методике заказчика.</li>
          <li><b>Пересчитайте все доступные кривые</b> и дождитесь завершения.</li>
          <li><b>Проверьте качество DEXP.</b> Откройте причины разрывов. SLIDE без
              забойного RPM может оставлять обоснованный разрыв.</li>
          <li><b>Обновите отчёт с графиками</b> и откройте предпросмотр.</li>
          <li><b>Проверьте графики, шкалы, единицы, абсолютные C1–C5 и
              перспективные интервалы.</b> Перспективные интервалы не заменяют
              заключение геолога.</li>
          <li><b>Сохраните Excel или Word</b> для проверки таблиц и редактирования.</li>
          <li><b>Сформируйте контрольный PDF.</b> Проверьте все страницы, переносы
              таблиц, читаемость графика и только после этого выполняйте печать.</li>
        </ol>
        <p><b>Критерий готовности:</b> расчёт завершён без ошибок, DEXP проверен,
        интервалы обоснованы, а PDF визуально просмотрен от первой до последней страницы.</p>
    """,
    AppLanguage.KK: """
        <h1>Газ каротажын интерпретациялау</h1>
        <p><b>Басып шығару → Интерпретация есептері → Газ каротажын
        интерпретациялау</b> тармағын ашыңыз.</p>
        <ol>
          <li><b>Ұңғыма мен деректер жиынын таңдаңыз.</b> C1–C5, ROP, RPM, WOB,
              BIT/BS және FLOW тексеріңіз. SLIDE үшін түптік RPM болғаны жөн.</li>
          <li><b>Нормаланған газ көзін таңдаңыз:</b> сервер, жергілікті есеп немесе салыстыру.</li>
          <li><b>BIT және кіріс деректерін баптаңыз.</b> Қашау диаметрі аралықтарын,
              бірліктерді және түсіндірілмеген бос орындарды тексеріңіз.</li>
          <li><b>ROP_REF, BIT_REF, FLOW_REF және газ жүйесінің тиімділігін тексеріңіз.</b></li>
          <li><b>Барлық қолжетімді қисықтарды қайта есептеңіз</b> және аяқталуын күтіңіз.</li>
          <li><b>DEXP сапасын тексеріңіз.</b> Үзіліс себептерін ашыңыз.</li>
          <li><b>Графиктері бар есепті жаңартып</b>, алдын ала көріністі ашыңыз.</li>
          <li><b>Графиктерді, шкалаларды, бірліктерді, C1–C5 абсолют мәндерін және
              перспективалы аралықтарды тексеріңіз.</b> Олар геолог қорытындысын алмастырмайды.</li>
          <li><b>Кестелерді тексеру үшін Excel немесе Word сақтаңыз.</b></li>
          <li><b>Бақылау PDF жасаңыз.</b> Барлық бетті тексергеннен кейін ғана басып шығарыңыз.</li>
        </ol>
        <p><b>Дайындық өлшемі:</b> есеп қатесіз аяқталды, DEXP тексерілді,
        аралықтар негізделді және PDF толық қаралды.</p>
    """,
    AppLanguage.EN: """
        <h1>Mud-gas interpretation</h1>
        <p>Open <b>Print → Interpretation reports → Mud-gas interpretation</b>.</p>
        <ol>
          <li><b>Select the well and dataset.</b> Check C1–C5, ROP, RPM, WOB,
              BIT/BS, and FLOW. Downhole RPM is preferable for SLIDE intervals.</li>
          <li><b>Select the normalised-gas source:</b> server, local calculation,
              or comparison of both curves.</li>
          <li><b>Configure BIT and the input data.</b> Check bit-size intervals,
              units, and unexplained gaps.</li>
          <li><b>Review ROP_REF, BIT_REF, FLOW_REF, and gas-system efficiency.</b></li>
          <li><b>Recalculate all available curves</b> and wait for completion.</li>
          <li><b>Review DEXP quality.</b> Open the reasons for gaps.</li>
          <li><b>Refresh the report with charts</b> and open the preview.</li>
          <li><b>Check charts, scales, units, absolute C1–C5 values, and prospective
              intervals.</b> Prospective intervals do not replace the geologist's conclusion.</li>
          <li><b>Save Excel or Word</b> for table checking and editing.</li>
          <li><b>Generate a control PDF.</b> Inspect every page, table continuation,
              and chart readability before printing.</li>
        </ol>
        <p><b>Ready criterion:</b> calculation completed without errors, DEXP was
        reviewed, intervals are justified, and the PDF was inspected from first page to last.</p>
    """,
}


_DIAGNOSTICS = {
    AppLanguage.RU: """
        <h1>Диагностика и обращение за помощью</h1>
        <ol>
          <li>Запишите последовательность действий и точное время ошибки.</li>
          <li>Сохраните исходный файл и получившийся PDF, Word или Excel.</li>
          <li>В разделе «Справка» откройте папку журналов либо создайте
              диагностический пакет.</li>
          <li>Не удаляйте исходные данные и не повторяйте массовый экспорт до анализа ошибки.</li>
          <li>Передавайте разработчику журнал, диагностический пакет, пример входного
              файла и снимок проблемной страницы.</li>
        </ol>
    """,
    AppLanguage.KK: """
        <h1>Диагностика және көмек сұрау</h1>
        <ol>
          <li>Әрекеттер ретін және қате уақытын жазыңыз.</li>
          <li>Бастапқы файлды және алынған PDF, Word немесе Excel файлын сақтаңыз.</li>
          <li>«Анықтама» бөлімінен журналдар қалтасын ашыңыз немесе диагностикалық жинақ жасаңыз.</li>
          <li>Қате талданғанша бастапқы деректерді жоймаңыз және жаппай экспортты қайталамаңыз.</li>
          <li>Әзірлеушіге журналды, диагностикалық жинақты, кіріс файлын және ақаулы беттің суретін беріңіз.</li>
        </ol>
    """,
    AppLanguage.EN: """
        <h1>Diagnostics and support</h1>
        <ol>
          <li>Record the exact sequence of actions and the time of the error.</li>
          <li>Keep the source file and the resulting PDF, Word, or Excel file.</li>
          <li>From Help, open the log folder or build a diagnostic bundle.</li>
          <li>Do not delete source data or repeat bulk exports until the failure is analysed.</li>
          <li>Provide the log, diagnostic bundle, sample input, and a screenshot of
              the affected page to the developer.</li>
        </ol>
    """,
}


_SECTION_TITLES = {
    AppLanguage.RU: {
        "overview": "Начало работы",
        "project": "Проект и ежедневный LAS",
        "tools": "Файлы, PDF и калькуляторы",
        "printing": "Печать и отчёты",
        "interpretation": "Газовый каротаж",
        "diagnostics": "Диагностика",
    },
    AppLanguage.KK: {
        "overview": "Жұмысты бастау",
        "project": "Жоба және күнделікті LAS",
        "tools": "Файлдар, PDF және калькуляторлар",
        "printing": "Басып шығару және есептер",
        "interpretation": "Газ каротажы",
        "diagnostics": "Диагностика",
    },
    AppLanguage.EN: {
        "overview": "Getting started",
        "project": "Project and daily LAS",
        "tools": "Files, PDF, and calculators",
        "printing": "Printing and reports",
        "interpretation": "Mud-gas interpretation",
        "diagnostics": "Diagnostics",
    },
}


def normalized_language(language: AppLanguage | str) -> AppLanguage:
    if isinstance(language, AppLanguage):
        return language
    value = str(language).strip().casefold()
    for candidate in AppLanguage:
        if candidate.value.casefold() == value:
            return candidate
    return AppLanguage.RU


def help_center_title(language: AppLanguage | str) -> str:
    return _TITLES[normalized_language(language)]


def help_action_text(language: AppLanguage | str) -> str:
    return _ACTION_TEXTS[normalized_language(language)]


def help_sections(language: AppLanguage | str) -> tuple[HelpSection, ...]:
    selected = normalized_language(language)
    contents = {
        "overview": _OVERVIEW[selected],
        "project": _PROJECT[selected],
        "tools": _TOOLS[selected],
        "printing": _PRINTING[selected],
        "interpretation": _INTERPRETATION[selected],
        "diagnostics": _DIAGNOSTICS[selected],
    }
    return tuple(
        HelpSection(key, _SECTION_TITLES[selected][key], contents[key])
        for key in (
            "overview",
            "project",
            "tools",
            "printing",
            "interpretation",
            "diagnostics",
        )
    )


def interpretation_guide_html(language: AppLanguage | str) -> str:
    return _INTERPRETATION[normalized_language(language)]

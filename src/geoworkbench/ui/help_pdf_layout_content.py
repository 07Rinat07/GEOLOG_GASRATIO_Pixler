from __future__ import annotations

from geoworkbench.services.localization import AppLanguage


_PDF_LAYOUT_HELP = {
    AppLanguage.RU: """
        <h2>Постраничный график газового каротажа</h2>
        <ul>
          <li>PDF-экспорт и системная печать используют один постраничный движок.</li>
          <li>Перед экспортом или печатью открывается форма реквизитов отчёта.
              Проект, скважину, месторождение, оператора, сервисную компанию,
              буровую, название набора, номер документа, ревизию, дату и подписи
              можно ввести вручную.</li>
          <li>Ручные значения действуют только для PDF и печати. Они не
              переименовывают проект, скважину и загруженные файлы в программе.
              Кнопка «Подставить данные из программы» возвращает исходные значения.</li>
          <li>Первая страница оформляется как самостоятельный отраслевой титульный
              лист с блоком управления документом и полями «Подготовил»,
              «Проверил», «Утвердил».</li>
          <li>Вертикальный масштаб выбирается автоматически из стандартного ряда
              и указывается на каждом графическом листе.</li>
          <li>На левой и правой шкалах печатаются усиленные основные деления с
              числами и более короткие промежуточные деления. Шаг подписей
              автоматически меняется для коротких и длинных интервалов.</li>
          <li>Короткая скважина не растягивается искусственно, а длинная делится
              на непрерывные последовательные диапазоны глубины.</li>
          <li>На каждом листе повторяются левая и правая шкалы глубины, внешние
              границы, заголовки дорожек, легенда и диапазон листа.</li>
          <li>Кривые печатаются векторно. Таблицы переносятся только между
              строками, а шапка повторяется на странице продолжения.</li>
        </ul>
        <h3>Печать на физическом принтере Windows</h3>
        <ol>
          <li>Заполните или отредактируйте реквизиты титульного листа.</li>
          <li>Выберите книжную или альбомную ориентацию и порядок страниц.</li>
          <li>В следующем системном окне Windows выберите Epson, диапазон страниц,
              число копий и свойства драйвера.</li>
          <li>Диапазон 1–2 отправляет на принтер только страницы 1 и 2 в выбранном порядке.</li>
          <li>Кнопка «Остановить» прекращает передачу ещё не отправленных страниц.
              Страницы, уже переданные в очередь Windows, при необходимости отменяются
              в системной очереди печати.</li>
          <li>Перед печатью проверьте титульный лист, числовые подписи глубины,
              первую и последнюю графические страницы, правую шкалу, легенду,
              примечание и страницы продолжения таблиц.</li>
        </ol>
    """,
    AppLanguage.KK: """
        <h2>Газ каротажының көпбетті графигі</h2>
        <ul>
          <li>PDF экспорты мен жүйелік басып шығару бір көпбетті қозғалтқышты пайдаланады.</li>
          <li>Экспорттау немесе басып шығару алдында есеп деректемелерінің пішіні
              ашылады. Жобаны, ұңғыманы, кен орнын, операторды, сервистік компанияны,
              бұрғылау қондырғысын, деректер атауын, құжат нөмірін, ревизияны,
              күнді және қол қоюшыларды қолмен енгізуге болады.</li>
          <li>Қолмен енгізілген мәндер тек PDF пен басып шығаруға қолданылады.
              Олар бағдарламадағы жоба, ұңғыма және жүктелген файл атауларын
              өзгертпейді. «Бағдарлама деректерін қою» түймесі бастапқы мәндерді қайтарады.</li>
          <li>Бірінші бет құжатты басқару блогы және «Дайындаған», «Тексерген»,
              «Бекіткен» өрістері бар жеке салалық титулдық бет ретінде рәсімделеді.</li>
          <li>Тік масштаб стандартты қатардан автоматты түрде таңдалып, әр
              график бетінде көрсетіледі.</li>
          <li>Сол және оң шкалаларда сандары бар айқын негізгі бөліктер және
              қысқа аралық бөліктер басылады. Қысқа және ұзын аралықтар үшін
              сандық жазбалардың қадамы автоматты түрде өзгереді.</li>
          <li>Қысқа ұңғыма жасанды созылмайды, ал ұзын ұңғыма тереңдіктің
              үздіксіз және ретімен жалғасатын аралықтарына бөлінеді.</li>
          <li>Әр бетте сол және оң тереңдік шкалалары, сыртқы шекаралар, жол
              тақырыптары, шартты белгілер және бет аралығы қайталанады.</li>
          <li>Қисықтар векторлық түрде басылады. Кестелер тек жолдар арасында
              тасымалданады, ал кесте тақырыбы жалғастыру бетінде қайталанады.</li>
        </ul>
        <h3>Windows жүйесіндегі физикалық принтерге басып шығару</h3>
        <ol>
          <li>Титулдық бет деректемелерін толтырыңыз немесе түзетіңіз.</li>
          <li>Кітапша немесе альбомдық бағдарды және беттердің ретін таңдаңыз.</li>
          <li>Келесі Windows жүйелік терезесінде Epson принтерін, бет ауқымын,
              көшірме санын және драйвер қасиеттерін таңдаңыз.</li>
          <li>1–2 ауқымы принтерге таңдалған ретпен тек 1 және 2-беттерді жібереді.</li>
          <li>«Тоқтату» түймесі әлі жіберілмеген беттердің берілуін тоқтатады.
              Windows кезегіне жіберіліп қойған беттер қажет болса жүйелік баспа
              кезегінде тоқтатылады.</li>
          <li>Басып шығару алдында титулдық бетті, тереңдік сандарын, бірінші және
              соңғы график бетін, оң шкаланы, шартты белгілерді, ескертпені және
              кесте жалғасын тексеріңіз.</li>
        </ol>
    """,
    AppLanguage.EN: """
        <h2>Multi-page mud-gas chart</h2>
        <ul>
          <li>PDF export and system printing use the same controlled renderer.</li>
          <li>A report-details form opens before export or printing. Project,
              well, field, operator, service company, rig, dataset label,
              document number, revision, date, and sign-off names can be edited manually.</li>
          <li>Manual values affect only PDF output and printing. They do not rename
              the project, well, or loaded files in the application. The
              “Restore application values” button restores the original suggestions.</li>
          <li>The first page is an independent industry-style cover with document
              control and Prepared by, Checked by, and Approved by blocks.</li>
          <li>The vertical scale is selected automatically from a standard series
              and printed on every chart sheet.</li>
          <li>Both depth scales show stronger labelled major ticks and shorter
              intermediate ticks. The numeric-label interval adapts to short and
              long depth ranges.</li>
          <li>A short well is not stretched artificially; a long well is divided
              into continuous, sequential depth ranges.</li>
          <li>Every sheet repeats the left and right depth scales, outer borders,
              track headings, legend, and sheet range.</li>
          <li>Curves are printed as vector graphics. Tables continue only between
              rows, and the table header repeats on continuation pages.</li>
        </ul>
        <h3>Printing to a physical Windows printer</h3>
        <ol>
          <li>Complete or edit the cover-page details.</li>
          <li>Select portrait or landscape orientation and the page order.</li>
          <li>In the following native Windows dialog, select the Epson printer,
              page range, copy count, and driver properties.</li>
          <li>A range of 1–2 sends only pages 1 and 2 in the selected order.</li>
          <li>The Stop button prevents unsent pages from being transferred. Pages
              already placed in the Windows queue may still need to be cancelled
              from the system print queue.</li>
          <li>Before printing, inspect the cover, numeric depth labels, the first
              and last chart sheets, the right scale, legend, note, and table continuations.</li>
        </ol>
    """,
}


def pdf_layout_help_html(language: AppLanguage) -> str:
    return _PDF_LAYOUT_HELP[language]


def append_pdf_layout_help(html: str, language: AppLanguage) -> str:
    return html + pdf_layout_help_html(language)


__all__ = ["append_pdf_layout_help", "pdf_layout_help_html"]

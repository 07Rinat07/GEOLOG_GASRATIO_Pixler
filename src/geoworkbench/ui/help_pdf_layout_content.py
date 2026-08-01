from __future__ import annotations

from geoworkbench.services.localization import AppLanguage


_PDF_LAYOUT_HELP = {
    AppLanguage.RU: """
        <h2>Постраничный график газового каротажа</h2>
        <ul>
          <li>PDF-экспорт и системная печать используют один постраничный движок.</li>
          <li>Первая страница оформляется отдельно: заголовок, реквизиты проекта,
              скважины и набора данных не смешиваются с содержательной частью.</li>
          <li>Вертикальный масштаб выбирается автоматически из стандартного ряда
              и указывается на каждом графическом листе.</li>
          <li>Короткая скважина не растягивается искусственно, а длинная делится
              на непрерывные последовательные диапазоны глубины.</li>
          <li>На каждом листе повторяются левая и правая шкалы глубины, внешние
              границы, заголовки дорожек, легенда и диапазон листа.</li>
          <li>Кривые печатаются векторно. Таблицы переносятся только между
              строками, а шапка повторяется на странице продолжения.</li>
        </ul>
        <h3>Печать на физическом принтере Windows</h3>
        <ol>
          <li>Сначала выберите книжную или альбомную ориентацию и порядок страниц.</li>
          <li>В следующем системном окне Windows выберите Epson, диапазон страниц,
              число копий и свойства драйвера.</li>
          <li>Диапазон 1–2 отправляет на принтер только страницы 1 и 2 в выбранном порядке.</li>
          <li>Кнопка «Остановить» прекращает передачу ещё не отправленных страниц.
              Страницы, уже переданные в очередь Windows, при необходимости отменяются
              в системной очереди печати.</li>
          <li>Перед печатью проверьте первую и последнюю графические страницы,
              правую шкалу, легенду, примечание и страницы продолжения таблиц.</li>
        </ol>
    """,
    AppLanguage.KK: """
        <h2>Газ каротажының көпбетті графигі</h2>
        <ul>
          <li>PDF экспорты мен жүйелік басып шығару бір көпбетті қозғалтқышты пайдаланады.</li>
          <li>Бірінші бет бөлек рәсімделеді: тақырып, жоба, ұңғыма және деректер
              жинағының деректемелері есеп мазмұнымен араласпайды.</li>
          <li>Тік масштаб стандартты қатардан автоматты түрде таңдалып, әр
              график бетінде көрсетіледі.</li>
          <li>Қысқа ұңғыма жасанды созылмайды, ал ұзын ұңғыма тереңдіктің
              үздіксіз және ретімен жалғасатын аралықтарына бөлінеді.</li>
          <li>Әр бетте сол және оң тереңдік шкалалары, сыртқы шекаралар, жол
              тақырыптары, шартты белгілер және бет аралығы қайталанады.</li>
          <li>Қисықтар векторлық түрде басылады. Кестелер тек жолдар арасында
              тасымалданады, ал кесте тақырыбы жалғастыру бетінде қайталанады.</li>
        </ul>
        <h3>Windows жүйесіндегі физикалық принтерге басып шығару</h3>
        <ol>
          <li>Алдымен кітапша немесе альбомдық бағдарды және беттердің ретін таңдаңыз.</li>
          <li>Келесі Windows жүйелік терезесінде Epson принтерін, бет ауқымын,
              көшірме санын және драйвер қасиеттерін таңдаңыз.</li>
          <li>1–2 ауқымы принтерге таңдалған ретпен тек 1 және 2-беттерді жібереді.</li>
          <li>«Тоқтату» түймесі әлі жіберілмеген беттердің берілуін тоқтатады.
              Windows кезегіне жіберіліп қойған беттер қажет болса жүйелік баспа
              кезегінде тоқтатылады.</li>
          <li>Басып шығару алдында бірінші және соңғы график бетін, оң шкаланы,
              шартты белгілерді, ескертпені және кесте жалғасын тексеріңіз.</li>
        </ol>
    """,
    AppLanguage.EN: """
        <h2>Multi-page mud-gas chart</h2>
        <ul>
          <li>PDF export and system printing use the same controlled renderer.</li>
          <li>The first page has a dedicated layout: the title and project, well,
              and dataset details are separated from the report body.</li>
          <li>The vertical scale is selected automatically from a standard series
              and printed on every chart sheet.</li>
          <li>A short well is not stretched artificially; a long well is divided
              into continuous, sequential depth ranges.</li>
          <li>Every sheet repeats the left and right depth scales, outer borders,
              track headings, legend, and sheet range.</li>
          <li>Curves are printed as vector graphics. Tables continue only between
              rows, and the table header repeats on continuation pages.</li>
        </ul>
        <h3>Printing to a physical Windows printer</h3>
        <ol>
          <li>First select portrait or landscape orientation and the page order.</li>
          <li>In the following native Windows dialog, select the Epson printer,
              page range, copy count, and driver properties.</li>
          <li>A range of 1–2 sends only pages 1 and 2 in the selected order.</li>
          <li>The Stop button prevents unsent pages from being transferred. Pages
              already placed in the Windows queue may still need to be cancelled
              from the system print queue.</li>
          <li>Before printing, inspect the first and last chart sheets, the right
              scale, legend, note, and all table continuation pages.</li>
        </ol>
    """,
}


def pdf_layout_help_html(language: AppLanguage) -> str:
    return _PDF_LAYOUT_HELP[language]


def append_pdf_layout_help(html: str, language: AppLanguage) -> str:
    return html + pdf_layout_help_html(language)


__all__ = ["append_pdf_layout_help", "pdf_layout_help_html"]

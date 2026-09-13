from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.rich_interval_text_editor import RichIntervalTextEditor


def test_template_anchor_survives_html_round_trip_and_removes_exact_block(qapp) -> None:
    editor = RichIntervalTextEditor(language=AppLanguage.EN)
    editor.append_html("Manual prefix")
    editor.append_template_block("block-1", "Sandstone [X%]")
    editor.append_html("Manual suffix")
    saved_html = editor.html()

    reopened = RichIntervalTextEditor(language=AppLanguage.EN)
    reopened.set_html(saved_html)

    assert reopened.has_template_block("block-1") is True
    assert reopened.remove_template_block("block-1") is True
    assert "Sandstone [X%]" not in reopened.editor.toPlainText()
    assert "Manual prefix" in reopened.editor.toPlainText()
    assert "Manual suffix" in reopened.editor.toPlainText()

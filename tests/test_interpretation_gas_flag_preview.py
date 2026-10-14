"""Full PDF proof can request an exact-source gas callout and regenerate."""

import fitz

from geoworkbench.ui.interpretation_full_report_preview import FullReportPreviewDialog


def test_full_report_gas_flag_action_updates_proof(qapp, tmp_path) -> None:
    target = tmp_path / "gas-proof.pdf"

    def write_page(text: str) -> None:
        with fitz.open() as source:
            page = source.new_page()
            page.insert_text((72, 72), text)
            source.save(target)

    write_page("before")
    changed = []

    def add_gas() -> None:
        changed.append("TG: 15 %")

    def refresh() -> None:
        target.unlink()
        write_page("after" if changed else "before")

    dialog = FullReportPreviewDialog(
        target,
        refresh_document=refresh,
        edit_annotations=lambda: None,
        export_document=lambda path: None,
        add_gas_value_flag=add_gas,
    )
    try:
        assert dialog.gas_flag_button.isEnabled()
        dialog.gas_flag_button.click()
        assert changed == ["TG: 15 %"]
        assert dialog.page_count == 1
        with fitz.open(target) as document:
            assert "after" in document[0].get_text()
    finally:
        dialog.close()
        qapp.processEvents()

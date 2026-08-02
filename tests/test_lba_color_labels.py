from pathlib import Path

from geoworkbench.services.lba_standard import (
    LBA_STANDARD_GROUPS,
    all_lba_color_labels,
    lba_color_code,
)
from geoworkbench.services.localization import AppLanguage


def test_lba_graph_label_uses_only_fluorescence_code() -> None:
    color = LBA_STANDARD_GROUPS[0].colors[0]

    assert lba_color_code(color.label(AppLanguage.RU)) == "БГ"
    assert lba_color_code(color.label(AppLanguage.KK)) == "БГ"
    assert lba_color_code(color.label(AppLanguage.EN)) == "БГ"


def test_lba_editor_keeps_explanatory_colour_label() -> None:
    labels = all_lba_color_labels(AppLanguage.RU)

    assert "БГ — беловато-голубой" in labels


def test_legacy_full_colour_label_is_normalized_for_graph_and_pdf() -> None:
    assert lba_color_code("БГ — беловато-голубой") == "БГ"
    assert lba_color_code("БГ - беловато голубой") == "БГ"
    assert lba_color_code("БГ") == "БГ"


def test_masterlog_inspection_preserves_human_readable_colour_text() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "src/geoworkbench/printing/masterlog_inspection.py"
    ).read_text(encoding="utf-8")

    # Compact codes belong only in narrow tablet/PDF cells. Inspection text and
    # tooltips must retain the value entered by the geologist, including case and
    # descriptive wording such as "yellow".
    assert "lba_color_code" not in source
    assert '(sample.lba_color or "").strip()' in source
    assert '(sample.lba_cut_color or "").strip()' in source
    assert '(sample.lba_residue_color or "").strip()' in source


def test_tablet_keeps_readable_lba_text_outside_compact_colour_cell() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "src/geoworkbench/tablet/tablet_view.py"
    ).read_text(encoding="utf-8")

    # Only the narrow graphics cell may normalize a full colour label to its
    # compact code. Cursor summaries and detailed tooltips preserve user text.
    assert source.count("lba_color_code(sample.lba_color)") == 1
    assert "lba_color_code(sample.lba_cut_color)" not in source
    assert "lba_color_code(sample.lba_residue_color)" not in source
    assert "lba_color_code(tablet." not in source
    assert "self._localizer.text('tablet.lba_color')" in source
    assert "self._localizer.text('tablet.lba_cut_color')" in source
    assert "self._localizer.text('tablet.lba_residue_color')" in source

from geoworkbench.services.lba_standard import (
    LBA_STANDARD_GROUPS,
    all_lba_color_labels,
    lba_color_code,
)
from geoworkbench.services.localization import AppLanguage


def test_lba_graph_label_uses_only_fluorescence_code() -> None:
    color = LBA_STANDARD_GROUPS[0].colors[0]

    assert color.label(AppLanguage.RU) == "БГ"
    assert color.label(AppLanguage.KK) == "БГ"
    assert color.label(AppLanguage.EN) == "БГ"


def test_lba_editor_keeps_explanatory_colour_label() -> None:
    labels = all_lba_color_labels(AppLanguage.RU)

    assert "БГ — беловато-голубой" in labels


def test_legacy_full_colour_label_is_normalized_for_graph_and_pdf() -> None:
    assert lba_color_code("БГ — беловато-голубой") == "БГ"
    assert lba_color_code("БГ - беловато голубой") == "БГ"
    assert lba_color_code("БГ") == "БГ"

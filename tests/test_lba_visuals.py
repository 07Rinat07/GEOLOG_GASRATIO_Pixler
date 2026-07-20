from geoworkbench.printing.lba_visuals import (
    LBA_TYPE_STYLES,
    lba_intensity_name,
    normalized_lba_intensity,
    resolve_lba_type_style,
)
from geoworkbench.services.localization import AppLanguage


def test_lba_type_aliases_resolve_to_reference_styles() -> None:
    assert resolve_lba_type_style("ЛБ").type_id == "light"
    assert resolve_lba_type_style("LB").type_id == "light"
    assert resolve_lba_type_style("LOB").code == "МБ"
    assert resolve_lba_type_style("MOB").code == "МСБ"
    assert resolve_lba_type_style("HOB").code == "СБ"
    assert resolve_lba_type_style("VHO").code == "САБ"
    assert len({item.color for item in LBA_TYPE_STYLES}) == 5


def test_lba_intensity_is_limited_to_five_reference_classes() -> None:
    assert normalized_lba_intensity(1) == 1
    assert normalized_lba_intensity(5) == 5
    assert normalized_lba_intensity(0) is None
    assert normalized_lba_intensity(6) is None
    assert normalized_lba_intensity(True) is None
    assert "ring" in lba_intensity_name(4, AppLanguage.EN)

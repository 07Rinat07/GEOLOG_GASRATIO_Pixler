import pytest

from geoworkbench.ui.branding import application_icon, logo_pixmap


def test_packaged_logo_loads_and_scales(qapp) -> None:
    original = logo_pixmap()
    scaled = logo_pixmap(128)

    assert not original.isNull()
    assert original.width() == 1254
    assert original.height() == 1254
    assert not scaled.isNull()
    assert scaled.width() <= 128
    assert scaled.height() <= 128
    assert not application_icon().isNull()


def test_logo_rejects_invalid_target_size(qapp) -> None:
    with pytest.raises(ValueError, match="положительным"):
        logo_pixmap(0)

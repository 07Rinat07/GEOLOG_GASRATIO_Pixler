from geoworkbench.services.text_normalization import clean_display_text, clean_mnemonic


def test_repairs_cp1251_bytes_decoded_as_latin1() -> None:
    damaged = "ДИАМЕТР".encode("cp1251").decode("latin1")
    assert clean_display_text(damaged) == "ДИАМЕТР"


def test_repairs_utf8_bytes_decoded_as_cp1251() -> None:
    damaged = "Давление".encode("utf-8").decode("cp1251")
    assert clean_display_text(damaged) == "Давление"


def test_mnemonic_removes_controls_and_spaces() -> None:
    assert clean_mnemonic("  Total\x00 Gas ") == "Total_Gas"

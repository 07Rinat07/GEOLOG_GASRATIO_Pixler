from geoworkbench.services.text_normalization import clean_display_text, clean_mnemonic


def test_repairs_cp1251_bytes_decoded_as_latin1() -> None:
    damaged = "ДИАМЕТР".encode("cp1251").decode("latin1")
    assert clean_display_text(damaged) == "ДИАМЕТР"


def test_repairs_utf8_bytes_decoded_as_cp1251() -> None:
    damaged = "Давление".encode("utf-8").decode("cp1251")
    assert clean_display_text(damaged) == "Давление"


def test_mnemonic_removes_controls_and_spaces() -> None:
    assert clean_mnemonic("  Total\x00 Gas ") == "Total_Gas"


def test_repairs_cp866_bytes_decoded_as_cp1251() -> None:
    damaged = "Скорость бурения".encode("cp866").decode("cp1251")
    assert clean_display_text(damaged) == "Скорость бурения"


def test_preserves_readable_russian_kazakh_and_english() -> None:
    for text in ("Положение талевого блока", "Қысым", "Rate of penetration"):
        assert clean_display_text(text) == text


def test_repairs_cp866_curve_description_and_mnemonic() -> None:
    damaged = "Гамма каротаж".encode("cp866").decode("cp1251")
    assert clean_display_text(damaged) == "Гамма каротаж"
    assert clean_mnemonic(damaged) == "Гамма_каротаж"

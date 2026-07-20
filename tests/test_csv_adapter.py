import numpy as np
import pytest

from geoworkbench.data.csv_adapter import CsvImportError, CsvImportPlan, import_csv, probe_csv
from geoworkbench.domain.models import IndexRole, IndexType


def test_probe_detects_delimiter_and_previews_columns(tmp_path) -> None:
    source = tmp_path / "logging.csv"
    source.write_text("DEPT;C1 [%];ROP [m/h]\n100;1.2;10\n101;1.3;11\n", encoding="utf-8")

    probe = probe_csv(source)

    assert probe.delimiter == ";"
    assert probe.columns == ("DEPT", "C1 [%]", "ROP [m/h]")
    assert probe.preview_rows[0] == ("100", "1.2", "10")


def test_import_csv_builds_typed_dataset_and_parses_units(tmp_path) -> None:
    source = tmp_path / "logging.csv"
    source.write_text(
        "DEPT,C1 [%],ROP [m/h]\n100,1.2,10\n101,-999.25,11\n",
        encoding="utf-8",
    )

    result = import_csv(source, CsvImportPlan(index_column="DEPT"))

    assert result.row_count == 2
    assert result.dataset.active_index.role is IndexRole.DEPTH
    assert result.dataset.active_index.index_type is IndexType.MD
    np.testing.assert_allclose(result.dataset.depth, [100.0, 101.0])
    c1 = result.dataset.curve_by_mnemonic("C1")
    assert c1 is not None and c1.metadata.unit == "%"
    assert np.isnan(c1.values[1])
    rop = result.dataset.curve_by_mnemonic("ROP")
    assert rop is not None and rop.metadata.unit == "m/h"


def test_import_csv_supports_decimal_comma_with_semicolon(tmp_path) -> None:
    source = tmp_path / "decimal.csv"
    source.write_text("DEPTH;C1\n100,5;1,25\n101,0;1,50\n", encoding="utf-8")

    result = import_csv(
        source,
        CsvImportPlan(delimiter=";", index_column="DEPTH"),
    )

    np.testing.assert_allclose(result.dataset.depth, [100.5, 101.0])
    np.testing.assert_allclose(result.dataset.curve_by_mnemonic("C1").values, [1.25, 1.5])


def test_import_csv_requires_index_and_valid_rectangular_numeric_data(tmp_path) -> None:
    source = tmp_path / "bad.csv"
    source.write_text("DEPT,C1\n100,text\n101\n", encoding="utf-8")

    with pytest.raises(CsvImportError, match="явно выбрать"):
        import_csv(source, CsvImportPlan())
    with pytest.raises(CsvImportError, match="ожидалось колонок"):
        import_csv(source, CsvImportPlan(index_column="DEPT"))

    source.write_text("DEPT,C1\n100,text\n", encoding="utf-8")
    with pytest.raises(CsvImportError, match="ожидалось число"):
        import_csv(source, CsvImportPlan(index_column="DEPT"))


def test_probe_rejects_duplicate_headers_and_wrong_encoding(tmp_path) -> None:
    duplicate = tmp_path / "duplicate.csv"
    duplicate.write_text("DEPT,dept\n1,2\n", encoding="utf-8")
    with pytest.raises(CsvImportError, match="повторяться"):
        probe_csv(duplicate)

    cp1251 = tmp_path / "russian.csv"
    cp1251.write_bytes("ГЛУБИНА;ГАЗ\n1;2\n".encode("cp1251"))
    with pytest.raises(CsvImportError, match="кодировке"):
        probe_csv(cp1251, CsvImportPlan(encoding="utf-8"))
    assert probe_csv(cp1251, CsvImportPlan(encoding="cp1251")).columns == ("ГЛУБИНА", "ГАЗ")


def test_plan_validates_delimiter() -> None:
    with pytest.raises(ValueError, match="одного символа"):
        CsvImportPlan(delimiter=";;")


def test_import_csv_accepts_iso8601_time_index_with_timezone(tmp_path) -> None:
    source = tmp_path / "time.csv"
    source.write_text(
        "RECORD_TIME,C1 [%]\n2026-07-15T10:00:00+05:00,1.2\n2026-07-15T10:00:01+05:00,1.3\n",
        encoding="utf-8",
    )

    result = import_csv(source, CsvImportPlan(index_column="RECORD_TIME"))

    index = result.dataset.active_index
    assert index.index_type is IndexType.DATETIME
    assert index.role is IndexRole.TIME
    assert index.datetime_format == "ISO8601"
    assert index.timezone == "UTC+05:00"
    np.testing.assert_array_equal(
        index.values,
        np.array(["2026-07-15T05:00:00", "2026-07-15T05:00:01"], dtype="datetime64[ns]"),
    )
    np.testing.assert_allclose(result.dataset.curve_by_mnemonic("C1").values, [1.2, 1.3])


def test_import_csv_keeps_naive_iso_time_without_assuming_utc(tmp_path) -> None:
    source = tmp_path / "naive.csv"
    source.write_text(
        "DATE,C1\n2026-07-15T10:00:00,1\n2026-07-15T10:00:01,2\n",
        encoding="utf-8",
    )

    result = import_csv(source, CsvImportPlan(index_column="DATE"))

    assert result.dataset.active_index.index_type is IndexType.DATETIME
    assert result.dataset.active_index.timezone is None


def test_import_csv_rejects_non_iso_string_index(tmp_path) -> None:
    source = tmp_path / "bad-time.csv"
    source.write_text("DATE,C1\n15.07.2026 10:00,1\n", encoding="utf-8")

    with pytest.raises(CsvImportError, match="ожидалось число"):
        import_csv(source, CsvImportPlan(index_column="DATE"))


def test_import_csv_combines_date_and_time_with_timezone(tmp_path) -> None:
    source = tmp_path / "composite.csv"
    source.write_text(
        "DATE;TIME;C1\n15.07.2026;10:00:00;1.2\n15.07.2026;10:00:01;1.3\n",
        encoding="utf-8",
    )

    result = import_csv(
        source,
        CsvImportPlan(
            delimiter=";",
            index_column="DATE",
            time_column="TIME",
            date_format="%d.%m.%Y",
            time_format="%H:%M:%S",
            timezone="Asia/Oral",
        ),
    )

    index = result.dataset.active_index
    assert index.mnemonic == "DATE_TIME"
    assert index.datetime_format == "%d.%m.%Y %H:%M:%S"
    assert index.timezone == "Asia/Oral"
    np.testing.assert_array_equal(
        index.values,
        np.array(["2026-07-15T05:00:00", "2026-07-15T05:00:01"], dtype="datetime64[ns]"),
    )
    assert result.dataset.curve_by_mnemonic("TIME") is None
    np.testing.assert_allclose(result.dataset.curve_by_mnemonic("C1").values, [1.2, 1.3])


def test_import_csv_validates_composite_time_mapping(tmp_path) -> None:
    source = tmp_path / "composite.csv"
    source.write_text("DATE,TIME,C1\n15.07.2026,10:00,1\n", encoding="utf-8")

    with pytest.raises(CsvImportError, match="должны различаться"):
        import_csv(source, CsvImportPlan(index_column="DATE", time_column="DATE"))
    with pytest.raises(CsvImportError, match="Строка 1"):
        import_csv(
            source,
            CsvImportPlan(index_column="DATE", time_column="TIME", timezone="UTC"),
        )

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from geoworkbench.importers.gs2.metadata import (
    AccessSnapshot,
    AccessTable,
    Gs2ChannelMetadata,
    Gs2Metadata,
    Gs2MetadataBackendUnavailable,
    Gs2MetadataState,
    _odbc_connection_string,
    annotate_gs2_dataset,
    channel_dictionary_for_table,
    channel_definitions_for_table,
    metadata_dataset_parameters,
    metadata_well_headers,
    read_gs2_metadata,
)


class _SnapshotBackend:
    def __init__(self, snapshot: AccessSnapshot) -> None:
        self.snapshot = snapshot

    def read(self, _source: Path) -> AccessSnapshot:
        return self.snapshot


class _UnavailableBackend:
    def read(self, _source: Path) -> AccessSnapshot:
        raise Gs2MetadataBackendUnavailable(
            "access-odbc-unavailable",
            "Access ODBC driver is missing",
            action="Install a matching-bitness Access Database Engine.",
            details=("64-bit application",),
        )


def test_access_odbc_connection_uses_unquoted_database_path() -> None:
    source = Path(r"C:\Temp Folder\GS2.mdb")

    connection = _odbc_connection_string(
        source,
        "Microsoft Access Driver (*.mdb, *.accdb)",
    )

    assert connection == (
        "DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
        r"DBQ=C:\Temp Folder\GS2.mdb;READONLY=TRUE;"
    )
    assert "DBQ={" not in connection


@dataclass(frozen=True)
class _Semantic:
    source_mnemonic: str
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class _CurveMetadata:
    provenance: str
    semantic: _Semantic | None


@dataclass
class _Curve:
    metadata: _CurveMetadata


@dataclass
class _Dataset:
    curves: dict[str, _Curve]


def test_access_snapshot_resolves_only_explicit_channels_for_selected_table(
    tmp_path: Path,
) -> None:
    source = tmp_path / "GS2.mdb"
    source.write_bytes(b"fixture")
    snapshot = AccessSnapshot(
        adapter="fixture",
        table_names=("CHANNELS", "FORMULAS", "WELLS"),
        tables=(
            AccessTable(
                "CHANNELS",
                (
                    {
                        "SOURCE_NAME": "S1",
                        "MNEMONIC": "C1",
                        "UNIT": "%",
                        "DESCRIPTION": "Methane",
                        "PARAMETERID": 1,
                        "SOURCE_MEMBER": "GS2#101.db",
                    },
                    {
                        "SOURCE_NAME": "S1",
                        "MNEMONIC": "ROP",
                        "UNIT": "m/h",
                        "DESCRIPTION": "Rate of penetration",
                        "PARAMETERID": 1,
                        "SOURCE_MEMBER": "GS2#113.db",
                    },
                ),
            ),
            AccessTable(
                "FORMULAS",
                (
                    {
                        "FORMULANAME": "Calculated gas",
                        "FORMULATEXT": "S1 * 2",
                        "RESGID": "2",
                        "SUBSET": "gas",
                    },
                    {
                        "FORMULANAME": "Unbound helper",
                        "FORMULATEXT": "S2 + 1",
                        "RESGID": None,
                    },
                ),
            ),
            AccessTable(
                "WELLS",
                (
                    {
                        "WELLID": "synthetic-001",
                        "WELLNAME": "SYNTHETIC-001",
                        "COUNTRY": "Testland",
                        "OILFIELD": "Synthetic Field",
                        "FIELD": "Synthetic Area",
                    },
                ),
            ),
        ),
    )

    metadata = read_gs2_metadata(source, backend=_SnapshotBackend(snapshot))

    assert metadata.state is Gs2MetadataState.LOADED
    assert len(metadata.channels) == 3
    assert len(metadata.formulas) == 2
    assert metadata.primary_well is not None
    definitions = channel_definitions_for_table(
        metadata,
        ("Time", "Depth", "S1", "S2"),
        "GS2#101.db",
    )
    by_source = {item.source: item for item in definitions}
    assert by_source["S1"].mnemonic == "C1"
    assert by_source["S1"].unit == "%"
    assert by_source["S2"].name_en == "Calculated gas"
    assert metadata_well_headers(metadata) == {
        "WELL": "SYNTHETIC-001",
        "FLD": "Synthetic Field",
        "LOC": "Synthetic Area",
        "CTRY": "Testland",
    }


def test_sensors_legacy_gid_fills_raw_gs2_channel_without_guessing(
    tmp_path: Path,
) -> None:
    source = tmp_path / "GS2.mdb"
    source.write_bytes(b"fixture")
    snapshot = AccessSnapshot(
        adapter="fixture",
        table_names=("LOGGINGSERVICE",),
        tables=(AccessTable("LOGGINGSERVICE", ({"STATIONMODEL": "GS2"},)),),
    )
    metadata = read_gs2_metadata(source, backend=_SnapshotBackend(snapshot))

    dictionary, metadata_count, sensor_count = channel_dictionary_for_table(
        metadata,
        ("Time", "S200", "SB5400"),
        "GS2#1_4.db",
    )

    assert metadata_count == 0
    assert sensor_count >= 1
    resolved = dictionary.resolve("S200")
    assert resolved is not None
    assert resolved.mnemonic == "HKLD"


def test_missing_access_driver_is_actionable_and_non_blocking(
    tmp_path: Path,
) -> None:
    source = tmp_path / "GS2.mdb"
    source.write_bytes(b"fixture")

    metadata = read_gs2_metadata(source, backend=_UnavailableBackend())

    assert metadata.state is Gs2MetadataState.UNAVAILABLE
    assert metadata.channels == ()
    assert metadata.diagnostics[0].code == "access-odbc-unavailable"
    assert "Install" in metadata.diagnostics[0].action
    parameters = metadata_dataset_parameters(metadata)
    assert parameters["GS2_METADATA_STATUS"] == "unavailable"
    assert "access-odbc-unavailable" in parameters["GS2_METADATA_DIAGNOSTICS"]


def test_exact_access_relation_is_retained_in_curve_provenance(
    tmp_path: Path,
) -> None:
    metadata = Gs2Metadata(
        source=tmp_path / "well.gs2",
        database_member="GS2.mdb",
        state=Gs2MetadataState.LOADED,
        channels=(
            Gs2ChannelMetadata(
                source_name="S1009",
                mnemonic="S1009",
                description="сумма ходов",
                parameter_id="1009",
                origin_table="FORMULAS",
            ),
        ),
    )
    dataset = _Dataset(
        curves={
            "curve": _Curve(
                _CurveMetadata("paradox:S1009:NUMBER", _Semantic("S1009"))
            )
        }
    )

    annotated = annotate_gs2_dataset(dataset, metadata, "GS2#101.db")

    assert annotated == 1
    curve_metadata = dataset.curves["curve"].metadata
    assert "gs2-mdb:FORMULAS:1009" in curve_metadata.provenance
    assert curve_metadata.semantic is not None
    assert "parameter_id=1009" in curve_metadata.semantic.evidence[0]


def test_loaded_database_without_channel_schema_reports_partial_fallback(
    tmp_path: Path,
) -> None:
    source = tmp_path / "GS2.mdb"
    source.write_bytes(b"fixture")
    snapshot = AccessSnapshot(
        adapter="fixture",
        table_names=("LOGGINGSERVICE",),
        tables=(AccessTable("LOGGINGSERVICE", ({"STATIONMODEL": "GS2"},)),),
    )

    metadata = read_gs2_metadata(source, backend=_SnapshotBackend(snapshot))

    assert metadata.state is Gs2MetadataState.PARTIAL
    assert metadata.diagnostics[0].code == "channel-schema-not-found"

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import zipfile

import numpy as np
import pytest

from geoworkbench.domain.models import IndexRole, IndexType
from geoworkbench.importers.witsml import WitsmlDataError, read_witsml_channel_sets
from geoworkbench.services.witsml_import_review import (
    WitsmlImportReviewController,
    WitsmlImportValidationError,
)


SAMPLE = Path("resources/samples/witsml/log_channel_set_2_1.xml")


def test_reads_embedded_channel_set_layout() -> None:
    package = read_witsml_channel_sets(SAMPLE)

    assert len(package.channel_sets) == 1
    channel_set = package.channel_sets[0]
    assert channel_set.title == "Depth drilling channels"
    assert channel_set.wellbore_title == "SG-8"
    assert len(channel_set.indexes) == 1
    assert len(channel_set.channels) == 3
    assert len(channel_set.rows) == 3
    assert channel_set.rows[0].index_values == (1000.0,)
    assert channel_set.rows[2].channel_values[0] is None
    assert channel_set.importable_channel_count == 2
    assert len(channel_set.source_sha256) == 64
    assert len(channel_set.data_sha256) == 64


def test_import_review_selects_numeric_channels_and_normalizes_uom() -> None:
    channel_set = read_witsml_channel_sets(SAMPLE).channel_sets[0]
    controller = WitsmlImportReviewController()
    plan = controller.initial_plan(channel_set)
    review = controller.preview(channel_set, plan)

    assert review.error_count == 0
    assert review.index_type is IndexType.MD
    assert review.index_role is IndexRole.DEPTH
    assert sum(item.import_enabled for item in review.channels) == 2
    state = next(item for item in review.channels if item.mnemonic == "STATE")
    assert not state.import_enabled

    commit = controller.commit(channel_set, plan)
    dataset = commit.dataset
    assert dataset.active_index.index_type is IndexType.MD
    np.testing.assert_allclose(dataset.active_index.values, [1000.0, 1000.5, 1001.0])
    rop = dataset.curve_by_mnemonic("ROP")
    np.testing.assert_allclose(rop.values[:2], [10.0, 12.0], rtol=1e-8)
    assert np.isnan(rop.values[2])
    assert rop.metadata.unit == "m/h"
    np.testing.assert_allclose(dataset.curve_by_mnemonic("WOB").values, [75.0, 76.0, 77.0])
    assert dataset.parameters["WITSML_DATA_LAYOUT"] == "[[indexes],[channels]]"
    assert dataset.parameters["WITSML_DATASET_DIGEST"] == commit.dataset_digest


def test_commit_is_deterministic_for_same_plan() -> None:
    channel_set = read_witsml_channel_sets(SAMPLE).channel_sets[0]
    controller = WitsmlImportReviewController()
    plan = controller.initial_plan(channel_set)

    first = controller.commit(channel_set, plan)
    second = controller.commit(channel_set, plan)

    assert first.dataset_digest == second.dataset_digest
    np.testing.assert_array_equal(first.dataset.active_index.values, second.dataset.active_index.values)


def test_enabling_string_channel_is_blocked() -> None:
    channel_set = read_witsml_channel_sets(SAMPLE).channel_sets[0]
    controller = WitsmlImportReviewController()
    plan = controller.initial_plan(channel_set)
    channels = tuple(
        replace(item, import_enabled=True) if channel_set.channels[index].mnemonic == "STATE" else item
        for index, item in enumerate(plan.channels)
    )
    invalid = replace(plan, channels=channels)

    review = controller.preview(channel_set, invalid)
    assert review.error_count >= 1
    with pytest.raises(WitsmlImportValidationError):
        controller.commit(channel_set, invalid)


def test_reads_relative_external_json_from_epc(tmp_path: Path) -> None:
    xml = SAMPLE.read_text(encoding="utf-8")
    embedded = xml.split("<Data>\n      <Data>", 1)[1].split("</Data>\n    </Data>", 1)[0]
    external_xml = xml.replace(
        f"<Data>\n      <Data>{embedded}</Data>\n    </Data>",
        "<Data><FileUri>./data/rows.json</FileUri></Data>",
    )
    package_path = tmp_path / "sample.epc"
    with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("objects/log.xml", external_xml)
        archive.writestr("objects/data/rows.json", embedded)

    package = read_witsml_channel_sets(package_path)
    assert len(package.channel_sets[0].rows) == 3


def test_rejects_external_path_traversal(tmp_path: Path) -> None:
    xml = SAMPLE.read_text(encoding="utf-8")
    start = xml.index("    <Data>")
    end = xml.index("    </Data>", start) + len("    </Data>")
    xml = xml[:start] + "    <Data><FileUri>../../outside.json</FileUri></Data>" + xml[end:]
    source = tmp_path / "unsafe.xml"
    source.write_text(xml, encoding="utf-8")

    with pytest.raises(WitsmlDataError, match="No readable"):
        read_witsml_channel_sets(source)


def test_invalid_index_row_is_preserved_for_review_and_dropped_on_commit(tmp_path: Path) -> None:
    xml = SAMPLE.read_text(encoding="utf-8").replace(
        '[[1000.5], [39.37007874, 76.0, "drilling"]]',
        '[[null], [39.37007874, 76.0, "drilling"]]',
    )
    source = tmp_path / "invalid-index.xml"
    source.write_text(xml, encoding="utf-8")

    channel_set = read_witsml_channel_sets(source).channel_sets[0]
    assert len(channel_set.rows) == 3
    assert any(issue.code == "invalid-index-value" for issue in channel_set.issues)

    controller = WitsmlImportReviewController()
    plan = controller.initial_plan(channel_set)
    review = controller.preview(channel_set, plan)
    assert review.import_row_count == 2
    assert review.skipped_row_count == 1

    commit = controller.commit(channel_set, plan)
    np.testing.assert_allclose(commit.dataset.active_index.values, [1000.0, 1001.0])
    assert commit.dataset.parameters["WITSML_ROWS_SKIPPED"] == "1"


def test_reads_utc_time_index_and_builds_datetime_dataset(tmp_path: Path) -> None:
    xml = '''<?xml version="1.0" encoding="UTF-8"?>
<ChannelSet xmlns="http://www.energistics.org/energyml/data/witsmlv2"
 xmlns:eml="http://www.energistics.org/energyml/data/commonv2"
 schemaVersion="2.1" uuid="time-set">
 <eml:Citation><eml:Title>Time channels</eml:Title></eml:Citation>
 <Index><IndexType>date time</IndexType><Mnemonic>TIME</Mnemonic><Direction>increasing</Direction></Index>
 <Channel uuid="gas"><Mnemonic>TGAS</Mnemonic><DataType>double</DataType><Uom>%</Uom></Channel>
 <Data><Data>[
   [["2026-07-27T04:00:00Z"],[1.5]],
   [["2026-07-27T04:00:01+00:00"],[1.7]]
 ]</Data></Data>
</ChannelSet>'''
    source = tmp_path / "time.xml"
    source.write_text(xml, encoding="utf-8")

    channel_set = read_witsml_channel_sets(source).channel_sets[0]
    controller = WitsmlImportReviewController()
    commit = controller.commit(channel_set, controller.initial_plan(channel_set))

    index = commit.dataset.active_index
    assert index.index_type is IndexType.DATETIME
    assert index.role is IndexRole.TIME
    assert index.timezone == "UTC"
    assert str(index.values.dtype) == "datetime64[ns]"
    assert index.values[1] - index.values[0] == np.timedelta64(1, "s")


def test_embedded_json_string_whitespace_is_preserved(tmp_path: Path) -> None:
    xml = '''<ChannelSet xmlns="http://www.energistics.org/energyml/data/witsmlv2"
 xmlns:eml="http://www.energistics.org/energyml/data/commonv2" schemaVersion="2.1">
 <eml:Citation><eml:Title>Text preservation</eml:Title></eml:Citation>
 <Index><IndexType>measured depth</IndexType><Mnemonic>MD</Mnemonic><Uom>m</Uom></Index>
 <Channel><Mnemonic>STATE</Mnemonic><DataType>string</DataType><Uom>1</Uom></Channel>
 <Data><Data>[[[1.0],["on  bottom"]]]</Data></Data>
</ChannelSet>'''
    source = tmp_path / "text.xml"
    source.write_text(xml, encoding="utf-8")

    row = read_witsml_channel_sets(source).channel_sets[0].rows[0]
    assert row.channel_values == ("on  bottom",)


def test_operator_can_select_secondary_depth_index(tmp_path: Path) -> None:
    xml = '''<ChannelSet xmlns="http://www.energistics.org/energyml/data/witsmlv2"
 xmlns:eml="http://www.energistics.org/energyml/data/commonv2" schemaVersion="2.1">
 <eml:Citation><eml:Title>Dual index channels</eml:Title></eml:Citation>
 <Index><IndexType>date time</IndexType><Mnemonic>TIME</Mnemonic><Direction>increasing</Direction></Index>
 <Index><IndexType>measured depth</IndexType><Mnemonic>MD</Mnemonic><Uom>ft</Uom><Direction>increasing</Direction></Index>
 <Channel><Mnemonic>ROP</Mnemonic><DataType>double</DataType><Uom>ft/h</Uom></Channel>
 <Data><Data>[
  [["2026-07-27T04:00:00Z",3280.839895],[32.80839895]],
  [["2026-07-27T04:00:01Z",3282.480315],[39.37007874]]
 ]</Data></Data>
</ChannelSet>'''
    source = tmp_path / "dual.xml"
    source.write_text(xml, encoding="utf-8")

    channel_set = read_witsml_channel_sets(source).channel_sets[0]
    controller = WitsmlImportReviewController()
    initial = controller.initial_plan(channel_set)
    assert initial.index_type is IndexType.DATETIME

    depth_plan = controller.plan_for_index(channel_set, initial, channel_set.indexes[1].key)
    commit = controller.commit(channel_set, depth_plan)
    assert commit.dataset.active_index.index_type is IndexType.MD
    assert commit.dataset.active_index.unit == "ft"
    np.testing.assert_allclose(commit.dataset.active_index.values, [3280.839895, 3282.480315])

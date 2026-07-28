from __future__ import annotations

import pytest

from geoworkbench.importers.etp12.models import Etp12ChannelMetadata
from geoworkbench.services.etp12_import_review import Etp12DiscoveryAccumulator
from geoworkbench.ui.etp12_dialog import _channel_uri_payload
from geoworkbench.ui.etp12_import_review_dialog import Etp12ImportReviewDialog


def _snapshot():
    discovery = Etp12DiscoveryAccumulator("ui-test")
    discovery.update_metadata(
        (
            Etp12ChannelMetadata(
                channel_id=10,
                channel_uri="eml:///witsml21.Channel(rop)",
                channel_name="ROP",
                data_kind="double",
                uom="m/h",
                index_kind="dateTime",
                start_index=1_000_000,
                end_index=2_000_000,
                index_uom="us",
            ),
        ),
        generation=1,
    )
    return discovery.snapshot()


def test_channel_uri_payload_rejects_untyped_worker_values() -> None:
    assert _channel_uri_payload(("a", "b")) == ("a", "b")

    with pytest.raises(TypeError, match="must be a tuple"):
        _channel_uri_payload(["a"])
    with pytest.raises(TypeError, match="must contain strings"):
        _channel_uri_payload(("a", 1))


def test_import_review_reports_missing_table_cell(qapp) -> None:
    dialog = Etp12ImportReviewDialog(_snapshot())
    removed = dialog.table.takeItem(0, 6)
    assert removed is not None

    with pytest.raises(ValueError, match=r"table cell \(0, 6\) is missing"):
        dialog._collect_plan()

    dialog.close()

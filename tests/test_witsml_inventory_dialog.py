from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from geoworkbench.services.localization import AppLanguage
from geoworkbench.ui.witsml_inventory_dialog import WitsmlInventoryDialog


WITSML_NS = "http://www.energistics.org/energyml/data/witsmlv2"
COMMON_NS = "http://www.energistics.org/energyml/data/commonv2"


def test_dialog_presents_object_channel_and_diagnostics_tabs(
    qapp: object,
    tmp_path: Path,
) -> None:
    source = tmp_path / "channel.xml"
    source.write_text(
        f"""<Channel xmlns="{WITSML_NS}"
                    xmlns:eml="{COMMON_NS}"
                    schemaVersion="2.1"
                    uuid="0d4d2c32-47a8-4fc9-9f48-42a00a6ebdda">
  <eml:Citation><eml:Title>Bit depth</eml:Title></eml:Citation>
  <Mnemonic>DEPT</Mnemonic>
  <DataType>double</DataType>
  <Uom>m</Uom>
  <Index>
    <IndexType>measured depth</IndexType>
    <Mnemonic>DEPT</Mnemonic>
    <Uom>m</Uom>
  </Index>
</Channel>""",
        encoding="utf-8",
    )

    dialog = WitsmlInventoryDialog(source, language=AppLanguage.EN)

    assert dialog.inventory is not None
    assert dialog.error is None
    assert dialog.objects_tree.topLevelItemCount() == 1
    assert dialog.channels_tree.topLevelItemCount() == 1
    assert dialog.tabs.count() == 3
    assert "1 objects" in dialog.summary.text()


def test_dialog_displays_safe_error_for_invalid_source(
    qapp: object,
    tmp_path: Path,
) -> None:
    source = tmp_path / "invalid.xml"
    source.write_text("<root/>", encoding="utf-8")

    dialog = WitsmlInventoryDialog(source, language=AppLanguage.RU)

    assert dialog.inventory is None
    assert dialog.error is not None
    assert "WITSML 2.x" in dialog.summary.text()

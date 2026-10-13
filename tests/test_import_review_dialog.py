from pathlib import Path

import numpy as np

from geoworkbench.domain.models import (
    CurveData,
    CurveMetadata,
    Dataset,
    DatasetKind,
    DepthDomain,
)
from geoworkbench.services.import_jobs import ImportSourceKind
from geoworkbench.services.semantic_channels import SemanticChannelDictionary
from geoworkbench.ui.import_review_dialog import ImportReviewDialog


def _dataset() -> Dataset:
    dataset = Dataset(
        "compact-review",
        "Compact review",
        DatasetKind.USER,
        DepthDomain.MD,
        np.array([100.0, 101.0, 102.0]),
    )
    semantic = SemanticChannelDictionary().resolve("ROP", unit="m/h")
    dataset.curves = {
        "rop": CurveData(
            CurveMetadata(
                "rop",
                "ROP",
                semantic.canonical_mnemonic,
                "m/h",
                "Rate of penetration",
                dataset.dataset_id,
                semantic=semantic,
            ),
            np.array([5.0, 6.0, 7.0]),
        )
    }
    return dataset


def test_import_review_starts_compact_and_keeps_primary_data_visible(qapp) -> None:
    dialog = ImportReviewDialog(
        _dataset(),
        Path("well.las"),
        ImportSourceKind.LAS,
    )

    assert dialog.index_section.is_expanded() is False
    assert dialog.channel_section.is_expanded() is False
    assert dialog.qc_section.is_expanded() is False
    assert dialog.review_summary.isHidden() is False
    assert dialog.channel_table.isHidden() is False
    assert dialog.channel_table.rowCount() == 1
    assert all(dialog.channel_table.isColumnHidden(column) for column in (6, 7, 8))

    dialog.close()


def test_import_review_reveals_technical_details_on_demand(qapp) -> None:
    dialog = ImportReviewDialog(
        _dataset(),
        Path("well.las"),
        ImportSourceKind.LAS,
    )

    dialog.index_section.set_expanded(True)
    dialog.channel_section.set_expanded(True)
    dialog.technical_columns_toggle.setChecked(True)

    assert dialog.index_section.is_expanded() is True
    assert dialog.channel_section.is_expanded() is True
    assert all(
        not dialog.channel_table.isColumnHidden(column) for column in (6, 7, 8)
    )

    dialog.close()


def test_import_review_capabilities_use_source_version_and_keep_data(qapp) -> None:
    from geoworkbench.services.localization import AppLanguage

    for language in AppLanguage:
        dataset = _dataset()
        dataset.version_headers["VERS"] = "3.0"
        before = dataset.depth.copy()
        dialog = ImportReviewDialog(dataset, Path("looks_like_2.0.las"),
                                    ImportSourceKind.LAS, language=language)
        text = dialog.format_capabilities_summary.text()
        assert "3.0" in text
        assert dialog._t("import_review.capability_unverified") in text
        assert dialog._t("import_review.capability_unavailable") in text
        assert text == dialog._t(
            "import_review.format_capabilities", format="LAS", version="3.0",
            read=dialog._t("import_review.capability_unverified"),
            edit=dialog._t("import_review.capability_unverified"),
            write=dialog._t("import_review.capability_unavailable"),
            export=dialog._t("import_review.capability_limited"),
        )
        np.testing.assert_array_equal(dataset.depth, before)
        dialog.reject()
        dialog.close()

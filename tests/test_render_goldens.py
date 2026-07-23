from __future__ import annotations

import json
from pathlib import Path

import pytest

from geoworkbench.services.render_goldens import (
    PX_TO_MM,
    build_golden_documents,
    expected_golden_files,
    verify_golden_fixture,
    write_golden_fixtures,
)


GOLDEN_DIR = Path(__file__).with_name("golden_rendering")


def test_committed_render_goldens_match_deterministic_generator(tmp_path: Path) -> None:
    generated = tmp_path / "golden_rendering"
    write_golden_fixtures(generated)

    assert tuple(sorted(path.name for path in GOLDEN_DIR.iterdir())) == tuple(
        sorted(expected_golden_files())
    )
    for filename in expected_golden_files():
        assert (generated / filename).read_bytes() == (GOLDEN_DIR / filename).read_bytes()


def test_json_goldens_have_valid_payload_checksums() -> None:
    for filename in build_golden_documents():
        assert verify_golden_fixture(GOLDEN_DIR / filename) == ()


def test_grid_golden_preserves_same_normalized_screen_print_contract() -> None:
    payload = _payload("grid_screen_print_v1.json")
    signature = payload["normalized_signature"]
    screen = payload["screen"]
    printed = payload["print"]

    assert len(signature) == 21
    assert sum(1 for line in signature if line["major"]) == 5
    assert [line["major"] for line in screen["x_lines"]] == [
        line["major"] for line in printed["x_lines"]
    ]
    screen_rect = screen["rect"]
    print_rect = printed["rect"]
    for normalized, screen_line, print_line in zip(
        signature,
        screen["x_lines"],
        printed["x_lines"],
        strict=True,
    ):
        screen_fraction = (
            screen_line["position"] - screen_rect["left"]
        ) / screen_rect["width"]
        print_fraction = (
            print_line["position"] - print_rect["left"]
        ) / print_rect["width"]
        assert screen_fraction == pytest.approx(normalized["fraction"])
        assert print_fraction == pytest.approx(normalized["fraction"])


def test_legend_golden_is_localized_ordered_and_deduplicated() -> None:
    payload = _payload("legend_multilingual_v1.json")
    entries = payload["entries"]

    assert [item["lithotype_id"] for item in entries["ru"]] == [
        "sandstone",
        "clay",
        "legacy_rock",
        "dolomite",
    ]
    assert entries["ru"][0]["name"] == "Песчаник"
    assert entries["kk"][0]["name"] == "Құмтас"
    assert entries["en"][0]["name"] == "Sandstone"
    assert entries["en"][2] == {
        "code": "legacy_rock",
        "color": "#b0b0b0",
        "lithotype_id": "legacy_rock",
        "name": "Legacy breccia / Наследованная брекчия",
        "pattern_key": "solid",
    }


def test_lithotype_golden_pins_bitmap_identity_and_physical_tile_size() -> None:
    payload = _payload("lithotype_patterns_v1.json")
    patterns = {item["requested_key"]: item for item in payload["patterns"]}
    sandstone = patterns["sandstone_bricks"]

    assert sandstone["resolved_key"] == "constructor:lithology-sandstone"
    assert sandstone["kind"] == "bitmap"
    assert len(sandstone["content_sha256"]) == 64
    assert sandstone["print_tile_mm_at_96dpi"][0] == pytest.approx(
        sandstone["screen_tile_px"][0] * PX_TO_MM,
        abs=1e-6,
    )
    assert patterns["unknown-pattern"]["resolved_key"] == "solid"


def test_annotation_golden_uses_same_reference_pixel_geometry_for_print() -> None:
    payload = _payload("annotations_screen_print_v1.json")
    annotations = {item["annotation_id"]: item for item in payload["annotations"]}
    callout = annotations["callout-gas"]

    screen = callout["screen"]
    printed = callout["print"]
    assert printed["box"]["width"] / PX_TO_MM == pytest.approx(
        screen["box"]["width"],
        abs=1e-5,
    )
    assert printed["box"]["height"] / PX_TO_MM == pytest.approx(
        screen["box"]["height"],
        abs=1e-5,
    )
    assert annotations["comment-note"]["screen"]["leader_endpoint"] is None
    assert annotations["comment-note"]["print"]["leader_endpoint"] is None
    assert annotations["warning-rotated"]["rotation_degrees"] == 12.0


def test_golden_payloads_contain_no_machine_specific_or_time_fields() -> None:
    forbidden = ("/mnt/", "\\\\", "created_at", "generated_at", "timestamp")
    for filename in build_golden_documents():
        text = (GOLDEN_DIR / filename).read_text(encoding="utf-8").casefold()
        assert all(token.casefold() not in text for token in forbidden)


def _payload(filename: str) -> dict[str, object]:
    document = json.loads((GOLDEN_DIR / filename).read_text(encoding="utf-8"))
    return document["payload"]

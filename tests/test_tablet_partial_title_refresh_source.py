from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _method_body(source: str, name: str, next_name: str) -> str:
    start = source.index(f"    def {name}(")
    end = source.index(f"    def {next_name}(", start)
    return source[start:end]


def test_tablet_rename_actions_prefer_partial_refresh_paths() -> None:
    source = (ROOT / "src/geoworkbench/ui/main_window.py").read_text(
        encoding="utf-8"
    )

    rename_track = _method_body(
        source,
        "_rename_live_track",
        "_rename_live_track_group",
    )
    rename_group = _method_body(
        source,
        "_rename_live_track_group",
        "_show_track_properties_from_context",
    )

    assert "refresh_track(" in rename_track
    assert "DirtyReason.STATIC" in rename_track
    assert "if not self.tablet_view.refresh_track(" in rename_track

    assert "refresh_group_headers()" in rename_group
    assert "refresh_view()" not in rename_group

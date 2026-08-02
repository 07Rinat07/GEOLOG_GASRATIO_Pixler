from __future__ import annotations

from pathlib import Path
import re
import subprocess


SOURCE_COMMIT = "1124c5a1d106bce782de9714c9ccf93a272df61c"
SOURCE_PATH = "tools/_integrate_tablet_shared_ruler.py"
TABLET_VIEW = Path("src/geoworkbench/tablet/tablet_view.py")
TEST_PATH = Path("tests/test_tablet_shared_vertical_ruler.py")


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"{path}: expected one replacement, found {count}: {old[:100]!r}"
        )
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_regex_once(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)
    if count != 1:
        raise RuntimeError(f"{path}: expected one regex replacement, found {count}")
    path.write_text(updated, encoding="utf-8")


def main() -> None:
    source = subprocess.run(
        ["git", "show", f"{SOURCE_COMMIT}:{SOURCE_PATH}"],
        text=True,
        capture_output=True,
        check=False,
    )
    if source.returncode != 0:
        raise RuntimeError(source.stderr.strip() or "Could not load integration script")
    namespace = {"__name__": "__main__", "__file__": SOURCE_PATH}
    exec(compile(source.stdout, SOURCE_PATH, "exec"), namespace)

    replace_once(TABLET_VIEW, "    format_datetime_axis_tick,\n", "")
    replace_once(TABLET_VIEW, "    adaptive_aligned_step,\n", "")
    replace_once(
        TABLET_VIEW,
        "    VerticalRulerMode,\n"
        "    VerticalRulerTrackSettings,\n",
        "    VerticalRulerMode,\n"
        "    VerticalRulerTick,\n"
        "    VerticalRulerTrackSettings,\n",
    )
    replace_once(
        TABLET_VIEW,
        "        self.descriptor = descriptor\n"
        "        self._shared_layout: VerticalRulerLayout | None = None\n",
        "        self.descriptor = descriptor\n"
        "        self._shared_layout: VerticalRulerLayout | None = None\n"
        "        self._resolved_ticks: tuple[VerticalRulerTick, ...] = ()\n",
    )
    replace_once(
        TABLET_VIEW,
        "    @property\n"
        "    def shared_layout(self) -> VerticalRulerLayout | None:\n"
        "        return self._shared_layout\n\n"
        "    def clear_shared_layout(self) -> None:\n"
        "        self._shared_layout = None\n"
        "        self.setTicks(None)\n",
        "    @property\n"
        "    def shared_layout(self) -> VerticalRulerLayout | None:\n"
        "        return self._shared_layout\n\n"
        "    @property\n"
        "    def resolved_ticks(self) -> tuple[VerticalRulerTick, ...]:\n"
        "        return self._resolved_ticks\n\n"
        "    def clear_shared_layout(self) -> None:\n"
        "        self._shared_layout = None\n"
        "        self._resolved_ticks = ()\n"
        "        self.setTicks(None)\n",
    )
    replace_once(
        TABLET_VIEW,
        "        visible_ticks = visible_vertical_ruler_ticks(layout, settings)\n"
        "        major_ticks = [\n"
        "            (tick.value, tick.label if show_labels else \"\")\n"
        "            for tick in visible_ticks\n"
        "            if tick.major\n"
        "        ]\n"
        "        minor_ticks = [\n"
        "            (tick.value, \"\")\n"
        "            for tick in visible_ticks\n"
        "            if not tick.major\n"
        "        ]\n",
        "        visible_ticks = visible_vertical_ruler_ticks(layout, settings)\n"
        "        self._resolved_ticks = tuple(\n"
        "            VerticalRulerTick(\n"
        "                value=tick.value,\n"
        "                major=tick.major,\n"
        "                label=tick.label if show_labels else \"\",\n"
        "                major_index=tick.major_index,\n"
        "                minor_index=tick.minor_index,\n"
        "            )\n"
        "            for tick in visible_ticks\n"
        "        )\n"
        "        major_ticks = [\n"
        "            (tick.value, tick.label)\n"
        "            for tick in self._resolved_ticks\n"
        "            if tick.major\n"
        "        ]\n"
        "        minor_ticks = [\n"
        "            (tick.value, \"\")\n"
        "            for tick in self._resolved_ticks\n"
        "            if not tick.major\n"
        "        ]\n",
    )

    replace_regex_once(
        TEST_PATH,
        r"def _axis_values\(axis: TabletVerticalAxisItem\) -> tuple\[float, \.\.\.\]:.*?\n\n(?=def _axis_labels)",
        "def _axis_values(axis: TabletVerticalAxisItem) -> tuple[float, ...]:\n"
        "    return tuple(tick.value for tick in axis.resolved_ticks)\n\n",
    )
    replace_regex_once(
        TEST_PATH,
        r"def _axis_labels\(axis: TabletVerticalAxisItem\) -> tuple\[str, \.\.\.\]:.*?\n\n(?=def test_depth)",
        "def _axis_labels(axis: TabletVerticalAxisItem) -> tuple[str, ...]:\n"
        "    return tuple(tick.label for tick in axis.resolved_ticks if tick.label)\n\n",
    )


if __name__ == "__main__":
    main()

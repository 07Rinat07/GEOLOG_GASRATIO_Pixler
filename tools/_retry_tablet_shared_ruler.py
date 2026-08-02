from __future__ import annotations

from pathlib import Path
import subprocess


SOURCE_COMMIT = "1124c5a1d106bce782de9714c9ccf93a272df61c"
SOURCE_PATH = "tools/_integrate_tablet_shared_ruler.py"
TABLET_VIEW = Path("src/geoworkbench/tablet/tablet_view.py")


def replace_once(old: str, new: str) -> None:
    text = TABLET_VIEW.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"tablet_view.py: expected one replacement, found {count}: {old!r}"
        )
    TABLET_VIEW.write_text(text.replace(old, new, 1), encoding="utf-8")


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
    replace_once("    format_datetime_axis_tick,\n", "")
    replace_once("    adaptive_aligned_step,\n", "")


if __name__ == "__main__":
    main()

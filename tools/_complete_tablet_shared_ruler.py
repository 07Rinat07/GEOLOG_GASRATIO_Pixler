from __future__ import annotations

from pathlib import Path
import subprocess


SOURCE_COMMIT = "7a150c8a0748a6a971de89d3f78215bd192e6b41"
SOURCE_PATH = "tools/_finalize_tablet_shared_ruler.py"
RULER = Path("src/geoworkbench/tablet/vertical_ruler.py")


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"{path}: expected one replacement, found {count}: {old[:100]!r}"
        )
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


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

    replace_once(
        RULER,
        "        threshold = 92 if layout.kind is VerticalRulerKind.DATETIME else 76\n",
        "        threshold = 120 if layout.kind is VerticalRulerKind.DATETIME else 92\n",
    )


if __name__ == "__main__":
    main()

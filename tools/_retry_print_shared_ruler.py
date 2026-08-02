from __future__ import annotations

import subprocess


SOURCE_COMMIT = "98efa71be54e4d804358ff9e6fbb8ebd5a817b5d"
SOURCE_PATH = "tools/_integrate_print_shared_ruler.py"


def main() -> None:
    source = subprocess.run(
        ["git", "show", f"{SOURCE_COMMIT}:{SOURCE_PATH}"],
        text=True,
        capture_output=True,
        check=False,
    )
    if source.returncode != 0:
        raise RuntimeError(source.stderr.strip() or "Could not load print integration script")

    old = '''    text = TABLET_PRINT.read_text(encoding="utf-8")
    activation = "        _activate_layout_tree(tablet)\\n"
    count = text.count(activation)
    if count < 2:
        raise RuntimeError(
            f"tablet_print.py: expected at least two layout activations, found {count}"
        )
    text = text.replace(
        activation,
        activation + "        tablet.refresh_shared_vertical_rulers()\\n",
    )
    TABLET_PRINT.write_text(text, encoding="utf-8")
'''
    new = '''    replace_once(
        TABLET_PRINT,
        "        _activate_layout_tree(tablet)\\n\\n"
        "        content_height = max(item.widget.height() for item in rendered)\\n",
        "        _activate_layout_tree(tablet)\\n"
        "        tablet.refresh_shared_vertical_rulers()\\n\\n"
        "        content_height = max(item.widget.height() for item in rendered)\\n",
    )
    replace_once(
        TABLET_PRINT,
        "                _activate_layout_tree(tablet)\\n"
        "            content_height = max(item.widget.height() for item in rendered)\\n",
        "                _activate_layout_tree(tablet)\\n"
        "                tablet.refresh_shared_vertical_rulers()\\n"
        "            content_height = max(item.widget.height() for item in rendered)\\n",
    )
    replace_once(
        TABLET_PRINT,
        "        _activate_layout_tree(tablet)\\n\\n"
        "    if layout is None:\\n",
        "        _activate_layout_tree(tablet)\\n"
        "        tablet.refresh_shared_vertical_rulers()\\n\\n"
        "    if layout is None:\\n",
    )
'''
    if source.stdout.count(old) != 1:
        raise RuntimeError("Original blanket activation patch was not found exactly once")
    corrected = source.stdout.replace(old, new, 1)
    namespace = {"__name__": "__main__", "__file__": SOURCE_PATH}
    exec(compile(corrected, SOURCE_PATH, "exec"), namespace)


if __name__ == "__main__":
    main()

from __future__ import annotations

from pathlib import Path
import subprocess


SOURCE_COMMIT = "88e2b1a50ce73708f2b6115c1120b60d46388e4d"
SOURCE_PATH = "tools/_integrate_gas_continuity_policy.py"


def replace_once(source: str, old: str, new: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one source replacement, found {count}: {old!r}")
    return source.replace(old, new, 1)


def main() -> None:
    result = subprocess.run(
        ["git", "show", f"{SOURCE_COMMIT}:{SOURCE_PATH}"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Could not load continuity source")
    source = result.stdout
    source = replace_once(
        source,
        'anchor = "## 13. Финальный критерий передачи\\n"',
        'anchor = "## 13. Правило обновления тестов и документации\\n"',
    )
    source = replace_once(
        source,
        '"## 14. Финальный критерий передачи\\n"',
        '"## 14. Правило обновления тестов и документации\\n"',
    )
    old_import = (
        '        "from geoworkbench.calculations.curve_continuity import (\\n"\n'
        '        "    CurveContinuityPolicy,\\n"\n'
        '        "    estimate_short_gap_limit,\\n"\n'
        '        "    interpolate_bounded_gaps,\\n"\n'
        '        "    interpolate_monotonic_unique,\\n"\n'
    )
    new_import = (
        '        "from geoworkbench.calculations.curve_continuity import (\\n"\n'
        '        "    CurveContinuityPolicy,\\n"\n'
        '        "    estimate_short_gap_limit,\\n"\n'
        '        "    interpolate_bounded_gaps as interpolate_bounded_gaps,\\n"\n'
        '        "    interpolate_monotonic_unique,\\n"\n'
    )
    source = replace_once(source, old_import, new_import)
    source = replace_once(
        source,
        '        "            connect: str | NDArray[np.bool_] = \\\"finite\\\"\\n"\n',
        '        "            connect: object = \\\"finite\\\"\\n"\n',
    )

    namespace = {"__name__": "__main__", "__file__": SOURCE_PATH}
    exec(compile(source, SOURCE_PATH, "exec"), namespace)

    testing = Path("docs/TESTING.md")
    text = testing.read_text(encoding="utf-8")
    old_heading = "## 14. Каталоги печатных шапок и логотипов\n"
    if text.count(old_heading) != 1:
        raise RuntimeError("TESTING.md print catalog heading not found exactly once")
    testing.write_text(
        text.replace(old_heading, "## 15. Каталоги печатных шапок и логотипов\n", 1),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

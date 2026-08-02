from __future__ import annotations

from pathlib import Path
import subprocess


SOURCE_COMMIT = "88e2b1a50ce73708f2b6115c1120b60d46388e4d"
SOURCE_PATH = "tools/_integrate_gas_continuity_policy.py"


def main() -> None:
    source = subprocess.run(
        ["git", "show", f"{SOURCE_COMMIT}:{SOURCE_PATH}"],
        text=True,
        capture_output=True,
        check=False,
    )
    if source.returncode != 0:
        raise RuntimeError(source.stderr.strip() or "Could not load continuity script")
    corrected = source.stdout.replace(
        'anchor = "## 13. Финальный критерий передачи\\n"',
        'anchor = "## 13. Правило обновления тестов и документации\\n"',
        1,
    ).replace(
        '"## 14. Финальный критерий передачи\\n"',
        '"## 14. Правило обновления тестов и документации\\n"',
        1,
    )
    namespace = {"__name__": "__main__", "__file__": SOURCE_PATH}
    exec(compile(corrected, SOURCE_PATH, "exec"), namespace)

    testing = Path("docs/TESTING.md")
    text = testing.read_text(encoding="utf-8")
    old = "## 14. Каталоги печатных шапок и логотипов\n"
    if text.count(old) != 1:
        raise RuntimeError("TESTING.md print catalog heading not found exactly once")
    testing.write_text(
        text.replace(old, "## 15. Каталоги печатных шапок и логотипов\n", 1),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import textwrap


SOURCE_COMMIT = "8d43b6269dc3249d51d81b78a6a52ba7bbcd6598"
SOURCE_PATH = ".github/workflows/integrate-ruler-editor-controls.yml"


def main() -> int:
    source = subprocess.run(
        ["git", "show", f"{SOURCE_COMMIT}:{SOURCE_PATH}"],
        text=True,
        capture_output=True,
        check=False,
    )
    if source.returncode != 0:
        sys.stderr.write(source.stderr)
        return source.returncode

    lines = source.stdout.splitlines()
    try:
        start = next(index for index, line in enumerate(lines) if "$patch = @'" in line) + 1
        end = next(
            index
            for index in range(start, len(lines))
            if lines[index].strip() == "'@"
        )
    except StopIteration:
        sys.stderr.write("Embedded patch block was not found\n")
        return 2

    patch = textwrap.dedent("\n".join(lines[start:end])) + "\n"
    result = subprocess.run(
        [sys.executable, "-"],
        input=patch,
        text=True,
        capture_output=True,
        check=False,
    )
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

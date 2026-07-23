from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    source_root = project_root / "src"
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))

    from geoworkbench.services.render_goldens import write_golden_fixtures

    target = project_root / "tests" / "golden_rendering"
    written = write_golden_fixtures(target)
    for path in written:
        print(path.relative_to(project_root))


if __name__ == "__main__":
    main()

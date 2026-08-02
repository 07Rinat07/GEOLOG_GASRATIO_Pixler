from __future__ import annotations

import subprocess


SOURCE_COMMIT = "b5249a4de2558f428b80a3b6286b372fbb8d4db0"
SOURCE_PATH = "tools/_finish_gas_continuity_policy.py"


def main() -> None:
    result = subprocess.run(
        ["git", "show", f"{SOURCE_COMMIT}:{SOURCE_PATH}"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Could not load verified continuity patch")
    namespace = {"__name__": "__main__", "__file__": SOURCE_PATH}
    exec(compile(result.stdout, SOURCE_PATH, "exec"), namespace)


if __name__ == "__main__":
    main()

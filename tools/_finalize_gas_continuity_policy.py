from __future__ import annotations

import subprocess


SOURCE_COMMIT = "aebea41736464fadec2e3bb170e7ddbeeddc52c2"
SOURCE_PATH = "tools/_retry_gas_continuity_policy.py"


def main() -> None:
    source = subprocess.run(
        ["git", "show", f"{SOURCE_COMMIT}:{SOURCE_PATH}"],
        text=True,
        capture_output=True,
        check=False,
    )
    if source.returncode != 0:
        raise RuntimeError(source.stderr.strip() or "Could not load continuity retry script")
    corrected = source.stdout.replace(
        'namespace = {"__name__": "__main__", "__file__": SOURCE_PATH}\n'
        '    exec(compile(corrected, SOURCE_PATH, "exec"), namespace)',
        'corrected = corrected.replace(\n'
        '        "    interpolate_bounded_gaps,\\n",\n'
        '        "    interpolate_bounded_gaps as interpolate_bounded_gaps,\\n",\n'
        '        1,\n'
        '    ).replace(\n'
        '        "            connect: str | NDArray[np.bool_] = \\\"finite\\\"\\n",\n'
        '        "            connect: object = \\\"finite\\\"\\n",\n'
        '        1,\n'
        '    )\n'
        '    namespace = {"__name__": "__main__", "__file__": SOURCE_PATH}\n'
        '    exec(compile(corrected, SOURCE_PATH, "exec"), namespace)',
        1,
    )
    namespace = {"__name__": "__main__", "__file__": SOURCE_PATH}
    exec(compile(corrected, SOURCE_PATH, "exec"), namespace)


if __name__ == "__main__":
    main()

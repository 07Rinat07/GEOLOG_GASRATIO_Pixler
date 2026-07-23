from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from geoworkbench.services.report_output_transaction import (  # noqa: E402
    ReportOutputRecoveryError,
    recover_report_output_transactions,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Recover interrupted GEOLOG report output/passport transactions."
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory containing report transaction journals (default: current directory).",
    )
    args = parser.parse_args()
    directory = Path(args.directory).resolve()
    try:
        recovered = recover_report_output_transactions(directory)
    except ReportOutputRecoveryError as exc:
        print(f"Recovery failed: {exc}", file=sys.stderr)
        return 2
    if not recovered:
        print(f"No pending report transactions in {directory}")
        return 0
    print(f"Recovered {len(recovered)} report transaction(s) in {directory}")
    for journal in recovered:
        print(f"- {journal.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "wits0_network_preflight.ps1"


def test_wits0_network_preflight_contract() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert '[string]$TargetHost = "192.168.0.100"' in text
    assert "[int]$TargetPort = 2041" in text
    assert "Test-NetConnection" in text
    assert "TcpTestSucceeded" in text
    assert "SourceAddress" in text
    assert "InterfaceAlias" in text
    assert "NetRouteNextHop" in text
    assert 'Add-ReportLine "Status=PASS"' in text
    assert 'Add-ReportLine "Status=FAIL"' in text
    assert "$exitCode = 0" in text
    assert "$exitCode = 2" in text
    assert "before changing WITS0 parsing or channel mapping" in text


@pytest.mark.skipif(os.name != "nt", reason="PowerShell parser check requires Windows")
def test_wits0_network_preflight_has_valid_powershell_syntax() -> None:
    shell = shutil.which("powershell.exe") or shutil.which("pwsh.exe") or shutil.which("pwsh")
    assert shell is not None

    escaped_path = str(SCRIPT).replace("'", "''")
    command = (
        "$tokens=$null; $errors=$null; "
        f"[System.Management.Automation.Language.Parser]::ParseFile('{escaped_path}',"
        "[ref]$tokens,[ref]$errors) | Out-Null; "
        "if ($errors.Count -gt 0) { "
        "$errors | ForEach-Object { Write-Error $_.Message }; exit 1 }; exit 0"
    )
    completed: subprocess.CompletedProcess[str] | None = None
    last_timeout: subprocess.TimeoutExpired | None = None
    for _attempt in range(2):
        try:
            completed = subprocess.run(
                [
                    shell,
                    "-NoLogo",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    command,
                ],
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
            )
            break
        except subprocess.TimeoutExpired as exc:
            last_timeout = exc

    if completed is None:
        pytest.fail(
            "PowerShell parser timed out twice while validating "
            f"{SCRIPT.name}: {last_timeout}",
            pytrace=False,
        )

    assert completed.returncode == 0, completed.stderr or completed.stdout

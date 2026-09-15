[CmdletBinding()]
param(
    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string]$TargetHost = "192.168.0.100",

    [Parameter()]
    [ValidateRange(1, 65535)]
    [int]$TargetPort = 2041,

    [Parameter()]
    [string]$OutputPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $evidenceDirectory = Join-Path $PSScriptRoot "..\build\field-evidence"
    New-Item -ItemType Directory -Force -Path $evidenceDirectory | Out-Null
    $OutputPath = Join-Path $evidenceDirectory ("wits0-network-preflight-{0}.txt" -f $timestamp)
}
else {
    $parentDirectory = Split-Path -Parent $OutputPath
    if (-not [string]::IsNullOrWhiteSpace($parentDirectory)) {
        New-Item -ItemType Directory -Force -Path $parentDirectory | Out-Null
    }
}

$report = New-Object "System.Collections.Generic.List[string]"

function Add-ReportLine {
    param([string]$Text = "")
    $report.Add($Text)
    Write-Host $Text
}

function Add-Section {
    param([Parameter(Mandatory = $true)][string]$Title)
    Add-ReportLine ""
    Add-ReportLine ("=== {0} ===" -f $Title)
}

function Add-CommandOutput {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][scriptblock]$Command
    )

    Add-Section $Name
    try {
        $output = & $Command 2>&1 | Out-String -Width 240
        if ([string]::IsNullOrWhiteSpace($output)) {
            Add-ReportLine "<no output>"
        }
        else {
            foreach ($line in ($output.TrimEnd() -split "`r?`n")) {
                Add-ReportLine $line
            }
        }
    }
    catch {
        Add-ReportLine ("ERROR: {0}" -f $_.Exception.Message)
    }
}

Add-ReportLine "GEOLOG GASRATIO@Pixler - WITS0 network preflight"
Add-ReportLine ("TimestampLocal={0}" -f (Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"))
Add-ReportLine ("ComputerName={0}" -f $env:COMPUTERNAME)
Add-ReportLine ("PowerShell={0}" -f $PSVersionTable.PSVersion)
Add-ReportLine ("OSVersion={0}" -f [Environment]::OSVersion.VersionString)
Add-ReportLine ("TargetHost={0}" -f $TargetHost)
Add-ReportLine ("TargetPort={0}" -f $TargetPort)

Add-CommandOutput "IPv4 addresses" {
    Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
        Where-Object { $_.IPAddress -ne "127.0.0.1" } |
        Sort-Object InterfaceMetric, InterfaceAlias, IPAddress |
        Select-Object InterfaceAlias, IPAddress, PrefixLength, AddressState
}

Add-CommandOutput "Network profiles" {
    Get-NetConnectionProfile -ErrorAction Stop |
        Select-Object InterfaceAlias, Name, NetworkCategory, IPv4Connectivity, IPv6Connectivity
}

Add-CommandOutput "IPv4 default routes" {
    Get-NetRoute -AddressFamily IPv4 -DestinationPrefix "0.0.0.0/0" -ErrorAction Stop |
        Sort-Object RouteMetric, InterfaceMetric |
        Select-Object InterfaceAlias, NextHop, RouteMetric, InterfaceMetric
}

Add-CommandOutput "ARP table" {
    & arp.exe -a
}

$pingSucceeded = $false
Add-Section "ICMP reachability"
try {
    $pingSucceeded = [bool](Test-Connection -ComputerName $TargetHost -Count 2 -Quiet -ErrorAction Stop)
    Add-ReportLine ("PingSucceeded={0}" -f $pingSucceeded)
}
catch {
    Add-ReportLine ("PingSucceeded=False")
    Add-ReportLine ("PingError={0}" -f $_.Exception.Message)
}

Add-Section "TCP reachability"
$tcpSucceeded = $false
$tcpResult = $null
try {
    $tcpResult = Test-NetConnection -ComputerName $TargetHost -Port $TargetPort -InformationLevel Detailed -WarningAction SilentlyContinue -ErrorAction Stop
    $tcpSucceeded = [bool]$tcpResult.TcpTestSucceeded

    foreach ($name in @(
        "ComputerName",
        "RemoteAddress",
        "RemotePort",
        "InterfaceAlias",
        "SourceAddress",
        "NetRoute",
        "PingSucceeded",
        "TcpTestSucceeded"
    )) {
        $property = $tcpResult.PSObject.Properties[$name]
        if ($null -ne $property) {
            if ($name -eq "NetRoute" -and $null -ne $property.Value) {
                Add-ReportLine ("NetRouteNextHop={0}" -f $property.Value.NextHop)
            }
            else {
                Add-ReportLine ("{0}={1}" -f $name, $property.Value)
            }
        }
    }
}
catch {
    Add-ReportLine ("TcpTestSucceeded=False")
    Add-ReportLine ("TcpError={0}" -f $_.Exception.Message)
}

Add-Section "Existing TCP connections to target"
try {
    $connections = Get-NetTCPConnection -RemotePort $TargetPort -ErrorAction Stop |
        Where-Object { [string]$_.RemoteAddress -eq [string]$TargetHost } |
        Select-Object LocalAddress, LocalPort, RemoteAddress, RemotePort, State, OwningProcess
    if ($null -eq $connections) {
        Add-ReportLine "<none>"
    }
    else {
        $formatted = $connections | Format-Table -AutoSize | Out-String -Width 240
        foreach ($line in ($formatted.TrimEnd() -split "`r?`n")) {
            Add-ReportLine $line
        }
    }
}
catch {
    Add-ReportLine ("ERROR: {0}" -f $_.Exception.Message)
}

Add-Section "Assessment"
if ($tcpSucceeded) {
    Add-ReportLine "Status=PASS"
    Add-ReportLine ("Reason=TCP {0}:{1} is reachable from this workstation." -f $TargetHost, $TargetPort)
    if (-not $pingSucceeded) {
        Add-ReportLine "Note=ICMP ping failed, but TCP succeeded; ICMP may be filtered and does not block WITS0."
    }
    $exitCode = 0
}
else {
    Add-ReportLine "Status=FAIL"
    Add-ReportLine ("Reason=TCP {0}:{1} is not reachable from this workstation." -f $TargetHost, $TargetPort)
    Add-ReportLine "Action=Check the selected SourceAddress/InterfaceAlias, local subnet or route, GeoScape listener, and firewall before changing WITS0 parsing or channel mapping."
    $exitCode = 2
}

$resolvedOutputPath = [System.IO.Path]::GetFullPath($OutputPath)
$report | Set-Content -LiteralPath $resolvedOutputPath -Encoding UTF8
Write-Host ""
Write-Host ("Report={0}" -f $resolvedOutputPath)
Write-Host ("ExitCode={0}" -f $exitCode)
exit $exitCode

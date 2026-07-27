param(
    [Parameter(Mandatory = $true)]
    [string]$MdbPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory,

    [string[]]$Tables = @(
        "WITS",
        "WITSRecordStreamMap",
        "WITSActivity",
        "WITSMeasureSystem",
        "NetConnectionLog"
    )
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function New-ReadOnlyConnectionString {
    param([string]$Path)

    $providers = @(
        "Microsoft.ACE.OLEDB.16.0",
        "Microsoft.ACE.OLEDB.12.0",
        "Microsoft.Jet.OLEDB.4.0"
    )
    foreach ($provider in $providers) {
        $candidate = "Provider=$provider;Data Source=$Path;Mode=Read;Persist Security Info=False;"
        $connection = New-Object System.Data.OleDb.OleDbConnection($candidate)
        try {
            $connection.Open()
            $connection.Close()
            return $candidate
        }
        catch {
            $connection.Dispose()
        }
    }
    throw "Не найден ACE/Jet OLE DB provider для read-only открытия MDB. Установите Microsoft Access Database Engine соответствующей разрядности."
}

function ConvertTo-CsvField {
    param([object]$Value)
    if ($null -eq $Value -or $Value -is [System.DBNull]) { return "" }
    $text = [Convert]::ToString($Value, [Globalization.CultureInfo]::InvariantCulture)
    return '"' + $text.Replace('"', '""') + '"'
}

$resolvedMdb = (Resolve-Path -LiteralPath $MdbPath).Path
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$resolvedOutput = (Resolve-Path -LiteralPath $OutputDirectory).Path
$connectionString = New-ReadOnlyConnectionString -Path $resolvedMdb
$connection = New-Object System.Data.OleDb.OleDbConnection($connectionString)
$manifestEntries = @()

try {
    $connection.Open()
    $schema = $connection.GetSchema("Tables")
    $available = @{}
    foreach ($row in $schema.Rows) {
        if ([string]$row.TABLE_TYPE -eq "TABLE") {
            $available[[string]$row.TABLE_NAME] = $true
        }
    }

    foreach ($table in $Tables) {
        if (-not $available.ContainsKey($table)) {
            Write-Warning "Таблица '$table' отсутствует в MDB."
            continue
        }

        # The table name comes only from the explicit allow-list / user parameter and is escaped.
        $escapedTable = $table.Replace("]", "]]" )
        $command = $connection.CreateCommand()
        $command.CommandText = "SELECT * FROM [$escapedTable]"
        $reader = $command.ExecuteReader()
        try {
            $target = Join-Path $resolvedOutput ($table + ".csv")
            $utf8 = New-Object System.Text.UTF8Encoding($false)
            $writer = New-Object System.IO.StreamWriter($target, $false, $utf8)
            try {
                $headers = for ($index = 0; $index -lt $reader.FieldCount; $index++) {
                    ConvertTo-CsvField $reader.GetName($index)
                }
                $writer.WriteLine(($headers -join ","))
                $rowCount = 0
                while ($reader.Read()) {
                    $values = for ($index = 0; $index -lt $reader.FieldCount; $index++) {
                        ConvertTo-CsvField $reader.GetValue($index)
                    }
                    $writer.WriteLine(($values -join ","))
                    $rowCount++
                }
            }
            finally {
                $writer.Dispose()
            }
            $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash.ToLowerInvariant()
            $manifestEntries += [ordered]@{
                table = $table
                rows = $rowCount
                file = [IO.Path]::GetFileName($target)
                sha256 = $hash
            }
        }
        finally {
            $reader.Dispose()
            $command.Dispose()
        }
    }
}
finally {
    if ($connection.State -ne [System.Data.ConnectionState]::Closed) {
        $connection.Close()
    }
    $connection.Dispose()
}

$manifest = [ordered]@{
    schemaVersion = 1
    source = [ordered]@{
        file = [IO.Path]::GetFileName($resolvedMdb)
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $resolvedMdb).Hash.ToLowerInvariant()
        mode = "read-only"
    }
    exportedTables = $manifestEntries
}
$manifestPath = Join-Path $resolvedOutput "mdb_export_manifest.json"
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding utf8
Write-Host "Read-only MDB export completed: $manifestPath"

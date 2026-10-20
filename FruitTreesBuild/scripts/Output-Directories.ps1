# Reserve only the directory number, then release the lock before generating.
# The persistent high-water mark prevents reusing numbers after folder removal.
function New-FruitAssetDirectory {
    param(
        [Parameter(Mandatory)][string]$OutputRoot,
        [Parameter(Mandatory)][ValidateSet('apple', 'orange')][string]$Fruit
    )
    $OutputRoot = [IO.Path]::GetFullPath($OutputRoot)
    [IO.Directory]::CreateDirectory($OutputRoot) | Out-Null
    $lockPath = Join-Path $OutputRoot '.asset-numbering.lock'
    $statePath = Join-Path $OutputRoot '.asset-numbering.json'
    $clock = [Diagnostics.Stopwatch]::StartNew()
    $allocationLock = $null
    while ($null -eq $allocationLock) {
        try {
            $allocationLock = [IO.File]::Open($lockPath, [IO.FileMode]::OpenOrCreate,
                [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
        } catch [IO.IOException] {
            if ($clock.Elapsed.TotalSeconds -ge 30) {
                throw 'Could not reserve an asset number within 30 seconds. No output was overwritten.'
            }
            [Threading.Thread]::Sleep(100)
        }
    }
    try {
        $state = @{schema_version = '1.0.0'; last_allocated = @{apple = 0L; orange = 0L}}
        if (Test-Path -LiteralPath $statePath) {
            $state = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 |
                ConvertFrom-Json -AsHashtable -ErrorAction Stop
            if ($state.schema_version -ne '1.0.0' -or $state.last_allocated -isnot [Collections.IDictionary]) {
                throw 'Invalid numbering state. Restore .asset-numbering.json; do not reset it to overwrite assets.'
            }
            foreach ($kind in @('apple', 'orange')) {
                $parsed = 0L
                if (-not [long]::TryParse([string]$state.last_allocated[$kind], [ref]$parsed) -or $parsed -lt 0) {
                    throw "Invalid numbering state for $kind."
                }
                $state.last_allocated[$kind] = $parsed
            }
        }
        $highest = [long]$state.last_allocated[$Fruit]
        # Include files and incomplete directories too: their names are reserved.
        foreach ($entry in Get-ChildItem -LiteralPath $OutputRoot -Force) {
            if ($entry.Name -match ('^' + $Fruit + '_tree_(\d+)$')) {
                $number = 0L
                if (-not [long]::TryParse($Matches[1], [ref]$number)) { throw 'Asset number is too large.' }
                $highest = [Math]::Max($highest, $number)
            }
        }
        if ($highest -eq [long]::MaxValue) { throw 'Asset numbering exhausted.' }
        $next = $highest + 1L
        $name = '{0}_tree_{1}' -f $Fruit, $next.ToString('D3', [Globalization.CultureInfo]::InvariantCulture)
        $directory = Join-Path $OutputRoot $name
        if (Test-Path -LiteralPath $directory) { throw "Refusing to reuse existing output: $directory" }
        [IO.Directory]::CreateDirectory($directory) | Out-Null
        $state.last_allocated[$Fruit] = $next
        $temporaryState = $statePath + '.' + [guid]::NewGuid().ToString('N') + '.tmp'
        [IO.File]::WriteAllText($temporaryState, ($state | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))
        [IO.File]::Move($temporaryState, $statePath, $true)
        return [pscustomobject]@{Name = $name; Number = $next; FullName = $directory}
    } finally {
        $allocationLock.Dispose()
    }
}

param(
    [ValidateSet('auto', 'space', 'sapling')][string]$Generator = 'auto',
    [ValidateSet('apple', 'orange')][string]$Fruit = 'apple',
    [ValidateSet('unknown', 'unripe', 'turning', 'ripe')][string]$MaturityStage = 'unknown',
    [string]$FruitVariantId,
    [object]$MaturityCounts,
    [ValidateRange(0, 2147483647)][int]$Seed = 42,
    [ValidateRange(0, 5000)][int]$Frames = 0,
    [ValidateSet('modern')][string]$Backend = 'modern',
    [string]$BlenderPath,
    [ValidateRange(64, 4096)][int]$Resolution = 512,
    [ValidateRange(1, 4096)][int]$Samples = 16,
    [ValidateRange(1, 256)][int]$Threads = 4,
    [ValidateSet('auto', 'orchard')][string]$Profile = 'orchard',
    [ValidateRange(0.5, 20)][double]$TreeHeight = 4.0,
    [ValidateRange(0.1, 10)][double]$TrunkHeight = 0.6,
    [ValidateRange(0, 20)][double]$CrownWidth = 0,
    [ValidateRange(0, .05)][double]$LeafFruitClearance = .006,
    [ValidateRange(0, 1)][double]$BranchUplift = .18,
    [ValidateRange(90, 180)][double]$BranchAngleMin = 120,
    [ValidateRange(0, .8)][double]$HeightTaper = .4,
    [ValidateRange(0.02, 1)][double]$TrunkDiameter = 0.18,
    [ValidateRange(0, 20000)][int]$LeafCount = 3000,
    [ValidateRange(0, 2000)][int]$FruitCount = 80,
    [ValidateRange(0.02, 0.5)][double]$LeafLength = 0.16,
    [ValidateRange(0.02, 0.3)][double]$FruitDiameter = 0.08,
    [ValidateRange(0, .1)][double]$LeafSpacing = .0015,
    [switch]$NoGround,
    [string]$Config
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $projectRoot 'scripts/Project-Paths.ps1')
. (Join-Path $projectRoot 'scripts/Output-Directories.ps1')
if ($Config) {
    $settings = Get-Content -LiteralPath $Config -Raw -Encoding UTF8 | ConvertFrom-Json
    $supported = @('generator', 'fruit', 'seed', 'frames', 'resolution', 'samples', 'threads',
        'profile', 'treeHeight', 'trunkHeight', 'trunkDiameter', 'leafCount', 'fruitCount',
        'leafLength', 'fruitDiameter', 'crownWidth', 'leafFruitClearance', 'branchUplift',
        'branchAngleMin', 'heightTaper', 'leafSpacing', 'noGround', 'backend', 'blenderPath', 'maturityStage', 'fruitVariantId', 'maturityCounts')
    foreach ($property in $settings.PSObject.Properties) {
        if ($property.Name -notin $supported) { throw "Unknown setting: $($property.Name)" }
        if ($property.Name -eq 'blenderPath' -and $PSBoundParameters.ContainsKey('Backend') -and
            $settings.backend -and $Backend -ne $settings.backend -and -not $PSBoundParameters.ContainsKey('BlenderPath')) { continue }
        # Explicit command-line parameters take precedence over the config file.
        if (-not $PSBoundParameters.ContainsKey($property.Name)) {
            Set-Variable -Name $property.Name -Value $property.Value
        }
    }
}
if ($Fruit -notin @('apple', 'orange')) { throw 'Fruit must be apple or orange.' }
if ($Generator -eq 'auto') {
    $Generator = if ($Fruit -eq 'orange') { 'sapling' } else { 'space' }
}
if ($Generator -eq 'sapling' -and $Fruit -ne 'orange') {
    throw 'The original Sapling example supports orange trees only.'
}
if ($TrunkHeight -ge $TreeHeight * 0.65) { throw 'TrunkHeight must be less than 65% of TreeHeight.' }
if ($Backend -ne 'modern' -or $Profile -notin @('auto', 'orchard')) {
    throw 'FruitTreesBuild contains only native Blender 5.2 and the orchard asset export.'
}
$blenderExecutable = Resolve-ProjectBlender -ProjectRoot $projectRoot -BlenderPath $BlenderPath
$versionText = (& $blenderExecutable --version 2>&1 | Select-Object -First 1).ToString()
if ($versionText -notmatch '^Blender 5\.2\.') {
    throw "Backend/version mismatch: $Backend / $versionText"
}
$reservation = New-FruitAssetDirectory -OutputRoot (Join-Path $projectRoot 'generated') -Fruit $Fruit
$runDirectory = $reservation.FullName
$previousEnvironment = @{}
foreach ($name in @('BLENDER_USER_CONFIG', 'BLENDER_USER_SCRIPTS', 'BLENDER_USER_DATAFILES')) {
    $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
$env:BLENDER_USER_CONFIG = Join-Path $projectRoot '.runtime\user\config'
$env:BLENDER_USER_SCRIPTS = Join-Path $projectRoot '.runtime\user\scripts'
$env:BLENDER_USER_DATAFILES = Join-Path $projectRoot '.runtime\user\datafiles'
Push-Location $projectRoot
try {
    Write-Output "Backend: $Backend / $versionText"
    Write-Output "Generator: $Generator"
    Write-Output "Asset folder: $($reservation.Name)"
    $shapeArguments = @('--profile', $Profile,
        '--tree-height', $TreeHeight.ToString([Globalization.CultureInfo]::InvariantCulture),
        '--trunk-height', $TrunkHeight.ToString([Globalization.CultureInfo]::InvariantCulture),
        '--trunk-diameter', $TrunkDiameter.ToString([Globalization.CultureInfo]::InvariantCulture),
        '--branch-uplift', $BranchUplift.ToString([Globalization.CultureInfo]::InvariantCulture),
        '--branch-angle-min', $BranchAngleMin.ToString([Globalization.CultureInfo]::InvariantCulture),
        '--height-taper', $HeightTaper.ToString([Globalization.CultureInfo]::InvariantCulture),
        '--leaf-spacing', $LeafSpacing.ToString([Globalization.CultureInfo]::InvariantCulture),
        '--leaf-count', $LeafCount, '--fruit-count', $FruitCount,
        '--leaf-length', $LeafLength.ToString([Globalization.CultureInfo]::InvariantCulture),
        '--fruit-diameter', $FruitDiameter.ToString([Globalization.CultureInfo]::InvariantCulture))
    if ($NoGround) { $shapeArguments += '--no-ground' }
    $shapeArguments += @('--leaf-fruit-clearance', $LeafFruitClearance.ToString([Globalization.CultureInfo]::InvariantCulture))
    if ($CrownWidth -gt 0) {
        $shapeArguments += @('--crown-width', $CrownWidth.ToString([Globalization.CultureInfo]::InvariantCulture))
    }
    $shapeArguments += @('--maturity-stage', $MaturityStage)
    if ($FruitVariantId) { $shapeArguments += @('--fruit-variant-id', $FruitVariantId) }
    if ($null -ne $MaturityCounts) {
        $shapeArguments += @('--maturity-counts', ($MaturityCounts | ConvertTo-Json -Compress))
    }
    & $blenderExecutable --background --factory-startup --disable-autoexec --python-exit-code 1 `
        --threads $Threads --python (Join-Path $projectRoot 'scripts\generate.py') -- `
        --generator $Generator --fruit $Fruit --seed $Seed --frames $Frames `
        --resolution $Resolution --samples $Samples --output $runDirectory @shapeArguments 2>&1 |
        Tee-Object -FilePath (Join-Path $runDirectory 'run.log')
    if ($LASTEXITCODE -ne 0) { throw "Generation failed. See $runDirectory\run.log" }
    if (Test-Path -LiteralPath (Join-Path $runDirectory 'asset.blend')) {
        & $blenderExecutable --background --factory-startup --disable-autoexec --python-exit-code 1 `
            --threads $Threads (Join-Path $runDirectory 'asset.blend') --python (Join-Path $projectRoot 'scripts\prepare_asset_file.py') -- `
            --asset-file (Join-Path $runDirectory 'asset.blend') 2>&1 |
            Tee-Object -FilePath (Join-Path $runDirectory 'run.log') -Append
        if ($LASTEXITCODE -ne 0) { throw "Candidate save failed. See $runDirectory\run.log" }
        Write-Output "Asset: $(Join-Path $runDirectory 'asset.blend')"
        Write-Output 'Review and save asset.blend. Set assetDir in configs/export_metadata.json, then run generate_metadata.py with no arguments.'
    }
    $runMetadataPath = Join-Path $runDirectory 'metadata.json'
    $runMetadata = Get-Content -LiteralPath $runMetadataPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $runMetadata.run_status = 'awaiting_manual_review'
    $runMetadata | Add-Member -NotePropertyName asset_folder -NotePropertyValue $reservation.Name -Force
    $runMetadata | Add-Member -NotePropertyName asset_number -NotePropertyValue $reservation.Number -Force
    $runMetadata | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $runMetadataPath -Encoding utf8
    Write-Output "Candidate ready (awaiting manual review): $runDirectory"
} catch {
    Write-Error "Reserved output retained for inspection: $runDirectory. Its number will not be reused." -ErrorAction Continue
    throw
} finally {
    Pop-Location
    foreach ($name in $previousEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $previousEnvironment[$name], 'Process')
    }
}

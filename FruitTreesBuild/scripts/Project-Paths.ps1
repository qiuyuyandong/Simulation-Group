function Resolve-ProjectBlender {
    param([Parameter(Mandatory)][string]$ProjectRoot, [string]$BlenderPath)
    if (-not $BlenderPath) { $BlenderPath = '.runtime/blender-5.2-windows64/blender.exe' }
    if (-not [IO.Path]::IsPathRooted($BlenderPath)) {
        $BlenderPath = Join-Path $ProjectRoot $BlenderPath
    }
    if (-not (Test-Path -LiteralPath $BlenderPath -PathType Leaf)) {
        throw "Blender executable missing: $BlenderPath. Use the bundled runtime or set blenderPath."
    }
    return (Resolve-Path -LiteralPath $BlenderPath).Path
}

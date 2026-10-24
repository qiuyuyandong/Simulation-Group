function Resolve-ProjectBlender {
    param([Parameter(Mandatory)][string]$ProjectRoot, [string]$BlenderPath)
    if (-not $BlenderPath) { throw 'Use generate_apple_tree.py or generate_orange_tree.py for automatic discovery, or pass -BlenderPath.' }
    if (-not [IO.Path]::IsPathRooted($BlenderPath)) {
        $BlenderPath = Join-Path $ProjectRoot $BlenderPath
    }
    if (-not (Test-Path -LiteralPath $BlenderPath -PathType Leaf)) {
        throw "Blender executable missing: $BlenderPath. Correct -BlenderPath or use the Python launcher."
    }
    return (Resolve-Path -LiteralPath $BlenderPath).Path
}

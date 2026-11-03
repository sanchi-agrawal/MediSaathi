# Render new fictional samples with Windows' Indic shaping, not a new OCR engine.
# Nirmala UI is used from the installed OS; the font itself is not redistributed.
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
$fixtureRoot = Join-Path $PSScriptRoot 'fixtures'
$manifestPath = Join-Path $fixtureRoot 'manifest.json'
$manifest = Get-Content -Raw -Encoding UTF8 -LiteralPath $manifestPath | ConvertFrom-Json
foreach ($fixture in $manifest.fixtures) {
    $canvas = New-Object System.Drawing.Bitmap(2000,1100)
    $graphics = [System.Drawing.Graphics]::FromImage($canvas)
    $graphics.Clear([System.Drawing.Color]::White)
    $style = [System.Drawing.FontStyle]::Regular
    if ($fixture.style -eq 'synthetic_handwriting_like') { $style = [System.Drawing.FontStyle]::Italic }
    $font = New-Object System.Drawing.Font('Nirmala UI',28,$style)
    $y = 70
    foreach ($line in $fixture.lines) {
        $left = 65
        if ($fixture.style -eq 'synthetic_handwriting_like') { $left += ($y % 23) }
        $rect = New-Object System.Drawing.Rectangle($left,$y,1850,180)
        $flags = [System.Windows.Forms.TextFormatFlags]::NoPadding -bor [System.Windows.Forms.TextFormatFlags]::WordBreak
        [System.Windows.Forms.TextRenderer]::DrawText($graphics,[string]$line,$font,$rect,[System.Drawing.Color]::FromArgb(20,20,20),$flags)
        $y += 190
    }
    $target = Join-Path $fixtureRoot $fixture.file
    $canvas.Save($target,[System.Drawing.Imaging.ImageFormat]::Png)
    $font.Dispose(); $graphics.Dispose(); $canvas.Dispose()
    $fixture | Add-Member -NotePropertyName sha256 -NotePropertyValue ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLower()) -Force
}
$manifest | ConvertTo-Json -Depth 30 | Set-Content -Encoding UTF8 -LiteralPath $manifestPath
Write-Output 'Rendered four fictional fixtures with native Devanagari shaping. No OCR performed.'

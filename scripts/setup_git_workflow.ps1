$ErrorActionPreference = 'Stop'

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
Push-Location $repoRoot
try {
    $hooksPath = (Join-Path $repoRoot '.githooks')
    if (-not (Test-Path $hooksPath -PathType Container)) {
        throw "Missing hooks directory: $hooksPath"
    }

    git config --local core.hooksPath .githooks
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to configure core.hooksPath.'
    }

    Write-Host 'Git workflow hooks enabled for this repository.'
    Write-Host ("core.hooksPath = " + (git config --local --get core.hooksPath))
}
finally {
    Pop-Location
}

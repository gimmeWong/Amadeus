param(
    [switch]$SkipOriginPush
)

$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
Push-Location $repoRoot
try {
    $status = git status --porcelain
    if ($status) {
        throw 'Working tree is not clean. Commit or stash changes before syncing main.'
    }

    $branch = git branch --show-current
    if ($branch -ne 'main') {
        throw "Current branch is '$branch'. Switch to main before syncing."
    }

    git fetch upstream --prune
    if ($LASTEXITCODE -ne 0) { throw 'git fetch upstream failed.' }

    git merge --ff-only upstream/main
    if ($LASTEXITCODE -ne 0) { throw 'upstream/main cannot be fast-forwarded into main.' }

    if (-not $SkipOriginPush) {
        git push origin main
        if ($LASTEXITCODE -ne 0) { throw 'git push origin main failed.' }
    }

    Write-Host 'main is synchronized with upstream/main.'
}
finally {
    Pop-Location
}

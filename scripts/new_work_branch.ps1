param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-z0-9][a-z0-9._/-]*$')]
    [string]$Name,

    [ValidateSet('feature', 'fix', 'docs', 'test', 'chore', 'refactor')]
    [string]$Kind = 'feature'
)

$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
Push-Location $repoRoot
try {
    if (git status --porcelain) {
        throw 'Working tree is not clean. Commit or stash changes before creating a branch.'
    }

    $branch = git branch --show-current
    if ($branch -ne 'main') {
        throw "Current branch is '$branch'. Switch to main and sync it first."
    }

    $target = "$Kind/$Name"
    if (git show-ref --verify --quiet "refs/heads/$target") {
        throw "Local branch already exists: $target"
    }

    git switch -c $target main
    if ($LASTEXITCODE -ne 0) { throw "Unable to create branch: $target" }
    Write-Host "Created and switched to $target from main."
}
finally {
    Pop-Location
}

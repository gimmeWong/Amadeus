param(
    [Parameter(Position = 0)]
    [string]$WorkBranch,

    [switch]$SkipOriginMainPush
)

$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
Push-Location $repoRoot

$originalBranch = $null
$promotedBranch = $null
$promotionCompleted = $false

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [string]$FailureMessage = 'Git command failed.'
    )

    & git @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw $FailureMessage
    }
}

function Test-GitRef {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Ref
    )

    & git show-ref --verify --quiet $Ref
    return $LASTEXITCODE -eq 0
}

try {
    $originalBranch = (git branch --show-current).Trim()
    if (-not $originalBranch) {
        throw 'Detached HEAD is not supported by this workflow.'
    }

    if (-not $WorkBranch) {
        $WorkBranch = $originalBranch
    }

    if ($WorkBranch -notmatch '^(feature|fix)/[a-z0-9][a-z0-9._/-]*$') {
        throw "Work branch must be feature/* or fix/*: $WorkBranch"
    }

    if ($originalBranch -ne $WorkBranch) {
        throw "Run this command while checked out on '$WorkBranch'. Current branch is '$originalBranch'."
    }

    if (git status --porcelain) {
        throw 'Working tree is not clean. Commit or stash changes before promoting a work branch.'
    }

    if (-not (Test-GitRef "refs/heads/$WorkBranch")) {
        throw "Local work branch does not exist: $WorkBranch"
    }

    Invoke-Git @('push', '-u', 'origin', $WorkBranch) "git push origin $WorkBranch failed."
    Invoke-Git @('fetch', 'upstream', '--prune') 'git fetch upstream failed.'
    Invoke-Git @('fetch', 'origin', '--prune') 'git fetch origin failed.'

    Invoke-Git @('switch', 'main') 'Unable to switch to main.'
    Invoke-Git @('merge', '--ff-only', 'upstream/main') 'upstream/main cannot be fast-forwarded into main.'

    if (-not $SkipOriginMainPush) {
        Invoke-Git @('push', 'origin', 'main') 'git push origin main failed.'
    }

    if (Test-GitRef 'refs/heads/personal/main') {
        Invoke-Git @('switch', 'personal/main') 'Unable to switch to personal/main.'
        if (Test-GitRef 'refs/remotes/origin/personal/main') {
            Invoke-Git @('merge', '--ff-only', 'origin/personal/main') 'Local personal/main diverges from origin/personal/main.'
        }
    }
    elseif (Test-GitRef 'refs/remotes/origin/personal/main') {
        Invoke-Git @('switch', '-c', 'personal/main', '--track', 'origin/personal/main') 'Unable to create personal/main from origin/personal/main.'
    }
    else {
        Invoke-Git @('switch', '-c', 'personal/main', 'main') 'Unable to create personal/main from main.'
    }
    $promotedBranch = 'personal/main'

    # Keep upstream changes and the selected work item as explicit merge commits.
    Invoke-Git @('merge', '--no-ff', 'main', '-m', 'chore: sync personal main with upstream') 'Unable to merge main into personal/main.'
    Invoke-Git @('merge', '--no-ff', $WorkBranch, '-m', "merge: promote $WorkBranch into personal/main") "Unable to merge $WorkBranch into personal/main."

    Write-Host 'Running Electron tests on personal/main...'
    & npm --prefix electron test
    if ($LASTEXITCODE -ne 0) {
        throw 'Electron tests failed. personal/main was not pushed.'
    }

    $env:AMADEUS_PERSONAL_PROMOTION = '1'
    try {
        Invoke-Git @('push', '-u', 'origin', 'personal/main') 'git push origin personal/main failed.'
    }
    finally {
        Remove-Item Env:AMADEUS_PERSONAL_PROMOTION -ErrorAction SilentlyContinue
    }
    $promotionCompleted = $true
    Write-Host "Promoted $WorkBranch into personal/main and pushed the tested result to origin."
}
finally {
    if ($promotionCompleted -and $originalBranch -and $promotedBranch -and ((git branch --show-current).Trim() -eq $promotedBranch)) {
        git switch $originalBranch | Out-Host
    }
    Pop-Location
}

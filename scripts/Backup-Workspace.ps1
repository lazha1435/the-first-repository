[CmdletBinding(SupportsShouldProcess = $true)]
param(
  [string]$Message,
  [switch]$SkipPush
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Invoke-Git {
  param(
    [Parameter(Mandatory = $true)]
    [string[]]$Arguments
  )

  & git @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "git $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
  }
}

Invoke-Git -Arguments @('rev-parse', '--is-inside-work-tree') | Out-Null

$branch = (& git branch --show-current).Trim()
if ([string]::IsNullOrWhiteSpace($branch)) {
  throw 'This repository is in detached HEAD state. Switch to a branch before running the backup script.'
}

Invoke-Git -Arguments @('add', '-A')

$stagedFiles = @( & git diff --cached --name-only )
if ($LASTEXITCODE -ne 0) {
  throw 'Failed to inspect staged changes.'
}

if ($stagedFiles.Count -gt 0) {
  if ([string]::IsNullOrWhiteSpace($Message)) {
    $Message = 'Backup ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
  }

  if ($PSCmdlet.ShouldProcess('staged changes', "git commit -m `"$Message`"")) {
    Invoke-Git -Arguments @('commit', '-m', $Message)
  }
} else {
  Write-Host 'No file changes to commit.'
}

if (-not $SkipPush) {
  if ($PSCmdlet.ShouldProcess($branch, "git push -u origin $branch")) {
    try {
      Invoke-Git -Arguments @('push', '-u', 'origin', $branch)
    } catch {
      Write-Error 'Local backup was saved, but push to GitHub failed.'
      throw
    }
  }
}

Write-Host 'Backup complete.'

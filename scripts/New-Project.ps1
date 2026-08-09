param(
  [Parameter(Position = 0)]
  [string]$Name,

  [string]$Date = (Get-Date -Format 'yyyy-MM-dd')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot

if ([string]::IsNullOrWhiteSpace($Name)) {
  $Name = Read-Host 'Project name'
}

$projectName = ($Name -replace '[<>:"/\\|?*]', '-').Trim()
if ([string]::IsNullOrWhiteSpace($projectName)) {
  throw 'Project name cannot be empty.'
}

$dateDir = Join-Path $repoRoot $Date
$projectDir = Join-Path $dateDir $projectName

New-Item -ItemType Directory -Force -Path $projectDir | Out-Null

$readmePath = Join-Path $projectDir 'README.md'
if (-not (Test-Path -LiteralPath $readmePath)) {
  @"
# $projectName

Created on $Date.

## Next
- Keep this work inside the repository root.
- Commit small, reversible steps.
"@ | Set-Content -LiteralPath $readmePath -Encoding utf8
}

Write-Host $projectDir

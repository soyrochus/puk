$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir '..')

$uv = Get-Command uv -ErrorAction SilentlyContinue
if ($uv) {
  & $uv.Path run --project $ProjectRoot python -m puk @args
  exit $LASTEXITCODE
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
  $python = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $python) {
  throw "Python executable not found in PATH (tried 'python' and 'python3')."
}

& $python.Path -m puk @args
exit $LASTEXITCODE

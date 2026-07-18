$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

if (-not (Test-Path -LiteralPath '.env')) {
    Write-Host '缺少 .env。请复制 .env.example 为 .env，并填写完整密钥与配对令牌。' -ForegroundColor Yellow
    exit 1
}

$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { $pythonPath = 'python' }
& $pythonPath -m uvicorn server:app --host 0.0.0.0 --port 8443

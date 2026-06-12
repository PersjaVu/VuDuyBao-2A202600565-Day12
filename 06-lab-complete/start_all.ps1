# start_all.ps1 — Khoi dong toan bo Legal Multi-Agent System tren Windows
# Su dung: .\start_all.ps1

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PidFile = Join-Path $ProjectDir ".service_pids.txt"

function Start-Service($Name, $Module, $Port) {
    Write-Host "Starting $Name on port $Port..." -ForegroundColor Cyan
    $proc = Start-Process powershell.exe -ArgumentList @(
        "-NoExit",
        "-Command",
        "cd '$ProjectDir'; `$env:PYTHONUTF8='1'; python -m uv run python -m $Module 2>&1 | Tee-Object -FilePath '${Module}.log'"
    ) -PassThru -WindowStyle Minimized
    Write-Host "  -> PID $($proc.Id)" -ForegroundColor Green
    return $proc.Id
}

# Xoa pid file cu
if (Test-Path $PidFile) { Remove-Item $PidFile }

# 1. Registry (phai start truoc)
$pids = @()
$pids += Start-Service "Registry"        "registry"         10000
Start-Sleep 3

# 2. Leaf agents (tax + compliance) - khong phu thuoc nhau
$pids += Start-Service "Tax Agent"        "tax_agent"        10102
$pids += Start-Service "Compliance Agent" "compliance_agent" 10103
Start-Sleep 4

# 3. Law Agent (sau khi tax + compliance da registered)
$pids += Start-Service "Law Agent"        "law_agent"        10101
Start-Sleep 4

# 4. Customer Agent (entry point)
$pids += Start-Service "Customer Agent"   "customer_agent"   10100
Start-Sleep 3

# Luu PIDs
$pids | Out-File $PidFile

Write-Host ""
Write-Host "All services started!" -ForegroundColor Green
Write-Host "  Registry:         http://localhost:10000/agents"
Write-Host "  Customer Agent:   http://localhost:10100/.well-known/agent.json"
Write-Host "  Law Agent:        http://localhost:10101/.well-known/agent.json"
Write-Host "  Tax Agent:        http://localhost:10102/.well-known/agent.json"
Write-Host "  Compliance Agent: http://localhost:10103/.well-known/agent.json"
Write-Host ""
Write-Host "Run test:  python -m uv run python test_client.py"
Write-Host "Stop all:  .\stop_all.ps1"

# stop_all.ps1 — Dung tat ca services tren cac port 10000-10103

$ports = @(10000, 10100, 10101, 10102, 10103)

foreach ($port in $ports) {
    $procs = netstat -ano | Select-String ":$port " | ForEach-Object {
        ($_ -split '\s+')[-1]
    } | Sort-Object -Unique
    foreach ($procId in $procs) {
        if ($procId -match '^\d+$' -and $procId -ne '0') {
            try {
                Stop-Process -Id ([int]$procId) -Force -ErrorAction SilentlyContinue
                Write-Host "Stopped PID $procId (port $port)" -ForegroundColor Yellow
            } catch {}
        }
    }
}

Write-Host "All services stopped." -ForegroundColor Green

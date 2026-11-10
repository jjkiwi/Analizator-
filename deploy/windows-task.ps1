# Harmonogram zadan Windows: uruchamia `cfd run` przy logowaniu i wznawia po awarii.
# Uruchom w PowerShell z katalogu glownego repo:  powershell -ExecutionPolicy Bypass -File deploy\windows-task.ps1
# Usuniecie:  Unregister-ScheduledTask -TaskName "AnalizatorCFD" -Confirm:$false
$repo = (Resolve-Path "$PSScriptRoot\..").Path
$cfd  = Join-Path $repo ".venv\Scripts\cfd.exe"
if (-not (Test-Path $cfd)) { throw "Brak $cfd. Najpierw: python -m venv .venv; .venv\Scripts\pip install -e ." }
New-Item -ItemType Directory -Force -Path (Join-Path $repo "logs") | Out-Null

# Wrapper: log dzienny + usuwanie logow starszych niz 14 dni (rotacja).
$wrapper = Join-Path $repo "deploy\run-cfd.cmd"
@"
@echo off
cd /d "$repo"
forfiles /p "$repo\logs" /m cfd-*.log /d -14 /c "cmd /c del @path" 2>nul
for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set DZIEN=%%d
"$cfd" -v run >> "$repo\logs\cfd-%DZIEN%.log" 2>&1
"@ | Set-Content -Encoding ASCII $wrapper

$action   = New-ScheduledTaskAction -Execute $wrapper -WorkingDirectory $repo
$trigger  = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
            -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "AnalizatorCFD" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName "AnalizatorCFD"
Write-Host "Zadanie AnalizatorCFD zarejestrowane i uruchomione. Logi: $repo\logs"

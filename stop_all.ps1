# stop_all.ps1 — Menghentikan seluruh proses backend, telegram bot, dan cloudflared
$ErrorActionPreference = "SilentlyContinue"

Write-Host "Menghentikan seluruh layanan Bobby Computer..." -ForegroundColor Yellow

# Matikan uvicorn
Get-Process -Name "uvicorn" | Stop-Process -Force
# Matikan cloudflared
Get-Process -Name "cloudflared" | Stop-Process -Force
# Matikan python telegram bot
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*telegram_bot.py*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
# Matikan proses uvicorn via python jika ada
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*app.main:app*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

Write-Host "Semua layanan (FastAPI, Bot Telegram, Cloudflare Tunnel) telah berhasil dimatikan!" -ForegroundColor Green
